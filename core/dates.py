"""Today's date, working days, and the readiness and ship-by dates (section 4.9).

Production and packaging durations count working days; transit counts calendar
days. Durations are rounded up to whole working days.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import date, datetime, timedelta
from decimal import Decimal

from core.units import ceil_int


def today() -> date:
    """The current date. The single source of "today"; tests pass their own date instead."""
    return date.today()


def now() -> datetime:
    """The current date and time, for action timestamps. Tests replace it to fix the clock."""
    return datetime.now()


def _check(working_days: Collection[int]) -> None:
    if not working_days:
        raise ValueError("At least one working day is required")


def is_working_day(day: date, working_days: Collection[int]) -> bool:
    return day.weekday() in working_days


def first_working_day_from(day: date, working_days: Collection[int]) -> date:
    """The day itself if it is a working day, otherwise the next working day."""
    _check(working_days)
    while not is_working_day(day, working_days):
        day += timedelta(days=1)
    return day


def add_working_days(day: date, count: int, working_days: Collection[int]) -> date:
    """The count-th working day after the given day. count = 0 returns the day."""
    _check(working_days)
    if count < 0:
        raise ValueError("count must not be negative")
    while count:
        day += timedelta(days=1)
        if is_working_day(day, working_days):
            count -= 1
    return day


def assignment_end(start: date, production_days: Decimal, working_days: Collection[int]) -> date:
    """The last of ceil(production_days) working days, counting the start as day one.

    A start on a non-working day begins counting at the next working day.
    """
    days = max(1, ceil_int(production_days))
    first = first_working_day_from(start, working_days)
    return add_working_days(first, days - 1, working_days)


def readiness_date(production_end: date, packaging_days: Decimal | None, working_days: Collection[int]) -> date:
    """Production end plus ceil(packaging_days) working days; without packaging, the end itself."""
    if packaging_days is None:
        return production_end
    return add_working_days(production_end, ceil_int(packaging_days), working_days)


def estimated_arrival(readiness: date, transit_days: int) -> date:
    return readiness + timedelta(days=transit_days)


def ship_by_date(delivery: date, transit_days: int) -> date:
    return delivery - timedelta(days=transit_days)
