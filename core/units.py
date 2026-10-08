"""Unit conversion, exact rounding helpers and Greek number and date formatting.

Storage units are integers: mass in mg (1 kg = 1,000,000 mg), percentages in
basis points (100% = 10,000), dimensions in mm. Conversions from user units are
exact and reject values with more decimals than the storage unit can hold.

Display follows section 11.6: thousands with a dot, decimals with a comma,
no trailing zeros, dates as DD/MM/YYYY.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

MG_PER_G = 1_000
MG_PER_KG = 1_000_000
BP_PER_PERCENT = 100
BP_FULL = 10_000
MM_PER_CM = 10

KG_DECIMALS = 3
G_DECIMALS = 3
PERCENT_DECIMALS = 2
CM_DECIMALS = 1
TIME_DECIMALS = 2

Number = int | Decimal

_DECIMAL_INPUT = re.compile(r"^[+-]?(\d+([.,]\d*)?|[.,]\d+)$")


class UnitError(ValueError):
    """Raised when a value cannot be parsed or converted exactly."""


def parse_decimal(text: str) -> Decimal:
    """Parse a typed number. Both comma and dot are accepted as decimal separator.

    Thousands separators are not accepted, so the text may contain at most one
    separator character.
    """
    cleaned = text.strip()
    if not _DECIMAL_INPUT.match(cleaned):
        raise UnitError(f"Not a number: {text!r}")
    return Decimal(cleaned.replace(",", "."))


_GROUPED_WHOLE = re.compile(r"^[+-]?\d{1,3}(\.\d{3})+$")


def parse_whole(text: str) -> int:
    """Parse a typed whole number (pieces, boxes, days).

    A whole number has no decimals, so a dot here can only group thousands:
    "385.000" is read as 385000, as it is displayed. Otherwise the rules of
    parse_decimal apply and the value must be whole.
    """
    cleaned = text.strip()
    if _GROUPED_WHOLE.match(cleaned):
        return int(cleaned.replace(".", ""))
    value = parse_decimal(cleaned)
    if value != value.to_integral_value():
        raise UnitError(f"Not a whole number: {text!r}")
    return int(value)


def _scale_exact(value: Number, factor: int, unit: str) -> int:
    scaled = Decimal(value) * factor
    if scaled != scaled.to_integral_value():
        raise UnitError(f"Too many decimals for {unit}: {value}")
    return int(scaled)


def kg_to_mg(kg: Number) -> int:
    """Convert kg to integer mg, exactly."""
    return _scale_exact(kg, MG_PER_KG, "kg")


def g_to_mg(grams: Number) -> int:
    """Convert g to integer mg, exactly."""
    return _scale_exact(grams, MG_PER_G, "g")


def percent_to_bp(percent: Number) -> int:
    """Convert a percentage (e.g. 96 or 12.5) to integer basis points, exactly."""
    return _scale_exact(percent, BP_PER_PERCENT, "%")


def cm_to_mm(cm: Number) -> int:
    """Convert cm to integer mm, exactly."""
    return _scale_exact(cm, MM_PER_CM, "cm")


def mg_to_kg(mg: Number) -> Decimal:
    return Decimal(mg) / MG_PER_KG


def mg_to_g(mg: Number) -> Decimal:
    return Decimal(mg) / MG_PER_G


def bp_to_percent(bp: Number) -> Decimal:
    return Decimal(bp) / BP_PER_PERCENT


def bp_to_fraction(bp: Number) -> Decimal:
    """Basis points as a fraction of one, e.g. 8000 -> 0.8."""
    return Decimal(bp) / BP_FULL


def mm_to_cm(mm: Number) -> Decimal:
    return Decimal(mm) / MM_PER_CM


def floor_int(value: Number) -> int:
    """Largest integer not above the value."""
    return int(Decimal(value).to_integral_value(rounding=ROUND_FLOOR))


def ceil_int(value: Number) -> int:
    """Smallest integer not below the value."""
    return int(Decimal(value).to_integral_value(rounding=ROUND_CEILING))


def apply_bp_ceil(quantity: int, percent_bp: int) -> int:
    """quantity x percent, rounded up to a whole unit.

    Used for every mass requirement, reservation and consumption, so the
    application never reserves less than what is needed.
    """
    return -(-quantity * percent_bp // BP_FULL)


def round_half_up(value: Number, decimals: int) -> Decimal:
    """Round to a fixed number of decimals, halves away from zero."""
    return Decimal(value).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def format_number(value: Number, max_decimals: int = 0) -> str:
    """Greek format: 16.041 and 128,332. Trailing zeros are dropped."""
    rounded = round_half_up(value, max_decimals)
    sign = "-" if rounded < 0 else ""
    integer_part, _, fraction = format(abs(rounded), "f").partition(".")
    fraction = fraction.rstrip("0")
    grouped = f"{int(integer_part):,}".replace(",", ".")
    return f"{sign}{grouped},{fraction}" if fraction else f"{sign}{grouped}"


def format_kg(mg: Number) -> str:
    """Mass stored in mg, shown in kg with up to 3 decimals."""
    return format_number(mg_to_kg(mg), KG_DECIMALS)


def format_g(mg: Number) -> str:
    """Mass stored in mg, shown in g with up to 3 decimals."""
    return format_number(mg_to_g(mg), G_DECIMALS)


def format_percent(bp: Number) -> str:
    """Percentage stored in basis points, shown with up to 2 decimals."""
    return format_number(bp_to_percent(bp), PERCENT_DECIMALS)


def format_cm(mm: Number) -> str:
    """Dimension stored in mm, shown in cm with up to 1 decimal."""
    return format_number(mm_to_cm(mm), CM_DECIMALS)


def format_time(value: Number) -> str:
    """Hours, days, minutes or speeds with up to 2 decimals."""
    return format_number(value, TIME_DECIMALS)


def format_int(value: int) -> str:
    """Whole count with thousands separator."""
    return format_number(value, 0)


def format_date(value: date) -> str:
    """DD/MM/YYYY."""
    return value.strftime("%d/%m/%Y")
