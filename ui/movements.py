"""Tab 6: Receipts and shipments. What comes in and what leaves (section 10)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.models import ItemKind, PackagingItemType, material_key, packaging_key
from core.state import ReceiptStatus
from core.units import format_cm, format_int, kg_to_mg, mg_to_kg
from data import actions
from ui import common, texts
from ui.common import STATUS_COLOURS, Fields, Page, Table, widget_key
from ui.warehouse import shelf_rows

KIND_LABELS = common.Lazy(lambda: {ItemKind.MATERIAL: texts.KIND_MATERIAL, ItemKind.PACKAGING: texts.KIND_PACKAGING})

# What the user picks in a receipt: a material, a packaging item (incl. cartons
# and pallets) or a label. Labels are packaging items in the data.
RECEIPT_CHOICES = ("material", "packaging", "label")
RECEIPT_CHOICE_LABELS = common.Lazy(lambda: {"material": texts.KIND_MATERIAL, "packaging": texts.KIND_PACKAGING,
                         "label": texts.KIND_LABEL})


def _receipt_choice(page: Page, receipt) -> str:
    if receipt.kind is ItemKind.MATERIAL:
        return "material"
    item = next((p for p in page.snapshot.packaging_items if p.id == receipt.packaging_item_id), None)
    return "label" if item is not None and item.item_type is PackagingItemType.LABEL else "packaging"


def render(page: Page) -> None:
    _receipts(page)
    st.divider()
    _ready(page)
    st.divider()
    _shipments(page)


# ---------------------------------------------------------------- receipts


def _item_label(page: Page, kind: ItemKind, item_id: int | None) -> str:
    items = page.snapshot.materials if kind is ItemKind.MATERIAL else page.snapshot.packaging_items
    item = next((i for i in items if i.id == item_id), None)
    return f"{item.name} ({item.code})" if item else ""


def _receipts(page: Page) -> None:
    st.subheader(texts.RC_TITLE, anchor=False)
    bar = st.container()
    lots = {lot.id: lot.lot_number for lot in page.snapshot.lots}
    table = Table([texts.COL_TYPE, texts.COL_KIND_ITEM, texts.COL_QUANTITY, texts.COL_STATUS, texts.COL_RECEIVED,
                   texts.COL_RECEIVED_QUANTITY, texts.COL_LOT_NUMBER, texts.COL_RECEIPT_DATE],
                  checkboxes=(texts.COL_RECEIVED,))
    table.formats = {texts.COL_RECEIPT_DATE: common.date_format}
    table.colour_column(texts.COL_STATUS)
    for receipt in page.snapshot.receipts:
        receipt_state = page.state.receipts[receipt.id]
        item_id = receipt.material_id if receipt.kind is ItemKind.MATERIAL else receipt.packaging_item_id
        if receipt_state.status is ReceiptStatus.RECEIVED:
            status, colour = texts.RECEIPT_RECEIVED, STATUS_COLOURS["ok"]
        elif receipt_state.status is ReceiptStatus.DELAYED:
            status, colour = texts.receipt_delayed(receipt_state.delay_days), STATUS_COLOURS["bad"]
        else:
            status, colour = texts.RECEIPT_EXPECTED, STATUS_COLOURS["info"]
        number = common.kg_unit_format if receipt.kind is ItemKind.MATERIAL else common.int_format
        table.add(receipt.id, [
            RECEIPT_CHOICE_LABELS[_receipt_choice(page, receipt)], _item_label(page, receipt.kind, item_id),
            receipt.quantity, status,
            receipt.is_received, receipt.received_quantity, lots.get(receipt.lot_id, "") if receipt.lot_id else "",
            common.as_date(receipt.receipt_date),
        ], {texts.COL_STATUS: colour},
            {texts.COL_QUANTITY: number, texts.COL_RECEIVED_QUANTITY: number})
    # Expected receipts first, nearest date on top; received ones after them.
    table.sort(lambda row: (row[4], row[7]))
    selected = common.show_table(page, "receipts", table)
    with bar:
        pressed = common.toolbar([texts.RC_ADD, texts.EDIT, texts.DELETE, texts.RC_RECEIVED], "receipts")
        if pressed == texts.RC_ADD:
            common.open_dialog("receipt_form")
        elif pressed == texts.EDIT and common.need_selection(selected):
            common.open_dialog("receipt_form", receipt_id=selected)
        elif pressed == texts.DELETE and common.need_selection(selected):
            receipt = next(r for r in page.snapshot.receipts if r.id == selected)
            item_id = receipt.material_id if receipt.kind is ItemKind.MATERIAL else receipt.packaging_item_id
            common.confirm_action(texts.CONFIRM_DELETE_TITLE,
                                  texts.confirm_delete(_item_label(page, receipt.kind, item_id)),
                                  actions.delete_receipt, selected)
        elif pressed == texts.RC_RECEIVED and common.need_selection(selected):
            common.open_dialog("receipt_received", receipt_id=selected)
    if selected is not None and page.state.receipts[selected].status is ReceiptStatus.DELAYED:
        _waiting_orders(page, selected)


def _waiting_orders(page: Page, receipt_id: int) -> None:
    """Orders that wait for the item of a late receipt (10.1)."""
    receipt = next(r for r in page.snapshot.receipts if r.id == receipt_id)
    key = (material_key(receipt.material_id) if receipt.kind is ItemKind.MATERIAL
           else packaging_key(receipt.packaging_item_id))
    st.markdown(f"**{texts.WAITING_FOR_ITEM}**")
    names = []
    for order in page.snapshot.orders:
        order_state = page.state.orders[order.id]
        short = [l for l in order_state.recipe_lines if l.key == key and l.shortage and not order_state.recipe_reserved]
        short += [l for l in order_state.packaging_lines if l.key == key and l.shortage
                  and not order_state.packaging_reserved]
        if short:
            names.append(f"{order.name}, {order.destination}: {common.quantity_text(key, short[0].shortage)}")
    for name in names:
        st.write(name)
    if not names:
        st.caption(texts.NO_WAITING_ORDERS)


def _receipt_title(page: Page, params: dict[str, Any]) -> str:
    return texts.T_EDIT_RECEIPT if params.get("receipt_id") else texts.T_NEW_RECEIPT


@common.dialog("receipt_form", _receipt_title)
def receipt_form(page: Page, params: dict[str, Any]) -> None:
    """An expected receipt: always chosen from the warehouse items, never free text."""
    if common.confirmation_pending(page, params):
        return
    receipt = next((r for r in page.snapshot.receipts if r.id == params.get("receipt_id")), None)
    choice = st.radio(texts.F_TYPE, RECEIPT_CHOICES,
                      index=RECEIPT_CHOICES.index(_receipt_choice(page, receipt)) if receipt else 0,
                      format_func=RECEIPT_CHOICE_LABELS.get, horizontal=True, key=widget_key(params, "kind"))
    kind = ItemKind.MATERIAL if choice == "material" else ItemKind.PACKAGING
    if kind is ItemKind.MATERIAL:
        options = {m.id: f"{m.name} ({m.code})" for m in sorted(page.snapshot.materials, key=lambda m: m.name.casefold())
                   if not m.is_deleted}
        current = receipt.material_id if receipt else None
    else:
        wanted_label = choice == "label"
        options = {p.id: f"{p.name} ({p.code})" for p in sorted(page.snapshot.packaging_items,
                                                                key=lambda p: p.name.casefold())
                   if not p.is_deleted and (p.item_type is PackagingItemType.LABEL) == wanted_label}
        current = receipt.packaging_item_id if receipt else None
    ids = list(options)
    item_id = st.selectbox(texts.F_ITEM, ids, index=ids.index(current) if current in ids else None,
                           format_func=options.get, key=widget_key(params, f"item:{choice}"),
                           placeholder=texts.F_ITEM)
    columns = st.columns(3)
    if columns[0].button(texts.T_NEW_MATERIAL, key=widget_key(params, "new_material")):
        common.open_dialog("material_form")
    if columns[1].button(texts.T_NEW_PACKAGING, key=widget_key(params, "new_packaging")):
        common.open_dialog("packaging_form")
    if columns[2].button(texts.T_NEW_LABEL, key=widget_key(params, "new_label")):
        common.open_dialog("label_form")
    fields = Fields()
    same_kind = receipt is not None and receipt.kind is kind
    if kind is ItemKind.MATERIAL:
        quantity = fields.stored(texts.F_QUANTITY, widget_key(params, "quantity:kg"), kg_to_mg, mg_to_kg,
                                 receipt.quantity if same_kind else None, texts.UNIT_KG)
    else:
        quantity = fields.whole(texts.F_QUANTITY, widget_key(params, "quantity:pcs"),
                                receipt.quantity if same_kind else None, texts.UNIT_PCS)
    st.caption(texts.unit_of(texts.UNIT_KG if kind is ItemKind.MATERIAL else texts.UNIT_PCS))
    receipt_date = common.date_field(texts.F_RECEIPT_DATE, widget_key(params, "date"),
                                     receipt.receipt_date if receipt else None)
    if common.form_buttons(params) and fields.ok():
        if item_id is None:
            st.error(texts.field_required(texts.F_ITEM))
            return
        if receipt is None:
            common.run_action(page, params, actions.create_receipt, kind=kind, item_id=item_id,
                              quantity=quantity, receipt_date=receipt_date)
        else:
            common.run_action(page, params, actions.update_receipt, receipt.id, kind=kind, item_id=item_id,
                              quantity=quantity, receipt_date=receipt_date)


@common.dialog("receipt_received", "T_RECEIVED")
def receipt_received(page: Page, params: dict[str, Any]) -> None:
    """Confirm what actually arrived: a new LOT for a material, more pieces for packaging."""
    if common.confirmation_pending(page, params):
        return
    receipt = next(r for r in page.snapshot.receipts if r.id == params["receipt_id"])
    item_id = receipt.material_id if receipt.kind is ItemKind.MATERIAL else receipt.packaging_item_id
    st.caption(_item_label(page, receipt.kind, item_id))
    fields = Fields()
    lot_number = expiry = None
    if receipt.kind is ItemKind.MATERIAL:
        quantity = fields.stored(texts.F_QUANTITY, widget_key(params, "quantity"), kg_to_mg, mg_to_kg,
                                 receipt.quantity, texts.UNIT_KG)
        lot_number = st.text_input(texts.F_LOT_NUMBER, key=widget_key(params, "lot"))
        expiry = common.date_field(texts.F_EXPIRY, widget_key(params, "expiry"), required=False)
    else:
        quantity = fields.whole(texts.F_QUANTITY, widget_key(params, "quantity"), receipt.quantity, texts.UNIT_PCS)
    receipt_date = common.date_field(texts.F_RECEIPT_DATE, widget_key(params, "date"), page.snapshot.today)
    if common.form_buttons(params, texts.RC_RECEIVED) and fields.ok():
        common.run_action(page, params, actions.mark_received, receipt.id, quantity=quantity,
                          receipt_date=receipt_date, lot_number=lot_number, expiry_date=expiry)


# ---------------------------------------------------------------- ready for shipment and shipments


def _dims(page: Page, item_id: int | None) -> str:
    item = next((p for p in page.snapshot.packaging_items if p.id == item_id), None)
    dims = item.dimensions_mm if item else None
    return " × ".join(format_cm(d) for d in dims) if dims else ""


def _outer_dims(page: Page, item_id: int | None) -> str:
    """A carton is shipped by its outer size; older cartons without one show their inner size."""
    item = next((p for p in page.snapshot.packaging_items if p.id == item_id), None)
    dims = (item.outer_dimensions_mm or item.dimensions_mm) if item else None
    return " \u00d7 ".join(format_cm(d) for d in dims) if dims else ""


def _box_format(dims: str):
    return lambda value: texts.boxes_cell(format_int(int(value)), dims)


def _carton_format(dims: str, loose: int):
    return lambda value: texts.cartons_cell(format_int(int(value)), dims, format_int(loose))


def _ready(page: Page) -> None:
    """Every shelf line with free boxes: each order that went through production and packaging (10.2)."""
    st.subheader(texts.READY_TITLE, anchor=False)
    table = Table([texts.COL_PRODUCT, texts.COL_ORDER_AND_DESTINATION, texts.COL_PALLETS, texts.COL_CARTONS,
                   texts.COL_BOXES, texts.COL_BOXES_PER_CARTON, texts.COL_FREE_BOXES, texts.COL_SHIP_BY])
    table.formats = {texts.COL_BOXES_PER_CARTON: common.int_format, texts.COL_FREE_BOXES: common.int_format,
                     texts.COL_SHIP_BY: common.date_format}
    for line, line_state, order, product in shelf_rows(page):
        if line_state.free_boxes <= 0:
            continue
        table.add(line.id, [
            product.name, f"{order.name}, {order.destination}", line_state.pallets, line_state.cartons, line.boxes,
            line.boxes_per_carton, line_state.free_boxes, common.as_date(page.state.orders[order.id].ship_by),
        ], formats={
            texts.COL_PALLETS: common.pallets_format(line_state.last_pallet_cartons),
            texts.COL_CARTONS: _carton_format(_outer_dims(page, line.carton_item_id), line_state.loose_boxes),
            texts.COL_BOXES: _box_format(_dims(page, line.box_item_id)),
        })
    table.sort(lambda row: (row[7], row[1]))
    common.show_table(page, "ready", table, selectable=False)


def _shipments(page: Page) -> None:
    st.subheader(texts.SH_TITLE, anchor=False)
    bar = st.container()
    lines = {line.id: (line, state, order, product) for line, state, order, product in shelf_rows(page)}
    all_lines = {l.id: l for l in page.snapshot.shelf_lines}
    orders = {o.id: o for o in page.snapshot.orders}
    products = {p.id: p for p in page.snapshot.products}
    table = Table([texts.COL_PRODUCT, texts.COL_ORDER_AND_DESTINATION, texts.COL_BOXES, texts.COL_CARTONS,
                   texts.COL_BOXES_PER_CARTON, texts.COL_PALLETS, texts.COL_LOOSE_BOXES, texts.COL_STATUS,
                   texts.COL_SHIPPED,
                   texts.COL_COMPLETION_DATE, texts.COL_SHIPMENT_DATE], checkboxes=(texts.COL_SHIPPED,))
    table.formats = {texts.COL_BOXES_PER_CARTON: common.int_format, texts.COL_LOOSE_BOXES: common.int_format,
                     texts.COL_COMPLETION_DATE: common.date_format, texts.COL_SHIPMENT_DATE: common.date_format}
    table.colour_column(texts.COL_STATUS)
    for shipment in page.snapshot.shipments:
        line = all_lines[shipment.shelf_line_id]
        order = orders[line.order_id]
        shipment_state = page.state.shipments[shipment.id]
        status = texts.SHIPMENT_SHIPPED if shipment.is_shipped else texts.SHIPMENT_PENDING
        colour = STATUS_COLOURS["ok"] if shipment.is_shipped else STATUS_COLOURS["info"]
        table.add(shipment.id, [
            products[order.product_id].name, f"{order.name}, {order.destination}", shipment.boxes,
            shipment_state.cartons, line.boxes_per_carton, shipment_state.pallets, shipment_state.loose_boxes,
            status, shipment.is_shipped,
            common.as_date(shipment.completion_date), common.as_date(shipment.shipment_date),
        ], {texts.COL_STATUS: colour}, {
            texts.COL_BOXES: _box_format(_dims(page, line.box_item_id)),
            texts.COL_CARTONS: lambda v, d=_outer_dims(page, line.carton_item_id): (
                f"{format_int(int(v))}, {d} cm" if d else format_int(int(v))),
            texts.COL_PALLETS: common.pallets_format(shipment_state.last_pallet_cartons),
        })
    # Pending shipments first.
    table.sort(lambda row: (row[8], row[1]))
    selected = common.show_table(page, "shipments", table)
    with bar:
        pressed = common.toolbar([texts.SH_ADD, texts.EDIT, texts.DELETE, texts.SH_SHIPPED], "shipments")
        if pressed == texts.SH_ADD:
            if not any(state.free_boxes > 0 for _, state, _, _ in lines.values()):
                st.warning(texts.NO_FREE_LINES)
            else:
                common.open_dialog("shipment_form")
        elif pressed == texts.EDIT and common.need_selection(selected):
            common.open_dialog("shipment_form", shipment_id=selected)
        elif pressed == texts.DELETE and common.need_selection(selected):
            shipment = next(s for s in page.snapshot.shipments if s.id == selected)
            order = orders[all_lines[shipment.shelf_line_id].order_id]
            common.confirm_action(texts.CONFIRM_DELETE_TITLE, texts.confirm_delete(f"{order.name}, {order.destination}"),
                                  actions.delete_shipment, selected)
        elif pressed == texts.SH_SHIPPED and common.need_selection(selected):
            common.open_dialog("shipment_shipped", shipment_id=selected)


def _cartons_note(boxes: int | None, per_carton: int | None) -> None:
    if boxes and per_carton:
        st.caption(texts.cartons_note(format_int(boxes), format_int(boxes // per_carton), format_int(per_carton)))


def _shipment_title(page: Page, params: dict[str, Any]) -> str:
    return texts.T_EDIT_SHIPMENT if params.get("shipment_id") else texts.T_NEW_SHIPMENT


@common.dialog("shipment_form", _shipment_title)
def shipment_form(page: Page, params: dict[str, Any]) -> None:
    """Choose a shelf line and the boxes to send; the boxes are prefilled with the free ones."""
    if common.confirmation_pending(page, params):
        return
    shipment = next((s for s in page.snapshot.shipments if s.id == params.get("shipment_id")), None)
    lines = {line.id: (line, state, order, product) for line, state, order, product in shelf_rows(page)}
    if shipment is None:
        options = {lid: f"{p.name}, {o.name}, {o.destination}" for lid, (l, s, o, p) in lines.items() if s.free_boxes > 0}
        line_id = st.selectbox(texts.F_SHELF_LINE, list(options), format_func=options.get,
                               key=widget_key(params, "line"))
        free = lines[line_id][1].free_boxes
    else:
        line_id = shipment.shelf_line_id
        line, state, order, product = lines[line_id]
        st.caption(f"{product.name}, {order.name}, {order.destination}")
        free = state.free_boxes + shipment.boxes
    line = lines[line_id][0]
    fields = Fields()
    boxes = fields.whole(texts.F_BOXES, widget_key(params, f"boxes:{line_id}"),
                         shipment.boxes if shipment else free, texts.UNIT_BOXES)
    _cartons_note(boxes, line.boxes_per_carton)
    completion = common.date_field(texts.F_COMPLETION_DATE, widget_key(params, "completion"),
                                   shipment.completion_date if shipment else None, required=False)
    shipped_on = common.date_field(texts.F_SHIPMENT_DATE, widget_key(params, "shipped_on"),
                                   shipment.shipment_date if shipment else None, required=False)
    if common.form_buttons(params) and fields.ok():
        if shipment is None:
            common.run_action(page, params, actions.create_shipment, shelf_line_id=line_id, boxes=boxes,
                              completion_date=completion, shipment_date=shipped_on)
        else:
            common.run_action(page, params, actions.update_shipment, shipment.id, boxes=boxes,
                              completion_date=completion, shipment_date=shipped_on)


@common.dialog("shipment_shipped", "T_SHIPPED")
def shipment_shipped(page: Page, params: dict[str, Any]) -> None:
    """Confirm the shipment, correcting boxes and dates if needed."""
    if common.confirmation_pending(page, params):
        return
    shipment = next(s for s in page.snapshot.shipments if s.id == params["shipment_id"])
    line = next(l for l in page.snapshot.shelf_lines if l.id == shipment.shelf_line_id)
    fields = Fields()
    boxes = fields.whole(texts.F_BOXES, widget_key(params, "boxes"), shipment.boxes, texts.UNIT_BOXES)
    _cartons_note(boxes, line.boxes_per_carton)
    completion = common.date_field(texts.F_COMPLETION_DATE, widget_key(params, "completion"),
                                   shipment.completion_date, required=False)
    shipped_on = common.date_field(texts.F_SHIPMENT_DATE, widget_key(params, "shipped_on"),
                                   shipment.shipment_date or page.snapshot.today, required=False)
    if common.form_buttons(params, texts.SH_SHIPPED) and fields.ok():
        common.run_action(page, params, actions.mark_shipped, shipment.id, boxes=boxes,
                          completion_date=completion, shipment_date=shipped_on)
