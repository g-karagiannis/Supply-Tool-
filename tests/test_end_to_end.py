"""Section 12.9: the whole flow through the data actions, checking stock after every step."""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

from core.models import MaterialCategory, PackagingItemType, StepKind, StepRole
from core.state import OrderStatus
from data import actions, history
from data.actions import AssignmentInput, MachineInput, PackagingItemInput, StepSpec
from data_helpers import conn, kg, state  # noqa: F401
from ui import texts

LATE = date(2027, 6, 30)


def _material(conn: sqlite3.Connection, code: str, name: str, quantity: int | str,
              category: MaterialCategory = MaterialCategory.EXCIPIENT) -> int:
    return actions.create_material(conn, code=code, name=name, category=category, lot_number=f"L-{code}",
                                   lot_quantity_mg=kg(quantity), lot_expiry=LATE).value


def _item(conn: sqlite3.Connection, code: str, name: str, pieces: int, **extra) -> int:
    return actions.create_packaging_item(conn, PackagingItemInput(code, name, pieces, **extra)).value


def _totals(conn: sqlite3.Connection, ids: list[int]) -> list[int]:
    current = state(conn)
    return [current.materials[i].total for i in ids]


def _pieces(conn: sqlite3.Connection, ids: list[int]) -> list[int]:
    return [conn.execute("SELECT quantity_pcs FROM packaging_items WHERE id = ?", (i,)).fetchone()[0] for i in ids]


def test_section_12_9(conn: sqlite3.Connection) -> None:
    # Initial stock.
    api = _material(conn, "RM-1", "Δραστική ουσία Χ", 150, MaterialCategory.RAW_MATERIAL)
    excipient_a = _material(conn, "EX-A", "Έκδοχο Α", 100)
    excipient_b = _material(conn, "EX-B", "Έκδοχο Β", 60)
    film = _material(conn, "PM-1", "Φιλμ", 150, MaterialCategory.PACKAGING_MATERIAL)
    foil = _material(conn, "PM-2", "Αλουμινόφυλλο", 40, MaterialCategory.PACKAGING_MATERIAL)
    blister = _item(conn, "PK-1", "Blister", 0, unit_weight_mg=5_000, components=((film, 8_000), (foil, 2_000)))
    box = _item(conn, "PK-2", "Κουτί 24 τεμαχίων", 20_000, length_mm=100, width_mm=60, height_mm=30)
    leaflet = _item(conn, "PK-3", "Χαρτί οδηγιών", 20_000)
    label = _item(conn, "PK-4", "Ετικέτα κουτιού", 20_000, item_type=PackagingItemType.LABEL)
    carton = _item(conn, "PK-5", "Κιβώτιο", 150, length_mm=400, width_mm=300, height_mm=250,
                   item_type=PackagingItemType.CARTON)
    recipe_ids = [api, excipient_a, excipient_b]

    # Order of 200 kg with 50%, 40%, 10%.
    product = actions.create_product(conn, name="Depon", unit_weight_mg=500,
                                     recipe=[(api, 5_000), (excipient_a, 4_000), (excipient_b, 1_000)]).value
    order = actions.create_order(conn, product_id=product, quantity_mg=kg(200), name="ΠΑΡ-001",
                                 destination="Βουλγαρία", delivery_date=date(2026, 10, 26), transit_days=5).value
    current = state(conn)
    assert current.orders[order].status is OrderStatus.READY_FOR_PRODUCTION
    assert [current.materials[i].reserved for i in recipe_ids] == [kg(100), kg(80), kg(20)]
    assert [current.materials[i].available for i in recipe_ids] == [kg(50), kg(20), kg(40)]

    # Assignment: batch 50 kg, cycle 120 minutes, 80%, 8 hours, 3% defects, 0,5 g.
    machine = actions.create_machine(conn, MachineInput("Μηχανή 1", kg(50), Decimal(120), 8_000, Decimal(8))).value
    actions.set_assignments(conn, order, [
        AssignmentInput(machine, kg(200), kg(50), Decimal(120), 300, date(2026, 10, 6)),
    ])
    order_state = state(conn).orders[order]
    assert order_state.production_days == Decimal("1.25")
    assert (order_state.planned_pieces, order_state.expected_pieces) == (400_000, 388_000)

    # Packaging plan as in 12.6, before production completes: 388.000 pieces.
    actions.save_packaging_plan(conn, order, hours_per_day=Decimal(8), utilization_bp=8_500, steps=[
        StepSpec(StepKind.LEVEL, blister, StepRole.PRIMARY, 12, False, Decimal(200)),
        StepSpec(StepKind.LEVEL, box, StepRole.BOX, 2, True, None, ((leaflet, 1),)),
        StepSpec(StepKind.LABELLING, label, None, None, False, Decimal(60)),
        StepSpec(StepKind.LEVEL, carton, StepRole.CARTON, 160, True),
    ])
    assert state(conn).orders[order].packaging.boxes == 16_166

    # Production completed with 385.000 actual pieces.
    assignment = conn.execute("SELECT id FROM order_assignments WHERE order_id = ?", (order,)).fetchone()[0]
    actions.complete_assignment(conn, assignment, actual_pieces=385_000)
    current = state(conn)
    assert _totals(conn, recipe_ids) == [kg(50), kg(20), kg(40)]
    assert [current.materials[i].reserved for i in recipe_ids] == [0, 0, 0]
    assert current.orders[order].status is OrderStatus.IN_PACKAGING
    assert current.orders[order].packaging.boxes == 16_041

    # Packaging completed.
    actions.complete_packaging(conn, order)
    assert _totals(conn, [film, foil]) == [kg("21.668"), kg("7.917")]
    assert _pieces(conn, [box, leaflet, label]) == [3_959, 3_959, 3_959]
    assert _pieces(conn, [carton]) == [50]
    shelf_line, boxes = conn.execute("SELECT id, boxes FROM shelf_lines WHERE order_id = ?", (order,)).fetchone()
    assert boxes == 16_041
    assert state(conn).orders[order].status is OrderStatus.ON_SHELF

    # Shipment of 16.041 boxes, then "Απεστάλη".
    shipment = actions.create_shipment(conn, shelf_line_id=shelf_line, boxes=16_041).value
    actions.mark_shipped(conn, shipment, boxes=16_041)
    current = state(conn)
    assert current.shelf_lines[shelf_line].depleted
    assert current.orders[order].status is OrderStatus.SHIPPED

    # Every action can be undone back to the empty database, newest first.
    while True:
        try:
            history.undo_last(conn)
        except history.NothingToUndo:
            break
    for table in ("materials", "packaging_items", "products", "orders", "shelf_lines", "shipments"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_every_action_code_has_a_label() -> None:
    source = (Path(__file__).resolve().parent.parent / "data" / "actions.py").read_text(encoding="utf-8")
    codes = set(re.findall(r'_run\(conn, "([a-z_]+)"', source))
    assert codes and codes == set(texts.ACTION_LABELS)
