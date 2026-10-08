"""Tab 3: Orders. Every order at any stage: create, rename, reorder and cancel (section 7)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.state import OrderStatus, preview_new_order
from core.units import format_int, format_kg, format_time, kg_to_mg, mg_to_kg
from data import actions
from ui import common, texts
from ui.common import Fields, Page, Table, widget_key

# Hidden by default; the checkbox "Εμφάνιση κλειστών παραγγελιών" shows them.
CLOSED = frozenset({OrderStatus.SHIPPED, OrderStatus.TRANSFERRED, OrderStatus.CANCELLED})


def render(page: Page) -> None:
    bar = st.container()
    show_closed = st.checkbox(texts.OR_SHOW_CLOSED, key="orders_show_closed")
    products = {p.id: p.name for p in page.snapshot.products}
    table = Table([texts.COL_SEQUENCE, texts.COL_ORDER, texts.COL_PRODUCT, texts.COL_DESTINATION,
                   texts.COL_QUANTITY_KG, texts.COL_STATUS, texts.COL_START, texts.COL_READINESS,
                   texts.COL_SHIP_BY, texts.COL_DELIVERY, texts.COL_WARNINGS])
    table.formats = {texts.COL_SEQUENCE: common.int_format, texts.COL_QUANTITY_KG: common.kg_format,
                     texts.COL_START: common.date_format, texts.COL_READINESS: common.date_format,
                     texts.COL_SHIP_BY: common.date_format, texts.COL_DELIVERY: common.date_format}
    table.colour_column(texts.COL_STATUS)
    for order in page.snapshot.orders:
        order_state = page.state.orders[order.id]
        if order_state.status in CLOSED and not show_closed:
            continue
        status, colour = common.order_status_label(order_state)
        is_open = order_state.status not in CLOSED and not order_state.packaging_completed
        table.add(order.id, [
            order.sequence if is_open else None, order.name, products[order.product_id], order.destination,
            order.quantity_mg, status, common.as_date(order_state.start_date),
            common.as_date(order_state.readiness), common.as_date(order_state.ship_by),
            common.as_date(order.delivery_date), ", ".join(common.warning_texts(page, order_state, short=True)),
        ], {texts.COL_STATUS: colour})
    table.sort(lambda row: (row[9], row[1]))
    selected = common.show_table(page, "orders", table)
    with bar:
        pressed = common.toolbar([texts.OR_NEW, texts.EDIT, texts.OR_SEQUENCE, texts.OR_CANCEL], "orders")
        if pressed == texts.OR_NEW:
            common.open_dialog("order_new")
        elif pressed == texts.EDIT and common.need_selection(selected):
            common.open_dialog("order_edit", order_id=selected)
        elif pressed == texts.OR_SEQUENCE and common.need_selection(selected):
            common.open_dialog("order_sequence", order_id=selected)
        elif pressed == texts.OR_CANCEL and common.need_selection(selected):
            order = next(o for o in page.snapshot.orders if o.id == selected)
            common.confirm_action(texts.T_CANCEL_ORDER, texts.confirm_cancel(order.name), actions.cancel_order, selected)
    if selected is not None:
        _details(page, selected)


def _details(page: Page, order_id: int) -> None:
    """Shortages, LOTs, assignments, packaging and every warning of the selected order."""
    order = next(o for o in page.snapshot.orders if o.id == order_id)
    order_state = page.state.orders[order_id]
    st.subheader(texts.order_details(order.name), anchor=False)

    st.markdown(f"**{texts.DETAILS_SHORTAGES}**")
    if order_state.recipe_lines:
        common.needs_table(page, f"details_needs:{order_id}", order_state.recipe_lines)
    else:
        st.caption(texts.NO_SHORTAGE_LINES)

    st.markdown(f"**{texts.DETAILS_LOTS}**")
    if order_state.lot_uses:
        lots = {lot.id: lot for lot in page.snapshot.lots}
        table = Table([texts.COL_LOT_NUMBER, texts.COL_MATERIAL, texts.COL_QUANTITY_KG, texts.COL_EXPIRY,
                       texts.COL_STATUS])
        table.formats = {texts.COL_QUANTITY_KG: common.kg_format, texts.COL_EXPIRY: common.date_format}
        table.colour_column(texts.COL_STATUS)
        for use in order_state.lot_uses:
            lot = lots[use.lot_id]
            status, colour = common.expiry_label(page.state.lots[lot.id])
            table.add(lot.id, [lot.lot_number, common.item_name(page, (common.ItemKind.MATERIAL, use.material_id)),
                               use.quantity_mg, common.as_date(lot.expiry_date), status], {texts.COL_STATUS: colour})
        common.show_table(page, f"details_lots:{order_id}", table, selectable=False)
    else:
        st.caption(texts.NO_LOTS)

    st.markdown(f"**{texts.DETAILS_ASSIGNMENTS}**")
    machines = {m.id: m.name for m in page.snapshot.machines}
    assignments = {a.id: a for a in page.snapshot.assignments}
    if order_state.assignments:
        for assignment_state in order_state.assignments:
            assignment = assignments[assignment_state.assignment_id]
            estimate = assignment_state.estimate
            st.write(texts.assignment_summary(
                machines[assignment.machine_id], format_kg(assignment.quantity_mg),
                format_time(estimate.production_days), format_int(estimate.expected_pieces or 0),
            ))
    else:
        st.caption(texts.NO_ASSIGNMENTS)
    if order_state.readiness is None:
        st.caption(texts.NO_START)

    st.markdown(f"**{texts.DETAILS_PACKAGING}**")
    if order_state.packaging is not None:
        result = order_state.packaging
        st.write(texts.packaging_summary(format_int(result.boxes), format_int(result.cartons or 0),
                                         format_time(result.packaging_days)))
    else:
        st.caption(texts.FLAG_NO_PACKAGING_PLAN)

    st.markdown(f"**{texts.DETAILS_WARNINGS}**")
    messages = common.warning_texts(page, order_state)
    for message in messages:
        st.warning(message)
    if not messages:
        st.caption(texts.NO_WARNINGS)


@common.dialog("order_new", "T_NEW_ORDER", width="large")
def order_new(page: Page, params: dict[str, Any]) -> None:
    """New order: shows today's available quantity and the shortage table while typing."""
    if common.confirmation_pending(page, params):
        return
    with_recipe = {line.product_id for line in page.snapshot.recipe_lines}
    products = {p.id: p.name for p in sorted(page.snapshot.products, key=lambda p: p.name.casefold())
                if p.id in with_recipe}
    fields = Fields()
    product_id = st.selectbox(texts.F_PRODUCT, list(products), index=None, format_func=products.get,
                              key=widget_key(params, "product"), placeholder=texts.F_PRODUCT)
    availability = page.state.products.get(product_id) if product_id is not None else None
    if availability is not None:
        st.write(texts.available_today(format_kg(availability.producible_mg)))
    quantity = fields.stored(texts.F_ORDER_QUANTITY, widget_key(params, "quantity"), kg_to_mg, mg_to_kg,
                             unit=texts.UNIT_KG)
    shortages = []
    if product_id is not None and quantity:
        lines = preview_new_order(page.snapshot, product_id, quantity)
        common.needs_table(page, f"new_order_needs:{params['_token']}", lines)
        shortages = [line for line in lines if line.shortage]
    left, right = st.columns(2)
    name = left.text_input(texts.F_ORDER_NAME, value=actions.suggest_order_name(page.snapshot),
                           key=widget_key(params, "name"))
    destination = right.text_input(texts.F_DESTINATION, key=widget_key(params, "destination"))
    left, right = st.columns(2)
    delivery = common.date_field(texts.F_DELIVERY, widget_key(params, "delivery"), container=left)
    transit = fields.whole(texts.F_TRANSIT, widget_key(params, "transit"),
                           page.snapshot.settings.default_transit_days, texts.UNIT_DAYS, container=right)

    def save(amount: int | None) -> None:
        if fields.ok():
            common.run_action(page, params, actions.create_order, product_id=product_id, quantity_mg=amount,
                              name=name, destination=destination, delivery_date=delivery, transit_days=transit)

    if not shortages:
        if common.form_buttons(params):
            if product_id is None:
                st.error(texts.field_required(texts.F_PRODUCT))
            else:
                save(quantity)
        return
    columns = st.columns(3)
    if columns[0].button(texts.SAVE_REDUCED, key=widget_key(params, "reduce"), width="stretch"):
        save(availability.producible_mg if availability else 0)
    if columns[1].button(texts.SAVE_WAITING, key=widget_key(params, "waiting"), type="primary",
                         width="stretch"):
        save(quantity)
    if columns[2].button(texts.CANCEL, key=widget_key(params, "cancel"), width="stretch"):
        common.close_dialog()
        st.rerun()


@common.dialog("order_edit", "T_EDIT_ORDER")
def order_edit(page: Page, params: dict[str, Any]) -> None:
    """Name, destination and dates change at any time; quantity until the first assignment completes."""
    if common.confirmation_pending(page, params):
        return
    order = next(o for o in page.snapshot.orders if o.id == params["order_id"])
    locked = any(a.is_completed for a in page.snapshot.assignments if a.order_id == order.id)
    fields = Fields()
    name = st.text_input(texts.F_ORDER_NAME, value=order.name, key=widget_key(params, "name"))
    destination = st.text_input(texts.F_DESTINATION, value=order.destination, key=widget_key(params, "destination"))
    quantity = fields.stored(texts.F_ORDER_QUANTITY, widget_key(params, "quantity"), kg_to_mg, mg_to_kg,
                             order.quantity_mg, texts.UNIT_KG, disabled=locked)
    if locked:
        st.caption(texts.QUANTITY_LOCKED_NOTE)
    delivery = common.date_field(texts.F_DELIVERY, widget_key(params, "delivery"), order.delivery_date)
    transit = fields.whole(texts.F_TRANSIT, widget_key(params, "transit"), order.transit_days, texts.UNIT_DAYS)
    if common.form_buttons(params) and fields.ok():
        common.run_action(page, params, actions.update_order, order.id, name=name, destination=destination,
                          delivery_date=delivery, transit_days=transit,
                          quantity_mg=order.quantity_mg if locked else quantity)


@common.dialog("order_sequence", "T_SEQUENCE", width="small")
def order_sequence(page: Page, params: dict[str, Any]) -> None:
    """Write the new position; the orders in between shift by one."""
    if common.confirmation_pending(page, params):
        return
    order = next(o for o in page.snapshot.orders if o.id == params["order_id"])
    open_orders = sorted((o for o in page.snapshot.orders
                          if page.state.orders[o.id].status not in CLOSED and not page.state.orders[o.id].packaging_completed),
                         key=lambda o: o.sequence)
    if order not in open_orders:
        st.error(texts.ORDER_CLOSED)
        return
    st.caption(f"{order.name}. {texts.current_position(open_orders.index(order) + 1, len(open_orders))}")
    fields = Fields()
    position = fields.whole(texts.F_NEW_POSITION, widget_key(params, "position"))
    if common.form_buttons(params) and fields.ok():
        if position is None:
            st.error(texts.field_required(texts.F_NEW_POSITION))
            return
        common.run_action(page, params, actions.change_sequence, order.id, new_position=position)
