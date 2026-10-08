"""Production time and pieces per machine assignment (4.6) and the inverse calculation (4.7).

Effective utilization expresses only time losses; the defect rate expresses only
quality losses. They never appear in the same formula. Batches are never rounded;
pieces are always rounded down.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from core.units import BP_FULL

MINUTES_PER_HOUR = 60
MAX_HOURS_PER_DAY = Decimal(24)


@dataclass(frozen=True, slots=True)
class ProductionEstimate:
    batches: Decimal
    net_minutes: Decimal
    operating_hours: Decimal
    production_days: Decimal
    planned_pieces: int | None
    expected_pieces: int | None
    expected_defects: int | None
    pieces_per_batch: int | None

    @property
    def net_hours(self) -> Decimal:
        return self.net_minutes / MINUTES_PER_HOUR


def production_estimate(
    quantity_mg: int,
    batch_size_mg: int,
    cycle_time_min: Decimal,
    utilization_bp: int,
    hours_per_day: Decimal,
    unit_weight_mg: int | None,
    defect_bp: int = 0,
) -> ProductionEstimate:
    """Apply the formulas of section 4.6 to one assignment.

    Products are formed before divisions so that exact cases stay exact.
    Pieces are None when the unit weight is unknown.
    """
    if quantity_mg <= 0 or batch_size_mg <= 0:
        raise ValueError("Quantity and batch size must be positive")
    if cycle_time_min <= 0 or hours_per_day <= 0:
        raise ValueError("Cycle time and hours per day must be positive")
    if not 0 < utilization_bp <= BP_FULL:
        raise ValueError("Utilization must be above 0% and at most 100%")
    if not 0 <= defect_bp <= BP_FULL:
        raise ValueError("Defect rate must be between 0% and 100%")

    quantity = Decimal(quantity_mg)
    batch = Decimal(batch_size_mg)
    batches = quantity / batch
    net_minutes = quantity * cycle_time_min / batch
    operating_hours = quantity * cycle_time_min * BP_FULL / (batch * MINUTES_PER_HOUR * utilization_bp)
    production_days = operating_hours / hours_per_day

    planned = expected = defects = per_batch = None
    if unit_weight_mg:
        planned = quantity_mg // unit_weight_mg
        expected = planned * (BP_FULL - defect_bp) // BP_FULL
        defects = planned - expected
        per_batch = batch_size_mg // unit_weight_mg
    return ProductionEstimate(
        batches=batches,
        net_minutes=net_minutes,
        operating_hours=operating_hours,
        production_days=production_days,
        planned_pieces=planned,
        expected_pieces=expected,
        expected_defects=defects,
        pieces_per_batch=per_batch,
    )


def split_equally(total: int, parts: int) -> list[int]:
    """Split a quantity into equal whole shares; the remainder goes to the last share."""
    if parts <= 0:
        raise ValueError("parts must be positive")
    share = total // parts
    return [share] * (parts - 1) + [total - share * (parts - 1)]


def scale_proportionally(amounts: list[int], new_total: int) -> list[int]:
    """Rescale shares to a new total with the same ratio; the remainder goes to the last share."""
    old_total = sum(amounts)
    if old_total <= 0:
        raise ValueError("amounts must add up to a positive total")
    scaled = [amount * new_total // old_total for amount in amounts[:-1]]
    return scaled + [new_total - sum(scaled)]


class Lever(str, Enum):
    """The parameter changed in one alternative of the inverse calculation."""

    CYCLE_TIME = "cycle_time"
    BATCH_SIZE = "batch_size"
    HOURS_PER_DAY = "hours_per_day"


class Infeasibility(str, Enum):
    ABOVE_24_HOURS = "above_24_hours"
    ABOVE_MAX_BATCH = "above_max_batch"
    BELOW_MIN_CYCLE = "below_min_cycle"


@dataclass(frozen=True, slots=True)
class InverseOption:
    """One alternative: change only this lever, keep the other two fixed.

    Batch values are in mg (Decimal, since the new batch need not be whole).
    """

    lever: Lever
    current: Decimal
    new: Decimal
    change_percent: Decimal
    limit: Decimal | None
    feasible: bool
    reason: Infeasibility | None


def inverse_calculation(
    current_days: Decimal,
    target_days: Decimal,
    cycle_time_min: Decimal,
    batch_size_mg: int,
    hours_per_day: Decimal,
    max_batch_mg: int | None = None,
    min_cycle_time_min: Decimal | None = None,
) -> tuple[InverseOption, InverseOption, InverseOption]:
    """Three alternatives that finish in target_days (section 4.7). Informational only.

    k = current / target; cycle / k, batch x k, hours x k.
    """
    if target_days <= 0:
        raise ValueError("Target days must be positive")
    if current_days <= 0:
        raise ValueError("Current days must be positive")

    batch = Decimal(batch_size_mg)
    new_cycle = cycle_time_min * target_days / current_days
    new_batch = batch * current_days / target_days
    new_hours = hours_per_day * current_days / target_days

    def change(old: Decimal, new: Decimal) -> Decimal:
        return (new - old) * 100 / old

    cycle_limit = min_cycle_time_min
    cycle_ok = cycle_limit is None or new_cycle >= cycle_limit
    batch_limit = Decimal(max_batch_mg) if max_batch_mg is not None else None
    batch_ok = batch_limit is None or new_batch <= batch_limit
    hours_ok = new_hours <= MAX_HOURS_PER_DAY

    return (
        InverseOption(
            Lever.CYCLE_TIME, cycle_time_min, new_cycle, change(cycle_time_min, new_cycle),
            cycle_limit, cycle_ok, None if cycle_ok else Infeasibility.BELOW_MIN_CYCLE,
        ),
        InverseOption(
            Lever.BATCH_SIZE, batch, new_batch, change(batch, new_batch),
            batch_limit, batch_ok, None if batch_ok else Infeasibility.ABOVE_MAX_BATCH,
        ),
        InverseOption(
            Lever.HOURS_PER_DAY, hours_per_day, new_hours, change(hours_per_day, new_hours),
            MAX_HOURS_PER_DAY, hours_ok, None if hours_ok else Infeasibility.ABOVE_24_HOURS,
        ),
    )
