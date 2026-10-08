"""compute_state(snapshot) -> AppState: every derived value, recomputed from scratch.

Nothing here is stored. Stock quantities, reservations, shortages, statuses,
dates and warnings all come from one pass over the snapshot, so every screen
drawn from the same AppState shows the same numbers.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from core.allocation import Need, OrderDemand, allocate
from core.dates import assignment_end, estimated_arrival, readiness_date, ship_by_date
from core.expiry import ExpiryStatus, LotExpiry, expiry_status, is_expired
from core.models import (
    ItemKey,
    ItemKind,
    MaterialLot,
    Order,
    OrderAssignment,
    OrderRecipeLine,
    PackagingPlan,
    PackagingStep,
    PackagingStepExtra,
    Receipt,
    Snapshot,
    material_key,
    packaging_key,
)
from core.packaging_calc import (
    PackagingResult,
    PlanError,
    PlanIssue,
    StepInput,
    compute_packaging,
    packable_boxes,
)
from core.product_calc import ProductAvailability, product_availability
from core.production_calc import ProductionEstimate, production_estimate
from core.units import apply_bp_ceil


class OrderStatus(str, Enum):
    """Order status of section 4.10, in the order the rules are checked.

    IN_PRODUCTION was added at the user's request (06/10/2026): materials are
    reserved and an assignment has reached its start date without being
    completed.
    """

    CANCELLED = "cancelled"
    SHIPPED = "shipped"
    TRANSFERRED = "transferred"
    ON_SHELF = "on_shelf"
    IN_PACKAGING = "in_packaging"
    IN_PRODUCTION = "in_production"
    READY_FOR_PRODUCTION = "ready_for_production"
    WAITING_MATERIALS = "waiting_materials"


CLOSED_STATUSES = frozenset(
    {OrderStatus.CANCELLED, OrderStatus.SHIPPED, OrderStatus.TRANSFERRED, OrderStatus.ON_SHELF}
)


class OrderFlag(str, Enum):
    NO_MACHINE = "no_machine"
    NO_PACKAGING_PLAN = "no_packaging_plan"
    MISSING_PACKAGING = "missing_packaging"


class PiecesBasis(str, Enum):
    """Which pieces the packaging is computed from (sections 4.8 and 9.1)."""

    EXPECTED = "expected"
    ACTUAL = "actual"
    WITHOUT_DEFECT_RATE = "without_defect_rate"


class WarningCode(str, Enum):
    START_BEFORE_RECEIPT = "start_before_receipt"
    NO_COVERING_RECEIPT = "no_covering_receipt"
    ARRIVAL_AFTER_DELIVERY = "arrival_after_delivery"
    RED_LOT = "red_lot"


@dataclass(frozen=True, slots=True)
class OrderWarning:
    """A warning of section 4.12. Only the fields its message needs are set."""

    code: WarningCode
    item_key: ItemKey | None = None
    lot_id: int | None = None
    day: date | None = None
    other_day: date | None = None
    quantity: int | None = None
    days: int | None = None


class ReceiptStatus(str, Enum):
    EXPECTED = "expected"
    DELAYED = "delayed"
    RECEIVED = "received"


@dataclass(frozen=True, slots=True)
class ExpectedReceipt:
    receipt_id: int
    quantity: int
    receipt_date: date


@dataclass(frozen=True, slots=True)
class StockState:
    """Quantities of one material (mg) or packaging item (pieces), section 4.2."""

    key: ItemKey
    total: int
    expired: int
    reserved: int
    available: int
    expected: tuple[ExpectedReceipt, ...]
    has_components: bool = False

    @property
    def depleted(self) -> bool:
        return self.total == 0


@dataclass(frozen=True, slots=True)
class AssignmentState:
    assignment_id: int
    estimate: ProductionEstimate
    end_date: date | None
    completed: bool


@dataclass(frozen=True, slots=True)
class LotUse:
    """A LOT the order is projected to consume from, in expiry order."""

    lot_id: int
    material_id: int
    quantity_mg: int


@dataclass(frozen=True, slots=True)
class OrderState:
    order_id: int
    status: OrderStatus
    flags: tuple[OrderFlag, ...]
    production_completed: bool
    packaging_completed: bool
    remaining_mg: int
    recipe_lines: tuple[Need, ...]
    recipe_reserved: bool
    assignments: tuple[AssignmentState, ...]
    production_days: Decimal | None
    planned_pieces: int | None
    expected_pieces: int | None
    actual_pieces: int | None
    packaging_pieces: int | None
    pieces_basis: PiecesBasis
    packaging: PackagingResult | None
    packaging_issues: tuple[PlanIssue, ...]
    packaging_lines: tuple[Need, ...]
    packaging_reserved: bool
    packable_boxes: int | None
    packaging_limiting: tuple[ItemKey, ...]
    start_date: date | None
    production_end: date | None
    readiness: date | None
    without_packaging: bool
    arrival: date | None
    ship_by: date
    lot_uses: tuple[LotUse, ...]
    warnings: tuple[OrderWarning, ...]


@dataclass(frozen=True, slots=True)
class ReceiptState:
    receipt_id: int
    status: ReceiptStatus
    delay_days: int


@dataclass(frozen=True, slots=True)
class ShelfLineState:
    line_id: int
    cartons: int | None
    loose_boxes: int
    pending_boxes: int
    free_boxes: int
    transfer_ids: tuple[int, ...]
    depleted: bool
    shipped_out: bool = False
    pallets: int | None = None
    last_pallet_cartons: int | None = None


@dataclass(frozen=True, slots=True)
class ShipmentState:
    shipment_id: int
    shipped: bool
    cartons: int | None
    loose_boxes: int
    pallets: int | None = None
    last_pallet_cartons: int | None = None


@dataclass(frozen=True, slots=True)
class AppState:
    today: date
    materials: dict[int, StockState]
    packaging_items: dict[int, StockState]
    lots: dict[int, LotExpiry]
    products: dict[int, ProductAvailability | None]
    orders: dict[int, OrderState]
    receipts: dict[int, ReceiptState]
    shelf_lines: dict[int, ShelfLineState]
    shipments: dict[int, ShipmentState]
    last_history_id: int | None

    def stock(self, key: ItemKey) -> StockState | None:
        """Stock state by item key."""
        kind, item_id = key
        table = self.materials if kind is ItemKind.MATERIAL else self.packaging_items
        return table.get(item_id)


def cartons_and_loose(boxes: int, boxes_per_carton: int | None) -> tuple[int | None, int]:
    """Full cartons only: floor(boxes / per carton), and the boxes that fill no carton."""
    if not boxes_per_carton:
        return None, boxes
    cartons = boxes // boxes_per_carton
    return cartons, boxes - cartons * boxes_per_carton


def pallets_for(cartons: int | None, cartons_per_pallet: int | None) -> tuple[int | None, int | None]:
    """Pallets needed for full cartons, rounded up, and the cartons on a partly loaded last pallet.

    E.g. 245 cartons at 20 per pallet: 13 pallets, the last with 5 cartons.
    The second value is None when every pallet is full.
    """
    if cartons is None or not cartons_per_pallet:
        return None, None
    pallets = -(-cartons // cartons_per_pallet)
    return pallets, (cartons % cartons_per_pallet) or None


def covering_receipt_date(
    shortage: int,
    pending: Iterable[ExpectedReceipt],
) -> date | None:
    """Date of the last pending receipt needed to cover a shortage, in date order."""
    covered = 0
    for receipt in sorted(pending, key=lambda r: (r.receipt_date, r.receipt_id)):
        covered += receipt.quantity
        if covered >= shortage:
            return receipt.receipt_date
    return None


def _group(items: Iterable, attribute: str) -> dict:
    grouped: dict = defaultdict(list)
    for item in items:
        grouped[getattr(item, attribute)].append(item)
    return grouped


def _step_inputs(snapshot: Snapshot, order_id: int) -> list[StepInput]:
    items = {item.id: item for item in snapshot.packaging_items}
    components = _group(snapshot.packaging_components, "packaging_item_id")
    extras = _group(snapshot.packaging_step_extras, "step_id")
    inputs = []
    for step in snapshot.packaging_steps:
        if step.order_id != order_id:
            continue
        item = items.get(step.packaging_item_id)
        inputs.append(
            StepInput(
                position=step.position,
                kind=step.kind,
                item_id=step.packaging_item_id,
                role=step.role,
                units_per=step.units_per,
                comes_ready=step.comes_ready,
                speed_per_min=step.speed_per_min,
                item_unit_weight_mg=item.unit_weight_mg if item else None,
                item_components=tuple(
                    (c.material_id, c.percent_bp) for c in components.get(step.packaging_item_id, [])
                ),
                extras=tuple((e.packaging_item_id, e.quantity_per_unit) for e in extras.get(step.id, [])),
            )
        )
    return inputs


@dataclass
class _OrderWork:
    """Intermediate per-order results, before reservation."""

    order: Order
    assignments: list[OrderAssignment]
    estimates: list[ProductionEstimate]
    production_completed: bool
    remaining_mg: int
    plan: PackagingPlan | None
    steps: list[StepInput]
    pieces: int | None
    basis: PiecesBasis
    packaging: PackagingResult | None
    packaging_issues: tuple[PlanIssue, ...]

    @property
    def is_open(self) -> bool:
        return not self.order.is_cancelled and not (self.plan is not None and self.plan.is_completed)


def _order_work(snapshot: Snapshot, order: Order, assignments: list[OrderAssignment]) -> _OrderWork:
    machines = {machine.id: machine for machine in snapshot.machines}
    estimates = []
    for assignment in assignments:
        machine = machines[assignment.machine_id]
        estimates.append(
            production_estimate(
                quantity_mg=assignment.quantity_mg,
                batch_size_mg=assignment.batch_size_mg,
                cycle_time_min=assignment.cycle_time_min,
                utilization_bp=machine.utilization_bp,
                hours_per_day=machine.hours_per_day,
                unit_weight_mg=order.unit_weight_mg,
                defect_bp=assignment.defect_bp,
            )
        )
    production_completed = bool(assignments) and all(a.is_completed for a in assignments)
    remaining = order.quantity_mg - sum(a.quantity_mg for a in assignments if a.is_completed)

    if production_completed:
        pieces: int | None = sum(a.actual_pieces or 0 for a in assignments)
        basis = PiecesBasis.ACTUAL
    elif assignments:
        expected = [e.expected_pieces for e in estimates]
        pieces = None if any(p is None for p in expected) else sum(expected)  # type: ignore[arg-type]
        basis = PiecesBasis.EXPECTED
    else:
        pieces = order.quantity_mg // order.unit_weight_mg if order.unit_weight_mg else None
        basis = PiecesBasis.WITHOUT_DEFECT_RATE

    plan = next((p for p in snapshot.packaging_plans if p.order_id == order.id), None)
    steps = _step_inputs(snapshot, order.id) if plan else []
    packaging = None
    issues: tuple[PlanIssue, ...] = ()
    if plan is not None and pieces is not None:
        try:
            packaging = compute_packaging(pieces, steps, plan.hours_per_day, plan.utilization_bp)
        except PlanError as error:
            issues = error.issues
    return _OrderWork(
        order=order,
        assignments=assignments,
        estimates=estimates,
        production_completed=production_completed,
        remaining_mg=remaining,
        plan=plan,
        steps=steps,
        pieces=pieces,
        basis=basis,
        packaging=packaging,
        packaging_issues=issues,
    )


def _project_lot_uses(
    works: list[_OrderWork],
    allocations: dict,
    lots: tuple[MaterialLot, ...],
    today: date,
) -> dict[int, tuple[LotUse, ...]]:
    """Which LOTs each reserved order would consume, nearest expiry first, in sequence order."""
    remaining: dict[int, list[list[int]]] = defaultdict(list)
    for lot in sorted(lots, key=lambda l: (l.expiry_date, l.id)):
        if lot.quantity_mg > 0 and not is_expired(lot.expiry_date, today):
            remaining[lot.material_id].append([lot.id, lot.quantity_mg])

    uses: dict[int, tuple[LotUse, ...]] = {}
    for work in sorted(works, key=lambda w: (w.order.sequence, w.order.id)):
        allocation = allocations.get(work.order.id)
        if allocation is None:
            continue
        lines: list[Need] = []
        if allocation.recipe_reserved:
            lines.extend(allocation.recipe_lines)
        if allocation.packaging_reserved:
            lines.extend(allocation.packaging_lines)
        order_uses = []
        for line in lines:
            kind, material_id = line.key
            if kind is not ItemKind.MATERIAL:
                continue
            needed = line.need
            for entry in remaining[material_id]:
                if needed == 0:
                    break
                take = min(entry[1], needed)
                if take:
                    entry[1] -= take
                    needed -= take
                    order_uses.append(LotUse(entry[0], material_id, take))
        uses[work.order.id] = tuple(order_uses)
    return uses


def compute_state(snapshot: Snapshot) -> AppState:
    """Compute every derived value of the application from the stored data."""
    today = snapshot.today
    settings = snapshot.settings

    lots_by_material = _group(snapshot.lots, "material_id")
    lot_states = {
        lot.id: expiry_status(lot.expiry_date, today, lot.quantity_mg, settings.yellow_days, settings.red_days)
        for lot in snapshot.lots
    }

    # Pools before reservation: materials exclude expired LOTs; packaging items are pieces.
    totals: dict[ItemKey, int] = {}
    expired: dict[ItemKey, int] = {}
    for material in snapshot.materials:
        key = material_key(material.id)
        material_lots = lots_by_material.get(material.id, [])
        totals[key] = sum(lot.quantity_mg for lot in material_lots)
        expired[key] = sum(lot.quantity_mg for lot in material_lots if is_expired(lot.expiry_date, today))
    for item in snapshot.packaging_items:
        key = packaging_key(item.id)
        totals[key] = item.quantity_pcs
        expired[key] = 0
    initial_pool = {key: totals[key] - expired[key] for key in totals}

    assignments_by_order = _group(sorted(snapshot.assignments, key=lambda a: a.id), "order_id")
    recipe_by_order = _group(snapshot.order_recipe_lines, "order_id")
    works = [
        _order_work(snapshot, order, assignments_by_order.get(order.id, []))
        for order in sorted(snapshot.orders, key=lambda o: (o.sequence, o.id))
    ]

    demands = []
    for work in works:
        if not work.is_open:
            continue
        recipe_needs = None
        if not work.production_completed:
            recipe_needs = {
                material_key(line.material_id): apply_bp_ceil(work.remaining_mg, line.percent_bp)
                for line in recipe_by_order.get(work.order.id, [])
            }
        packaging_needs = work.packaging.requirements if work.packaging is not None else None
        demands.append(OrderDemand(work.order.id, work.order.sequence, recipe_needs, packaging_needs))
    allocation = allocate(initial_pool, demands)

    pending_by_key: dict[ItemKey, list[ExpectedReceipt]] = defaultdict(list)
    for receipt in snapshot.receipts:
        if not receipt.is_received:
            pending_by_key[receipt.item_key].append(
                ExpectedReceipt(receipt.id, receipt.quantity, receipt.receipt_date)
            )
    for pending in pending_by_key.values():
        pending.sort(key=lambda r: (r.receipt_date, r.receipt_id))

    components_by_item = _group(snapshot.packaging_components, "packaging_item_id")

    def stock_state(key: ItemKey, has_components: bool = False) -> StockState:
        reserved = allocation.reserved.get(key, 0)
        return StockState(
            key=key,
            total=totals[key],
            expired=expired[key],
            reserved=reserved,
            available=totals[key] - expired[key] - reserved,
            expected=tuple(pending_by_key.get(key, [])),
            has_components=has_components,
        )

    material_states = {m.id: stock_state(material_key(m.id)) for m in snapshot.materials}
    packaging_states = {
        p.id: stock_state(packaging_key(p.id), bool(components_by_item.get(p.id))) for p in snapshot.packaging_items
    }

    available_materials = {material_id: state.available for material_id, state in material_states.items()}
    recipes = _group(snapshot.recipe_lines, "product_id")
    product_states = {
        product.id: product_availability(
            [(line.material_id, line.percent_bp) for line in recipes.get(product.id, [])],
            available_materials,
            product.unit_weight_mg,
        )
        for product in snapshot.products
    }

    lot_uses = _project_lot_uses([w for w in works if w.is_open], allocation.orders, snapshot.lots, today)
    lots_by_id = {lot.id: lot for lot in snapshot.lots}

    shelf_by_order = {line.order_id: line for line in snapshot.shelf_lines}
    shipments_by_line = _group(snapshot.shipments, "shelf_line_id")

    order_states: dict[int, OrderState] = {}
    for work in works:
        order = work.order
        order_allocation = allocation.orders.get(order.id)
        recipe_lines = order_allocation.recipe_lines if order_allocation else ()
        recipe_reserved = order_allocation.recipe_reserved if order_allocation else False
        packaging_lines = order_allocation.packaging_lines if order_allocation else ()
        packaging_reserved = order_allocation.packaging_reserved if order_allocation else False
        packaging_completed = work.plan is not None and work.plan.is_completed

        shelf_line = shelf_by_order.get(order.id)
        line_shipments = shipments_by_line.get(shelf_line.id, []) if shelf_line else []
        if order.is_cancelled:
            status = OrderStatus.CANCELLED
        elif packaging_completed and shelf_line is not None and shelf_line.boxes == 0:
            status = OrderStatus.SHIPPED if line_shipments else OrderStatus.TRANSFERRED
        elif packaging_completed:
            status = OrderStatus.ON_SHELF
        elif work.production_completed:
            status = OrderStatus.IN_PACKAGING
        elif recipe_reserved and any(
            not a.is_completed and a.start_date is not None and a.start_date <= today for a in work.assignments
        ):
            # From its start date until "Ολοκληρώθηκε" is pressed, an assignment is in production.
            status = OrderStatus.IN_PRODUCTION
        elif recipe_reserved:
            status = OrderStatus.READY_FOR_PRODUCTION
        else:
            status = OrderStatus.WAITING_MATERIALS

        flags: list[OrderFlag] = []
        if status not in CLOSED_STATUSES:
            if not work.assignments:
                flags.append(OrderFlag.NO_MACHINE)
            if work.plan is None:
                flags.append(OrderFlag.NO_PACKAGING_PLAN)
            elif any(line.shortage for line in packaging_lines):
                flags.append(OrderFlag.MISSING_PACKAGING)

        assignment_states = []
        ends: list[date] = []
        for assignment, estimate in zip(work.assignments, work.estimates):
            end = None
            if assignment.completed_at is not None:
                # A completed assignment ends on the day it was actually completed.
                end = assignment.completed_at.date()
            elif assignment.start_date is not None:
                end = assignment_end(assignment.start_date, estimate.production_days, settings.working_days)
            if end is not None:
                ends.append(end)
            assignment_states.append(AssignmentState(assignment.id, estimate, end, assignment.is_completed))

        starts = [a.start_date for a in work.assignments if a.start_date is not None]
        start_date = min(starts) if starts else None
        has_estimate = bool(work.assignments) and len(ends) == len(work.assignments)
        production_end = max(ends) if has_estimate else None
        without_packaging = work.packaging is None
        readiness = arrival = None
        if production_end is not None:
            packaging_days = work.packaging.packaging_days if work.packaging is not None else None
            readiness = readiness_date(production_end, packaging_days, settings.working_days)
            arrival = estimated_arrival(readiness, order.transit_days)

        packable: int | None = None
        limiting: tuple[ItemKey, ...] = ()
        if work.packaging is not None and any(line.shortage for line in packaging_lines):
            pools = {line.key: line.pool for line in packaging_lines}
            packable, limiting = packable_boxes(work.steps, work.packaging.boxes, pools)

        warnings: list[OrderWarning] = []
        if status not in CLOSED_STATUSES:
            short_lines = [] if recipe_reserved else [l for l in recipe_lines if l.shortage]
            if not packaging_reserved:
                short_lines += [l for l in packaging_lines if l.shortage]
            for line in short_lines:
                cover = covering_receipt_date(line.shortage, pending_by_key.get(line.key, []))
                if cover is None:
                    warnings.append(
                        OrderWarning(WarningCode.NO_COVERING_RECEIPT, item_key=line.key, quantity=line.shortage)
                    )
                elif start_date is not None and start_date < cover:
                    warnings.append(OrderWarning(WarningCode.START_BEFORE_RECEIPT, item_key=line.key, day=cover))
            if arrival is not None and arrival > order.delivery_date:
                warnings.append(
                    OrderWarning(WarningCode.ARRIVAL_AFTER_DELIVERY, day=arrival, other_day=order.delivery_date)
                )
            for use in lot_uses.get(order.id, ()):
                lot_state = lot_states[use.lot_id]
                if lot_state.status is ExpiryStatus.RED:
                    warnings.append(
                        OrderWarning(
                            WarningCode.RED_LOT,
                            item_key=material_key(lots_by_id[use.lot_id].material_id),
                            lot_id=use.lot_id,
                            days=lot_state.days_left,
                        )
                    )

        estimates = work.estimates
        planned = None if any(e.planned_pieces is None for e in estimates) else sum(e.planned_pieces for e in estimates)  # type: ignore[misc]
        expected = None if any(e.expected_pieces is None for e in estimates) else sum(e.expected_pieces for e in estimates)  # type: ignore[misc]
        actual = sum(a.actual_pieces or 0 for a in work.assignments) if work.production_completed else None

        order_states[order.id] = OrderState(
            order_id=order.id,
            status=status,
            flags=tuple(flags),
            production_completed=work.production_completed,
            packaging_completed=packaging_completed,
            remaining_mg=work.remaining_mg,
            recipe_lines=recipe_lines,
            recipe_reserved=recipe_reserved,
            assignments=tuple(assignment_states),
            production_days=max((e.production_days for e in estimates), default=None),
            planned_pieces=planned if estimates else None,
            expected_pieces=expected if estimates else None,
            actual_pieces=actual,
            packaging_pieces=work.pieces,
            pieces_basis=work.basis,
            packaging=work.packaging,
            packaging_issues=work.packaging_issues,
            packaging_lines=packaging_lines,
            packaging_reserved=packaging_reserved,
            packable_boxes=packable,
            packaging_limiting=limiting,
            start_date=start_date,
            production_end=production_end,
            readiness=readiness,
            without_packaging=without_packaging,
            arrival=arrival,
            ship_by=ship_by_date(order.delivery_date, order.transit_days),
            lot_uses=lot_uses.get(order.id, ()),
            warnings=tuple(warnings),
        )

    receipt_states = {receipt.id: _receipt_state(receipt, today) for receipt in snapshot.receipts}

    shelf_states = {}
    for line in snapshot.shelf_lines:
        cartons, loose = cartons_and_loose(line.boxes, line.boxes_per_carton)
        pending = sum(s.boxes for s in shipments_by_line.get(line.id, []) if not s.is_shipped)
        transfers = tuple(
            t.id for t in snapshot.shelf_transfers if line.id in (t.from_line_id, t.to_line_id)
        )
        pallets, last_pallet = pallets_for(cartons, line.cartons_per_pallet)
        shelf_states[line.id] = ShelfLineState(
            line_id=line.id,
            cartons=cartons,
            loose_boxes=loose,
            pending_boxes=pending,
            free_boxes=line.boxes - pending,
            transfer_ids=transfers,
            depleted=line.boxes == 0,
            # Emptied by a shipment: nothing is left on the shelf for this order.
            shipped_out=line.boxes == 0 and any(s.is_shipped for s in shipments_by_line.get(line.id, [])),
            pallets=pallets,
            last_pallet_cartons=last_pallet,
        )

    lines_by_id = {line.id: line for line in snapshot.shelf_lines}
    shipment_states = {}
    for shipment in snapshot.shipments:
        line = lines_by_id.get(shipment.shelf_line_id)
        cartons, loose = cartons_and_loose(shipment.boxes, line.boxes_per_carton if line else None)
        pallets, last_pallet = pallets_for(cartons, line.cartons_per_pallet if line else None)
        shipment_states[shipment.id] = ShipmentState(
            shipment.id, shipment.is_shipped, cartons, loose, pallets, last_pallet
        )

    return AppState(
        today=today,
        materials=material_states,
        packaging_items=packaging_states,
        lots=lot_states,
        products=product_states,
        orders=order_states,
        receipts=receipt_states,
        shelf_lines=shelf_states,
        shipments=shipment_states,
        last_history_id=snapshot.last_history_id,
    )


def _receipt_state(receipt: Receipt, today: date) -> ReceiptState:
    if receipt.is_received:
        return ReceiptState(receipt.id, ReceiptStatus.RECEIVED, 0)
    if today > receipt.receipt_date:
        return ReceiptState(receipt.id, ReceiptStatus.DELAYED, (today - receipt.receipt_date).days)
    return ReceiptState(receipt.id, ReceiptStatus.EXPECTED, 0)


PREVIEW_ORDER_ID = -1


def preview_new_order(snapshot: Snapshot, product_id: int, quantity_mg: int) -> tuple[Need, ...]:
    """Shortage table of an order not yet saved, placed last in the sequence.

    The product's current recipe is used, as it would be copied on saving.
    """
    product = next(p for p in snapshot.products if p.id == product_id)
    open_sequences = [o.sequence for o in snapshot.orders]
    candidate = Order(
        id=PREVIEW_ORDER_ID,
        name="",
        product_id=product_id,
        quantity_mg=quantity_mg,
        unit_weight_mg=product.unit_weight_mg,
        destination="",
        delivery_date=snapshot.today,
        transit_days=0,
        sequence=max(open_sequences, default=0) + 1,
        created_at=datetime.combine(snapshot.today, datetime.min.time()),
    )
    copy = tuple(
        OrderRecipeLine(PREVIEW_ORDER_ID, line.material_id, line.percent_bp)
        for line in snapshot.recipe_lines
        if line.product_id == product_id
    )
    preview = replace(
        snapshot,
        orders=snapshot.orders + (candidate,),
        order_recipe_lines=snapshot.order_recipe_lines + copy,
    )
    return compute_state(preview).orders[PREVIEW_ORDER_ID].recipe_lines


def preview_packaging_plan(
    snapshot: Snapshot,
    order_id: int,
    hours_per_day: Decimal,
    utilization_bp: int,
    steps: Sequence[PackagingStep],
    extras: Sequence[PackagingStepExtra],
) -> OrderState:
    """The order's state as it would be with this packaging plan saved (section 9.5).

    Steps and extras should use negative ids so they never collide with stored ones.
    """
    plan = PackagingPlan(order_id, hours_per_day, utilization_bp,
                         datetime.combine(snapshot.today, datetime.min.time()))
    kept_steps = tuple(s for s in snapshot.packaging_steps if s.order_id != order_id)
    kept_ids = {s.id for s in kept_steps}
    preview = replace(
        snapshot,
        packaging_plans=tuple(p for p in snapshot.packaging_plans if p.order_id != order_id) + (plan,),
        packaging_steps=kept_steps + tuple(steps),
        packaging_step_extras=tuple(e for e in snapshot.packaging_step_extras if e.step_id in kept_ids) + tuple(extras),
    )
    return compute_state(preview).orders[order_id]


@dataclass(frozen=True, slots=True)
class LostReservation:
    """An order that a change would send back to "waiting for materials"."""

    order_id: int
    already_started: bool


def lost_reservations(before: AppState, after: AppState, exclude_order_id: int | None = None) -> tuple[LostReservation, ...]:
    """Orders ready for production before a change and waiting for materials after it.

    already_started is True when the order's start date is today or earlier,
    which calls for the stronger confirmation of section 4.12.
    """
    lost = []
    for order_id, old in before.orders.items():
        if order_id == exclude_order_id or not old.recipe_reserved:
            continue
        new = after.orders.get(order_id)
        if new is not None and new.status is OrderStatus.WAITING_MATERIALS:
            started = new.start_date is not None and new.start_date <= after.today
            lost.append(LostReservation(order_id, started))
    return tuple(lost)
