"""Producible quantity of a product and its limiting material (section 4.3)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from core.units import BP_FULL, apply_bp_ceil, floor_int


@dataclass(frozen=True, slots=True)
class MaterialUse:
    """One recipe line of the availability table."""

    material_id: int
    percent_bp: int
    available_mg: int
    enough_for_mg: Decimal
    consumed_mg: int
    leftover_mg: int
    is_limiting: bool


@dataclass(frozen=True, slots=True)
class ProductAvailability:
    """How much of a product today's available materials allow."""

    lines: tuple[MaterialUse, ...]
    producible_mg: int
    limiting_material_id: int
    pieces: int | None


def recipe_total_bp(percents_bp: Iterable[int]) -> int:
    """Sum of recipe or breakdown percentages, to compare against 100% (10000)."""
    return sum(percents_bp)


def is_complete_recipe(percents_bp: Iterable[int]) -> bool:
    """True when the percentages add up to exactly 100%."""
    return recipe_total_bp(percents_bp) == BP_FULL


def product_availability(
    recipe: Sequence[tuple[int, int]],
    available_mg: Mapping[int, int],
    unit_weight_mg: int | None,
) -> ProductAvailability | None:
    """Compute the availability table for a recipe of (material_id, percent_bp) lines.

    enough_for(i) = available(i) / percent(i); the minimum decides. The result is
    rounded down to a whole mg, so consumption never exceeds what is available.
    Returns None for an empty recipe.
    """
    if not recipe:
        return None
    enough = [
        (material_id, bp, available_mg.get(material_id, 0),
         Decimal(available_mg.get(material_id, 0)) * BP_FULL / bp)
        for material_id, bp in recipe
    ]
    limiting_id, _, _, limiting_enough = min(enough, key=lambda row: row[3])
    producible = floor_int(limiting_enough)
    lines = []
    for material_id, bp, available, enough_for in enough:
        consumed = apply_bp_ceil(producible, bp)
        lines.append(
            MaterialUse(
                material_id=material_id,
                percent_bp=bp,
                available_mg=available,
                enough_for_mg=enough_for,
                consumed_mg=consumed,
                leftover_mg=available - consumed,
                is_limiting=material_id == limiting_id,
            )
        )
    pieces = producible // unit_weight_mg if unit_weight_mg else None
    return ProductAvailability(
        lines=tuple(lines),
        producible_mg=producible,
        limiting_material_id=limiting_id,
        pieces=pieces,
    )
