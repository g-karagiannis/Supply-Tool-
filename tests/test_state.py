"""compute_state(): statuses (4.10), warnings (4.12), packaging basis (9.1, 9.6) and shelf."""

from __future__ import annotations

from datetime import date, datetime

from core.models import (
    PackagingItem,
    Receipt,
    ItemKind,
    ShelfLine,
    ShelfTransfer,
    Shipment,
    Snapshot,
    material_key,
    packaging_key,
)
from core.state import (
    OrderFlag,
    OrderStatus,
    PiecesBasis,
    ReceiptStatus,
    WarningCode,
    cartons_and_loose,
    compute_state,
    covering_receipt_date,
    ExpectedReceipt,
    lost_reservations,
)
from factories import (
    BOX,
    CARTON,
    CREATED,
    FILM,
    FOIL,
    LABEL,
    TODAY,
    assignment,
    blister_components,
    kg,
    lot,
    machine,
    material,
    order,
    packaging_items,
    packaging_plan,
    packaging_steps,
    recipe,
)


def scenario(**overrides) -> Snapshot:
    """The end-to-end data of section 12.9: one 200 kg order, 50/40/10."""
    steps, extras = packaging_steps(1)
    values = dict(
        today=TODAY,
        materials=(material(1), material(2), material(3), material(FILM), material(FOIL)),
        lots=(lot(1, 1, 150), lot(2, 2, 100), lot(3, 3, 60), lot(4, FILM, 150), lot(5, FOIL, 40)),
        packaging_items=packaging_items(),
        packaging_components=blister_components(),
        machines=(machine(),),
        orders=(order(1, 200, 1),),
        order_recipe_lines=recipe(1, (1, 50), (2, 40), (3, 10)),
        assignments=(assignment(1, 1, 200, start=date(2026, 10, 6)),),
        packaging_plans=(packaging_plan(1),),
        packaging_steps=steps,
        packaging_step_extras=extras,
    )
    values.update(overrides)
    return Snapshot(**values)


def test_ready_for_production_with_reservations() -> None:
    state = compute_state(scenario())
    order_state = state.orders[1]
    assert order_state.status is OrderStatus.READY_FOR_PRODUCTION
    assert [state.materials[i].reserved for i in (1, 2, 3)] == [kg(100), kg(80), kg(20)]
    assert [state.materials[i].available for i in (1, 2, 3)] == [kg(50), kg(20), kg(40)]
    assert order_state.planned_pieces == 400_000
    assert order_state.expected_pieces == 388_000
    assert order_state.production_days == 1.25
    assert order_state.production_end == date(2026, 10, 7)


def test_packaging_uses_expected_pieces_before_completion() -> None:
    order_state = compute_state(scenario()).orders[1]
    assert order_state.pieces_basis is PiecesBasis.EXPECTED
    assert order_state.packaging is not None and order_state.packaging.boxes == 16_166
    assert order_state.packaging_reserved


def test_packaging_switches_to_actual_pieces() -> None:
    state = compute_state(scenario(assignments=(assignment(1, 1, 200, start=date(2026, 10, 6), actual_pieces=385_000),)))
    order_state = state.orders[1]
    assert order_state.status is OrderStatus.IN_PACKAGING
    assert order_state.pieces_basis is PiecesBasis.ACTUAL
    assert order_state.packaging is not None and order_state.packaging.boxes == 16_041
    assert [state.materials[i].reserved for i in (1, 2, 3)] == [0, 0, 0]
    assert state.materials[FILM].reserved == kg("128.332")
    assert state.packaging_items[BOX].reserved == 16_041


def test_without_machine_uses_pieces_without_defect_rate() -> None:
    order_state = compute_state(scenario(assignments=())).orders[1]
    assert order_state.pieces_basis is PiecesBasis.WITHOUT_DEFECT_RATE
    assert order_state.packaging_pieces == 400_000
    assert OrderFlag.NO_MACHINE in order_state.flags
    assert order_state.readiness is None


def test_no_packaging_plan_flag_and_readiness() -> None:
    order_state = compute_state(scenario(packaging_plans=(), packaging_steps=(), packaging_step_extras=())).orders[1]
    assert OrderFlag.NO_PACKAGING_PLAN in order_state.flags
    assert order_state.without_packaging
    assert order_state.readiness == order_state.production_end


def test_missing_packaging_flag_and_limiting_item() -> None:
    items = tuple(
        PackagingItem(i.id, i.code, i.name, 15_000) if i.id == LABEL else i for i in packaging_items()
    )
    order_state = compute_state(scenario(packaging_items=items)).orders[1]
    assert OrderFlag.MISSING_PACKAGING in order_state.flags
    assert not order_state.packaging_reserved
    assert order_state.recipe_reserved
    assert order_state.packable_boxes == 15_000
    assert order_state.packaging_limiting == (packaging_key(LABEL),)


def test_readiness_includes_packaging_days() -> None:
    order_state = compute_state(scenario()).orders[1]
    assert order_state.readiness == date(2026, 10, 9)
    assert order_state.arrival == date(2026, 10, 14)
    assert order_state.ship_by == date(2026, 10, 21)
    assert all(w.code is not WarningCode.ARRIVAL_AFTER_DELIVERY for w in order_state.warnings)


def test_arrival_after_delivery_warning() -> None:
    late = order(1, 200, 1, delivery=date(2026, 10, 12))
    order_state = compute_state(scenario(orders=(late,))).orders[1]
    codes = [w.code for w in order_state.warnings]
    assert WarningCode.ARRIVAL_AFTER_DELIVERY in codes


def test_no_start_date_gives_no_estimate() -> None:
    order_state = compute_state(scenario(assignments=(assignment(1, 1, 200),))).orders[1]
    assert order_state.production_end is None and order_state.readiness is None


def _shelf_scenario(boxes: int, shipments: tuple[Shipment, ...] = ()) -> Snapshot:
    return scenario(
        assignments=(assignment(1, 1, 200, start=date(2026, 10, 6), actual_pieces=385_000),),
        packaging_plans=(packaging_plan(1, completed=True),),
        shelf_lines=(ShelfLine(1, 1, boxes, 24, BOX, CREATED, 160, CARTON),),
        shipments=shipments,
    )


def test_completed_packaging_releases_reservations() -> None:
    state = compute_state(_shelf_scenario(16_041))
    assert state.orders[1].status is OrderStatus.ON_SHELF
    assert state.orders[1].flags == ()
    assert state.materials[FILM].reserved == 0
    assert state.shelf_lines[1].cartons == 100
    assert state.shelf_lines[1].loose_boxes == 41


def test_shipped_and_transferred_statuses() -> None:
    shipped = Shipment(1, 1, 16_041, shipped_at=datetime(2026, 10, 20, 10))
    assert compute_state(_shelf_scenario(0, (shipped,))).orders[1].status is OrderStatus.SHIPPED
    assert compute_state(_shelf_scenario(0)).orders[1].status is OrderStatus.TRANSFERRED
    assert compute_state(_shelf_scenario(0)).shelf_lines[1].depleted


def test_pending_shipment_reduces_free_boxes() -> None:
    pending = Shipment(1, 1, 8_000)
    state = compute_state(_shelf_scenario(12_000, (pending,)))
    line = state.shelf_lines[1]
    assert (line.pending_boxes, line.free_boxes) == (8_000, 4_000)
    assert state.shipments[1].cartons == 50 and state.shipments[1].loose_boxes == 0


def test_shelf_transfers_listed_on_both_lines() -> None:
    snapshot = scenario(
        orders=(order(1, 200, 1), order(2, 200, 2)),
        order_recipe_lines=(),
        assignments=(),
        packaging_plans=(packaging_plan(1, True), packaging_plan(2, True)),
        packaging_steps=(),
        packaging_step_extras=(),
        shelf_lines=(ShelfLine(1, 1, 4_000, 24, BOX, CREATED, 160), ShelfLine(2, 2, 6_000, 24, BOX, CREATED, 160)),
        shelf_transfers=(ShelfTransfer(1, 1, 2, 1_000, TODAY),),
    )
    state = compute_state(snapshot)
    assert state.shelf_lines[1].transfer_ids == (1,) and state.shelf_lines[2].transfer_ids == (1,)


def test_cartons_and_loose() -> None:
    assert cartons_and_loose(16_041, 160) == (100, 41)
    assert cartons_and_loose(500, None) == (None, 500)


def _short_scenario(receipts: tuple[Receipt, ...], start: date | None = date(2026, 10, 6)) -> Snapshot:
    return scenario(
        lots=(lot(1, 1, 150), lot(2, 2, 20), lot(3, 3, 60), lot(4, FILM, 150), lot(5, FOIL, 40)),
        assignments=(assignment(1, 1, 200, start=start),),
        receipts=receipts,
    )


def test_start_before_covering_receipt() -> None:
    receipts = (
        Receipt(1, ItemKind.MATERIAL, kg(30), date(2026, 10, 8), material_id=2),
        Receipt(2, ItemKind.MATERIAL, kg(200), date(2026, 10, 14), material_id=2),
    )
    order_state = compute_state(_short_scenario(receipts)).orders[1]
    assert order_state.status is OrderStatus.WAITING_MATERIALS
    warning = next(w for w in order_state.warnings if w.code is WarningCode.START_BEFORE_RECEIPT)
    assert warning.item_key == material_key(2) and warning.day == date(2026, 10, 14)


def test_no_covering_receipt() -> None:
    order_state = compute_state(_short_scenario(())).orders[1]
    warning = next(w for w in order_state.warnings if w.code is WarningCode.NO_COVERING_RECEIPT)
    assert warning.item_key == material_key(2) and warning.quantity == kg(60)


def test_covering_receipt_date() -> None:
    pending = [ExpectedReceipt(2, kg(200), date(2026, 10, 14)), ExpectedReceipt(1, kg(30), date(2026, 10, 8))]
    assert covering_receipt_date(kg(25), pending) == date(2026, 10, 8)
    assert covering_receipt_date(kg(60), pending) == date(2026, 10, 14)
    assert covering_receipt_date(kg(300), pending) is None


def test_expected_receipts_shown_not_available() -> None:
    receipts = (Receipt(1, ItemKind.MATERIAL, kg(200), date(2026, 10, 14), material_id=2),)
    state = compute_state(_short_scenario(receipts))
    assert state.materials[2].available == kg(20)
    assert [(r.quantity, r.receipt_date) for r in state.materials[2].expected] == [(kg(200), date(2026, 10, 14))]


def test_receipt_statuses() -> None:
    receipts = (
        Receipt(1, ItemKind.MATERIAL, kg(1), date(2026, 10, 14), material_id=1),
        Receipt(2, ItemKind.PACKAGING, 100, date(2026, 10, 1), packaging_item_id=BOX),
        Receipt(3, ItemKind.MATERIAL, kg(1), date(2026, 9, 1), material_id=1,
                received_at=datetime(2026, 9, 1), received_quantity=kg(1), lot_id=1),
    )
    states = compute_state(scenario(receipts=receipts)).receipts
    assert states[1].status is ReceiptStatus.EXPECTED
    assert (states[2].status, states[2].delay_days) == (ReceiptStatus.DELAYED, 4)
    assert states[3].status is ReceiptStatus.RECEIVED


def test_red_lot_warning_and_lot_order() -> None:
    lots = (
        lot(1, 1, 60, expiry=date(2026, 10, 20)), lot(6, 1, 100), lot(2, 2, 100), lot(3, 3, 60),
        lot(4, FILM, 150), lot(5, FOIL, 40),
    )
    order_state = compute_state(scenario(lots=lots)).orders[1]
    uses = [(u.lot_id, u.quantity_mg) for u in order_state.lot_uses if u.material_id == 1]
    assert uses == [(1, kg(60)), (6, kg(40))]
    warning = next(w for w in order_state.warnings if w.code is WarningCode.RED_LOT)
    assert warning.lot_id == 1 and warning.days == 15


def test_lost_reservation_detected() -> None:
    before = compute_state(scenario())
    after = compute_state(scenario(lots=(lot(1, 1, 150), lot(2, 2, 70), lot(3, 3, 60), lot(4, FILM, 150), lot(5, FOIL, 40))))
    lost = lost_reservations(before, after)
    assert [(x.order_id, x.already_started) for x in lost] == [(1, False)]
    started_after = compute_state(scenario(today=date(2026, 10, 6), lots=after_lots()))
    assert lost_reservations(before, started_after)[0].already_started


def after_lots():
    return (lot(1, 1, 150), lot(2, 2, 70), lot(3, 3, 60), lot(4, FILM, 150), lot(5, FOIL, 40))


def test_product_availability_after_reservations() -> None:
    from core.models import Product, RecipeLine

    state = compute_state(scenario(
        products=(Product(1, "Product A", 500),),
        recipe_lines=(RecipeLine(1, 1, 5000), RecipeLine(1, 2, 4000), RecipeLine(1, 3, 1000)),
    ))
    availability = state.products[1]
    assert availability is not None
    assert availability.producible_mg == kg(50)
    assert availability.limiting_material_id == 2


def test_in_production_from_start_date_until_completed() -> None:
    def status(start: date, today: date = TODAY) -> OrderStatus:
        snapshot = scenario(today=today, assignments=(assignment(1, 1, 200, start=start),))
        return compute_state(snapshot).orders[1].status

    assert status(start=date(2026, 10, 6)) is OrderStatus.READY_FOR_PRODUCTION
    assert status(start=TODAY) is OrderStatus.IN_PRODUCTION
    assert status(start=date(2026, 10, 1)) is OrderStatus.IN_PRODUCTION
    assert status(start=date(2026, 10, 6), today=date(2026, 10, 6)) is OrderStatus.IN_PRODUCTION


def test_in_production_needs_reserved_materials() -> None:
    lots = (lot(1, 1, 150), lot(2, 2, 20), lot(3, 3, 60), lot(4, FILM, 150), lot(5, FOIL, 40))
    snapshot = scenario(lots=lots, assignments=(assignment(1, 1, 200, start=TODAY),))
    assert compute_state(snapshot).orders[1].status is OrderStatus.WAITING_MATERIALS


def test_completion_ends_in_production() -> None:
    done = assignment(1, 1, 200, start=TODAY, actual_pieces=385_000)
    assert compute_state(scenario(assignments=(done,))).orders[1].status is OrderStatus.IN_PACKAGING


def test_two_machines_one_started() -> None:
    shares = (assignment(1, 1, 100, start=TODAY), assignment(2, 1, 100, start=date(2026, 10, 9)))
    assert compute_state(scenario(assignments=shares)).orders[1].status is OrderStatus.IN_PRODUCTION


def test_shelf_line_shipped_out_only_when_a_shipment_empties_it() -> None:
    shipped = Shipment(1, 1, 16_041, shipped_at=datetime(2026, 10, 20, 10))
    assert compute_state(_shelf_scenario(0, (shipped,))).shelf_lines[1].shipped_out
    # Emptied by a transfer, not a shipment: stays on the shelf as "Εξαντλήθηκε".
    assert not compute_state(_shelf_scenario(0)).shelf_lines[1].shipped_out
    # Partial shipment: the remaining boxes stay on the shelf.
    partial = Shipment(1, 1, 8_000, shipped_at=datetime(2026, 10, 20, 10))
    assert not compute_state(_shelf_scenario(4_000, (partial,))).shelf_lines[1].shipped_out
