"""Unit conversions and the Greek number format of section 11.6."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from core import units


@pytest.mark.parametrize("text, expected", [
    ("1,5", Decimal("1.5")),
    ("1.5", Decimal("1.5")),
    (" 200 ", Decimal("200")),
    (",5", Decimal("0.5")),
    ("0,125", Decimal("0.125")),
])
def test_parse_accepts_comma_or_dot(text: str, expected: Decimal) -> None:
    assert units.parse_decimal(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "1.000,5", "1.000.000", "1e5", "1,2,3", "nan"])
def test_parse_rejects_invalid(text: str) -> None:
    with pytest.raises(units.UnitError):
        units.parse_decimal(text)


def test_exact_conversions() -> None:
    assert units.kg_to_mg(Decimal("128.332")) == 128_332_000
    assert units.g_to_mg(Decimal("0.5")) == 500
    assert units.percent_to_bp(Decimal("12.5")) == 1250
    assert units.cm_to_mm(Decimal("10.5")) == 105


@pytest.mark.parametrize("convert, value", [
    (units.percent_to_bp, Decimal("33.333")),
    (units.cm_to_mm, Decimal("1.25")),
    (units.g_to_mg, Decimal("0.0005")),
])
def test_conversion_rejects_extra_decimals(convert, value: Decimal) -> None:
    with pytest.raises(units.UnitError):
        convert(value)


def test_requirement_rounds_up_to_whole_mg() -> None:
    assert units.apply_bp_ceil(150_000_000, 3333) == 49_995_000
    assert units.apply_bp_ceil(1, 3333) == 1
    assert units.apply_bp_ceil(0, 5000) == 0


@pytest.mark.parametrize("value, decimals, expected", [
    (16041, 0, "16.041"),
    (Decimal("128.332"), 3, "128,332"),
    (Decimal("2.50"), 2, "2,5"),
    (Decimal("4000.000"), 3, "4.000"),
    (Decimal("3.1454"), 2, "3,15"),
    (Decimal("0.655"), 2, "0,66"),
    (Decimal("-20"), 2, "-20"),
    (Decimal("1234567.5"), 1, "1.234.567,5"),
    (0, 2, "0"),
])
def test_format_number(value, decimals: int, expected: str) -> None:
    assert units.format_number(value, decimals) == expected


def test_format_helpers() -> None:
    assert units.format_kg(4_000_000_000) == "4.000"
    assert units.format_kg(128_332_000) == "128,332"
    assert units.format_g(500) == "0,5"
    assert units.format_percent(9600) == "96"
    assert units.format_percent(1250) == "12,5"
    assert units.format_cm(105) == "10,5"
    assert units.format_date(date(2026, 10, 5)) == "05/10/2026"


@pytest.mark.parametrize("text, expected", [
    ("385000", 385_000),
    ("385.000", 385_000),
    ("1.000.000", 1_000_000),
    ("16.041", 16_041),
    ("12", 12),
    ("12,0", 12),
])
def test_parse_whole_reads_dots_as_thousands(text: str, expected: int) -> None:
    assert units.parse_whole(text) == expected


@pytest.mark.parametrize("text", ["12,5", "1.5", "1.0001", "abc", ""])
def test_parse_whole_rejects_fractions_and_text(text: str) -> None:
    with pytest.raises(units.UnitError):
        units.parse_whole(text)
