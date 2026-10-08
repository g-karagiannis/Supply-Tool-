"""Labels, cartons with inner and outer dimensions, and pallets (added 07/10/2026)."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core.models import MaterialCategory, PackagingItemType, StepKind, StepRole, packaging_key
from core.packaging_calc import MAX_STEPS, PlanIssue, StepInput, carton_fits, compute_packaging, validate_plan
from core.state import compute_state, pallets_for
from core.units import round_half_up
from data import actions, db
from data.actions import ActionError, AssignmentInput, MachineInput, PackagingItemInput, StepSpec
from data_helpers import conn, kg, state  # noqa: F401
from factories import BLISTER, BOX, CARTON, FILM, FOIL, LABEL, TODAY
from test_state import _shelf_scenario

PALLET = 15
BLISTER_LABEL = 16


def plan(*extra: StepInput) -> list[StepInput]:
    """The plan of section 12.6, with steps appended."""
    return [
        StepInput(1, StepKind.LEVEL, BLISTER, StepRole.PRIMARY, 12, False, Decimal(200), 5_000,
                  ((FILM, 8000), (FOIL, 2000))),
        StepInput(2, StepKind.LEVEL, BOX, StepRole.BOX, 2, True),
        StepInput(3, StepKind.LABELLING, LABEL, speed_per_min=Decimal(60)),
        StepInput(4, StepKind.LEVEL, CARTON, StepRole.CARTON, 160, True),
        *extra,
    ]


# ---------------------------------------------------------------- calculations


def test_pallets_round_up_and_report_the_last_one() -> None:
    pieces = 245 * 160 * 24  # exactly 245 full cartons
    result = compute_packaging(pieces, plan(StepInput(5, StepKind.LEVEL, PALLET, StepRole.PALLET, 20, True)),
                               Decimal(8), 8500)
    pallet_step = result.steps[-1]
    assert (result.cartons, result.pallets, result.cartons_per_pallet) == (245, 13, 20)
    assert pallet_step.last_unit_contents == 5
    assert result.requirements[packaging_key(PALLET)] == 13


def test_full_pallets_have_no_last_note() -> None:
    result = compute_packaging(240 * 160 * 24, plan(StepInput(5, StepKind.LEVEL, PALLET, StepRole.PALLET, 20, True)),
                               Decimal(8), 8500)
    assert result.pallets == 12 and result.steps[-1].last_unit_contents is None


def test_cartons_on_pallet_use_outer_dimensions() -> None:
    fits = carton_fits((410, 310, 260), (1200, 800, 1500))
    assert fits[0].per_axis == (2, 2, 5) and fits[0].boxes == 20
    assert len(fits) == 6


def test_labelling_after_product_packaging_runs_in_parallel() -> None:
    steps = plan()
    steps.insert(1, StepInput(2, StepKind.LABELLING, BLISTER_LABEL, speed_per_min=Decimal(150)))
    steps = [replace(s, position=i) for i, s in enumerate(steps, start=1)]
    result = compute_packaging(385_000, steps, Decimal(8), 8500)
    blister, blister_label, _, box_label, _ = (s.hours for s in result.steps)
    assert blister_label > blister
    expected = (max(blister, blister_label) + box_label) / 8
    assert result.sequential_days == expected
    assert round_half_up(result.sequential_days, 2) == Decimal("1.18")
    assert result.inline_days == max(blister, blister_label, box_label) / 8


def test_other_labelling_steps_add_up() -> None:
    result = compute_packaging(385_000, plan(), Decimal(8), 8500)
    assert round_half_up(result.sequential_days, 2) == Decimal("1.05")


@pytest.mark.parametrize("steps, issue", [
    (plan()[:2] + [StepInput(3, StepKind.LEVEL, PALLET, StepRole.PALLET, 20, True)], PlanIssue.PALLET_WITHOUT_CARTON),
    (plan(StepInput(5, StepKind.LEVEL, PALLET, StepRole.PALLET, 20, True),
          StepInput(6, StepKind.LEVEL, PALLET, StepRole.PALLET, 2, True)), PlanIssue.MULTIPLE_PALLETS),
    (plan(StepInput(5, StepKind.LEVEL, PALLET, StepRole.PALLET, 20, True),
          StepInput(6, StepKind.LEVEL, BOX, StepRole.OTHER, 1, True)), PlanIssue.LEVEL_AFTER_PALLET),
    (plan(*[StepInput(5 + i, StepKind.LABELLING, LABEL) for i in range(MAX_STEPS - 3)]), PlanIssue.TOO_MANY_STEPS),
])
def test_pallet_and_size_rules(steps, issue: PlanIssue) -> None:
    assert issue in validate_plan(steps)


def test_labelling_after_pallet_is_allowed_and_ten_steps_fit() -> None:
    steps = plan(StepInput(5, StepKind.LEVEL, PALLET, StepRole.PALLET, 20, True),
                 *[StepInput(6 + i, StepKind.LABELLING, LABEL) for i in range(MAX_STEPS - 5)])
    assert len(steps) == MAX_STEPS and validate_plan(steps) == ()


def test_pallets_for() -> None:
    assert pallets_for(245, 20) == (13, 5)
    assert pallets_for(240, 20) == (12, None)
    assert pallets_for(100, None) == (None, None)


def test_shelf_line_shows_pallets() -> None:
    snapshot = _shelf_scenario(39_200)
    line = replace(snapshot.shelf_lines[0], cartons_per_pallet=20, pallet_item_id=PALLET)
    shelf = compute_state(replace(snapshot, shelf_lines=(line,))).shelf_lines[line.id]
    assert (shelf.cartons, shelf.pallets, shelf.last_pallet_cartons) == (245, 13, 5)


# ---------------------------------------------------------------- data actions


def _item(conn: sqlite3.Connection, code: str, kind: PackagingItemType, pieces: int = 1_000, **extra) -> int:
    return actions.create_packaging_item(conn, PackagingItemInput(code, code, pieces, item_type=kind, **extra)).value


@pytest.mark.parametrize("kind, extra", [
    (PackagingItemType.LABEL, {"length_mm": 10, "width_mm": 10, "height_mm": 1}),
    (PackagingItemType.PALLET, {"length_mm": 1200, "width_mm": 800, "height_mm": 1500}),
    (PackagingItemType.PACKAGING, {"outer_length_mm": 10, "outer_width_mm": 10, "outer_height_mm": 10}),
    (PackagingItemType.CARTON, {"outer_length_mm": 10, "outer_width_mm": 10}),
])
def test_item_type_field_rules(conn: sqlite3.Connection, kind: PackagingItemType, extra: dict) -> None:
    with pytest.raises(ActionError):
        _item(conn, "X", kind, **extra)


def test_carton_keeps_both_sizes_and_type_is_locked(conn: sqlite3.Connection) -> None:
    carton = _item(conn, "C", PackagingItemType.CARTON, length_mm=400, width_mm=300, height_mm=250,
                   outer_length_mm=410, outer_width_mm=310, outer_height_mm=260)
    from data.repositories import load_snapshot

    item = next(p for p in load_snapshot(conn).packaging_items if p.id == carton)
    assert item.dimensions_mm == (400, 300, 250) and item.outer_dimensions_mm == (410, 310, 260)
    with pytest.raises(ActionError, match="τύπος"):
        actions.update_packaging_item(conn, carton, PackagingItemInput("C", "C", 1_000, item_type=PackagingItemType.PALLET))


def _order_ready_for_packaging(conn: sqlite3.Connection) -> int:
    api = actions.create_material(conn, code="A", name="A", category=MaterialCategory.RAW_MATERIAL, lot_number="L",
                                  lot_quantity_mg=kg(500), lot_expiry=date(2027, 6, 30)).value
    product = actions.create_product(conn, name="P", unit_weight_mg=500, recipe=[(api, 10_000)]).value
    order = actions.create_order(conn, product_id=product, quantity_mg=kg(100), name="ΠΑΡ-001", destination="Β",
                                 delivery_date=date(2026, 10, 26), transit_days=5).value
    machine = actions.create_machine(conn, MachineInput("M", kg(50), Decimal(120), 8000, Decimal(8))).value
    actions.set_assignments(conn, order, [AssignmentInput(machine, kg(100), kg(50), Decimal(120), 0, TODAY)])
    return order


def test_plan_steps_take_items_of_the_right_type(conn: sqlite3.Connection) -> None:
    order = _order_ready_for_packaging(conn)
    pack = _item(conn, "PK", PackagingItemType.PACKAGING)
    box = _item(conn, "BX", PackagingItemType.PACKAGING)
    carton = _item(conn, "CT", PackagingItemType.CARTON)
    label = _item(conn, "LB", PackagingItemType.LABEL)
    good = [StepSpec(StepKind.LEVEL, pack, StepRole.PRIMARY, 10), StepSpec(StepKind.LABELLING, label),
            StepSpec(StepKind.LEVEL, box, StepRole.BOX, 2), StepSpec(StepKind.LEVEL, carton, StepRole.CARTON, 50)]
    with pytest.raises(ActionError, match="Στο βήμα 2 διάλεξε ετικέτα"):
        actions.save_packaging_plan(conn, order, hours_per_day=Decimal(8), utilization_bp=10_000,
                                    steps=[good[0], StepSpec(StepKind.LABELLING, box), *good[2:]])
    with pytest.raises(ActionError, match="Στο βήμα 4 διάλεξε κιβώτιο"):
        actions.save_packaging_plan(conn, order, hours_per_day=Decimal(8), utilization_bp=10_000,
                                    steps=[*good[:3], StepSpec(StepKind.LEVEL, box, StepRole.CARTON, 50)])
    actions.save_packaging_plan(conn, order, hours_per_day=Decimal(8), utilization_bp=10_000, steps=good)


def test_completed_packaging_puts_pallets_on_the_shelf(conn: sqlite3.Connection) -> None:
    order = _order_ready_for_packaging(conn)
    pack = _item(conn, "PK", PackagingItemType.PACKAGING, pieces=50_000)
    box = _item(conn, "BX", PackagingItemType.PACKAGING, pieces=50_000)
    carton = actions.create_packaging_item(conn, PackagingItemInput(
        "CT", "CT", 1_000, item_type=PackagingItemType.CARTON)).value
    pallet = actions.create_packaging_item(conn, PackagingItemInput(
        "PL", "PL", 50, item_type=PackagingItemType.PALLET)).value
    steps = [StepSpec(StepKind.LEVEL, pack, StepRole.PRIMARY, 10, True), StepSpec(StepKind.LEVEL, box, StepRole.BOX, 2, True),
             StepSpec(StepKind.LEVEL, carton, StepRole.CARTON, 50, True),
             StepSpec(StepKind.LEVEL, pallet, StepRole.PALLET, 30, True)]
    actions.save_packaging_plan(conn, order, hours_per_day=Decimal(8), utilization_bp=10_000, steps=steps)
    assignment = conn.execute("SELECT id FROM order_assignments").fetchone()[0]
    actions.complete_assignment(conn, assignment, actual_pieces=200_000)
    actions.complete_packaging(conn, order)
    line = conn.execute("SELECT boxes, cartons_per_pallet, pallet_item_id FROM shelf_lines").fetchone()
    assert tuple(line) == (10_000, 30, pallet)
    # 200 cartons at 30 per pallet: 7 pallets, the last with 20 cartons.
    assert conn.execute("SELECT quantity_pcs FROM packaging_items WHERE id = ?", (pallet,)).fetchone()[0] == 43
    shelf = next(iter(state(conn).shelf_lines.values()))
    assert (shelf.pallets, shelf.last_pallet_cartons) == (7, 20)


# ---------------------------------------------------------------- migration of existing data


def test_migration_classifies_labels_and_cartons(tmp_path: Path) -> None:
    old = tmp_path / "old_migrations"
    old.mkdir()
    for path in sorted(db.MIGRATIONS_DIR.glob("*.sql"))[:3]:
        shutil.copy(path, old / path.name)
    connection = db.connect(tmp_path / "app.db")
    assert db.migrate(connection, old) == 3
    connection.executescript("""
        INSERT INTO products (id, name, unit_weight_mg) VALUES (1, 'P', 500);
        INSERT INTO orders (id, name, product_id, quantity_mg, unit_weight_mg, destination, delivery_date,
                            transit_days, sequence, created_at)
            VALUES (1, 'ΠΑΡ-001', 1, 1000000, 500, 'Β', '2026-10-26', 5, 1, '2026-10-05T10:00:00');
        INSERT INTO packaging_items (id, code, name, quantity_pcs, length_mm, width_mm, height_mm)
            VALUES (1, 'B', 'Κουτί', 10, 100, 60, 30), (2, 'L', 'Ετικέτα', 10, NULL, NULL, NULL),
                   (3, 'C', 'Κιβώτιο', 10, 400, 300, 250), (4, 'X', 'Άλλο', 10, NULL, NULL, NULL);
        INSERT INTO packaging_plans (order_id, hours_per_day, utilization_bp, saved_at)
            VALUES (1, '8', 10000, '2026-10-05T10:00:00');
        INSERT INTO packaging_steps (id, order_id, position, kind, role, packaging_item_id, units_per, comes_ready)
            VALUES (1, 1, 1, 'level', 'box', 1, 2, 1), (2, 1, 2, 'labelling', NULL, 2, NULL, 0),
                   (3, 1, 3, 'level', 'carton', 3, 160, 1);
        INSERT INTO packaging_step_extras (step_id, packaging_item_id, quantity_per_unit) VALUES (1, 4, 1);
    """)
    assert db.migrate(connection) == len(db.available_migrations())
    types = dict(connection.execute("SELECT id, item_type FROM packaging_items").fetchall())
    assert types == {1: "packaging", 2: "label", 3: "carton", 4: "packaging"}
    assert connection.execute("SELECT COUNT(*) FROM packaging_steps").fetchone()[0] == 3
    assert connection.execute("SELECT COUNT(*) FROM packaging_step_extras").fetchone()[0] == 1
    connection.execute("INSERT INTO packaging_steps (order_id, position, kind, role, packaging_item_id, units_per,"
                       " comes_ready) VALUES (1, 4, 'level', 'pallet', 4, 20, 1)")
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    connection.close()
