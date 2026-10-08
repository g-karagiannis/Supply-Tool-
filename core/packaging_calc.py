"""Packaging levels, requirements, carton and pallet fit, and time (section 4.8).

A packaging plan is an ordered list of at most ten steps. A level puts units
of the previous level into a package; a labelling step sticks one label on
every unit of the nearest level before it. Only whole packages count, except
pallets: the last pallet may be partly loaded, so pallets round up. Leftovers
are shown but not tracked as stock.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from itertools import permutations

from core.models import ItemKey, StepKind, StepRole, material_key, packaging_key
from core.units import BP_FULL

MINUTES_PER_HOUR = 60
MAX_STEPS = 10


@dataclass(frozen=True, slots=True)
class StepInput:
    """One packaging step, with the facts of its packaging item resolved.

    item_components are (material_id, percent_bp); extras are
    (packaging_item_id, quantity_per_unit).
    """

    position: int
    kind: StepKind
    item_id: int
    role: StepRole | None = None
    units_per: int | None = None
    comes_ready: bool = False
    speed_per_min: Decimal | None = None
    item_unit_weight_mg: int | None = None
    item_components: tuple[tuple[int, int], ...] = ()
    extras: tuple[tuple[int, int], ...] = ()


class PlanIssue(str, Enum):
    NO_STEPS = "no_steps"
    LABELLING_BEFORE_LEVEL = "labelling_before_level"
    LEVEL_WITHOUT_ROLE = "level_without_role"
    LEVEL_WITHOUT_CONTENTS = "level_without_contents"
    BOX_COUNT = "box_count"
    CARTON_BEFORE_BOX = "carton_before_box"
    MULTIPLE_CARTONS = "multiple_cartons"
    COMPONENTS_WITHOUT_WEIGHT = "components_without_weight"
    NON_POSITIVE_SPEED = "non_positive_speed"
    NON_POSITIVE_EXTRA = "non_positive_extra"
    TOO_MANY_STEPS = "too_many_steps"
    PALLET_WITHOUT_CARTON = "pallet_without_carton"
    MULTIPLE_PALLETS = "multiple_pallets"
    LEVEL_AFTER_PALLET = "level_after_pallet"


class PlanError(ValueError):
    """Raised when a plan breaks the structure rules of section 9.2."""

    def __init__(self, issues: Sequence[PlanIssue]) -> None:
        super().__init__(", ".join(issue.value for issue in issues))
        self.issues = tuple(issues)


def validate_plan(steps: Sequence[StepInput]) -> tuple[PlanIssue, ...]:
    """Return every structure problem of a plan, or an empty tuple if it is valid."""
    if not steps:
        return (PlanIssue.NO_STEPS,)
    ordered = sorted(steps, key=lambda s: s.position)
    issues: list[PlanIssue] = []

    def add(issue: PlanIssue) -> None:
        if issue not in issues:
            issues.append(issue)

    if len(ordered) > MAX_STEPS:
        add(PlanIssue.TOO_MANY_STEPS)
    seen_level = False

    def positions(role: StepRole) -> list[int]:
        return [s.position for s in ordered if s.kind is StepKind.LEVEL and s.role is role]

    box_positions = positions(StepRole.BOX)
    carton_positions = positions(StepRole.CARTON)
    pallet_positions = positions(StepRole.PALLET)
    for step in ordered:
        if step.kind is StepKind.LABELLING:
            if not seen_level:
                add(PlanIssue.LABELLING_BEFORE_LEVEL)
        else:
            seen_level = True
            if step.role is None:
                add(PlanIssue.LEVEL_WITHOUT_ROLE)
            if step.units_per is None or step.units_per <= 0:
                add(PlanIssue.LEVEL_WITHOUT_CONTENTS)
            if not step.comes_ready and step.item_components and not step.item_unit_weight_mg:
                add(PlanIssue.COMPONENTS_WITHOUT_WEIGHT)
        if step.speed_per_min is not None and step.speed_per_min <= 0:
            add(PlanIssue.NON_POSITIVE_SPEED)
        if any(quantity <= 0 for _, quantity in step.extras):
            add(PlanIssue.NON_POSITIVE_EXTRA)
    if len(box_positions) != 1:
        add(PlanIssue.BOX_COUNT)
    if len(carton_positions) > 1:
        add(PlanIssue.MULTIPLE_CARTONS)
    if box_positions and any(position < box_positions[0] for position in carton_positions):
        add(PlanIssue.CARTON_BEFORE_BOX)
    if len(pallet_positions) > 1:
        add(PlanIssue.MULTIPLE_PALLETS)
    if pallet_positions and not (carton_positions and carton_positions[0] < pallet_positions[0]):
        add(PlanIssue.PALLET_WITHOUT_CARTON)
    if pallet_positions and any(s.kind is StepKind.LEVEL and s.position > pallet_positions[0] for s in ordered):
        add(PlanIssue.LEVEL_AFTER_PALLET)
    return tuple(issues)


@dataclass(frozen=True, slots=True)
class StepResult:
    position: int
    kind: StepKind
    role: StepRole | None
    item_id: int
    units: int
    leftover: int | None
    net_minutes: Decimal | None
    hours: Decimal | None
    # For a pallet: the cartons on the last, partly loaded pallet; None when all are full.
    last_unit_contents: int | None = None


@dataclass(frozen=True, slots=True)
class PackagingResult:
    pieces: int
    steps: tuple[StepResult, ...]
    requirements: dict[ItemKey, int]
    pieces_per_box: int
    boxes: int
    boxes_per_carton: int | None
    cartons: int | None
    sequential_days: Decimal
    inline_days: Decimal
    cartons_per_pallet: int | None = None
    pallets: int | None = None

    @property
    def packaging_days(self) -> Decimal:
        """The longer of the two times, used for every estimate."""
        return self.sequential_days


def _add(requirements: dict[ItemKey, int], key: ItemKey, quantity: int) -> None:
    requirements[key] = requirements.get(key, 0) + quantity


Row = tuple[StepInput, int, int | None, int | None]


def _walk(pieces: int, ordered: Sequence[StepInput]) -> tuple[list[Row], dict[ItemKey, int]]:
    """Units, leftover and last-pallet contents per step, and the requirements they create."""
    requirements: dict[ItemKey, int] = {}
    rows: list[Row] = []
    previous_units = pieces
    for step in ordered:
        last_contents: int | None = None
        if step.kind is StepKind.LEVEL and step.role is StepRole.PALLET:
            # Pallets round up: a partly loaded last pallet is still a pallet.
            assert step.units_per is not None
            units = -(-previous_units // step.units_per)
            leftover: int | None = None
            last_contents = (previous_units % step.units_per) or None
            previous_units = units
            _add(requirements, packaging_key(step.item_id), units)
        elif step.kind is StepKind.LEVEL:
            assert step.units_per is not None
            units = previous_units // step.units_per
            leftover = previous_units - units * step.units_per
            previous_units = units
            if step.comes_ready or not step.item_components:
                _add(requirements, packaging_key(step.item_id), units)
            else:
                assert step.item_unit_weight_mg is not None
                for material_id, percent_bp in step.item_components:
                    mass = -(-units * step.item_unit_weight_mg * percent_bp // BP_FULL)
                    _add(requirements, material_key(material_id), mass)
        else:
            units = previous_units
            leftover = None
            _add(requirements, packaging_key(step.item_id), units)
        for extra_item_id, per_unit in step.extras:
            _add(requirements, packaging_key(extra_item_id), per_unit * units)
        rows.append((step, units, leftover, last_contents))
    return rows, requirements


def _structure(ordered: Sequence[StepInput]) -> tuple[int, int | None, int | None]:
    """Pieces per box, boxes per carton and cartons per pallet, from the "contains" of each level."""
    pieces_per_box = 1
    boxes_per_carton: int | None = None
    cartons_per_pallet: int | None = None
    after_box = after_carton = False
    running = 1
    for step in ordered:
        if step.kind is not StepKind.LEVEL:
            continue
        assert step.units_per is not None
        if not after_box:
            pieces_per_box *= step.units_per
            if step.role is StepRole.BOX:
                after_box = True
        else:
            running *= step.units_per
            if step.role is StepRole.CARTON and not after_carton:
                boxes_per_carton = running
                after_carton = True
                running = 1
            elif step.role is StepRole.PALLET and after_carton:
                cartons_per_pallet = running
    return pieces_per_box, boxes_per_carton, cartons_per_pallet


def _parallel_positions(ordered: Sequence[StepInput]) -> set[int]:
    """The product packaging level and the labelling steps right after it.

    Labelling of the product packaging runs at the same time as that packaging,
    so these steps count with the longest of their times; all other steps
    follow one another.
    """
    for index, step in enumerate(ordered):
        if step.kind is StepKind.LEVEL and step.role is StepRole.PRIMARY:
            group = {step.position}
            for following in ordered[index + 1:]:
                if following.kind is not StepKind.LABELLING:
                    break
                group.add(following.position)
            return group
    return set()


def compute_packaging(
    pieces: int,
    steps: Sequence[StepInput],
    hours_per_day: Decimal,
    utilization_bp: int,
) -> PackagingResult:
    """Units, leftovers, requirements and time of a packaging plan for a number of pieces."""
    issues = validate_plan(steps)
    if issues:
        raise PlanError(issues)
    if hours_per_day <= 0 or not 0 < utilization_bp <= BP_FULL:
        raise ValueError("Packaging hours per day and utilization must be positive")
    ordered = sorted(steps, key=lambda s: s.position)
    rows, requirements = _walk(pieces, ordered)

    results = []
    timed_hours: list[Decimal] = []
    parallel = _parallel_positions(ordered)
    parallel_hours = Decimal(0)
    sequential_hours = Decimal(0)
    boxes = 0
    cartons: int | None = None
    pallets: int | None = None
    for step, units, leftover, last_contents in rows:
        net_minutes = hours = None
        if not step.comes_ready and step.speed_per_min is not None:
            net_minutes = Decimal(units) / step.speed_per_min
            hours = Decimal(units) * BP_FULL / (step.speed_per_min * MINUTES_PER_HOUR * utilization_bp)
            timed_hours.append(hours)
            if step.position in parallel:
                parallel_hours = max(parallel_hours, hours)
            else:
                sequential_hours += hours
        if step.kind is StepKind.LEVEL and step.role is StepRole.BOX:
            boxes = units
        if step.kind is StepKind.LEVEL and step.role is StepRole.CARTON:
            cartons = units
        if step.kind is StepKind.LEVEL and step.role is StepRole.PALLET:
            pallets = units
        results.append(
            StepResult(step.position, step.kind, step.role, step.item_id, units, leftover, net_minutes, hours,
                       last_contents)
        )
    pieces_per_box, boxes_per_carton, cartons_per_pallet = _structure(ordered)
    sequential = (sequential_hours + parallel_hours) / hours_per_day
    inline = max(timed_hours, default=Decimal(0)) / hours_per_day
    return PackagingResult(
        pieces=pieces,
        steps=tuple(results),
        requirements=requirements,
        pieces_per_box=pieces_per_box,
        boxes=boxes,
        boxes_per_carton=boxes_per_carton,
        cartons=cartons,
        sequential_days=sequential,
        inline_days=inline,
        cartons_per_pallet=cartons_per_pallet,
        pallets=pallets,
    )


def packable_boxes(
    steps: Sequence[StepInput],
    boxes: int,
    available: Mapping[ItemKey, int],
) -> tuple[int, tuple[ItemKey, ...]]:
    """How many boxes the available stock allows, and which items limit it.

    Searches the largest box count b <= boxes whose requirements, computed for
    b x pieces-per-box pieces, are all covered. The limiting items are those
    that would fall short at b + 1. Returns (boxes, ()) when nothing is short.
    """
    ordered = sorted(steps, key=lambda s: s.position)
    pieces_per_box = _structure(ordered)[0]

    def requirements_for(box_count: int) -> dict[ItemKey, int]:
        return _walk(box_count * pieces_per_box, ordered)[1]

    def fits(box_count: int) -> bool:
        return all(q <= available.get(k, 0) for k, q in requirements_for(box_count).items())

    if fits(boxes):
        return boxes, ()
    low, high = 0, boxes
    while low < high:
        middle = (low + high + 1) // 2
        if fits(middle):
            low = middle
        else:
            high = middle - 1
    over = requirements_for(low + 1)
    limiting = tuple(key for key, quantity in over.items() if quantity > available.get(key, 0))
    return low, limiting


@dataclass(frozen=True, slots=True)
class CartonFit:
    """One way of placing boxes in a carton, or cartons on a pallet. Dimensions in mm."""

    orientation: tuple[int, int, int]
    per_axis: tuple[int, int, int]
    boxes: int


def carton_fits(box_mm: tuple[int, int, int], carton_inner_mm: tuple[int, int, int]) -> tuple[CartonFit, ...]:
    """Every distinct orientation of the box in the carton, at most six.

    count = floor(L / a) x floor(W / b) x floor(H / c). Volume division is never used.
    The same rule places cartons (outer dimensions) on a pallet (base and maximum
    load height).
    """
    length, width, height = carton_inner_mm
    fits = []
    seen: set[tuple[int, int, int]] = set()
    for orientation in permutations(box_mm):
        if orientation in seen:
            continue
        seen.add(orientation)
        a, b, c = orientation
        per_axis = (length // a, width // b, height // c)
        fits.append(CartonFit(orientation, per_axis, per_axis[0] * per_axis[1] * per_axis[2]))
    return tuple(fits)


def best_carton_fit(fits: Sequence[CartonFit]) -> CartonFit | None:
    """The default choice: the most boxes, the first such orientation on a tie."""
    return max(fits, key=lambda fit: fit.boxes) if fits else None
