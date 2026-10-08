"""Tab 1: Warehouse. Materials and their LOTs, packaging items, and the finished-goods shelf (section 5)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import streamlit as st

from core.models import ItemKind, MaterialCategory, PackagingItem, PackagingItemType
from core.units import (
    format_cm,
    format_date,
    format_g,
    format_int,
    format_number,
    format_percent,
    g_to_mg,
    cm_to_mm,
    kg_to_mg,
    mg_to_g,
    mg_to_kg,
    mm_to_cm,
    percent_to_bp,
    bp_to_percent,
)
from data import actions
from ui import common, texts
from ui.common import Fields, Page, Table, widget_key


def render(page: Page) -> None:
    _materials(page)
    st.divider()
    _lots(page)
    st.divider()
    _packaging(page)
    st.divider()
    _labels(page)
    st.divider()
    _shelf(page)


# ---------------------------------------------------------------- materials


def _materials(page: Page) -> None:
    st.subheader(texts.WH_MATERIALS, anchor=False)
    bar = st.container()
    table = Table([texts.COL_CODE, texts.COL_NAME, texts.COL_CATEGORY, texts.COL_TOTAL_KG,
                   texts.COL_RESERVED_KG, texts.COL_AVAILABLE_KG, texts.COL_EXPECTED, texts.COL_INDICATOR])
    table.formats = {c: common.kg_format for c in (texts.COL_TOTAL_KG, texts.COL_RESERVED_KG, texts.COL_AVAILABLE_KG)}
    for material in page.snapshot.materials:
        if material.is_deleted:
            continue
        stock = page.state.materials[material.id]
        table.add(material.id, [
            material.code, material.name, common.CATEGORY_LABELS[material.category], stock.total,
            stock.reserved, stock.available, common.expected_text(stock.expected, ItemKind.MATERIAL),
            texts.DEPLETED if stock.depleted else "",
        ])
    table.sort(lambda row: row[1].casefold())
    selected = common.show_table(page, "materials", table)
    with bar:
        pressed = common.toolbar([texts.WH_ADD_MATERIAL, texts.EDIT, texts.WH_ADD_LOT, texts.DELETE], "materials")
        if pressed == texts.WH_ADD_MATERIAL:
            common.open_dialog("material_form")
        elif pressed == texts.EDIT and common.need_selection(selected):
            common.open_dialog("material_form", material_id=selected)
        elif pressed == texts.WH_ADD_LOT and common.need_selection(selected):
            common.open_dialog("lot_form", material_id=selected)
        elif pressed == texts.DELETE and common.need_selection(selected):
            material = next(m for m in page.snapshot.materials if m.id == selected)
            common.confirm_action(texts.CONFIRM_DELETE_TITLE, texts.confirm_delete(material.name),
                                  actions.delete_material, selected)


def _material_title(page: Page, params: dict[str, Any]) -> str:
    return texts.T_EDIT_MATERIAL if params.get("material_id") else texts.T_NEW_MATERIAL


@common.dialog("material_form", _material_title)
def material_form(page: Page, params: dict[str, Any]) -> None:
    """Create or edit a material; a new material may come with its first LOT."""
    if common.confirmation_pending(page, params):
        return
    material = next((m for m in page.snapshot.materials if m.id == params.get("material_id")), None)
    fields = Fields()
    name = st.text_input(texts.F_MATERIAL_NAME, value=material.name if material else "", key=widget_key(params, "name"))
    code = st.text_input(texts.F_CODE, value=material.code if material else "", key=widget_key(params, "code"))
    categories = list(MaterialCategory)
    category = st.selectbox(
        texts.F_CATEGORY, categories, index=categories.index(material.category) if material else None,
        format_func=lambda c: common.CATEGORY_LABELS[c], key=widget_key(params, "category"),
        placeholder=texts.F_CATEGORY,
    )
    st.caption(texts.UNIT_FIXED_KG)
    description = st.text_input(texts.F_DESCRIPTION, value=common.text_or_empty(material.description if material else None),
                                key=widget_key(params, "description"))
    lot_number = lot_quantity = lot_expiry = None
    if material is None:
        st.markdown(f"**{texts.F_FIRST_LOT}**")
        lot_number = st.text_input(texts.F_LOT_NUMBER, key=widget_key(params, "lot_number")) or None
        lot_quantity = fields.stored(texts.F_QUANTITY_KG, widget_key(params, "lot_quantity"), kg_to_mg, mg_to_kg,
                                     unit=texts.UNIT_KG)
        lot_expiry = common.date_field(texts.F_EXPIRY, widget_key(params, "lot_expiry"), required=False)
    if common.form_buttons(params) and fields.ok():
        if category is None:
            st.error(texts.field_required(texts.F_CATEGORY))
            return
        if material is None:
            common.run_action(page, params, actions.create_material, code=code, name=name, category=category,
                              description=description, lot_number=lot_number, lot_quantity_mg=lot_quantity,
                              lot_expiry=lot_expiry)
        else:
            common.run_action(page, params, actions.update_material, material.id, code=code, name=name,
                              category=category, description=description)


# ---------------------------------------------------------------- LOTs


def _lots(page: Page) -> None:
    st.subheader(texts.WH_LOTS, anchor=False)
    bar = st.container()
    materials = {m.id: m for m in page.snapshot.materials}
    table = Table([texts.COL_MATERIAL, texts.COL_LOT_NUMBER, texts.COL_QUANTITY_KG, texts.COL_EXPIRY,
                   texts.COL_DAYS_LEFT, texts.COL_STATUS])
    table.formats = {texts.COL_QUANTITY_KG: common.kg_format, texts.COL_EXPIRY: common.date_format,
                     texts.COL_DAYS_LEFT: common.int_format}
    table.colour_column(texts.COL_STATUS)
    for lot in page.snapshot.lots:
        material = materials[lot.material_id]
        if material.is_deleted:
            continue
        expiry = page.state.lots[lot.id]
        status, colour = common.expiry_label(expiry)
        table.add(lot.id, [
            f"{material.name} ({material.code})", lot.lot_number, lot.quantity_mg, common.as_date(lot.expiry_date),
            expiry.days_left, status,
        ], {texts.COL_STATUS: colour})
    table.sort(lambda row: (row[3], row[1]))
    selected = common.show_table(page, "lots", table)
    with bar:
        pressed = common.toolbar([texts.WH_EDIT_LOT, texts.WH_DELETE_LOT], "lots")
        if pressed == texts.WH_EDIT_LOT and common.need_selection(selected):
            common.open_dialog("lot_form", lot_id=selected)
        elif pressed == texts.WH_DELETE_LOT and common.need_selection(selected):
            lot = next(l for l in page.snapshot.lots if l.id == selected)
            common.confirm_action(texts.CONFIRM_DELETE_TITLE, texts.confirm_delete(f"LOT {lot.lot_number}"),
                                  actions.delete_lot, selected)


def _lot_title(page: Page, params: dict[str, Any]) -> str:
    return texts.T_EDIT_LOT if params.get("lot_id") else texts.T_NEW_LOT


@common.dialog("lot_form", _lot_title)
def lot_form(page: Page, params: dict[str, Any]) -> None:
    """Add a LOT to a material, or correct one (e.g. after a stock count)."""
    if common.confirmation_pending(page, params):
        return
    lot = next((l for l in page.snapshot.lots if l.id == params.get("lot_id")), None)
    material_id = lot.material_id if lot else params["material_id"]
    material = next(m for m in page.snapshot.materials if m.id == material_id)
    st.caption(f"{texts.COL_MATERIAL}: {material.name} ({material.code})")
    fields = Fields()
    number = st.text_input(texts.F_LOT_NUMBER, value=lot.lot_number if lot else "", key=widget_key(params, "number"))
    quantity = fields.stored(texts.F_QUANTITY_KG, widget_key(params, "quantity"), kg_to_mg, mg_to_kg,
                             default=lot.quantity_mg if lot else None, unit=texts.UNIT_KG)
    expiry = common.date_field(texts.F_EXPIRY, widget_key(params, "expiry"), lot.expiry_date if lot else None,
                               required=False)
    if common.form_buttons(params) and fields.ok():
        if lot is None:
            common.run_action(page, params, actions.add_lot, material_id, lot_number=number,
                              quantity_mg=quantity, expiry_date=expiry)
        else:
            common.run_action(page, params, actions.update_lot, lot.id, lot_number=number,
                              quantity_mg=quantity, expiry_date=expiry)


# ---------------------------------------------------------------- packaging items


def _breakdown_text(page: Page, item_id: int, weight_mg: int | None) -> str:
    materials = {m.id: m.name for m in page.snapshot.materials}
    parts = [f"{format_percent(c.percent_bp)}% {materials[c.material_id]}"
             for c in page.snapshot.packaging_components if c.packaging_item_id == item_id]
    if not parts:
        return texts.IMPORTED
    return texts.breakdown_text(", ".join(parts), format_g(weight_mg or 0))


def _dims_text(dims: tuple[int, int, int] | None) -> str:
    return " \u00d7 ".join(format_cm(d) for d in dims) if dims else ""


CONTAINER_TYPES = (PackagingItemType.CARTON, PackagingItemType.PALLET)


def _packaging(page: Page) -> None:
    """Ordinary packaging, cartons and pallets. Labels have their own section."""
    st.subheader(texts.WH_PACKAGING, anchor=False)
    bar = st.container()
    table = Table([texts.COL_CODE, texts.COL_NAME, texts.COL_TYPE, texts.COL_DIMENSIONS, texts.COL_OUTER_DIMENSIONS,
                   texts.COL_BREAKDOWN, texts.COL_TOTAL_PCS, texts.COL_RESERVED_PCS, texts.COL_AVAILABLE_PCS,
                   texts.COL_EXPECTED, texts.COL_INDICATOR])
    table.formats = {c: common.int_format for c in (texts.COL_TOTAL_PCS, texts.COL_RESERVED_PCS, texts.COL_AVAILABLE_PCS)}
    for item in page.snapshot.packaging_items:
        if item.is_deleted or item.item_type is PackagingItemType.LABEL:
            continue
        stock = page.state.packaging_items[item.id]
        # Section 5.2: an item made in house from materials normally has no pieces in stock.
        depleted = stock.depleted and not stock.has_components
        breakdown = _breakdown_text(page, item.id, item.unit_weight_mg) if item.item_type is PackagingItemType.PACKAGING else ""
        table.add(item.id, [
            item.code, item.name, texts.ITEM_FIELD_LABELS[item.item_type.value], _dims_text(item.dimensions_mm),
            _dims_text(item.outer_dimensions_mm), breakdown, stock.total, stock.reserved, stock.available,
            common.expected_text(stock.expected, ItemKind.PACKAGING), texts.DEPLETED if depleted else "",
        ])
    table.sort(lambda row: (row[2], row[1].casefold()))
    selected = common.show_table(page, "packaging", table)
    st.caption(texts.CARTON_DIMENSIONS_NOTE)
    with bar:
        pressed = common.toolbar([texts.WH_ADD_PACKAGING, texts.WH_ADD_CONTAINER, texts.EDIT, texts.DELETE], "packaging")
        if pressed == texts.WH_ADD_PACKAGING:
            common.open_dialog("packaging_form")
        elif pressed == texts.WH_ADD_CONTAINER:
            common.open_dialog("container_form")
        elif pressed == texts.EDIT and common.need_selection(selected):
            item = next(p for p in page.snapshot.packaging_items if p.id == selected)
            common.open_dialog("container_form" if item.item_type in CONTAINER_TYPES else "packaging_form",
                               item_id=selected)
        elif pressed == texts.DELETE and common.need_selection(selected):
            item = next(p for p in page.snapshot.packaging_items if p.id == selected)
            common.confirm_action(texts.CONFIRM_DELETE_TITLE, texts.confirm_delete(item.name),
                                  actions.delete_packaging_item, selected)


def _labels(page: Page) -> None:
    """Labels: counted in pieces, chosen in the labelling steps of a packaging plan."""
    st.subheader(texts.WH_LABELS, anchor=False)
    bar = st.container()
    table = Table([texts.COL_CODE, texts.COL_NAME, texts.COL_TOTAL_PCS, texts.COL_RESERVED_PCS,
                   texts.COL_AVAILABLE_PCS, texts.COL_EXPECTED, texts.COL_INDICATOR])
    table.formats = {c: common.int_format for c in (texts.COL_TOTAL_PCS, texts.COL_RESERVED_PCS, texts.COL_AVAILABLE_PCS)}
    for item in page.snapshot.packaging_items:
        if item.is_deleted or item.item_type is not PackagingItemType.LABEL:
            continue
        stock = page.state.packaging_items[item.id]
        table.add(item.id, [
            item.code, item.name, stock.total, stock.reserved, stock.available,
            common.expected_text(stock.expected, ItemKind.PACKAGING), texts.DEPLETED if stock.depleted else "",
        ])
    table.sort(lambda row: row[1].casefold())
    selected = common.show_table(page, "labels", table)
    with bar:
        pressed = common.toolbar([texts.WH_ADD_LABEL, texts.EDIT, texts.DELETE], "labels")
        if pressed == texts.WH_ADD_LABEL:
            common.open_dialog("label_form")
        elif pressed == texts.EDIT and common.need_selection(selected):
            common.open_dialog("label_form", item_id=selected)
        elif pressed == texts.DELETE and common.need_selection(selected):
            item = next(p for p in page.snapshot.packaging_items if p.id == selected)
            common.confirm_action(texts.CONFIRM_DELETE_TITLE, texts.confirm_delete(item.name),
                                  actions.delete_packaging_item, selected)


def _packaging_title(page: Page, params: dict[str, Any]) -> str:
    return texts.T_EDIT_PACKAGING if params.get("item_id") else texts.T_NEW_PACKAGING


def material_options(page: Page) -> dict[int, str]:
    """Materials offered in choices: name and code, deleted ones left out."""
    return {m.id: f"{m.name} ({m.code})" for m in sorted(page.snapshot.materials, key=lambda m: m.name.casefold())
            if not m.is_deleted}


def percent_lines(lines: list[tuple[int | None, Any]], fields: Fields) -> list[tuple[int, int]] | None:
    """(material, percent) rows converted to (material_id, basis points), or None if a row is incomplete."""
    result = []
    for material_id, percent in lines:
        if material_id is None or percent is None:
            fields.errors.append(texts.field_required(texts.F_PERCENT if material_id else texts.COL_MATERIAL))
            return None
        try:
            result.append((material_id, percent_to_bp(percent)))
        except ValueError:
            fields.errors.append(texts.field_decimals(texts.F_PERCENT))
            return None
    return result


def show_percent_total(lines: list[tuple[int | None, Any]]) -> None:
    total = sum((p for _, p in lines if p is not None), start=Decimal(0))
    st.caption(texts.percent_sum(format_number(total, 2)))


@common.dialog("packaging_form", _packaging_title, width="large")
def packaging_form(page: Page, params: dict[str, Any]) -> None:
    """Create or edit a packaging item, with optional dimensions, weight and material breakdown."""
    if common.confirmation_pending(page, params):
        return
    item = next((p for p in page.snapshot.packaging_items if p.id == params.get("item_id")), None)
    fields = Fields()
    left, right = st.columns(2)
    name = left.text_input(texts.F_NAME, value=item.name if item else "", key=widget_key(params, "name"))
    code = right.text_input(texts.F_CODE, value=item.code if item else "", key=widget_key(params, "code"))
    description = st.text_input(texts.F_DESCRIPTION, value=common.text_or_empty(item.description if item else None),
                                key=widget_key(params, "description"))
    quantity = fields.whole(texts.F_QUANTITY_PCS, widget_key(params, "quantity"), item.quantity_pcs if item else 0,
                            texts.UNIT_PCS)
    dims = item.dimensions_mm if item else None
    columns = st.columns(3)
    measured = [
        fields.stored(label, widget_key(params, f"dim{i}"), cm_to_mm, mm_to_cm, dims[i] if dims else None,
                      "cm", 1, container=columns[i], help=texts.DIMENSIONS_HELP)
        for i, label in enumerate((texts.F_LENGTH, texts.F_WIDTH, texts.F_HEIGHT))
    ]
    weight = fields.stored(texts.F_UNIT_WEIGHT_G, widget_key(params, "weight"), g_to_mg, mg_to_g,
                           item.unit_weight_mg if item else None, "g")
    st.markdown(f"**{texts.F_BREAKDOWN}**")
    initial = [(c.material_id, bp_to_percent(c.percent_bp)) for c in page.snapshot.packaging_components
               if item and c.packaging_item_id == item.id]
    lines = common.line_editor(params, "breakdown", material_options(page), initial, fields,
                               texts.COL_MATERIAL, texts.F_PERCENT, texts.ADD_BREAKDOWN_LINE, "%", 2)
    if lines:
        show_percent_total(lines)
    if common.form_buttons(params):
        components = percent_lines(lines, fields)
        if not fields.ok() or components is None:
            return
        data = actions.PackagingItemInput(
            code=code, name=name, quantity_pcs=quantity, description=description,
            length_mm=measured[0], width_mm=measured[1], height_mm=measured[2], unit_weight_mg=weight,
            components=tuple(components), item_type=PackagingItemType.PACKAGING,
        )
        if item is None:
            common.run_action(page, params, actions.create_packaging_item, data)
        else:
            common.run_action(page, params, actions.update_packaging_item, item.id, data)


def _common_fields(params: dict[str, Any], item: PackagingItem | None, fields: Fields) -> tuple[str, str, str, int | None]:
    """Name, code, description and pieces in stock: the fields every packaging form starts with."""
    left, right = st.columns(2)
    name = left.text_input(texts.F_NAME, value=item.name if item else "", key=widget_key(params, "name"))
    code = right.text_input(texts.F_CODE, value=item.code if item else "", key=widget_key(params, "code"))
    description = st.text_input(texts.F_DESCRIPTION, value=common.text_or_empty(item.description if item else None),
                                key=widget_key(params, "description"))
    quantity = fields.whole(texts.F_QUANTITY_PCS, widget_key(params, "quantity"), item.quantity_pcs if item else 0,
                            texts.UNIT_PCS)
    return name, code, description, quantity


def _dimension_fields(params: dict[str, Any], prefix: str, labels: tuple[str, str, str],
                      dims: tuple[int, int, int] | None, fields: Fields) -> list[int | None]:
    columns = st.columns(3)
    return [
        fields.stored(label, widget_key(params, f"{prefix}{i}"), cm_to_mm, mm_to_cm, dims[i] if dims else None,
                      "cm", 1, container=columns[i])
        for i, label in enumerate(labels)
    ]


def _container_title(page: Page, params: dict[str, Any]) -> str:
    return texts.T_EDIT_CONTAINER if params.get("item_id") else texts.T_NEW_CONTAINER


@common.dialog("container_form", _container_title, width="large")
def container_form(page: Page, params: dict[str, Any]) -> None:
    """A carton (inner and outer dimensions) or a pallet (base and maximum load height)."""
    if common.confirmation_pending(page, params):
        return
    item = next((p for p in page.snapshot.packaging_items if p.id == params.get("item_id")), None)
    kind = st.radio(texts.F_CONTAINER_TYPE, list(CONTAINER_TYPES),
                    index=CONTAINER_TYPES.index(item.item_type) if item else 0,
                    format_func=lambda t: texts.ITEM_FIELD_LABELS[t.value], horizontal=True,
                    disabled=item is not None, key=widget_key(params, "type"))
    fields = Fields()
    name, code, description, quantity = _common_fields(params, item, fields)
    inner: list[int | None] = [None, None, None]
    if kind is PackagingItemType.CARTON:
        st.markdown(f"**{texts.F_INNER_DIMENSIONS}**")
        st.caption(texts.INNER_DIMENSIONS_HELP)
        inner = _dimension_fields(params, "inner", (texts.F_LENGTH, texts.F_WIDTH, texts.F_HEIGHT),
                                  item.dimensions_mm if item else None, fields)
        st.markdown(f"**{texts.F_OUTER_DIMENSIONS}**")
        st.caption(texts.OUTER_DIMENSIONS_HELP)
        outer = _dimension_fields(params, "outer", (texts.F_LENGTH, texts.F_WIDTH, texts.F_HEIGHT),
                                  item.outer_dimensions_mm if item else None, fields)
    else:
        st.markdown(f"**{texts.F_OUTER_DIMENSIONS}**")
        st.caption(texts.PALLET_DIMENSIONS_HELP)
        outer = _dimension_fields(params, "outer", (texts.F_PALLET_LENGTH, texts.F_PALLET_WIDTH, texts.F_PALLET_HEIGHT),
                                  item.outer_dimensions_mm if item else None, fields)
    if common.form_buttons(params) and fields.ok():
        data = actions.PackagingItemInput(
            code=code, name=name, quantity_pcs=quantity, description=description,
            length_mm=inner[0], width_mm=inner[1], height_mm=inner[2],
            outer_length_mm=outer[0], outer_width_mm=outer[1], outer_height_mm=outer[2], item_type=kind,
        )
        if item is None:
            common.run_action(page, params, actions.create_packaging_item, data)
        else:
            common.run_action(page, params, actions.update_packaging_item, item.id, data)


def _label_title(page: Page, params: dict[str, Any]) -> str:
    return texts.T_EDIT_LABEL if params.get("item_id") else texts.T_NEW_LABEL


@common.dialog("label_form", _label_title)
def label_form(page: Page, params: dict[str, Any]) -> None:
    """A label: name, code, description and pieces in stock."""
    if common.confirmation_pending(page, params):
        return
    item = next((p for p in page.snapshot.packaging_items if p.id == params.get("item_id")), None)
    fields = Fields()
    name, code, description, quantity = _common_fields(params, item, fields)
    if common.form_buttons(params) and fields.ok():
        data = actions.PackagingItemInput(code=code, name=name, quantity_pcs=quantity, description=description,
                                          item_type=PackagingItemType.LABEL)
        if item is None:
            common.run_action(page, params, actions.create_packaging_item, data)
        else:
            common.run_action(page, params, actions.update_packaging_item, item.id, data)


# ---------------------------------------------------------------- finished goods shelf


def _transfers_text(page: Page, line_id: int) -> str:
    lines = {l.id: l for l in page.snapshot.shelf_lines}
    orders = {o.id: o for o in page.snapshot.orders}
    parts = []
    for transfer in page.snapshot.shelf_transfers:
        if line_id == transfer.from_line_id:
            other, direction = lines[transfer.to_line_id], texts.TRANSFER_TO
        elif line_id == transfer.to_line_id:
            other, direction = lines[transfer.from_line_id], texts.TRANSFER_FROM
        else:
            continue
        parts.append(texts.transfer_entry(format_int(transfer.boxes), direction, orders[other.order_id].destination,
                                          format_date(transfer.transferred_on)))
    return ", ".join(parts)


def shelf_rows(page: Page) -> list[tuple[Any, Any, Any, Any]]:
    """(line, line state, order, product) for every visible shelf line."""
    orders = {o.id: o for o in page.snapshot.orders}
    products = {p.id: p for p in page.snapshot.products}
    rows = []
    for line in page.snapshot.shelf_lines:
        if line.is_deleted:
            continue
        order = orders[line.order_id]
        rows.append((line, page.state.shelf_lines[line.id], order, products[order.product_id]))
    return rows


def _shelf(page: Page) -> None:
    st.subheader(texts.WH_SHELF, anchor=False)
    bar = st.container()
    table = Table([texts.COL_PRODUCT, texts.COL_ORDER, texts.COL_DESTINATION, texts.COL_BOXES, texts.COL_PIECES_PER_BOX,
                   texts.COL_CARTONS, texts.COL_BOXES_PER_CARTON, texts.COL_PALLETS, texts.COL_LOOSE_BOXES,
                   texts.COL_PENDING_BOXES, texts.COL_FREE_BOXES, texts.COL_DELIVERY, texts.COL_SHIP_BY,
                   texts.COL_TRANSFERS, texts.COL_INDICATOR])
    counts = (texts.COL_BOXES, texts.COL_PIECES_PER_BOX, texts.COL_CARTONS, texts.COL_BOXES_PER_CARTON,
              texts.COL_LOOSE_BOXES, texts.COL_PENDING_BOXES, texts.COL_FREE_BOXES)
    table.formats = {c: common.int_format for c in counts}
    table.formats.update({texts.COL_DELIVERY: common.date_format, texts.COL_SHIP_BY: common.date_format})
    for line, line_state, order, product in shelf_rows(page):
        if line_state.shipped_out:
            # A line emptied by "Απεστάλη" leaves the shelf; undoing the shipment brings it back.
            continue
        table.add(line.id, [
            product.name, order.name, order.destination, line.boxes, line.pieces_per_box, line_state.cartons,
            line.boxes_per_carton, line_state.pallets, line_state.loose_boxes, line_state.pending_boxes,
            line_state.free_boxes, common.as_date(order.delivery_date),
            common.as_date(page.state.orders[order.id].ship_by),
            _transfers_text(page, line.id), texts.DEPLETED if line_state.depleted else "",
        ], formats={texts.COL_PALLETS: common.pallets_format(line_state.last_pallet_cartons)})
    table.sort(lambda row: (row[0].casefold(), row[1]))
    selected = common.show_table(page, "shelf", table)
    with bar:
        pressed = common.toolbar([texts.WH_TRANSFER, texts.DELETE], "shelf")
        if pressed == texts.WH_TRANSFER and common.need_selection(selected):
            common.open_dialog("transfer_form", line_id=selected)
        elif pressed == texts.DELETE and common.need_selection(selected):
            line = next(l for l in page.snapshot.shelf_lines if l.id == selected)
            order = next(o for o in page.snapshot.orders if o.id == line.order_id)
            common.confirm_action(texts.CONFIRM_DELETE_TITLE, texts.confirm_delete(order.name),
                                  actions.delete_shelf_line, selected)


@common.dialog("transfer_form", "T_TRANSFER")
def transfer_form(page: Page, params: dict[str, Any]) -> None:
    """Move free boxes to a shelf line of the same product, pieces per box and boxes per carton."""
    if common.confirmation_pending(page, params):
        return
    rows = {line.id: (line, state, order, product) for line, state, order, product in shelf_rows(page)}
    source, source_state, source_order, product = rows[params["line_id"]]
    st.caption(f"{product.name}, {source_order.name}, {source_order.destination}")
    st.caption(texts.free_boxes_note(format_int(source_state.free_boxes)))
    targets = {
        line.id: f"{order.name}, {order.destination}"
        for line, state, order, other_product in rows.values()
        if line.id != source.id and other_product.id == product.id and not state.shipped_out
        and line.pieces_per_box == source.pieces_per_box and line.boxes_per_carton == source.boxes_per_carton
    }
    if not targets:
        st.info(texts.NO_COMPATIBLE_LINE)
        return
    target = st.selectbox(texts.F_TARGET_LINE, list(targets), format_func=targets.get, key=widget_key(params, "target"))
    fields = Fields()
    boxes = fields.whole(texts.F_BOXES, widget_key(params, "boxes"), unit=texts.UNIT_BOXES)
    if common.form_buttons(params) and fields.ok():
        common.run_action(page, params, actions.transfer_boxes, from_line_id=source.id, to_line_id=target,
                          boxes=boxes)
