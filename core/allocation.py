"""Reservation by order sequence (section 4.5) and FEFO consumption of LOTs (4.11).

Reservations are never stored. They are recomputed on every run from the stock
pools and the open orders, in ascending sequence. An order reserves all of its
recipe materials or none of them, and separately all of its packaging needs or
none of them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from core.expiry import is_expired
from core.models import ItemKey, MaterialLot


@dataclass(frozen=True, slots=True)
class Need:
    """One line of a shortage table: what an order needs and the pool at its turn."""

    key: ItemKey
    need: int
    pool: int

    @property
    def shortage(self) -> int:
        return max(0, self.need - self.pool)


@dataclass(frozen=True, slots=True)
class OrderDemand:
    """What one open order asks for.

    recipe_needs is None once production is complete; packaging_needs is None
    when there is no saved packaging plan or packaging is complete.
    """

    order_id: int
    sequence: int
    recipe_needs: Mapping[ItemKey, int] | None
    packaging_needs: Mapping[ItemKey, int] | None


@dataclass(frozen=True, slots=True)
class OrderAllocation:
    order_id: int
    recipe_lines: tuple[Need, ...] = ()
    recipe_reserved: bool = False
    packaging_lines: tuple[Need, ...] = ()
    packaging_reserved: bool = False


@dataclass(frozen=True, slots=True)
class AllocationResult:
    orders: dict[int, OrderAllocation]
    reserved: dict[ItemKey, int] = field(default_factory=dict)
    remaining: dict[ItemKey, int] = field(default_factory=dict)


def _try_reserve(
    needs: Mapping[ItemKey, int],
    pool: dict[ItemKey, int],
    reserved: dict[ItemKey, int],
) -> tuple[tuple[Need, ...], bool]:
    lines = tuple(Need(key, quantity, pool.get(key, 0)) for key, quantity in needs.items())
    if all(line.shortage == 0 for line in lines):
        for line in lines:
            pool[line.key] = pool.get(line.key, 0) - line.need
            reserved[line.key] = reserved.get(line.key, 0) + line.need
        return lines, True
    return lines, False


def allocate(
    initial_pool: Mapping[ItemKey, int],
    demands: Sequence[OrderDemand],
) -> AllocationResult:
    """Run the reservation algorithm over the open orders in ascending sequence."""
    pool = dict(initial_pool)
    reserved: dict[ItemKey, int] = {}
    results: dict[int, OrderAllocation] = {}
    for demand in sorted(demands, key=lambda d: (d.sequence, d.order_id)):
        recipe_lines: tuple[Need, ...] = ()
        recipe_ok = False
        if demand.recipe_needs is not None:
            recipe_lines, recipe_ok = _try_reserve(demand.recipe_needs, pool, reserved)
        packaging_lines: tuple[Need, ...] = ()
        packaging_ok = False
        if demand.packaging_needs is not None:
            packaging_lines, packaging_ok = _try_reserve(demand.packaging_needs, pool, reserved)
        results[demand.order_id] = OrderAllocation(
            order_id=demand.order_id,
            recipe_lines=recipe_lines,
            recipe_reserved=recipe_ok,
            packaging_lines=packaging_lines,
            packaging_reserved=packaging_ok,
        )
    return AllocationResult(orders=results, reserved=reserved, remaining=pool)


@dataclass(frozen=True, slots=True)
class LotTake:
    lot_id: int
    quantity_mg: int


@dataclass(frozen=True, slots=True)
class FefoPlan:
    """Which LOTs a consumption takes from, and what could not be covered."""

    takes: tuple[LotTake, ...]
    shortfall_mg: int
    expired_lot_ids: tuple[int, ...]


def consume_fefo(
    lots: Sequence[MaterialLot],
    quantity_mg: int,
    today: date,
    include_expired: bool = False,
) -> FefoPlan:
    """Take a quantity from the LOTs with the nearest expiry first.

    Expired LOTs are skipped unless include_expired is True; then they are used
    only after every valid LOT, which is the "consumed in this production?"
    confirmation of section 4.11. expired_lot_ids lists the expired LOTs with
    stock that could cover a shortfall.
    """
    def order_key(lot: MaterialLot) -> tuple[date, int]:
        return (lot.expiry_date, lot.id)

    with_stock = [lot for lot in lots if lot.quantity_mg > 0]
    valid = sorted((lot for lot in with_stock if not is_expired(lot.expiry_date, today)), key=order_key)
    expired = sorted((lot for lot in with_stock if is_expired(lot.expiry_date, today)), key=order_key)
    sources = valid + expired if include_expired else valid

    takes = []
    remaining = quantity_mg
    for lot in sources:
        if remaining == 0:
            break
        take = min(lot.quantity_mg, remaining)
        takes.append(LotTake(lot.id, take))
        remaining -= take
    return FefoPlan(
        takes=tuple(takes),
        shortfall_mg=remaining,
        expired_lot_ids=tuple(lot.id for lot in expired),
    )
