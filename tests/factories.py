"""Small builders for core test data, in the user units of the specification."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from core.models import (
    Machine,
    Material,
    MaterialCategory,
    MaterialLot,
    Order,
    OrderAssignment,
    OrderRecipeLine,
    PackagingItem,
    PackagingItemComponent,
    PackagingPlan,
    PackagingStep,
    PackagingStepExtra,
    StepKind,
    StepRole,
)
from core.units import g_to_mg, kg_to_mg, percent_to_bp

# Monday 05/10/2026, the reference date of every example in section 12.
TODAY = date(2026, 10, 5)
CREATED = datetime(2026, 10, 1, 9, 0)


def kg(value: str | int) -> int:
    """kg as written in the specification (e.g. "128.332") to mg."""
    return kg_to_mg(Decimal(str(value)))


def material(material_id: int, name: str = "", category: MaterialCategory = MaterialCategory.EXCIPIENT) -> Material:
    return Material(material_id, f"M-{material_id:03d}", name or f"Material {material_id}", category)


def lot(lot_id: int, material_id: int, quantity_kg: str | int, expiry: date = date(2027, 6, 30)) -> MaterialLot:
    return MaterialLot(lot_id, material_id, f"L-{lot_id:03d}", kg(quantity_kg), expiry)


def order(
    order_id: int,
    quantity_kg: str | int,
    sequence: int,
    product_id: int = 1,
    delivery: date = date(2026, 10, 26),
    transit_days: int = 5,
    unit_weight_g: str = "0.5",
    cancelled: bool = False,
) -> Order:
    return Order(
        id=order_id,
        name=f"ORD-{order_id:03d}",
        product_id=product_id,
        quantity_mg=kg(quantity_kg),
        unit_weight_mg=g_to_mg(Decimal(unit_weight_g)),
        destination="Destination",
        delivery_date=delivery,
        transit_days=transit_days,
        sequence=sequence,
        created_at=CREATED,
        cancelled_at=CREATED if cancelled else None,
    )


def recipe(order_id: int, *lines: tuple[int, str | int]) -> tuple[OrderRecipeLine, ...]:
    """Order recipe copy from (material_id, percent) pairs."""
    return tuple(OrderRecipeLine(order_id, m, percent_to_bp(Decimal(str(p)))) for m, p in lines)


def machine(machine_id: int = 1, batch_kg: str = "50", cycle: str = "120", utilization: str = "80", hours: str = "8") -> Machine:
    return Machine(
        id=machine_id,
        name=f"Machine {machine_id}",
        batch_size_mg=kg(batch_kg),
        cycle_time_min=Decimal(cycle),
        utilization_bp=percent_to_bp(Decimal(utilization)),
        hours_per_day=Decimal(hours),
    )


def assignment(
    assignment_id: int,
    order_id: int,
    quantity_kg: str | int,
    machine_id: int = 1,
    batch_kg: str = "50",
    cycle: str = "120",
    defect: str = "3",
    start: date | None = None,
    actual_pieces: int | None = None,
) -> OrderAssignment:
    return OrderAssignment(
        id=assignment_id,
        order_id=order_id,
        machine_id=machine_id,
        quantity_mg=kg(quantity_kg),
        batch_size_mg=kg(batch_kg),
        cycle_time_min=Decimal(cycle),
        defect_bp=percent_to_bp(Decimal(defect)),
        start_date=start,
        completed_at=CREATED if actual_pieces is not None else None,
        actual_pieces=actual_pieces,
    )


# Packaging of section 12.6: blister of 12 (5 g, 80% film, 20% aluminium foil,
# made in house at 200 per minute), box of 2 blisters with 1 leaflet (comes
# ready), box labelling at 60 per minute, carton of 160 boxes (comes ready).
FILM, FOIL = 20, 21
BLISTER, BOX, LEAFLET, LABEL, CARTON = 10, 11, 12, 13, 14


def packaging_items(stock: int = 20_000, cartons: int = 150) -> tuple[PackagingItem, ...]:
    return (
        PackagingItem(BLISTER, "P-010", "Blister", 0, unit_weight_mg=g_to_mg(5)),
        PackagingItem(BOX, "P-011", "Box", stock, length_mm=100, width_mm=60, height_mm=30),
        PackagingItem(LEAFLET, "P-012", "Leaflet", stock),
        PackagingItem(LABEL, "P-013", "Box label", stock),
        PackagingItem(CARTON, "P-014", "Carton", cartons, length_mm=400, width_mm=300, height_mm=250),
    )


def blister_components() -> tuple[PackagingItemComponent, ...]:
    return (
        PackagingItemComponent(BLISTER, FILM, percent_to_bp(80)),
        PackagingItemComponent(BLISTER, FOIL, percent_to_bp(20)),
    )


def packaging_plan(order_id: int, completed: bool = False) -> PackagingPlan:
    return PackagingPlan(order_id, Decimal(8), percent_to_bp(85), CREATED, CREATED if completed else None)


def packaging_steps(order_id: int) -> tuple[tuple[PackagingStep, ...], tuple[PackagingStepExtra, ...]]:
    base = order_id * 10
    steps = (
        PackagingStep(base + 1, order_id, 1, StepKind.LEVEL, BLISTER, StepRole.PRIMARY, 12, False, Decimal(200)),
        PackagingStep(base + 2, order_id, 2, StepKind.LEVEL, BOX, StepRole.BOX, 2, True, None),
        PackagingStep(base + 3, order_id, 3, StepKind.LABELLING, LABEL, None, None, False, Decimal(60)),
        PackagingStep(base + 4, order_id, 4, StepKind.LEVEL, CARTON, StepRole.CARTON, 160, True, None),
    )
    extras = (PackagingStepExtra(base + 2, LEAFLET, 1),)
    return steps, extras
