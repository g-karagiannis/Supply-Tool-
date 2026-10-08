"""Sections 12.4 (production) and 12.5 (inverse calculation)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.production_calc import Infeasibility, Lever, inverse_calculation, production_estimate
from core.units import round_half_up
from factories import kg


def r2(value: Decimal) -> Decimal:
    return round_half_up(value, 2)


def test_time_example() -> None:
    estimate = production_estimate(kg(4000), kg(200), Decimal(48), 8000, Decimal(8), None)
    assert estimate.batches == 20
    assert estimate.net_minutes == 960
    assert estimate.net_hours == 16
    assert estimate.operating_hours == 20
    assert estimate.production_days == Decimal("2.5")


def test_batches_never_rounded() -> None:
    estimate = production_estimate(kg(4000), kg(150), Decimal(48), 8000, Decimal(8), None)
    assert r2(estimate.batches) == Decimal("26.67")
    assert estimate.batches != 26 and estimate.batches != 27
    assert estimate.net_minutes == 1280


def test_pieces_example() -> None:
    estimate = production_estimate(kg(200), kg(50), Decimal(120), 8000, Decimal(8), 500, defect_bp=300)
    assert estimate.batches == 4
    assert estimate.net_hours == 8
    assert estimate.operating_hours == 10
    assert estimate.production_days == Decimal("1.25")
    assert estimate.pieces_per_batch == 100_000
    assert estimate.planned_pieces == 400_000
    assert estimate.expected_pieces == 388_000
    assert estimate.expected_defects == 12_000


def test_pieces_round_down() -> None:
    estimate = production_estimate(1_001, 1_000, Decimal(1), 10_000, Decimal(8), 2, defect_bp=150)
    assert estimate.planned_pieces == 500
    assert estimate.expected_pieces == 492


@pytest.mark.parametrize("kwargs", [
    {"quantity_mg": 0},
    {"batch_size_mg": 0},
    {"utilization_bp": 0},
    {"utilization_bp": 10_001},
    {"defect_bp": -1},
])
def test_invalid_inputs(kwargs) -> None:
    values = dict(quantity_mg=kg(1), batch_size_mg=kg(1), cycle_time_min=Decimal(1),
                  utilization_bp=8000, hours_per_day=Decimal(8), unit_weight_mg=None)
    values.update(kwargs)
    with pytest.raises(ValueError):
        production_estimate(**values)


def _inverse(target: str, max_batch: int | None = None, min_cycle: str | None = None):
    return inverse_calculation(
        Decimal("2.5"), Decimal(target), Decimal(48), kg(200), Decimal(8),
        max_batch_mg=max_batch, min_cycle_time_min=Decimal(min_cycle) if min_cycle else None,
    )


def test_inverse_two_days() -> None:
    cycle, batch, hours = _inverse("2")
    assert (cycle.lever, batch.lever, hours.lever) == (Lever.CYCLE_TIME, Lever.BATCH_SIZE, Lever.HOURS_PER_DAY)
    assert cycle.new == Decimal("38.4") and cycle.feasible
    assert batch.new == kg(250) and batch.feasible
    assert hours.new == 10 and hours.feasible
    assert (cycle.change_percent, batch.change_percent, hours.change_percent) == (-20, 25, 25)


def test_inverse_with_machine_limits() -> None:
    cycle, batch, hours = _inverse("1.5", max_batch=kg(300), min_cycle="30")
    assert r2(cycle.new) == Decimal("28.80") and not cycle.feasible
    assert cycle.reason is Infeasibility.BELOW_MIN_CYCLE
    assert r2(batch.new / 1_000_000) == Decimal("333.33") and not batch.feasible
    assert batch.reason is Infeasibility.ABOVE_MAX_BATCH
    assert r2(hours.new) == Decimal("13.33") and hours.feasible


def test_inverse_half_day_without_limits() -> None:
    cycle, batch, hours = _inverse("0.5")
    assert cycle.new == Decimal("9.6") and cycle.feasible
    assert batch.new == kg(1000) and batch.feasible
    assert hours.new == 40 and not hours.feasible
    assert hours.reason is Infeasibility.ABOVE_24_HOURS


def test_limits_only_checked_when_declared() -> None:
    cycle, batch, _ = _inverse("0.1")
    assert cycle.feasible and batch.feasible


def test_inverse_rejects_non_positive_target() -> None:
    with pytest.raises(ValueError):
        _inverse("0")
