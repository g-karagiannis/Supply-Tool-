"""Section 12.7: dates with working days Monday to Friday. 05/10/2026 is a Monday."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from core import dates

WEEKDAYS = frozenset({0, 1, 2, 3, 4})


def test_reference_date_is_monday() -> None:
    assert date(2026, 10, 5).weekday() == 0


@pytest.mark.parametrize("start, days, end", [
    (date(2026, 10, 6), "1.25", date(2026, 10, 7)),
    (date(2026, 10, 10), "1", date(2026, 10, 12)),
    (date(2026, 10, 6), "2.5", date(2026, 10, 8)),
    (date(2026, 10, 9), "2", date(2026, 10, 12)),
])
def test_production_end(start: date, days: str, end: date) -> None:
    assert dates.assignment_end(start, Decimal(days), WEEKDAYS) == end


@pytest.mark.parametrize("production_end, packaging_days, ready", [
    (date(2026, 10, 7), "3", date(2026, 10, 12)),
    (date(2026, 10, 7), "1.2", date(2026, 10, 9)),
])
def test_readiness(production_end: date, packaging_days: str, ready: date) -> None:
    assert dates.readiness_date(production_end, Decimal(packaging_days), WEEKDAYS) == ready


def test_readiness_without_packaging_equals_production_end() -> None:
    assert dates.readiness_date(date(2026, 10, 7), None, WEEKDAYS) == date(2026, 10, 7)


def test_arrival_and_ship_by_on_time() -> None:
    arrival = dates.estimated_arrival(date(2026, 10, 12), 5)
    assert arrival == date(2026, 10, 17)
    assert dates.ship_by_date(date(2026, 10, 26), 5) == date(2026, 10, 21)
    assert not arrival > date(2026, 10, 26)


def test_arrival_late() -> None:
    arrival = dates.estimated_arrival(date(2026, 10, 23), 5)
    assert arrival == date(2026, 10, 28)
    assert arrival > date(2026, 10, 26)


def test_transit_counts_calendar_days() -> None:
    assert dates.estimated_arrival(date(2026, 10, 9), 2) == date(2026, 10, 11)


def test_working_days_follow_settings() -> None:
    six_days = frozenset({0, 1, 2, 3, 4, 5})
    assert dates.assignment_end(date(2026, 10, 9), Decimal(2), six_days) == date(2026, 10, 10)


def test_no_working_days_is_rejected() -> None:
    with pytest.raises(ValueError):
        dates.assignment_end(date(2026, 10, 6), Decimal(1), frozenset())


def test_today_is_the_single_source() -> None:
    assert dates.today() == date.today()
