"""Section 12.1: LOT expiry, today 05/10/2026, yellow 120, red 30."""

from __future__ import annotations

from datetime import date

import pytest

from core.expiry import STATUS_BACKGROUND, ExpiryStatus, expiry_status
from factories import TODAY


@pytest.mark.parametrize("expiry, days_left, status", [
    (date(2027, 2, 3), 121, ExpiryStatus.GREEN),
    (date(2027, 2, 2), 120, ExpiryStatus.YELLOW),
    (date(2026, 12, 31), 87, ExpiryStatus.YELLOW),
    (date(2026, 11, 4), 30, ExpiryStatus.YELLOW),
    (date(2026, 11, 3), 29, ExpiryStatus.RED),
    (date(2026, 10, 5), 0, ExpiryStatus.RED),
    (date(2026, 10, 4), -1, ExpiryStatus.EXPIRED),
])
def test_section_12_1(expiry: date, days_left: int, status: ExpiryStatus) -> None:
    result = expiry_status(expiry, TODAY, 1_000_000, yellow_days=120, red_days=30)
    assert result.days_left == days_left
    assert result.status is status


def test_expiring_today_is_not_expired() -> None:
    assert not expiry_status(TODAY, TODAY, 1, 120, 30).is_expired


@pytest.mark.parametrize("expiry", [date(2027, 6, 30), date(2026, 10, 20), date(2026, 9, 30)])
def test_depleted_overrides_every_status(expiry: date) -> None:
    assert expiry_status(expiry, TODAY, 0, 120, 30).status is ExpiryStatus.DEPLETED


def test_section_4_1_examples() -> None:
    assert expiry_status(date(2027, 6, 30), TODAY, 1, 120, 30).days_left == 268
    assert expiry_status(date(2026, 10, 20), TODAY, 1, 120, 30).status is ExpiryStatus.RED
    assert expiry_status(date(2026, 9, 30), TODAY, 1, 120, 30).status is ExpiryStatus.EXPIRED


def test_thresholds_follow_settings() -> None:
    assert expiry_status(date(2026, 12, 31), TODAY, 1, yellow_days=60, red_days=10).status is ExpiryStatus.GREEN


def test_every_status_has_a_colour() -> None:
    assert set(STATUS_BACKGROUND) == set(ExpiryStatus)
