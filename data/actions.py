"""One function per user action (sections 3, 4.11 and 5 to 11).

Every action runs in one transaction: it validates the input, writes its rows
through a Writer, and records one history entry with the before and after image
of each changed row.

After the writes, the action recomputes the state inside the same transaction.
If an order would lose its reserved materials, or the action needs a
confirmation of its own, the transaction is rolled back and NeedsConfirmation
lists the messages. Calling the action again with confirm=True commits it.

Inputs are in storage units: mass in mg, percentages in basis points,
dimensions in mm, times as Decimal.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Any

from core import dates
from core.allocation import FefoPlan, consume_fefo
from core.models import (
    ItemKind,
    MaterialCategory,
    MaterialLot,
    Order,
    PackagingItemType,
    Settings,
    Snapshot,
    StepKind,
    StepRole,
    material_key,
)
from core.packaging_calc import MAX_STEPS, StepInput, validate_plan
from core.production_calc import scale_proportionally
from core.state import AppState, compute_state, lost_reservations
from core.units import BP_FULL, apply_bp_ceil, format_date, format_int, format_kg, format_percent
from data import history
from data.db import transaction
from data.repositories import Writer, decimal_text, iso, load_snapshot, settings_rows
from ui import texts


class ActionError(Exception):
    """The action was rejected. The message says what happened and what to do."""


class NeedsConfirmation(Exception):
    """The action needs the user's confirmation. Nothing was saved."""

    def __init__(self, messages: Sequence[str]) -> None:
        super().__init__(" ".join(messages))
        self.messages = tuple(messages)


@dataclass(frozen=True, slots=True)
class ActionResult:
    """history_id is None when the action changed nothing; value is e.g. a new row id."""

    history_id: int | None
    value: Any = None


@dataclass
class Context:
    """What an action body works with."""

    conn: sqlite3.Connection
    writer: Writer
    snapshot: Snapshot
    state: AppState
    today: date
    confirmations: list[str] = field(default_factory=list)
    value: Any = None

    def ask(self, message: str) -> None:
        """Require a confirmation before this action is committed."""
        if message not in self.confirmations:
            self.confirmations.append(message)


def _run(conn: sqlite3.Connection, code: str, body: Callable[[Context], str], confirm: bool) -> ActionResult:
    try:
        with transaction(conn):
            snapshot = load_snapshot(conn)
            state = compute_state(snapshot)
            ctx = Context(conn, Writer(conn), snapshot, state, snapshot.today)
            description = body(ctx)
            after = compute_state(load_snapshot(conn, today=snapshot.today))
            names = {o.id: o.name for o in snapshot.orders}
            for lost in lost_reservations(state, after):
                start = state.orders[lost.order_id].start_date
                if lost.already_started and start is not None:
                    ctx.ask(texts.loses_materials_started(names[lost.order_id], start.strftime("%d/%m")))
                else:
                    ctx.ask(texts.loses_materials(names[lost.order_id]))
            if ctx.confirmations and not confirm:
                raise NeedsConfirmation(ctx.confirmations)
            if not ctx.writer.changes:
                return ActionResult(None, ctx.value)
            history_id = history.record(conn, code, description, ctx.writer.changes)
            return ActionResult(history_id, ctx.value)
    except sqlite3.IntegrityError as error:
        raise ActionError(texts.action_failed(str(error))) from error


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ActionError(message)


def _text(value: str | None, field_name: str, required: bool = True) -> str | None:
    cleaned = (value or "").strip()
    if required:
        _require(bool(cleaned), texts.field_required(field_name))
    return cleaned or None


def _positive(value: int | Decimal | None, field_name: str) -> None:
    _require(value is not None, texts.field_required(field_name))
    _require(value > 0, texts.field_positive(field_name))  # type: ignore[operator]


def _not_negative(value: int | Decimal | None, field_name: str) -> None:
    _require(value is not None, texts.field_required(field_name))
    _require(value >= 0, texts.field_not_negative(field_name))  # type: ignore[operator]


def _check_percentages(ctx: Context, lines: Sequence[tuple[int, int]], allow_empty: bool) -> None:
    if not lines:
        _require(allow_empty, texts.RECIPE_EMPTY)
        return
    materials = {m.id: m for m in ctx.snapshot.materials}
    seen: set[int] = set()
    for material_id, percent_bp in lines:
        _require(material_id in materials, texts.field_required(texts.FIELDS["material"]))
        _require(material_id not in seen, texts.duplicate_material(materials[material_id].name))
        _require(percent_bp > 0, texts.PERCENT_POSITIVE)
        seen.add(material_id)
    total = sum(bp for _, bp in lines)
    _require(total == BP_FULL, texts.percent_total(format_percent(total)))


def _order(ctx: Context, order_id: int) -> Order:
    order = next((o for o in ctx.snapshot.orders if o.id == order_id), None)
    if order is None:
        raise ActionError(texts.action_failed(f"order {order_id}"))
    return order


def _is_open(ctx: Context, order: Order) -> bool:
    plan = next((p for p in ctx.snapshot.packaging_plans if p.order_id == order.id), None)
    return not order.is_cancelled and not (plan is not None and plan.is_completed)


def _open_orders(ctx: Context) -> list[Order]:
    return sorted((o for o in ctx.snapshot.orders if _is_open(ctx, o)), key=lambda o: (o.sequence, o.id))


def _compact_sequence(ctx: Context, excluding: int | None = None, insert_at: tuple[int, int] | None = None) -> None:
    """Renumber the open orders 1..n without gaps, keeping their relative order.

    excluding drops an order that is closing; insert_at = (order_id, position)
    places an order at a new position.
    """
    ordered = [o for o in _open_orders(ctx) if o.id != excluding]
    if insert_at is not None:
        moving_id, position = insert_at
        moving = next(o for o in ordered if o.id == moving_id)
        ordered.remove(moving)
        ordered.insert(position - 1, moving)
    for number, order in enumerate(ordered, start=1):
        if order.sequence != number:
            ctx.writer.update("orders", {"id": order.id}, {"sequence": number})


def _fefo_consume(ctx: Context, material_id: int, quantity_mg: int) -> None:
    """Take a quantity from a material's LOTs, nearest expiry first, and write it.

    If valid LOTs do not suffice but expired ones would, the action asks for
    the "consumed in this production?" confirmation of section 4.11.
    """
    if quantity_mg <= 0:
        return
    lots = [_current_lot(ctx, lot.id) for lot in ctx.snapshot.lots if lot.material_id == material_id]
    plan: FefoPlan = consume_fefo(lots, quantity_mg, ctx.today)
    if plan.shortfall_mg:
        plan = consume_fefo(lots, quantity_mg, ctx.today, include_expired=True)
        _require(plan.shortfall_mg == 0, texts.NEGATIVE_STOCK)
        used = {take.lot_id for take in plan.takes}
        for lot in lots:
            if lot.id in used and lot.id in plan.expired_lot_ids:
                ctx.ask(texts.expired_lot_consumed(lot.lot_number, format_date(lot.expiry_date)))
    for take in plan.takes:
        lot = _current_lot(ctx, take.lot_id)
        ctx.writer.update("material_lots", {"id": lot.id}, {"quantity_mg": lot.quantity_mg - take.quantity_mg})


def _reserved_counting_expired(ctx: Context, order_id: int, packaging: bool) -> bool:
    """Whether the order would hold its materials if LOTs that expired were still valid.

    Production or packaging recorded after a LOT expired is the case of
    section 4.11: the action goes ahead and asks whether the LOT was consumed.
    """
    relaxed = replace(ctx.snapshot, lots=tuple(
        replace(lot, expiry_date=max(lot.expiry_date, ctx.today)) for lot in ctx.snapshot.lots
    ))
    order_state = compute_state(relaxed).orders[order_id]
    return order_state.packaging_reserved if packaging else order_state.recipe_reserved


def _current_lot(ctx: Context, lot_id: int) -> MaterialLot:
    """A LOT as it stands now in the transaction, after earlier writes of this action."""
    row = ctx.conn.execute("SELECT * FROM material_lots WHERE id = ?", (lot_id,)).fetchone()
    return MaterialLot(row["id"], row["material_id"], row["lot_number"], row["quantity_mg"],
                       date.fromisoformat(row["expiry_date"]))


# ---------------------------------------------------------------- materials and LOTs


def _check_material_fields(ctx: Context, code: str, name: str, exclude_id: int | None) -> tuple[str, str]:
    code_clean = _text(code, texts.FIELDS["code"])
    name_clean = _text(name, texts.FIELDS["material_name"])
    assert code_clean is not None and name_clean is not None
    for material in ctx.snapshot.materials:
        if material.id != exclude_id:
            _require(material.code != code_clean, texts.code_exists(code_clean))
    return code_clean, name_clean


def create_material(
    conn: sqlite3.Connection,
    *,
    code: str,
    name: str,
    category: MaterialCategory,
    description: str | None = None,
    lot_number: str | None = None,
    lot_quantity_mg: int | None = None,
    lot_expiry: date | None = None,
    confirm: bool = False,
) -> ActionResult:
    """Add a material, optionally with its first LOT. The value is the new material id."""
    def body(ctx: Context) -> str:
        code_clean, name_clean = _check_material_fields(ctx, code, name, None)
        material_id = ctx.writer.insert("materials", {
            "code": code_clean, "name": name_clean, "category": MaterialCategory(category).value,
            "description": _text(description, texts.FIELDS["description"], required=False),
        })
        if lot_number or lot_quantity_mg or lot_expiry:
            _insert_lot(ctx, material_id, lot_number, lot_quantity_mg, lot_expiry)
        ctx.value = material_id
        return texts.h_material_created(name_clean)
    return _run(conn, "material_create", body, confirm)


def update_material(
    conn: sqlite3.Connection,
    material_id: int,
    *,
    code: str,
    name: str,
    category: MaterialCategory,
    description: str | None = None,
    confirm: bool = False,
) -> ActionResult:
    def body(ctx: Context) -> str:
        code_clean, name_clean = _check_material_fields(ctx, code, name, material_id)
        ctx.writer.update("materials", {"id": material_id}, {
            "code": code_clean, "name": name_clean, "category": MaterialCategory(category).value,
            "description": _text(description, texts.FIELDS["description"], required=False),
        })
        return texts.h_material_updated(name_clean)
    return _run(conn, "material_update", body, confirm)


def delete_material(conn: sqlite3.Connection, material_id: int, *, confirm: bool = False) -> ActionResult:
    """Soft-delete a material whose LOTs are all 0 and that no recipe or breakdown uses."""
    def body(ctx: Context) -> str:
        material = next(m for m in ctx.snapshot.materials if m.id == material_id)
        _require(ctx.state.materials[material_id].total == 0, texts.material_has_stock(material.name))
        products = {p.id: p.name for p in ctx.snapshot.products}
        for line in ctx.snapshot.recipe_lines:
            if line.material_id == material_id:
                raise ActionError(texts.material_in_recipe(material.name, products[line.product_id]))
        items = {p.id: p for p in ctx.snapshot.packaging_items}
        for component in ctx.snapshot.packaging_components:
            if component.material_id == material_id and not items[component.packaging_item_id].is_deleted:
                raise ActionError(texts.material_in_breakdown(material.name, items[component.packaging_item_id].name))
        for order in _open_orders(ctx):
            order_state = ctx.state.orders[order.id]
            needed = [line for line in order_state.recipe_lines + order_state.packaging_lines
                      if line.key == material_key(material_id) and line.need > 0]
            if needed:
                raise ActionError(texts.material_in_open_order(material.name, order.name))
        ctx.writer.update("materials", {"id": material_id}, {"deleted_at": iso(dates.now())})
        return texts.h_material_deleted(material.name)
    return _run(conn, "material_delete", body, confirm)


def _insert_lot(ctx: Context, material_id: int, lot_number: str | None, quantity_mg: int | None,
                expiry: date | None) -> int:
    number = _text(lot_number, texts.FIELDS["lot_number"])
    _positive(quantity_mg, texts.FIELDS["quantity"])
    _require(expiry is not None, texts.EXPIRY_REQUIRED)
    return ctx.writer.insert("material_lots", {
        "material_id": material_id, "lot_number": number, "quantity_mg": quantity_mg,
        "expiry_date": iso(expiry),
    })


def add_lot(
    conn: sqlite3.Connection,
    material_id: int,
    *,
    lot_number: str,
    quantity_mg: int,
    expiry_date: date,
    confirm: bool = False,
) -> ActionResult:
    def body(ctx: Context) -> str:
        material = next(m for m in ctx.snapshot.materials if m.id == material_id)
        ctx.value = _insert_lot(ctx, material_id, lot_number, quantity_mg, expiry_date)
        return texts.h_lot_created(lot_number.strip(), material.name, format_kg(quantity_mg))
    return _run(conn, "lot_create", body, confirm)


def update_lot(
    conn: sqlite3.Connection,
    lot_id: int,
    *,
    lot_number: str,
    quantity_mg: int,
    expiry_date: date,
    confirm: bool = False,
) -> ActionResult:
    """Correct a LOT, e.g. after a stock count. A quantity change is logged with old and new value."""
    def body(ctx: Context) -> str:
        old = next(lot for lot in ctx.snapshot.lots if lot.id == lot_id)
        number = _text(lot_number, texts.FIELDS["lot_number"])
        _not_negative(quantity_mg, texts.FIELDS["quantity"])
        _require(expiry_date is not None, texts.EXPIRY_REQUIRED)
        ctx.writer.update("material_lots", {"id": lot_id}, {
            "lot_number": number, "quantity_mg": quantity_mg, "expiry_date": iso(expiry_date),
        })
        if quantity_mg != old.quantity_mg:
            return texts.h_lot_quantity(old.lot_number, format_kg(old.quantity_mg), format_kg(quantity_mg))
        return texts.h_lot_updated(old.lot_number)
    return _run(conn, "lot_update", body, confirm)


def delete_lot(conn: sqlite3.Connection, lot_id: int, *, confirm: bool = False) -> ActionResult:
    """Delete a LOT with quantity 0. Receipts that created it keep their data without the link."""
    def body(ctx: Context) -> str:
        lot = next(lot for lot in ctx.snapshot.lots if lot.id == lot_id)
        _require(lot.quantity_mg == 0, texts.lot_not_empty(lot.lot_number))
        for receipt in ctx.snapshot.receipts:
            if receipt.lot_id == lot_id:
                ctx.writer.update("receipts", {"id": receipt.id}, {"lot_id": None})
        ctx.writer.delete("material_lots", {"id": lot_id})
        return texts.h_lot_deleted(lot.lot_number)
    return _run(conn, "lot_delete", body, confirm)


# ---------------------------------------------------------------- packaging items


@dataclass(frozen=True, slots=True)
class PackagingItemInput:
    code: str
    name: str
    quantity_pcs: int
    description: str | None = None
    length_mm: int | None = None
    width_mm: int | None = None
    height_mm: int | None = None
    unit_weight_mg: int | None = None
    components: tuple[tuple[int, int], ...] = ()
    item_type: PackagingItemType = PackagingItemType.PACKAGING
    outer_length_mm: int | None = None
    outer_width_mm: int | None = None
    outer_height_mm: int | None = None


def _check_dimensions(dims: tuple[int | None, int | None, int | None]) -> None:
    _require(all(d is None for d in dims) or all(d is not None for d in dims), texts.DIMENSIONS_ALL_OR_NONE)
    for dim, label in zip(dims, (texts.FIELDS["length"], texts.FIELDS["width"], texts.FIELDS["height"])):
        if dim is not None:
            _positive(dim, label)


def _packaging_values(ctx: Context, item: PackagingItemInput, exclude_id: int | None) -> dict[str, Any]:
    """Validate a packaging item by its type.

    Ordinary packaging: dimensions, weight and material breakdown, all optional.
    Label: no dimensions and no breakdown. Carton: inner and outer dimensions.
    Pallet: outer dimensions only (base and maximum load height).
    """
    code = _text(item.code, texts.FIELDS["code"])
    name = _text(item.name, texts.FIELDS["name"])
    for existing in ctx.snapshot.packaging_items:
        if existing.id != exclude_id:
            _require(existing.code != code, texts.code_exists(code or ""))
    _not_negative(item.quantity_pcs, texts.FIELDS["quantity_pcs"])
    item_type = PackagingItemType(item.item_type)
    inner = (item.length_mm, item.width_mm, item.height_mm)
    outer = (item.outer_length_mm, item.outer_width_mm, item.outer_height_mm)
    _check_dimensions(inner)
    _check_dimensions(outer)
    if item_type is not PackagingItemType.CARTON and item_type is not PackagingItemType.PALLET:
        _require(all(d is None for d in outer), texts.OUTER_ONLY_FOR_CONTAINERS)
    if item_type in (PackagingItemType.LABEL, PackagingItemType.PALLET):
        _require(all(d is None for d in inner), texts.NO_INNER_DIMENSIONS)
    if item_type is not PackagingItemType.PACKAGING:
        _require(not item.components, texts.BREAKDOWN_ONLY_FOR_PACKAGING)
    if item.unit_weight_mg is not None:
        _positive(item.unit_weight_mg, texts.FIELDS["unit_weight"])
    if item.components:
        _require(item.unit_weight_mg is not None, texts.BREAKDOWN_NEEDS_WEIGHT)
        _check_percentages(ctx, item.components, allow_empty=False)
    return {
        "code": code, "name": name, "description": _text(item.description, texts.FIELDS["description"], required=False),
        "quantity_pcs": item.quantity_pcs, "length_mm": item.length_mm, "width_mm": item.width_mm,
        "height_mm": item.height_mm, "unit_weight_mg": item.unit_weight_mg, "item_type": item_type.value,
        "outer_length_mm": item.outer_length_mm, "outer_width_mm": item.outer_width_mm,
        "outer_height_mm": item.outer_height_mm,
    }


def create_packaging_item(conn: sqlite3.Connection, item: PackagingItemInput, *, confirm: bool = False) -> ActionResult:
    def body(ctx: Context) -> str:
        values = _packaging_values(ctx, item, None)
        item_id = ctx.writer.insert("packaging_items", values)
        for material_id, percent_bp in item.components:
            ctx.writer.insert("packaging_item_components", {
                "packaging_item_id": item_id, "material_id": material_id, "percent_bp": percent_bp,
            })
        ctx.value = item_id
        return texts.h_packaging_created(values["name"])
    return _run(conn, "packaging_create", body, confirm)


def update_packaging_item(
    conn: sqlite3.Connection, item_id: int, item: PackagingItemInput, *, confirm: bool = False
) -> ActionResult:
    def body(ctx: Context) -> str:
        old = next(p for p in ctx.snapshot.packaging_items if p.id == item_id)
        _require(PackagingItemType(item.item_type) is old.item_type, texts.TYPE_LOCKED)
        values = _packaging_values(ctx, item, item_id)
        ctx.writer.update("packaging_items", {"id": item_id}, values)
        old_components = [(c.material_id, c.percent_bp) for c in ctx.snapshot.packaging_components
                          if c.packaging_item_id == item_id]
        if old_components != list(item.components):
            for material_id, _ in old_components:
                ctx.writer.delete("packaging_item_components", {"packaging_item_id": item_id, "material_id": material_id})
            for material_id, percent_bp in item.components:
                ctx.writer.insert("packaging_item_components", {
                    "packaging_item_id": item_id, "material_id": material_id, "percent_bp": percent_bp,
                })
        fields = ("code", "name", "description", "length_mm", "width_mm", "height_mm", "unit_weight_mg",
                  "outer_length_mm", "outer_width_mm", "outer_height_mm")
        only_quantity = (
            old.quantity_pcs != item.quantity_pcs
            and all(getattr(old, f) == values[f] for f in fields)
            and old_components == list(item.components)
        )
        if only_quantity:
            return texts.h_packaging_quantity(old.name, format_int(old.quantity_pcs), format_int(item.quantity_pcs))
        return texts.h_packaging_updated(values["name"])
    return _run(conn, "packaging_update", body, confirm)


def _open_orders_using_item(ctx: Context, item_id: int) -> list[Order]:
    step_orders = {s.order_id for s in ctx.snapshot.packaging_steps if s.packaging_item_id == item_id}
    step_ids_with_extra = {e.step_id for e in ctx.snapshot.packaging_step_extras if e.packaging_item_id == item_id}
    step_orders |= {s.order_id for s in ctx.snapshot.packaging_steps if s.id in step_ids_with_extra}
    return [o for o in _open_orders(ctx) if o.id in step_orders]


def delete_packaging_item(conn: sqlite3.Connection, item_id: int, *, confirm: bool = False) -> ActionResult:
    """Soft-delete a packaging item with 0 pieces that no open order uses."""
    def body(ctx: Context) -> str:
        item = next(p for p in ctx.snapshot.packaging_items if p.id == item_id)
        _require(item.quantity_pcs == 0, texts.packaging_has_stock(item.name))
        using = _open_orders_using_item(ctx, item_id)
        if using:
            raise ActionError(texts.packaging_in_open_order(item.name, using[0].name))
        ctx.writer.update("packaging_items", {"id": item_id}, {"deleted_at": iso(dates.now())})
        return texts.h_packaging_deleted(item.name)
    return _run(conn, "packaging_delete", body, confirm)


# ---------------------------------------------------------------- products


def _product_values(ctx: Context, name: str, unit_weight_mg: int | None, recipe: Sequence[tuple[int, int]],
                    exclude_id: int | None) -> str:
    name_clean = _text(name, texts.FIELDS["product_name"])
    assert name_clean is not None
    for product in ctx.snapshot.products:
        if product.id != exclude_id:
            _require(product.name != name_clean, texts.name_exists(name_clean))
    _positive(unit_weight_mg, texts.FIELDS["weight_per_piece"])
    _check_percentages(ctx, recipe, allow_empty=False)
    return name_clean


def create_product(
    conn: sqlite3.Connection,
    *,
    name: str,
    unit_weight_mg: int | None,
    recipe: Sequence[tuple[int, int]],
    confirm: bool = False,
) -> ActionResult:
    def body(ctx: Context) -> str:
        name_clean = _product_values(ctx, name, unit_weight_mg, recipe, None)
        product_id = ctx.writer.insert("products", {"name": name_clean, "unit_weight_mg": unit_weight_mg})
        for material_id, percent_bp in recipe:
            ctx.writer.insert("recipe_lines", {"product_id": product_id, "material_id": material_id, "percent_bp": percent_bp})
        ctx.value = product_id
        return texts.h_product_created(name_clean)
    return _run(conn, "product_create", body, confirm)


def update_product(
    conn: sqlite3.Connection,
    product_id: int,
    *,
    name: str,
    unit_weight_mg: int | None,
    recipe: Sequence[tuple[int, int]],
    confirm: bool = False,
) -> ActionResult:
    """Change a product. Existing orders keep their own recipe copy."""
    def body(ctx: Context) -> str:
        name_clean = _product_values(ctx, name, unit_weight_mg, recipe, product_id)
        ctx.writer.update("products", {"id": product_id}, {"name": name_clean, "unit_weight_mg": unit_weight_mg})
        old = [(l.material_id, l.percent_bp) for l in ctx.snapshot.recipe_lines if l.product_id == product_id]
        if old != list(recipe):
            for material_id, _ in old:
                ctx.writer.delete("recipe_lines", {"product_id": product_id, "material_id": material_id})
            for material_id, percent_bp in recipe:
                ctx.writer.insert("recipe_lines", {"product_id": product_id, "material_id": material_id,
                                                   "percent_bp": percent_bp})
        return texts.h_product_updated(name_clean)
    return _run(conn, "product_update", body, confirm)


def delete_product(conn: sqlite3.Connection, product_id: int, *, confirm: bool = False) -> ActionResult:
    def body(ctx: Context) -> str:
        product = next(p for p in ctx.snapshot.products if p.id == product_id)
        order = next((o for o in ctx.snapshot.orders if o.product_id == product_id), None)
        if order is not None:
            raise ActionError(texts.product_has_orders(product.name, order.name))
        for line in ctx.snapshot.recipe_lines:
            if line.product_id == product_id:
                ctx.writer.delete("recipe_lines", {"product_id": product_id, "material_id": line.material_id})
        ctx.writer.delete("products", {"id": product_id})
        return texts.h_product_deleted(product.name)
    return _run(conn, "product_delete", body, confirm)


# ---------------------------------------------------------------- orders


# A name like ORD-014, or the older form with Greek letters; numbering continues across both.
_ORDER_NUMBER = re.compile(r"^[^\W\d_]+-(\d+)$")


def suggest_order_name(snapshot: Snapshot) -> str:
    """The next free name of the form ORD-001, ORD-002 and so on, after the highest existing number."""
    numbers = [
        int(match.group(1))
        for order in snapshot.orders
        if (match := _ORDER_NUMBER.match(order.name))
    ]
    return f"{texts.ORDER_NAME_PREFIX}{max(numbers, default=0) + 1:03d}"


def _check_order_name(ctx: Context, name: str, exclude_id: int | None) -> str:
    name_clean = _text(name, texts.FIELDS["name"])
    assert name_clean is not None
    for order in ctx.snapshot.orders:
        if order.id != exclude_id:
            _require(order.name != name_clean, texts.name_exists(name_clean))
    return name_clean


def create_order(
    conn: sqlite3.Connection,
    *,
    product_id: int,
    quantity_mg: int,
    name: str,
    destination: str,
    delivery_date: date,
    transit_days: int,
    confirm: bool = False,
) -> ActionResult:
    """Save an order last in the sequence, with a copy of the product's recipe and weight."""
    def body(ctx: Context) -> str:
        product = next((p for p in ctx.snapshot.products if p.id == product_id), None)
        _require(product is not None, texts.field_required(texts.FIELDS["product"]))
        assert product is not None
        recipe = [l for l in ctx.snapshot.recipe_lines if l.product_id == product_id]
        _require(bool(recipe), texts.PRODUCT_WITHOUT_RECIPE)
        _require(product.unit_weight_mg is not None, texts.PRODUCT_WITHOUT_WEIGHT)
        _positive(quantity_mg, texts.FIELDS["quantity_kg"])
        name_clean = _check_order_name(ctx, name, None)
        destination_clean = _text(destination, texts.FIELDS["destination"])
        _require(delivery_date is not None, texts.field_required(texts.FIELDS["delivery_date"]))
        _not_negative(transit_days, texts.FIELDS["transit_days"])
        sequence = max((o.sequence for o in _open_orders(ctx)), default=0) + 1
        order_id = ctx.writer.insert("orders", {
            "name": name_clean, "product_id": product_id, "quantity_mg": quantity_mg,
            "unit_weight_mg": product.unit_weight_mg, "destination": destination_clean,
            "delivery_date": iso(delivery_date), "transit_days": transit_days, "sequence": sequence,
            "created_at": iso(dates.now()),
        })
        for line in recipe:
            ctx.writer.insert("order_recipe_lines", {
                "order_id": order_id, "material_id": line.material_id, "percent_bp": line.percent_bp,
            })
        ctx.value = order_id
        return texts.h_order_created(name_clean, product.name, format_kg(quantity_mg))
    return _run(conn, "order_create", body, confirm)


def update_order(
    conn: sqlite3.Connection,
    order_id: int,
    *,
    name: str,
    destination: str,
    delivery_date: date,
    transit_days: int,
    quantity_mg: int,
    confirm: bool = False,
) -> ActionResult:
    """Name, destination and dates change at any time; the quantity until the first assignment completes.

    With assignments, their quantities follow the new total in the same ratio.
    """
    def body(ctx: Context) -> str:
        order = _order(ctx, order_id)
        name_clean = _check_order_name(ctx, name, order_id)
        destination_clean = _text(destination, texts.FIELDS["destination"])
        _require(delivery_date is not None, texts.field_required(texts.FIELDS["delivery_date"]))
        _not_negative(transit_days, texts.FIELDS["transit_days"])
        values: dict[str, Any] = {
            "name": name_clean, "destination": destination_clean,
            "delivery_date": iso(delivery_date), "transit_days": transit_days,
        }
        if quantity_mg != order.quantity_mg:
            _positive(quantity_mg, texts.FIELDS["quantity_kg"])
            _require(_is_open(ctx, order), texts.ORDER_CLOSED)
            assignments = [a for a in ctx.snapshot.assignments if a.order_id == order_id]
            _require(not any(a.is_completed for a in assignments), texts.QUANTITY_LOCKED)
            values["quantity_mg"] = quantity_mg
            if assignments:
                shares = scale_proportionally([a.quantity_mg for a in assignments], quantity_mg)
                for assignment, share in zip(assignments, shares):
                    _positive(share, texts.FIELDS["assignment_quantity"])
                    ctx.writer.update("order_assignments", {"id": assignment.id}, {"quantity_mg": share})
        ctx.writer.update("orders", {"id": order_id}, values)
        return texts.h_order_updated(name_clean)
    return _run(conn, "order_update", body, confirm)


def change_sequence(conn: sqlite3.Connection, order_id: int, *, new_position: int, confirm: bool = False) -> ActionResult:
    """Move an open order to a new position; the orders in between shift by one."""
    def body(ctx: Context) -> str:
        order = _order(ctx, order_id)
        _require(_is_open(ctx, order), texts.ORDER_CLOSED)
        open_orders = _open_orders(ctx)
        _require(1 <= new_position <= len(open_orders), texts.position_range(len(open_orders)))
        old_position = [o.id for o in open_orders].index(order_id) + 1
        _compact_sequence(ctx, insert_at=(order_id, new_position))
        return texts.h_sequence(order.name, old_position, new_position)
    return _run(conn, "order_sequence", body, confirm)


def cancel_order(conn: sqlite3.Connection, order_id: int, *, confirm: bool = False) -> ActionResult:
    """Cancel an order before any assignment completes. Its reservations end, since they are computed."""
    def body(ctx: Context) -> str:
        order = _order(ctx, order_id)
        _require(_is_open(ctx, order), texts.ORDER_CLOSED)
        _require(not any(a.is_completed for a in ctx.snapshot.assignments if a.order_id == order_id),
                 texts.CANCEL_LOCKED)
        ctx.writer.update("orders", {"id": order_id}, {"cancelled_at": iso(dates.now())})
        _compact_sequence(ctx, excluding=order_id)
        return texts.h_order_cancelled(order.name)
    return _run(conn, "order_cancel", body, confirm)


# ---------------------------------------------------------------- machines and production


@dataclass(frozen=True, slots=True)
class MachineInput:
    name: str
    batch_size_mg: int
    cycle_time_min: Decimal
    utilization_bp: int
    hours_per_day: Decimal
    max_batch_mg: int | None = None
    min_cycle_time_min: Decimal | None = None


def _machine_values(ctx: Context, machine: MachineInput, exclude_id: int | None) -> dict[str, Any]:
    name = _text(machine.name, texts.FIELDS["name"])
    for existing in ctx.snapshot.machines:
        if existing.id != exclude_id:
            _require(existing.name != name, texts.name_exists(name or ""))
    _positive(machine.batch_size_mg, texts.FIELDS["batch_size"])
    _positive(machine.cycle_time_min, texts.FIELDS["cycle_time"])
    _require(100 <= machine.utilization_bp <= BP_FULL, texts.field_range(texts.FIELDS["utilization"], "1", "100"))
    _positive(machine.hours_per_day, texts.FIELDS["hours_per_day"])
    _require(machine.hours_per_day <= 24, texts.field_range(texts.FIELDS["hours_per_day"], "0", "24"))
    if machine.max_batch_mg is not None:
        _positive(machine.max_batch_mg, texts.FIELDS["max_batch"])
    if machine.min_cycle_time_min is not None:
        _positive(machine.min_cycle_time_min, texts.FIELDS["min_cycle"])
    return {
        "name": name, "batch_size_mg": machine.batch_size_mg,
        "cycle_time_min": decimal_text(machine.cycle_time_min), "utilization_bp": machine.utilization_bp,
        "hours_per_day": decimal_text(machine.hours_per_day), "max_batch_mg": machine.max_batch_mg,
        "min_cycle_time_min": decimal_text(machine.min_cycle_time_min),
    }


def create_machine(conn: sqlite3.Connection, machine: MachineInput, *, confirm: bool = False) -> ActionResult:
    def body(ctx: Context) -> str:
        values = _machine_values(ctx, machine, None)
        ctx.value = ctx.writer.insert("machines", values)
        return texts.h_machine_created(values["name"])
    return _run(conn, "machine_create", body, confirm)


def update_machine(conn: sqlite3.Connection, machine_id: int, machine: MachineInput, *, confirm: bool = False) -> ActionResult:
    def body(ctx: Context) -> str:
        values = _machine_values(ctx, machine, machine_id)
        ctx.writer.update("machines", {"id": machine_id}, values)
        return texts.h_machine_updated(values["name"])
    return _run(conn, "machine_update", body, confirm)


def delete_machine(conn: sqlite3.Connection, machine_id: int, *, confirm: bool = False) -> ActionResult:
    """Soft-delete a machine without an assignment in an open order."""
    def body(ctx: Context) -> str:
        machine = next(m for m in ctx.snapshot.machines if m.id == machine_id)
        open_ids = {o.id: o for o in _open_orders(ctx)}
        for assignment in ctx.snapshot.assignments:
            if assignment.machine_id == machine_id and assignment.order_id in open_ids:
                raise ActionError(texts.machine_in_open_order(machine.name, open_ids[assignment.order_id].name))
        ctx.writer.update("machines", {"id": machine_id}, {"deleted_at": iso(dates.now())})
        return texts.h_machine_deleted(machine.name)
    return _run(conn, "machine_delete", body, confirm)


@dataclass(frozen=True, slots=True)
class AssignmentInput:
    """One machine share of an order. assignment_id is None for a new share."""

    machine_id: int
    quantity_mg: int
    batch_size_mg: int
    cycle_time_min: Decimal
    defect_bp: int = 0
    start_date: date | None = None
    assignment_id: int | None = None


def set_assignments(
    conn: sqlite3.Connection, order_id: int, rows: Sequence[AssignmentInput], *, confirm: bool = False
) -> ActionResult:
    """Replace the not yet completed assignments of an order.

    The shares must add up to the quantity still to be produced. Completed
    assignments never change.
    """
    def body(ctx: Context) -> str:
        order = _order(ctx, order_id)
        _require(_is_open(ctx, order), texts.ORDER_CLOSED)
        existing = [a for a in ctx.snapshot.assignments if a.order_id == order_id]
        completed = [a for a in existing if a.is_completed]
        _require(not existing or not all(a.is_completed for a in existing), texts.PRODUCTION_DONE)
        remaining = order.quantity_mg - sum(a.quantity_mg for a in completed)
        machines = {m.id: m for m in ctx.snapshot.machines}
        for row in rows:
            _require(row.machine_id in machines, texts.field_required(texts.FIELDS["machine"]))
            _positive(row.quantity_mg, texts.FIELDS["quantity_kg"])
            _positive(row.batch_size_mg, texts.FIELDS["batch_size"])
            _positive(row.cycle_time_min, texts.FIELDS["cycle_time"])
            _require(0 <= row.defect_bp <= BP_FULL, texts.field_range(texts.FIELDS["defect_rate"], "0", "100"))
        total = sum(row.quantity_mg for row in rows)
        _require(not rows or total == remaining, texts.assignment_sum(format_kg(total), format_kg(remaining)))

        open_existing = {a.id: a for a in existing if not a.is_completed}
        kept = {row.assignment_id for row in rows if row.assignment_id in open_existing}
        for assignment_id in open_existing:
            if assignment_id not in kept:
                ctx.writer.delete("order_assignments", {"id": assignment_id})
        for row in rows:
            values = {
                "order_id": order_id, "machine_id": row.machine_id, "quantity_mg": row.quantity_mg,
                "batch_size_mg": row.batch_size_mg, "cycle_time_min": decimal_text(row.cycle_time_min),
                "defect_bp": row.defect_bp, "start_date": iso(row.start_date),
            }
            if row.assignment_id in open_existing:
                ctx.writer.update("order_assignments", {"id": row.assignment_id}, values)
            else:
                ctx.writer.insert("order_assignments", values)
        return texts.h_assignments(order.name)
    return _run(conn, "assignments_set", body, confirm)


def complete_assignment(
    conn: sqlite3.Connection, assignment_id: int, *, actual_pieces: int, confirm: bool = False
) -> ActionResult:
    """Mark one assignment as produced and take its materials from the LOTs (section 8.5).

    Each material takes quantity x percent, nearest expiry first. The amount is
    computed as the difference of the rounded-up totals before and after this
    assignment, so the consumptions of an order never exceed its reservation.
    """
    def body(ctx: Context) -> str:
        assignment = next(a for a in ctx.snapshot.assignments if a.id == assignment_id)
        _require(not assignment.is_completed, texts.ASSIGNMENT_DONE)
        order = _order(ctx, assignment.order_id)
        _require(_is_open(ctx, order), texts.ORDER_CLOSED)
        order_state = ctx.state.orders[order.id]
        _require(order_state.recipe_reserved or _reserved_counting_expired(ctx, order.id, packaging=False),
                 texts.WAITING_MATERIALS)
        _not_negative(actual_pieces, texts.FIELDS["actual_pieces"])
        estimate = next(s.estimate for s in order_state.assignments if s.assignment_id == assignment_id)
        if estimate.planned_pieces is not None and actual_pieces > estimate.planned_pieces:
            ctx.ask(texts.ACTUAL_OVER_PLANNED)
        done_before = sum(a.quantity_mg for a in ctx.snapshot.assignments
                          if a.order_id == order.id and a.is_completed)
        for line in ctx.snapshot.order_recipe_lines:
            if line.order_id != order.id:
                continue
            quantity = (apply_bp_ceil(done_before + assignment.quantity_mg, line.percent_bp)
                        - apply_bp_ceil(done_before, line.percent_bp))
            _fefo_consume(ctx, line.material_id, quantity)
        ctx.writer.update("order_assignments", {"id": assignment_id}, {
            "completed_at": iso(dates.now()), "actual_pieces": actual_pieces,
        })
        machine = next(m for m in ctx.snapshot.machines if m.id == assignment.machine_id)
        return texts.h_production_completed(order.name, machine.name, format_int(actual_pieces))
    return _run(conn, "production_complete", body, confirm)


# ---------------------------------------------------------------- packaging


@dataclass(frozen=True, slots=True)
class StepSpec:
    """One step of a packaging plan as the user defines it."""

    kind: StepKind
    packaging_item_id: int
    role: StepRole | None = None
    units_per: int | None = None
    comes_ready: bool = False
    speed_per_min: Decimal | None = None
    extras: tuple[tuple[int, int], ...] = ()


def step_inputs(snapshot: Snapshot, steps: Sequence[StepSpec]) -> list[StepInput]:
    """Plan steps resolved with their packaging items, for the core calculations."""
    items = {p.id: p for p in snapshot.packaging_items}
    components: dict[int, list[tuple[int, int]]] = {}
    for c in snapshot.packaging_components:
        components.setdefault(c.packaging_item_id, []).append((c.material_id, c.percent_bp))
    return [
        StepInput(
            position=position,
            kind=step.kind,
            item_id=step.packaging_item_id,
            role=step.role if step.kind is StepKind.LEVEL else None,
            units_per=step.units_per if step.kind is StepKind.LEVEL else None,
            comes_ready=step.comes_ready,
            speed_per_min=None if step.comes_ready else step.speed_per_min,
            item_unit_weight_mg=items[step.packaging_item_id].unit_weight_mg if step.packaging_item_id in items else None,
            item_components=tuple(components.get(step.packaging_item_id, ())),
            extras=step.extras,
        )
        for position, step in enumerate(steps, start=1)
    ]


EXTRA_TYPES = frozenset({PackagingItemType.PACKAGING, PackagingItemType.LABEL})


def step_item_type(kind: StepKind, role: StepRole | None) -> PackagingItemType:
    """The packaging item type a step takes: labels for labelling, cartons and pallets for their roles."""
    if kind is StepKind.LABELLING:
        return PackagingItemType.LABEL
    if role is StepRole.CARTON:
        return PackagingItemType.CARTON
    if role is StepRole.PALLET:
        return PackagingItemType.PALLET
    return PackagingItemType.PACKAGING


def save_packaging_plan(
    conn: sqlite3.Connection,
    order_id: int,
    *,
    hours_per_day: Decimal,
    utilization_bp: int,
    steps: Sequence[StepSpec],
    confirm: bool = False,
) -> ActionResult:
    """Save the packaging plan of an order. Its packaging needs are then reserved by sequence."""
    def body(ctx: Context) -> str:
        order = _order(ctx, order_id)
        _require(_is_open(ctx, order), texts.ORDER_CLOSED)
        _positive(hours_per_day, texts.FIELDS["hours_per_day"])
        _require(hours_per_day <= 24, texts.field_range(texts.FIELDS["hours_per_day"], "0", "24"))
        _require(100 <= utilization_bp <= BP_FULL, texts.field_range(texts.FIELDS["utilization"], "1", "100"))
        types = {p.id: p.item_type for p in ctx.snapshot.packaging_items}
        _require(len(steps) <= MAX_STEPS, texts.PLAN_ISSUES["too_many_steps"])
        for number, step in enumerate(steps, start=1):
            _require(step.packaging_item_id in types, texts.field_required(texts.FIELDS["packaging_item"]))
            expected = step_item_type(step.kind, step.role)
            _require(types[step.packaging_item_id] is expected, texts.wrong_item_type(number, expected.value))
            for extra_id, _ in step.extras:
                _require(extra_id in types, texts.field_required(texts.FIELDS["extras"]))
                _require(types[extra_id] in EXTRA_TYPES, texts.wrong_extra_type(number))
        issues = validate_plan(step_inputs(ctx.snapshot, steps))
        if issues:
            raise ActionError(" ".join(texts.PLAN_ISSUES[issue.value] for issue in issues))

        old_steps = [s for s in ctx.snapshot.packaging_steps if s.order_id == order_id]
        old_step_ids = {s.id for s in old_steps}
        for extra in ctx.snapshot.packaging_step_extras:
            if extra.step_id in old_step_ids:
                ctx.writer.delete("packaging_step_extras", {"step_id": extra.step_id, "packaging_item_id": extra.packaging_item_id})
        for step in old_steps:
            ctx.writer.delete("packaging_steps", {"id": step.id})
        plan_values = {"hours_per_day": decimal_text(hours_per_day), "utilization_bp": utilization_bp,
                       "saved_at": iso(dates.now())}
        if any(p.order_id == order_id for p in ctx.snapshot.packaging_plans):
            ctx.writer.update("packaging_plans", {"order_id": order_id}, plan_values)
        else:
            ctx.writer.insert("packaging_plans", {"order_id": order_id, **plan_values})
        for position, step in enumerate(steps, start=1):
            is_level = step.kind is StepKind.LEVEL
            step_id = ctx.writer.insert("packaging_steps", {
                "order_id": order_id, "position": position, "kind": step.kind.value,
                "role": step.role.value if is_level and step.role else None,
                "packaging_item_id": step.packaging_item_id,
                "units_per": step.units_per if is_level else None,
                "comes_ready": 1 if step.comes_ready else 0,
                "speed_per_min": None if step.comes_ready else decimal_text(step.speed_per_min),
            })
            for extra_id, quantity in step.extras:
                ctx.writer.insert("packaging_step_extras", {
                    "step_id": step_id, "packaging_item_id": extra_id, "quantity_per_unit": quantity,
                })
        return texts.h_packaging_plan(order.name)
    return _run(conn, "packaging_plan", body, confirm)


def complete_packaging(conn: sqlite3.Connection, order_id: int, *, confirm: bool = False) -> ActionResult:
    """Take the packaging items and their materials from stock and create the shelf line (9.7)."""
    def body(ctx: Context) -> str:
        order = _order(ctx, order_id)
        _require(not order.is_cancelled, texts.ORDER_CLOSED)
        order_state = ctx.state.orders[order_id]
        _require(not order_state.packaging_completed, texts.PACKAGING_DONE)
        _require(order_state.production_completed, texts.PRODUCTION_NOT_DONE)
        result = order_state.packaging
        _require(result is not None, texts.NO_PLAN)
        assert result is not None
        _require(order_state.packaging_reserved or _reserved_counting_expired(ctx, order_id, packaging=True),
                 texts.MISSING_PACKAGING)

        items = {p.id: p for p in ctx.snapshot.packaging_items}
        for (kind, item_id), quantity in result.requirements.items():
            if kind is ItemKind.PACKAGING:
                current = ctx.conn.execute("SELECT quantity_pcs FROM packaging_items WHERE id = ?", (item_id,)).fetchone()[0]
                _require(current >= quantity, texts.NEGATIVE_STOCK)
                ctx.writer.update("packaging_items", {"id": item_id}, {"quantity_pcs": current - quantity})
            else:
                _fefo_consume(ctx, item_id, quantity)

        steps = sorted((s for s in ctx.snapshot.packaging_steps if s.order_id == order_id), key=lambda s: s.position)
        box_step = next(s for s in steps if s.kind is StepKind.LEVEL and s.role is StepRole.BOX)
        carton_step = next((s for s in steps if s.kind is StepKind.LEVEL and s.role is StepRole.CARTON), None)
        pallet_step = next((s for s in steps if s.kind is StepKind.LEVEL and s.role is StepRole.PALLET), None)
        ctx.writer.insert("shelf_lines", {
            "order_id": order_id, "boxes": result.boxes, "pieces_per_box": result.pieces_per_box,
            "boxes_per_carton": result.boxes_per_carton, "box_item_id": box_step.packaging_item_id,
            "carton_item_id": carton_step.packaging_item_id if carton_step else None,
            "cartons_per_pallet": result.cartons_per_pallet,
            "pallet_item_id": pallet_step.packaging_item_id if pallet_step else None,
            "created_at": iso(dates.now()),
        })
        ctx.writer.update("packaging_plans", {"order_id": order_id}, {"completed_at": iso(dates.now())})
        _compact_sequence(ctx, excluding=order_id)

        leftovers: list[str] = []
        previous_name: str | None = None
        for step, step_result in zip(steps, result.steps):
            if step.kind is not StepKind.LEVEL:
                continue
            if step_result.leftover:
                unit = texts.UNIT_PIECES if previous_name is None else previous_name
                leftovers.append(f"{format_int(step_result.leftover)} {unit}")
            if step.role is StepRole.BOX:
                break
            previous_name = items[step.packaging_item_id].name
        return texts.h_packaging_completed(order.name, format_int(result.boxes), leftovers)
    return _run(conn, "packaging_complete", body, confirm)


# ---------------------------------------------------------------- receipts


def _receipt_item(ctx: Context, kind: ItemKind, item_id: int) -> tuple[str, dict[str, Any]]:
    """Display name of the item and the receipt columns that point to it."""
    if kind is ItemKind.MATERIAL:
        material = next((m for m in ctx.snapshot.materials if m.id == item_id), None)
        _require(material is not None, texts.field_required(texts.FIELDS["item"]))
        assert material is not None
        return material.name, {"material_id": item_id, "packaging_item_id": None}
    item = next((p for p in ctx.snapshot.packaging_items if p.id == item_id), None)
    _require(item is not None, texts.field_required(texts.FIELDS["item"]))
    assert item is not None
    return item.name, {"material_id": None, "packaging_item_id": item_id}


def format_receipt_quantity(kind: ItemKind, quantity: int) -> str:
    """Quantity with its unit: kg for a material, pieces for packaging."""
    if kind is ItemKind.MATERIAL:
        return f"{format_kg(quantity)} {texts.UNIT_KG}"
    return f"{format_int(quantity)} {texts.UNIT_PCS}"


def create_receipt(
    conn: sqlite3.Connection, *, kind: ItemKind, item_id: int, quantity: int, receipt_date: date,
    confirm: bool = False,
) -> ActionResult:
    def body(ctx: Context) -> str:
        name, refs = _receipt_item(ctx, ItemKind(kind), item_id)
        _positive(quantity, texts.FIELDS["quantity"])
        _require(receipt_date is not None, texts.field_required(texts.FIELDS["receipt_date"]))
        ctx.value = ctx.writer.insert("receipts", {
            "kind": ItemKind(kind).value, **refs, "quantity": quantity, "receipt_date": iso(receipt_date),
        })
        return texts.h_receipt_created(name, format_receipt_quantity(ItemKind(kind), quantity))
    return _run(conn, "receipt_create", body, confirm)


def update_receipt(
    conn: sqlite3.Connection, receipt_id: int, *, kind: ItemKind, item_id: int, quantity: int,
    receipt_date: date, confirm: bool = False,
) -> ActionResult:
    def body(ctx: Context) -> str:
        receipt = next(r for r in ctx.snapshot.receipts if r.id == receipt_id)
        _require(not receipt.is_received, texts.RECEIPT_ALREADY_RECEIVED)
        name, refs = _receipt_item(ctx, ItemKind(kind), item_id)
        _positive(quantity, texts.FIELDS["quantity"])
        _require(receipt_date is not None, texts.field_required(texts.FIELDS["receipt_date"]))
        ctx.writer.update("receipts", {"id": receipt_id}, {
            "kind": ItemKind(kind).value, **refs, "quantity": quantity, "receipt_date": iso(receipt_date),
        })
        return texts.h_receipt_updated(name)
    return _run(conn, "receipt_update", body, confirm)


def delete_receipt(conn: sqlite3.Connection, receipt_id: int, *, confirm: bool = False) -> ActionResult:
    def body(ctx: Context) -> str:
        receipt = next(r for r in ctx.snapshot.receipts if r.id == receipt_id)
        _require(not receipt.is_received, texts.RECEIPT_ALREADY_RECEIVED)
        item_id = receipt.material_id if receipt.kind is ItemKind.MATERIAL else receipt.packaging_item_id
        name, _ = _receipt_item(ctx, receipt.kind, item_id or 0)
        ctx.writer.delete("receipts", {"id": receipt_id})
        return texts.h_receipt_deleted(name)
    return _run(conn, "receipt_delete", body, confirm)


def mark_received(
    conn: sqlite3.Connection,
    receipt_id: int,
    *,
    quantity: int,
    receipt_date: date,
    lot_number: str | None = None,
    expiry_date: date | None = None,
    confirm: bool = False,
) -> ActionResult:
    """Confirm a receipt: a new LOT for a material, more pieces for packaging (10.1)."""
    def body(ctx: Context) -> str:
        receipt = next(r for r in ctx.snapshot.receipts if r.id == receipt_id)
        _require(not receipt.is_received, texts.RECEIPT_ALREADY_RECEIVED)
        _positive(quantity, texts.FIELDS["quantity"])
        _require(receipt_date is not None, texts.field_required(texts.FIELDS["receipt_date"]))
        values: dict[str, Any] = {
            "received_at": iso(dates.now()), "received_quantity": quantity, "receipt_date": iso(receipt_date),
        }
        lot_clean = None
        if receipt.kind is ItemKind.MATERIAL:
            assert receipt.material_id is not None
            name, _ = _receipt_item(ctx, receipt.kind, receipt.material_id)
            lot_clean = _text(lot_number, texts.FIELDS["lot_number"])
            values["lot_id"] = _insert_lot(ctx, receipt.material_id, lot_clean, quantity, expiry_date)
        else:
            assert receipt.packaging_item_id is not None
            name, _ = _receipt_item(ctx, receipt.kind, receipt.packaging_item_id)
            current = ctx.conn.execute("SELECT quantity_pcs FROM packaging_items WHERE id = ?",
                                       (receipt.packaging_item_id,)).fetchone()[0]
            ctx.writer.update("packaging_items", {"id": receipt.packaging_item_id}, {"quantity_pcs": current + quantity})
        ctx.writer.update("receipts", {"id": receipt_id}, values)
        return texts.h_received(name, format_receipt_quantity(receipt.kind, quantity), lot_clean)
    return _run(conn, "receipt_received", body, confirm)


# ---------------------------------------------------------------- shelf and shipments


def _shelf_names(ctx: Context, line_id: int) -> tuple[str, Order]:
    line = next(l for l in ctx.snapshot.shelf_lines if l.id == line_id)
    order = _order(ctx, line.order_id)
    product = next(p for p in ctx.snapshot.products if p.id == order.product_id)
    return product.name, order


def create_shipment(
    conn: sqlite3.Connection, *, shelf_line_id: int, boxes: int, completion_date: date | None = None,
    shipment_date: date | None = None, confirm: bool = False,
) -> ActionResult:
    def body(ctx: Context) -> str:
        line = next(l for l in ctx.snapshot.shelf_lines if l.id == shelf_line_id)
        _require(not line.is_deleted, texts.field_required(texts.FIELDS["shelf_line"]))
        _positive(boxes, texts.FIELDS["boxes"])
        free = ctx.state.shelf_lines[shelf_line_id].free_boxes
        _require(boxes <= free, texts.boxes_over_free(format_int(free)))
        ctx.value = ctx.writer.insert("shipments", {
            "shelf_line_id": shelf_line_id, "boxes": boxes, "completion_date": iso(completion_date),
            "shipment_date": iso(shipment_date),
        })
        product, order = _shelf_names(ctx, shelf_line_id)
        return texts.h_shipment_created(product, order.name, format_int(boxes))
    return _run(conn, "shipment_create", body, confirm)


def update_shipment(
    conn: sqlite3.Connection, shipment_id: int, *, boxes: int, completion_date: date | None = None,
    shipment_date: date | None = None, confirm: bool = False,
) -> ActionResult:
    def body(ctx: Context) -> str:
        shipment = next(s for s in ctx.snapshot.shipments if s.id == shipment_id)
        _require(not shipment.is_shipped, texts.SHIPMENT_ALREADY_SHIPPED)
        _positive(boxes, texts.FIELDS["boxes"])
        free = ctx.state.shelf_lines[shipment.shelf_line_id].free_boxes + shipment.boxes
        _require(boxes <= free, texts.boxes_over_free(format_int(free)))
        ctx.writer.update("shipments", {"id": shipment_id}, {
            "boxes": boxes, "completion_date": iso(completion_date), "shipment_date": iso(shipment_date),
        })
        product, order = _shelf_names(ctx, shipment.shelf_line_id)
        return texts.h_shipment_updated(product, order.name)
    return _run(conn, "shipment_update", body, confirm)


def delete_shipment(conn: sqlite3.Connection, shipment_id: int, *, confirm: bool = False) -> ActionResult:
    def body(ctx: Context) -> str:
        shipment = next(s for s in ctx.snapshot.shipments if s.id == shipment_id)
        _require(not shipment.is_shipped, texts.SHIPMENT_ALREADY_SHIPPED)
        ctx.writer.delete("shipments", {"id": shipment_id})
        product, order = _shelf_names(ctx, shipment.shelf_line_id)
        return texts.h_shipment_deleted(product, order.name)
    return _run(conn, "shipment_delete", body, confirm)


def mark_shipped(
    conn: sqlite3.Connection, shipment_id: int, *, boxes: int, completion_date: date | None = None,
    shipment_date: date | None = None, confirm: bool = False,
) -> ActionResult:
    """Boxes leave the shelf. If fewer left than registered, the rest stay on the shelf as free."""
    def body(ctx: Context) -> str:
        shipment = next(s for s in ctx.snapshot.shipments if s.id == shipment_id)
        _require(not shipment.is_shipped, texts.SHIPMENT_ALREADY_SHIPPED)
        line = next(l for l in ctx.snapshot.shelf_lines if l.id == shipment.shelf_line_id)
        _positive(boxes, texts.FIELDS["boxes"])
        free = ctx.state.shelf_lines[line.id].free_boxes + shipment.boxes
        _require(boxes <= free, texts.boxes_over_free(format_int(free)))
        _require(boxes <= line.boxes, texts.boxes_over_line(format_int(line.boxes)))
        ctx.writer.update("shipments", {"id": shipment_id}, {
            "boxes": boxes, "completion_date": iso(completion_date), "shipment_date": iso(shipment_date),
            "shipped_at": iso(dates.now()),
        })
        ctx.writer.update("shelf_lines", {"id": line.id}, {"boxes": line.boxes - boxes})
        product, order = _shelf_names(ctx, line.id)
        return texts.h_shipped(product, order.name, format_int(boxes))
    return _run(conn, "shipment_shipped", body, confirm)


def transfer_boxes(
    conn: sqlite3.Connection, *, from_line_id: int, to_line_id: int, boxes: int, confirm: bool = False,
) -> ActionResult:
    """Move free boxes between shelf lines of the same product and packing (5.3)."""
    def body(ctx: Context) -> str:
        _require(from_line_id != to_line_id, texts.TRANSFER_SAME_LINE)
        lines = {l.id: l for l in ctx.snapshot.shelf_lines}
        source, target = lines[from_line_id], lines[to_line_id]
        _require(not source.is_deleted and not target.is_deleted, texts.TRANSFER_MISMATCH)
        source_product, source_order = _shelf_names(ctx, from_line_id)
        _, target_order = _shelf_names(ctx, to_line_id)
        _require(
            source_order.product_id == target_order.product_id
            and source.pieces_per_box == target.pieces_per_box
            and source.boxes_per_carton == target.boxes_per_carton,
            texts.TRANSFER_MISMATCH,
        )
        _positive(boxes, texts.FIELDS["boxes"])
        free = ctx.state.shelf_lines[from_line_id].free_boxes
        _require(boxes <= free, texts.boxes_over_free(format_int(free)))
        ctx.writer.update("shelf_lines", {"id": from_line_id}, {"boxes": source.boxes - boxes})
        ctx.writer.update("shelf_lines", {"id": to_line_id}, {"boxes": target.boxes + boxes})
        ctx.writer.insert("shelf_transfers", {
            "from_line_id": from_line_id, "to_line_id": to_line_id, "boxes": boxes,
            "transferred_on": iso(ctx.today),
        })
        return texts.h_transfer(format_int(boxes), source_product, source_order.destination, target_order.destination)
    return _run(conn, "shelf_transfer", body, confirm)


def delete_shelf_line(conn: sqlite3.Connection, line_id: int, *, confirm: bool = False) -> ActionResult:
    """Hide a shelf line with 0 boxes. Its order keeps its status and its shipments."""
    def body(ctx: Context) -> str:
        line = next(l for l in ctx.snapshot.shelf_lines if l.id == line_id)
        _require(line.boxes == 0, texts.SHELF_NOT_EMPTY)
        ctx.writer.update("shelf_lines", {"id": line_id}, {"deleted_at": iso(dates.now())})
        product, order = _shelf_names(ctx, line_id)
        return texts.h_shelf_deleted(product, order.name)
    return _run(conn, "shelf_delete", body, confirm)


# ---------------------------------------------------------------- settings


def update_settings(conn: sqlite3.Connection, settings: Settings, *, confirm: bool = False) -> ActionResult:
    def body(ctx: Context) -> str:
        _positive(settings.yellow_days, texts.FIELDS["yellow_days"])
        _not_negative(settings.red_days, texts.FIELDS["red_days"])
        _require(settings.red_days < settings.yellow_days, texts.RED_NOT_BELOW_YELLOW)
        _require(bool(settings.working_days) and settings.working_days <= set(range(7)), texts.NO_WORKING_DAYS)
        _positive(settings.machine_hours_per_day, texts.FIELDS["machine_hours"])
        _require(settings.machine_hours_per_day <= 24,
                 texts.field_range(texts.FIELDS["machine_hours"], "0", "24"))
        _not_negative(settings.default_transit_days, texts.FIELDS["transit_days"])
        _positive(settings.packaging_hours_per_day, texts.FIELDS["packaging_hours"])
        _require(settings.packaging_hours_per_day <= 24,
                 texts.field_range(texts.FIELDS["packaging_hours"], "0", "24"))
        _require(100 <= settings.packaging_utilization_bp <= BP_FULL,
                 texts.field_range(texts.FIELDS["packaging_utilization"], "1", "100"))
        for key, value in settings_rows(settings).items():
            if ctx.conn.execute("SELECT 1 FROM settings WHERE key = ?", (key,)).fetchone():
                ctx.writer.update("settings", {"key": key}, {"value": value})
            else:
                ctx.writer.insert("settings", {"key": key, "value": value})
        return texts.H_SETTINGS
    return _run(conn, "settings_update", body, confirm)
