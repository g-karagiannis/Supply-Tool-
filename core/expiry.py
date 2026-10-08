"""LOT expiry status (section 4.1) and the cell background colour of each status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class ExpiryStatus(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    EXPIRED = "expired"
    DEPLETED = "depleted"


# Dark tints, so that the light cell text stays readable on the dark theme.
# The colour always accompanies a text label; it never carries meaning alone.
STATUS_BACKGROUND: dict[ExpiryStatus, str] = {
    ExpiryStatus.GREEN: "#12301c",
    ExpiryStatus.YELLOW: "#3a3510",
    ExpiryStatus.RED: "#4a1616",
    ExpiryStatus.EXPIRED: "#4a1616",
    ExpiryStatus.DEPLETED: "#23252a",
}


@dataclass(frozen=True, slots=True)
class LotExpiry:
    """Status of one LOT. days_left is calendar days to expiry, negative once expired."""

    status: ExpiryStatus
    days_left: int
    is_expired: bool


def is_expired(expiry_date: date, today: date) -> bool:
    """A LOT that expires today is not yet expired."""
    return today > expiry_date


def expiry_status(
    expiry_date: date,
    today: date,
    quantity_mg: int,
    yellow_days: int,
    red_days: int,
) -> LotExpiry:
    """Classify a LOT. "Depleted" overrides every other status when the quantity is 0."""
    days_left = (expiry_date - today).days
    expired = is_expired(expiry_date, today)
    if quantity_mg == 0:
        status = ExpiryStatus.DEPLETED
    elif expired:
        status = ExpiryStatus.EXPIRED
    elif days_left < red_days:
        status = ExpiryStatus.RED
    elif days_left <= yellow_days:
        status = ExpiryStatus.YELLOW
    else:
        status = ExpiryStatus.GREEN
    return LotExpiry(status=status, days_left=days_left, is_expired=expired)
