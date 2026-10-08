"""Section 12.8 (stock movements) at the data level, plus history, undo and confirmations."""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from core import dates
from core.models import ItemKind, MaterialCategory
from core.state import OrderStatus
from data import actions, history
from data.actions import ActionError, AssignmentInput, MachineInput, NeedsConfirmation
from data.repositories import last_undoable, list_history, load_snapshot
from data_helpers import conn, kg, lot_quantities, material, seed_shelf, state  # noqa: F401

LATE = date(2027, 6, 30)
EARLY = date(2027, 1, 31)


def product(conn: sqlite3.Connection, name: str, recipe: list[tuple[int, int]], weight_mg: int = 500) -> int:
    return actions.create_product(conn, name=name, unit_weight_mg=weight_mg, recipe=recipe).value


def machine(conn: sqlite3.Connection) -> int:
    return actions.create_machine(conn, MachineInput("Μηχανή 1", kg(50), Decimal(120), 8000, Decimal(8))).value


def order(conn: sqlite3.Connection, product_id: int, quantity_kg: int, name: str) -> int:
    return actions.create_order(
        conn, product_id=product_id, quantity_mg=kg(quantity_kg), name=name, destination="Βουλγαρία",
        delivery_date=date(2026, 10, 26), transit_days=5,
    ).value


def produce(conn: sqlite3.Connection, order_id: int, machine_id: int, quantity_kg: int, pieces: int) -> int:
    actions.set_assignments(conn, order_id, [
        AssignmentInput(machine_id, kg(quantity_kg), kg(50), Decimal(120), 300, date(2026, 10, 6)),
    ])
    assignment_id = conn.execute("SELECT id FROM order_assignments WHERE order_id = ?", (order_id,)).fetchone()[0]
    actions.complete_assignment(conn, assignment_id, actual_pieces=pieces)
    return assignment_id


# ---------------------------------------------------------------- 12.8


def test_consumption_takes_nearest_expiry_first(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α", ("L-002", 200, LATE), ("L-001", 100, EARLY))
    product_id = product(conn, "Δισκία Α", [(excipient, 10_000)])
    machine_id = machine(conn)

    first = order(conn, product_id, 150, "ΠΑΡ-001")
    produce(conn, first, machine_id, 150, 300_000)
    assert lot_quantities(conn, excipient) == {"L-001": 0, "L-002": kg(150)}
    lots = {l.lot_number: l.id for l in load_snapshot(conn).lots}
    assert state(conn).lots[lots["L-001"]].status.value == "depleted"

    second = order(conn, product_id, 150, "ΠΑΡ-002")
    produce(conn, second, machine_id, 150, 300_000)
    assert lot_quantities(conn, excipient) == {"L-001": 0, "L-002": 0}
    assert state(conn).materials[excipient].depleted


def test_receipt_creates_lot_and_clears_expected(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α", ("L-001", 20, LATE))
    receipt = actions.create_receipt(conn, kind=ItemKind.MATERIAL, item_id=excipient, quantity=kg(200),
                                     receipt_date=date(2026, 10, 14)).value
    before = state(conn).materials[excipient]
    assert before.available == kg(20)
    assert [r.quantity for r in before.expected] == [kg(200)]

    result = actions.mark_received(conn, receipt, quantity=kg(195), receipt_date=date(2026, 10, 14),
                                   lot_number="L-002", expiry_date=LATE)
    after = state(conn).materials[excipient]
    assert after.available == kg(215)
    assert after.expected == ()
    assert lot_quantities(conn, excipient)["L-002"] == kg(195)
    assert last_undoable(conn).description == "Παραλήφθηκε: Έκδοχο Α, 195 kg, LOT L-002"
    assert result.history_id is not None


def test_shelf_cartons_and_loose_boxes(conn: sqlite3.Connection) -> None:
    (line,) = seed_shelf(conn, [("Βουλγαρία", 16_041)])
    shelf = state(conn).shelf_lines[line]
    assert (shelf.cartons, shelf.loose_boxes) == (100, 41)


def test_shipping_takes_boxes_off_the_shelf(conn: sqlite3.Connection) -> None:
    (line,) = seed_shelf(conn, [("Βουλγαρία", 12_000)])
    shipment = actions.create_shipment(conn, shelf_line_id=line, boxes=8_000).value
    assert state(conn).shipments[shipment].cartons == 50
    actions.mark_shipped(conn, shipment, boxes=8_000)
    assert conn.execute("SELECT boxes FROM shelf_lines WHERE id = ?", (line,)).fetchone()[0] == 4_000
    assert last_undoable(conn).description == "Απεστάλη: Depon, ΠΑΡ-001, 8.000 κουτιά"


def test_transfer_keeps_total(conn: sqlite3.Connection) -> None:
    germany, bulgaria = seed_shelf(conn, [("Γερμανία", 5_000), ("Βουλγαρία", 5_000)])
    actions.transfer_boxes(conn, from_line_id=germany, to_line_id=bulgaria, boxes=1_000)
    boxes = dict(conn.execute("SELECT id, boxes FROM shelf_lines").fetchall())
    assert (boxes[germany], boxes[bulgaria]) == (4_000, 6_000)
    assert sum(boxes.values()) == 10_000
    assert last_undoable(conn).description == "Μεταφορά: 1.000 κουτιά Depon από Γερμανία σε Βουλγαρία"
    shelf = state(conn).shelf_lines
    assert shelf[germany].transfer_ids == shelf[bulgaria].transfer_ids != ()


def test_transfer_rejected_when_boxes_are_pending(conn: sqlite3.Connection) -> None:
    germany, bulgaria = seed_shelf(conn, [("Γερμανία", 5_000), ("Βουλγαρία", 5_000)])
    actions.create_shipment(conn, shelf_line_id=germany, boxes=5_000)
    assert state(conn).shelf_lines[germany].free_boxes == 0
    with pytest.raises(ActionError, match="ελεύθερα κουτιά"):
        actions.transfer_boxes(conn, from_line_id=germany, to_line_id=bulgaria, boxes=1_000)


def test_undo_shipping_restores_shelf_and_shipment(conn: sqlite3.Connection) -> None:
    (line,) = seed_shelf(conn, [("Βουλγαρία", 12_000)])
    shipment = actions.create_shipment(conn, shelf_line_id=line, boxes=8_000).value
    actions.mark_shipped(conn, shipment, boxes=8_000)
    undone = history.undo_last(conn)
    assert undone.description.startswith("Απεστάλη")
    assert conn.execute("SELECT boxes FROM shelf_lines WHERE id = ?", (line,)).fetchone()[0] == 12_000
    assert not state(conn).shipments[shipment].shipped


def test_two_undos_go_backwards(conn: sqlite3.Connection) -> None:
    first = material(conn, "M-1", "Πρώτο")
    second = material(conn, "M-2", "Δεύτερο")
    assert history.undo_last(conn).description == "Νέο υλικό: Δεύτερο"
    assert conn.execute("SELECT COUNT(*) FROM materials WHERE id = ?", (second,)).fetchone()[0] == 0
    assert history.undo_last(conn).description == "Νέο υλικό: Πρώτο"
    assert conn.execute("SELECT COUNT(*) FROM materials WHERE id = ?", (first,)).fetchone()[0] == 0
    with pytest.raises(history.NothingToUndo):
        history.undo_last(conn)


# ---------------------------------------------------------------- history and undo


def test_every_action_is_logged_and_undo_is_marked(conn: sqlite3.Connection) -> None:
    material(conn, "M-1", "Έκδοχο Α", ("L-001", 100, LATE))
    entries = list_history(conn)
    assert [e.description for e in entries] == ["Νέο LOT: L-001, Έκδοχο Α, 100 kg", "Νέο υλικό: Έκδοχο Α"]
    history.undo_last(conn)
    entries = list_history(conn)
    assert entries[0].undone_at is not None and entries[1].undone_at is None
    assert last_undoable(conn).description == "Νέο υλικό: Έκδοχο Α"


def test_lot_correction_logged_with_old_and_new(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "M-1", "Έκδοχο Α", ("L-001", 100, LATE))
    lot_id = conn.execute("SELECT id FROM material_lots").fetchone()[0]
    actions.update_lot(conn, lot_id, lot_number="L-001", quantity_mg=kg(70), expiry_date=LATE)
    assert last_undoable(conn).description == "Διόρθωση ποσότητας: LOT L-001 από 100 kg σε 70 kg"
    assert state(conn).materials[excipient].available == kg(70)


def test_undo_restores_a_deleted_row(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "M-1", "Έκδοχο Α")
    actions.add_lot(conn, excipient, lot_number="L-001", quantity_mg=kg(1), expiry_date=LATE)
    lot_id = conn.execute("SELECT id FROM material_lots").fetchone()[0]
    actions.update_lot(conn, lot_id, lot_number="L-001", quantity_mg=0, expiry_date=LATE)
    actions.delete_lot(conn, lot_id)
    assert lot_quantities(conn, excipient) == {}
    history.undo_last(conn)
    assert lot_quantities(conn, excipient) == {"L-001": 0}


def test_action_without_changes_is_not_logged(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "M-1", "Έκδοχο Α")
    count = len(list_history(conn))
    result = actions.update_material(conn, excipient, code="M-1", name="Έκδοχο Α", category=MaterialCategory.EXCIPIENT)
    assert result.history_id is None and len(list_history(conn)) == count


# ---------------------------------------------------------------- confirmations and sequence


def _two_orders(conn: sqlite3.Connection) -> tuple[int, int, int, int]:
    excipient = material(conn, "E-A", "Έκδοχο Α", ("L-001", 80, LATE))
    product_id = product(conn, "Δισκία Α", [(excipient, 10_000)])
    bulgaria = order(conn, product_id, 60, "ΠΑΡ-001")
    germany = order(conn, product_id, 60, "ΠΑΡ-002")
    return excipient, product_id, bulgaria, germany


def test_sequence_change_moves_reservation_after_confirmation(conn: sqlite3.Connection) -> None:
    _, _, bulgaria, germany = _two_orders(conn)
    assert state(conn).orders[bulgaria].status is OrderStatus.READY_FOR_PRODUCTION
    with pytest.raises(NeedsConfirmation) as asked:
        actions.change_sequence(conn, germany, new_position=1)
    assert asked.value.messages == ("Η παραγγελία ΠΑΡ-001 θα επιστρέψει σε Περιμένει υλικά. Συνέχεια;",)
    assert state(conn).orders[bulgaria].status is OrderStatus.READY_FOR_PRODUCTION

    actions.change_sequence(conn, germany, new_position=1, confirm=True)
    orders = state(conn).orders
    assert orders[germany].status is OrderStatus.READY_FOR_PRODUCTION
    assert orders[bulgaria].status is OrderStatus.WAITING_MATERIALS
    assert last_undoable(conn).description == "Αλλαγή σειράς: ΠΑΡ-002 από τη θέση 2 στη θέση 1"
    assert dict(conn.execute("SELECT name, sequence FROM orders").fetchall()) == {"ΠΑΡ-001": 2, "ΠΑΡ-002": 1}


def test_lot_correction_asks_when_an_order_loses_materials(conn: sqlite3.Connection) -> None:
    excipient, _, bulgaria, _ = _two_orders(conn)
    lot_id = conn.execute("SELECT id FROM material_lots WHERE material_id = ?", (excipient,)).fetchone()[0]
    with pytest.raises(NeedsConfirmation):
        actions.update_lot(conn, lot_id, lot_number="L-001", quantity_mg=kg(50), expiry_date=LATE)
    assert lot_quantities(conn, excipient) == {"L-001": kg(80)}


def test_started_order_gets_the_stronger_message(conn: sqlite3.Connection) -> None:
    excipient, _, bulgaria, _ = _two_orders(conn)
    machine_id = machine(conn)
    actions.set_assignments(conn, bulgaria, [AssignmentInput(machine_id, kg(60), kg(50), Decimal(120), 0, date(2026, 10, 5))])
    lot_id = conn.execute("SELECT id FROM material_lots WHERE material_id = ?", (excipient,)).fetchone()[0]
    with pytest.raises(NeedsConfirmation) as asked:
        actions.update_lot(conn, lot_id, lot_number="L-001", quantity_mg=kg(50), expiry_date=LATE)
    assert "05/10 και πιθανόν παράγεται ήδη" in asked.value.messages[0]


def test_cancel_frees_materials_and_closes_gap(conn: sqlite3.Connection) -> None:
    _, _, bulgaria, germany = _two_orders(conn)
    actions.cancel_order(conn, bulgaria)
    orders = state(conn).orders
    assert orders[bulgaria].status is OrderStatus.CANCELLED
    assert orders[germany].status is OrderStatus.READY_FOR_PRODUCTION
    assert conn.execute("SELECT sequence FROM orders WHERE id = ?", (germany,)).fetchone()[0] == 1
    assert last_undoable(conn).description == "Ακύρωση παραγγελίας: ΠΑΡ-001"


def test_new_order_goes_last_and_copies_recipe(conn: sqlite3.Connection) -> None:
    excipient, product_id, bulgaria, germany = _two_orders(conn)
    assert dict(conn.execute("SELECT name, sequence FROM orders").fetchall()) == {"ΠΑΡ-001": 1, "ΠΑΡ-002": 2}
    actions.update_product(conn, product_id, name="Δισκία Α", unit_weight_mg=500,
                           recipe=[(excipient, 10_000)])
    copy = conn.execute("SELECT COUNT(*) FROM order_recipe_lines WHERE order_id = ?", (bulgaria,)).fetchone()[0]
    assert copy == 1


def test_suggested_order_name(conn: sqlite3.Connection) -> None:
    _two_orders(conn)
    # The older ΠΑΡ- names keep their numbers; the next name continues after them.
    assert actions.suggest_order_name(load_snapshot(conn)) == "ORD-003"


def test_order_quantity_scales_assignments(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α", ("L-001", 500, LATE))
    product_id = product(conn, "Δισκία Α", [(excipient, 10_000)])
    order_id = order(conn, product_id, 100, "ΠΑΡ-001")
    machine_id = machine(conn)
    actions.set_assignments(conn, order_id, [
        AssignmentInput(machine_id, kg(50), kg(50), Decimal(120)),
        AssignmentInput(machine_id, kg(50), kg(50), Decimal(120)),
    ])
    actions.update_order(conn, order_id, name="ΠΑΡ-001", destination="Βουλγαρία",
                         delivery_date=date(2026, 10, 26), transit_days=5, quantity_mg=kg(150))
    shares = [r[0] for r in conn.execute("SELECT quantity_mg FROM order_assignments ORDER BY id")]
    assert shares == [kg(75), kg(75)]


def test_assignment_shares_must_match_order(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α", ("L-001", 500, LATE))
    order_id = order(conn, product(conn, "Δισκία Α", [(excipient, 10_000)]), 100, "ΠΑΡ-001")
    machine_id = machine(conn)
    with pytest.raises(ActionError, match="άθροισμα"):
        actions.set_assignments(conn, order_id, [AssignmentInput(machine_id, kg(90), kg(50), Decimal(120))])


def test_production_rejected_while_waiting(conn: sqlite3.Connection) -> None:
    _, _, _, germany = _two_orders(conn)
    machine_id = machine(conn)
    actions.set_assignments(conn, germany, [AssignmentInput(machine_id, kg(60), kg(50), Decimal(120))])
    assignment_id = conn.execute("SELECT id FROM order_assignments").fetchone()[0]
    with pytest.raises(ActionError, match="περιμένει υλικά"):
        actions.complete_assignment(conn, assignment_id, actual_pieces=1)


def test_expired_lot_needs_confirmation(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α", ("L-001", 60, date(2026, 10, 6)))
    order_id = order(conn, product(conn, "Δισκία Α", [(excipient, 10_000)]), 60, "ΠΑΡ-001")
    machine_id = machine(conn)
    actions.set_assignments(conn, order_id, [AssignmentInput(machine_id, kg(60), kg(50), Decimal(120))])
    assignment_id = conn.execute("SELECT id FROM order_assignments").fetchone()[0]
    assert state(conn).orders[order_id].recipe_reserved

    # Production is recorded on 07/10, after the LOT expired on 06/10.
    monkeypatch.setattr(dates, "today", lambda: date(2026, 10, 7))
    assert not state(conn).orders[order_id].recipe_reserved
    with pytest.raises(NeedsConfirmation) as asked:
        actions.complete_assignment(conn, assignment_id, actual_pieces=100_000)
    assert asked.value.messages == ("Το LOT L-001 έληξε στις 06/10/2026. Καταναλώθηκε σε αυτή την παραγωγή;",)
    assert lot_quantities(conn, excipient) == {"L-001": kg(60)}
    actions.complete_assignment(conn, assignment_id, actual_pieces=100_000, confirm=True)
    assert lot_quantities(conn, excipient) == {"L-001": 0}


def test_expired_lot_does_not_cover_a_real_shortage(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α", ("L-001", 30, LATE))
    order_id = order(conn, product(conn, "Δισκία Α", [(excipient, 10_000)]), 60, "ΠΑΡ-001")
    actions.set_assignments(conn, order_id, [AssignmentInput(machine(conn), kg(60), kg(50), Decimal(120))])
    assignment_id = conn.execute("SELECT id FROM order_assignments").fetchone()[0]
    with pytest.raises(ActionError, match="περιμένει υλικά"):
        actions.complete_assignment(conn, assignment_id, actual_pieces=1)


def test_actual_over_planned_asks(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α", ("L-001", 200, LATE))
    order_id = order(conn, product(conn, "Δισκία Α", [(excipient, 10_000)]), 200, "ΠΑΡ-001")
    machine_id = machine(conn)
    actions.set_assignments(conn, order_id, [AssignmentInput(machine_id, kg(200), kg(50), Decimal(120))])
    assignment_id = conn.execute("SELECT id FROM order_assignments").fetchone()[0]
    with pytest.raises(NeedsConfirmation, match="ξεπερνούν τα προγραμματισμένα"):
        actions.complete_assignment(conn, assignment_id, actual_pieces=400_001)


# ---------------------------------------------------------------- integrity and delete rules


def test_negative_stock_rejected(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α", ("L-001", 10, LATE))
    lot_id = conn.execute("SELECT id FROM material_lots").fetchone()[0]
    with pytest.raises(ActionError):
        actions.update_lot(conn, lot_id, lot_number="L-001", quantity_mg=-1, expiry_date=LATE)
    assert lot_quantities(conn, excipient) == {"L-001": kg(10)}


def test_material_in_recipe_cannot_be_deleted(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α")
    product(conn, "Δισκία Α", [(excipient, 10_000)])
    with pytest.raises(ActionError) as error:
        actions.delete_material(conn, excipient)
    assert str(error.value) == "Το Έκδοχο Α ανήκει στη συνταγή του προϊόντος Δισκία Α."


def test_material_with_stock_cannot_be_deleted(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α", ("L-001", 1, LATE))
    with pytest.raises(ActionError, match="έχει ακόμα απόθεμα"):
        actions.delete_material(conn, excipient)


def test_soft_delete_keeps_the_row(conn: sqlite3.Connection) -> None:
    excipient = material(conn, "E-A", "Έκδοχο Α")
    actions.delete_material(conn, excipient)
    assert conn.execute("SELECT deleted_at FROM materials WHERE id = ?", (excipient,)).fetchone()[0] is not None
    history.undo_last(conn)
    assert conn.execute("SELECT deleted_at FROM materials WHERE id = ?", (excipient,)).fetchone()[0] is None


def test_recipe_percentages_must_total_100(conn: sqlite3.Connection) -> None:
    a = material(conn, "A", "Α")
    b = material(conn, "B", "Β")
    with pytest.raises(ActionError) as error:
        actions.create_product(conn, name="Χ", unit_weight_mg=500, recipe=[(a, 5000), (b, 4700)])
    assert str(error.value) == "Τα ποσοστά δίνουν 97%. Πρέπει να δίνουν 100%."


def test_duplicate_code_rejected(conn: sqlite3.Connection) -> None:
    material(conn, "E-A", "Έκδοχο Α")
    with pytest.raises(ActionError, match="υπάρχει ήδη"):
        material(conn, "E-A", "Άλλο")


def test_product_with_orders_cannot_be_deleted(conn: sqlite3.Connection) -> None:
    _, product_id, _, _ = _two_orders(conn)
    with pytest.raises(ActionError, match="έχει την παραγγελία"):
        actions.delete_product(conn, product_id)


def test_settings_validation_and_undo(conn: sqlite3.Connection) -> None:
    from core.models import Settings

    with pytest.raises(ActionError):
        actions.update_settings(conn, Settings(yellow_days=30, red_days=30))
    actions.update_settings(conn, Settings(yellow_days=90, red_days=20))
    assert conn.execute("SELECT value FROM settings WHERE key = 'yellow_days'").fetchone()[0] == "90"
    history.undo_last(conn)
    assert conn.execute("SELECT value FROM settings WHERE key = 'yellow_days'").fetchone()[0] == "120"


def test_backup_copies_the_database(conn: sqlite3.Connection, tmp_path) -> None:
    from data import db

    material(conn, "E-A", "Έκδοχο Α")
    path = conn.execute("PRAGMA database_list").fetchone()["file"]
    target = db.backup_database(path, tmp_path / "backups")
    assert target.exists() and target.name.startswith("app_")
    copy = db.connect(target)
    assert copy.execute("SELECT name FROM materials").fetchone()[0] == "Έκδοχο Α"
    copy.close()


def test_machine_hours_setting_saved_validated_and_undone(conn: sqlite3.Connection) -> None:
    from core.models import Settings

    with pytest.raises(ActionError, match="από 0 έως 24"):
        actions.update_settings(conn, Settings(machine_hours_per_day=Decimal(25)))
    actions.update_settings(conn, Settings(machine_hours_per_day=Decimal("16")))
    assert conn.execute("SELECT value FROM settings WHERE key = 'machine_hours_per_day'").fetchone()[0] == "16"
    assert load_snapshot(conn).settings.machine_hours_per_day == 16
    history.undo_last(conn)
    assert load_snapshot(conn).settings.machine_hours_per_day == 8


def test_machine_hours_setting_does_not_change_existing_machines(conn: sqlite3.Connection) -> None:
    from core.models import Settings

    machine_id = machine(conn)
    actions.update_settings(conn, Settings(machine_hours_per_day=Decimal(16)))
    stored = next(m for m in load_snapshot(conn).machines if m.id == machine_id)
    assert stored.hours_per_day == 8


def test_wipe_all_data_returns_to_first_start(conn: sqlite3.Connection) -> None:
    from core.models import Settings
    from data import db
    from data.repositories import WRITABLE_TABLES, wipe_all_data

    _, product_id, _, _ = _two_orders(conn)
    actions.update_settings(conn, Settings(yellow_days=90, red_days=20))
    version = db.current_version(conn)

    wipe_all_data(conn)

    for table in WRITABLE_TABLES - {"settings"}:
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    assert list_history(conn) == [] and last_undoable(conn) is None
    assert load_snapshot(conn).settings == Settings()
    assert db.current_version(conn) == version
    material(conn, "E-A", "Έκδοχο Α", ("L-001", 10, LATE))
    assert len(list_history(conn)) == 2
