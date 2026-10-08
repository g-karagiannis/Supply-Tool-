"""Section 12.6: packaging levels, requirements, time and carton fit."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from core.models import StepKind, StepRole, material_key, packaging_key
from core.packaging_calc import (
    PlanError,
    PlanIssue,
    StepInput,
    best_carton_fit,
    carton_fits,
    compute_packaging,
    packable_boxes,
    validate_plan,
)
from core.units import g_to_mg, round_half_up
from factories import BLISTER, BOX, CARTON, FILM, FOIL, LABEL, LEAFLET, kg


def steps(blister_ready: bool = False) -> list[StepInput]:
    return [
        StepInput(1, StepKind.LEVEL, BLISTER, StepRole.PRIMARY, 12, blister_ready, Decimal(200),
                  g_to_mg(5), ((FILM, 8000), (FOIL, 2000))),
        StepInput(2, StepKind.LEVEL, BOX, StepRole.BOX, 2, True, None, extras=((LEAFLET, 1),)),
        StepInput(3, StepKind.LABELLING, LABEL, speed_per_min=Decimal(60)),
        StepInput(4, StepKind.LEVEL, CARTON, StepRole.CARTON, 160, True),
    ]


def pack(pieces: int, plan: list[StepInput] | None = None):
    return compute_packaging(pieces, plan or steps(), Decimal(8), 8500)


def test_units_and_leftovers() -> None:
    result = pack(385_000)
    assert [(s.units, s.leftover) for s in result.steps] == [
        (32_083, 4), (16_041, 1), (16_041, None), (100, 41),
    ]
    assert (result.boxes, result.cartons, result.pieces_per_box, result.boxes_per_carton) == (16_041, 100, 24, 160)


def test_expected_pieces() -> None:
    result = pack(388_000)
    assert result.steps[0].units == 32_333
    assert result.boxes == 16_166


def test_material_requirements_of_blister_made_in_house() -> None:
    requirements = pack(385_000).requirements
    assert requirements[material_key(FILM)] == kg("128.332")
    assert requirements[material_key(FOIL)] == kg("32.083")
    assert packaging_key(BLISTER) not in requirements


def test_blister_that_comes_ready() -> None:
    requirements = pack(385_000, steps(blister_ready=True)).requirements
    assert requirements[packaging_key(BLISTER)] == 32_083
    assert material_key(FILM) not in requirements and material_key(FOIL) not in requirements


def test_packaging_item_requirements() -> None:
    requirements = pack(385_000).requirements
    assert requirements[packaging_key(BOX)] == 16_041
    assert requirements[packaging_key(LEAFLET)] == 16_041
    assert requirements[packaging_key(LABEL)] == 16_041
    assert requirements[packaging_key(CARTON)] == 100


def test_time() -> None:
    result = pack(385_000)
    hours = [round_half_up(s.hours, 2) if s.hours is not None else None for s in result.steps]
    assert hours == [Decimal("3.15"), None, Decimal("5.24"), None]
    net = [round_half_up(s.net_minutes / 60, 2) if s.net_minutes is not None else None for s in result.steps]
    assert net == [Decimal("2.67"), None, Decimal("4.46"), None]
    assert round_half_up(result.sequential_days, 2) == Decimal("1.05")
    assert round_half_up(result.inline_days, 2) == Decimal("0.66")
    assert result.packaging_days == result.sequential_days


def test_ticked_step_is_not_timed_even_with_speed() -> None:
    plan = steps()
    plan[1] = replace(plan[1], speed_per_min=Decimal(100))
    assert pack(385_000, plan).steps[1].hours is None


def test_no_timed_steps_gives_zero_days() -> None:
    plan = [replace(s, speed_per_min=None) for s in steps()]
    result = pack(385_000, plan)
    assert result.sequential_days == 0 and result.inline_days == 0


def test_carton_fit() -> None:
    fits = carton_fits((100, 60, 30), (400, 300, 250))
    assert [fit.boxes for fit in fits] == [160, 160, 144, 120, 156, 130]
    assert [fit.per_axis for fit in fits][4] == (13, 3, 4)
    best = best_carton_fit(fits)
    assert best is not None and best.boxes == 160 and best.orientation == (100, 60, 30)


def test_carton_fit_lists_distinct_orientations_only() -> None:
    assert len(carton_fits((50, 50, 50), (400, 300, 250))) == 1
    assert len(carton_fits((50, 50, 30), (400, 300, 250))) == 3


def test_limiting_packaging() -> None:
    available = {
        material_key(FILM): kg(150), material_key(FOIL): kg(40),
        packaging_key(BOX): 20_000, packaging_key(LEAFLET): 20_000,
        packaging_key(LABEL): 15_000, packaging_key(CARTON): 150,
    }
    boxes, limiting = packable_boxes(steps(), 16_041, available)
    assert boxes == 15_000
    assert limiting == (packaging_key(LABEL),)


def test_nothing_limits_when_covered() -> None:
    available = {key: 10**12 for key in pack(385_000).requirements}
    assert packable_boxes(steps(), 16_041, available) == (16_041, ())


@pytest.mark.parametrize("plan, issue", [
    ([], PlanIssue.NO_STEPS),
    ([StepInput(1, StepKind.LABELLING, LABEL)] + steps()[:2], PlanIssue.LABELLING_BEFORE_LEVEL),
    ([steps()[0]], PlanIssue.BOX_COUNT),
    (steps() + [StepInput(5, StepKind.LEVEL, BOX, StepRole.BOX, 1, True)], PlanIssue.BOX_COUNT),
    ([steps()[0], replace(steps()[3], position=2), replace(steps()[1], position=3)], PlanIssue.CARTON_BEFORE_BOX),
    ([replace(steps()[0], item_unit_weight_mg=None)] + steps()[1:], PlanIssue.COMPONENTS_WITHOUT_WEIGHT),
    ([replace(steps()[0], units_per=None)] + steps()[1:], PlanIssue.LEVEL_WITHOUT_CONTENTS),
])
def test_structure_rules(plan, issue: PlanIssue) -> None:
    assert issue in validate_plan(plan)
    with pytest.raises(PlanError):
        compute_packaging(1000, plan, Decimal(8), 10_000)


def test_valid_plan_has_no_issues() -> None:
    assert validate_plan(steps()) == ()
