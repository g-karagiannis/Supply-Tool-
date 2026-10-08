"""Section 12.2: available product quantity and limiting material."""

from __future__ import annotations

import pytest

from core.product_calc import is_complete_recipe, product_availability, recipe_total_bp
from core.units import g_to_mg
from factories import kg


@pytest.mark.parametrize("lines, producible, leftovers", [
    ([("4800", 96), ("120", 3), ("60", 1)], "4000", ["960", "0", "20"]),
    ([("300", 60), ("120", 30), ("50", 10)], "400", ["60", "0", "10"]),
    ([("150", 50), ("100", 40), ("60", 10)], "250", ["25", "0", "35"]),
])
def test_section_12_2(lines, producible: str, leftovers: list[str]) -> None:
    recipe = [(i, percent * 100) for i, (_, percent) in enumerate(lines, start=1)]
    available = {i: kg(quantity) for i, (quantity, _) in enumerate(lines, start=1)}
    result = product_availability(recipe, available, unit_weight_mg=None)
    assert result is not None
    assert result.producible_mg == kg(producible)
    assert result.limiting_material_id == 2
    assert [line.leftover_mg for line in result.lines] == [kg(v) for v in leftovers]
    assert [line.is_limiting for line in result.lines] == [False, True, False]


def test_not_the_sum_of_materials() -> None:
    result = product_availability([(1, 5000), (2, 5000)], {1: kg(100), 2: kg(10)}, None)
    assert result is not None
    assert result.producible_mg == kg(20)


def test_section_4_3_table() -> None:
    result = product_availability([(1, 9600), (2, 300), (3, 100)], {1: kg(4800), 2: kg(120), 3: kg(60)}, None)
    assert result is not None
    assert [line.enough_for_mg for line in result.lines] == [kg(5000), kg(4000), kg(6000)]
    assert [line.consumed_mg for line in result.lines] == [kg(3840), kg(120), kg(40)]


def test_product_sheet_pieces() -> None:
    result = product_availability([(1, 5000), (2, 4000), (3, 1000)], {1: kg(150), 2: kg(100), 3: kg(60)}, g_to_mg(0.5))
    assert result is not None
    assert result.pieces == 500_000


def test_consumption_never_exceeds_available() -> None:
    result = product_availability([(1, 3333), (2, 6667)], {1: 1_000_003, 2: 7_777_777}, None)
    assert result is not None
    assert all(line.leftover_mg >= 0 for line in result.lines)


def test_missing_material_gives_zero() -> None:
    result = product_availability([(1, 5000), (2, 5000)], {1: kg(100)}, None)
    assert result is not None
    assert result.producible_mg == 0
    assert result.limiting_material_id == 2


def test_empty_recipe() -> None:
    assert product_availability([], {}, None) is None


def test_recipe_total() -> None:
    assert recipe_total_bp([5000, 4000, 700]) == 9700
    assert is_complete_recipe([5000, 4000, 1000])
    assert not is_complete_recipe([5000, 4000, 700])
