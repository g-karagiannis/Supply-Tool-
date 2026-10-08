"""Section 12.3: shortages and reservation by sequence, and FEFO consumption (4.11)."""

from __future__ import annotations

from datetime import date

from core.allocation import consume_fefo
from core.models import MaterialLot, Product, RecipeLine, Snapshot
from core.state import OrderStatus, compute_state
from factories import TODAY, kg, lot, material, order, recipe


def _needs(state, order_id: int) -> list[tuple[int, int]]:
    return [(line.need, line.shortage) for line in state.orders[order_id].recipe_lines]


def test_order_shortages() -> None:
    snapshot = Snapshot(
        today=TODAY,
        materials=(material(1), material(2), material(3)),
        lots=(lot(1, 1, 50), lot(2, 2, 20), lot(3, 3, 40)),
        orders=(order(1, 150, sequence=1),),
        order_recipe_lines=recipe(1, (1, 50), (2, 40), (3, 10)),
    )
    state = compute_state(snapshot)
    assert _needs(state, 1) == [(kg(75), kg(25)), (kg(60), kg(40)), (kg(15), 0)]
    assert state.orders[1].status is OrderStatus.WAITING_MATERIALS
    assert state.materials[1].reserved == 0


def _two_orders(stock: int, first: int, second: int, first_sequence: int = 1, second_sequence: int = 2) -> Snapshot:
    return Snapshot(
        today=TODAY,
        materials=(material(1),),
        lots=(lot(1, 1, stock),),
        orders=(order(1, first, first_sequence), order(2, second, second_sequence)),
        order_recipe_lines=recipe(1, (1, 100)) + recipe(2, (1, 100)),
    )


def test_first_in_sequence_reserves() -> None:
    state = compute_state(_two_orders(80, 60, 60))
    assert state.orders[1].status is OrderStatus.READY_FOR_PRODUCTION
    assert state.orders[2].status is OrderStatus.WAITING_MATERIALS
    assert _needs(state, 2) == [(kg(60), kg(40))]
    assert state.materials[1].reserved == kg(60)
    assert state.materials[1].available == kg(20)


def test_reversed_sequence_reverses_result() -> None:
    state = compute_state(_two_orders(80, 60, 60, first_sequence=2, second_sequence=1))
    assert state.orders[2].status is OrderStatus.READY_FOR_PRODUCTION
    assert state.orders[1].status is OrderStatus.WAITING_MATERIALS
    assert state.materials[1].available == kg(20)


def test_waiting_order_holds_nothing() -> None:
    state = compute_state(_two_orders(50, 60, 40))
    assert state.orders[1].status is OrderStatus.WAITING_MATERIALS
    assert _needs(state, 1) == [(kg(60), kg(10))]
    assert state.orders[2].status is OrderStatus.READY_FOR_PRODUCTION
    assert state.materials[1].reserved == kg(40)
    assert state.materials[1].available == kg(10)


def test_expired_lot_not_available() -> None:
    snapshot = Snapshot(
        today=TODAY,
        materials=(material(1),),
        lots=(lot(1, 1, 30, expiry=date(2026, 9, 30)), lot(2, 1, 20)),
    )
    stock = compute_state(snapshot).materials[1]
    assert stock.total == kg(50)
    assert stock.expired == kg(30)
    assert stock.available == kg(20)


def test_order_keeps_its_recipe_copy() -> None:
    snapshot = Snapshot(
        today=TODAY,
        materials=(material(1), material(2), material(3)),
        lots=(lot(1, 1, 1000), lot(2, 2, 1000), lot(3, 3, 1000)),
        products=(Product(1, "Product A", 500),),
        recipe_lines=(RecipeLine(1, 1, 4500), RecipeLine(1, 2, 4500), RecipeLine(1, 3, 1000)),
        orders=(order(1, 150, 1), order(2, 150, 2)),
        order_recipe_lines=recipe(1, (1, 50), (2, 40), (3, 10)) + recipe(2, (1, 45), (2, 45), (3, 10)),
    )
    state = compute_state(snapshot)
    assert [line.need for line in state.orders[1].recipe_lines] == [kg(75), kg(60), kg(15)]
    assert [line.need for line in state.orders[2].recipe_lines] == [kg("67.5"), kg("67.5"), kg(15)]


def test_cancelled_order_reserves_nothing() -> None:
    snapshot = Snapshot(
        today=TODAY,
        materials=(material(1),),
        lots=(lot(1, 1, 80),),
        orders=(order(1, 60, 1, cancelled=True), order(2, 60, 2)),
        order_recipe_lines=recipe(1, (1, 100)) + recipe(2, (1, 100)),
    )
    state = compute_state(snapshot)
    assert state.orders[1].status is OrderStatus.CANCELLED
    assert state.orders[2].status is OrderStatus.READY_FOR_PRODUCTION
    assert state.materials[1].reserved == kg(60)


def _lots() -> list[MaterialLot]:
    return [
        MaterialLot(2, 1, "L-002", kg(200), date(2027, 6, 30)),
        MaterialLot(1, 1, "L-001", kg(100), date(2027, 1, 31)),
        MaterialLot(3, 1, "L-003", kg(50), date(2026, 9, 30)),
    ]


def test_fefo_takes_nearest_expiry_first() -> None:
    plan = consume_fefo(_lots(), kg(150), TODAY)
    assert [(t.lot_id, t.quantity_mg) for t in plan.takes] == [(1, kg(100)), (2, kg(50))]
    assert plan.shortfall_mg == 0


def test_fefo_skips_expired_lots() -> None:
    plan = consume_fefo(_lots(), kg(320), TODAY)
    assert plan.shortfall_mg == kg(20)
    assert plan.expired_lot_ids == (3,)


def test_fefo_uses_expired_after_confirmation() -> None:
    plan = consume_fefo(_lots(), kg(320), TODAY, include_expired=True)
    assert [(t.lot_id, t.quantity_mg) for t in plan.takes] == [(1, kg(100)), (2, kg(200)), (3, kg(20))]
    assert plan.shortfall_mg == 0
