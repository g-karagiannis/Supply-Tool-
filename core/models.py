"""Dataclasses for every stored entity, and the snapshot that groups them.

The fields mirror the database columns. Units follow the storage rules:
mass in integer mg, percentages in integer basis points (100% = 10000),
dimensions in integer mm. Cycle times, hours per day and speeds are Decimal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class MaterialCategory(str, Enum):
    """Category of a material; the value is what the database stores."""

    RAW_MATERIAL = "raw_material"
    EXCIPIENT = "excipient"
    PACKAGING_MATERIAL = "packaging_material"


class ItemKind(str, Enum):
    """Whether a stock item is a material (kg, LOTs) or a packaging item (pieces)."""

    MATERIAL = "material"
    PACKAGING = "packaging"


class StepKind(str, Enum):
    """A packaging step either nests units into a package or labels them."""

    LEVEL = "level"
    LABELLING = "labelling"


class StepRole(str, Enum):
    """Role of a packaging level."""

    PRIMARY = "primary"
    BOX = "box"
    CARTON = "carton"
    PALLET = "pallet"
    OTHER = "other"


class PackagingItemType(str, Enum):
    """What a packaging item is. Each type is entered from its own form."""

    PACKAGING = "packaging"
    LABEL = "label"
    CARTON = "carton"
    PALLET = "pallet"


# A stock item is identified by its kind and id, because materials and
# packaging items live in separate tables and their ids can coincide.
ItemKey = tuple[ItemKind, int]


def material_key(material_id: int) -> ItemKey:
    """Key of a material in stock pools."""
    return (ItemKind.MATERIAL, material_id)


def packaging_key(packaging_item_id: int) -> ItemKey:
    """Key of a packaging item in stock pools."""
    return (ItemKind.PACKAGING, packaging_item_id)


@dataclass(frozen=True, slots=True)
class Settings:
    """User settings (section 11.5). Working days are Python weekdays, Monday = 0."""

    yellow_days: int = 120
    red_days: int = 30
    working_days: frozenset[int] = frozenset({0, 1, 2, 3, 4})
    machine_hours_per_day: Decimal = Decimal("8")
    default_transit_days: int = 5
    packaging_hours_per_day: Decimal = Decimal("8")
    packaging_utilization_bp: int = 10_000


@dataclass(frozen=True, slots=True)
class Material:
    id: int
    code: str
    name: str
    category: MaterialCategory
    description: str | None = None
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


@dataclass(frozen=True, slots=True)
class MaterialLot:
    id: int
    material_id: int
    lot_number: str
    quantity_mg: int
    expiry_date: date


@dataclass(frozen=True, slots=True)
class PackagingItem:
    id: int
    code: str
    name: str
    quantity_pcs: int
    description: str | None = None
    length_mm: int | None = None
    width_mm: int | None = None
    height_mm: int | None = None
    unit_weight_mg: int | None = None
    deleted_at: datetime | None = None
    item_type: PackagingItemType = PackagingItemType.PACKAGING
    outer_length_mm: int | None = None
    outer_width_mm: int | None = None
    outer_height_mm: int | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def dimensions_mm(self) -> tuple[int, int, int] | None:
        """(length, width, height) in mm, or None if not declared.

        For a carton these are its inner dimensions, where boxes go.
        """
        if self.length_mm is None or self.width_mm is None or self.height_mm is None:
            return None
        return (self.length_mm, self.width_mm, self.height_mm)

    @property
    def outer_dimensions_mm(self) -> tuple[int, int, int] | None:
        """Outer dimensions in mm: a carton on a pallet, or a pallet's base and maximum load height."""
        if self.outer_length_mm is None or self.outer_width_mm is None or self.outer_height_mm is None:
            return None
        return (self.outer_length_mm, self.outer_width_mm, self.outer_height_mm)


@dataclass(frozen=True, slots=True)
class PackagingItemComponent:
    packaging_item_id: int
    material_id: int
    percent_bp: int


@dataclass(frozen=True, slots=True)
class Product:
    id: int
    name: str
    unit_weight_mg: int | None = None


@dataclass(frozen=True, slots=True)
class RecipeLine:
    product_id: int
    material_id: int
    percent_bp: int


@dataclass(frozen=True, slots=True)
class Machine:
    id: int
    name: str
    batch_size_mg: int
    cycle_time_min: Decimal
    utilization_bp: int
    hours_per_day: Decimal
    max_batch_mg: int | None = None
    min_cycle_time_min: Decimal | None = None
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


@dataclass(frozen=True, slots=True)
class Order:
    id: int
    name: str
    product_id: int
    quantity_mg: int
    unit_weight_mg: int | None
    destination: str
    delivery_date: date
    transit_days: int
    sequence: int
    created_at: datetime
    cancelled_at: datetime | None = None

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled_at is not None


@dataclass(frozen=True, slots=True)
class OrderRecipeLine:
    order_id: int
    material_id: int
    percent_bp: int


@dataclass(frozen=True, slots=True)
class OrderAssignment:
    id: int
    order_id: int
    machine_id: int
    quantity_mg: int
    batch_size_mg: int
    cycle_time_min: Decimal
    defect_bp: int = 0
    start_date: date | None = None
    completed_at: datetime | None = None
    actual_pieces: int | None = None

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None


@dataclass(frozen=True, slots=True)
class PackagingPlan:
    order_id: int
    hours_per_day: Decimal
    utilization_bp: int
    saved_at: datetime
    completed_at: datetime | None = None

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None


@dataclass(frozen=True, slots=True)
class PackagingStep:
    id: int
    order_id: int
    position: int
    kind: StepKind
    packaging_item_id: int
    role: StepRole | None = None
    units_per: int | None = None
    comes_ready: bool = False
    speed_per_min: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PackagingStepExtra:
    step_id: int
    packaging_item_id: int
    quantity_per_unit: int


@dataclass(frozen=True, slots=True)
class ShelfLine:
    id: int
    order_id: int
    boxes: int
    pieces_per_box: int
    box_item_id: int
    created_at: datetime
    boxes_per_carton: int | None = None
    carton_item_id: int | None = None
    deleted_at: datetime | None = None
    cartons_per_pallet: int | None = None
    pallet_item_id: int | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


@dataclass(frozen=True, slots=True)
class ShelfTransfer:
    id: int
    from_line_id: int
    to_line_id: int
    boxes: int
    transferred_on: date


@dataclass(frozen=True, slots=True)
class Receipt:
    id: int
    kind: ItemKind
    quantity: int
    receipt_date: date
    material_id: int | None = None
    packaging_item_id: int | None = None
    received_at: datetime | None = None
    received_quantity: int | None = None
    lot_id: int | None = None

    @property
    def item_key(self) -> ItemKey:
        """The stock item this receipt brings in."""
        if self.kind is ItemKind.MATERIAL:
            assert self.material_id is not None
            return material_key(self.material_id)
        assert self.packaging_item_id is not None
        return packaging_key(self.packaging_item_id)

    @property
    def is_received(self) -> bool:
        return self.received_at is not None


@dataclass(frozen=True, slots=True)
class Shipment:
    id: int
    shelf_line_id: int
    boxes: int
    completion_date: date | None = None
    shipment_date: date | None = None
    shipped_at: datetime | None = None

    @property
    def is_shipped(self) -> bool:
        return self.shipped_at is not None


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    id: int
    created_at: datetime
    action_code: str
    description: str
    changes_json: str
    undone_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Everything stored, as loaded in one read. The only input of compute_state()."""

    today: date
    settings: Settings = field(default_factory=Settings)
    materials: tuple[Material, ...] = ()
    lots: tuple[MaterialLot, ...] = ()
    packaging_items: tuple[PackagingItem, ...] = ()
    packaging_components: tuple[PackagingItemComponent, ...] = ()
    products: tuple[Product, ...] = ()
    recipe_lines: tuple[RecipeLine, ...] = ()
    machines: tuple[Machine, ...] = ()
    orders: tuple[Order, ...] = ()
    order_recipe_lines: tuple[OrderRecipeLine, ...] = ()
    assignments: tuple[OrderAssignment, ...] = ()
    packaging_plans: tuple[PackagingPlan, ...] = ()
    packaging_steps: tuple[PackagingStep, ...] = ()
    packaging_step_extras: tuple[PackagingStepExtra, ...] = ()
    shelf_lines: tuple[ShelfLine, ...] = ()
    shelf_transfers: tuple[ShelfTransfer, ...] = ()
    receipts: tuple[Receipt, ...] = ()
    shipments: tuple[Shipment, ...] = ()
    last_history_id: int | None = None
