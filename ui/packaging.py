"""Tab 5: Packaging. Plan per order, carton fit, requirements, time and completion (section 9)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import streamlit as st

from core.models import PackagingItemType, PackagingStep, PackagingStepExtra, StepKind, StepRole
from core.packaging_calc import MAX_STEPS, PlanError, best_carton_fit, carton_fits
from core.state import OrderStatus, PiecesBasis, WarningCode, preview_packaging_plan
from core.units import bp_to_percent, format_cm, format_date, format_int, format_time, percent_to_bp
from data import actions
from ui import common, texts
from ui.common import Fields, Page, Table, widget_key

CLOSED = frozenset({OrderStatus.CANCELLED, OrderStatus.SHIPPED, OrderStatus.TRANSFERRED, OrderStatus.ON_SHELF})

BASIS_LABELS = common.Lazy(lambda: {
    PiecesBasis.EXPECTED: texts.BASIS_EXPECTED,
    PiecesBasis.ACTUAL: texts.BASIS_ACTUAL,
    PiecesBasis.WITHOUT_DEFECT_RATE: texts.BASIS_WITHOUT_DEFECTS,
})
BASIS_NOTES = common.Lazy(lambda: {
    PiecesBasis.EXPECTED: texts.CALC_WITH_EXPECTED,
    PiecesBasis.ACTUAL: texts.CALC_WITH_ACTUAL,
    PiecesBasis.WITHOUT_DEFECT_RATE: texts.CALC_WITHOUT_DEFECTS,
})
KIND_LABELS = common.Lazy(lambda: {StepKind.LEVEL: texts.STEP_LEVEL, StepKind.LABELLING: texts.STEP_LABELLING})
ROLE_LABELS = common.Lazy(lambda: {StepRole.PRIMARY: texts.ROLE_PRIMARY, StepRole.BOX: texts.ROLE_BOX,
               StepRole.CARTON: texts.ROLE_CARTON, StepRole.PALLET: texts.ROLE_PALLET,
               StepRole.OTHER: texts.ROLE_OTHER})


def render(page: Page) -> None:
    bar = st.container()
    products = {p.id: p.name for p in page.snapshot.products}
    plans = {p.order_id for p in page.snapshot.packaging_plans}
    table = Table([texts.COL_ORDER, texts.COL_PRODUCT, texts.COL_DESTINATION, texts.COL_STATUS, texts.COL_PIECES,
                   texts.COL_BASIS, texts.COL_PLAN, texts.COL_BOXES, texts.COL_CARTONS, texts.COL_PALLETS,
                   texts.COL_PACKAGING_DAYS, texts.COL_READINESS, texts.COL_INDICATIONS])
    table.formats = {texts.COL_PIECES: common.int_format, texts.COL_BOXES: common.int_format,
                     texts.COL_CARTONS: common.int_format, texts.COL_PALLETS: common.int_format,
                     texts.COL_PACKAGING_DAYS: common.time_format,
                     texts.COL_READINESS: common.date_format}
    table.colour_column(texts.COL_STATUS)
    for order in page.snapshot.orders:
        order_state = page.state.orders[order.id]
        if order_state.status in CLOSED:
            continue
        status, colour = common.ORDER_STATUS[order_state.status]
        result = order_state.packaging
        indications = [common.FLAG_LABELS[f] for f in order_state.flags if f is not common.OrderFlag.NO_MACHINE]
        table.add(order.id, [
            order.name, products[order.product_id], order.destination, status, order_state.packaging_pieces,
            BASIS_LABELS[order_state.pieces_basis], texts.YES if order.id in plans else texts.NO,
            result.boxes if result else None, result.cartons if result else None,
            result.pallets if result else None,
            common.as_number(result.packaging_days) if result else None, common.as_date(order_state.readiness),
            ", ".join(indications),
        ], {texts.COL_STATUS: colour})
    table.sort(lambda row: row[0])
    selected = common.show_table(page, "packaging_orders", table)
    with bar:
        pressed = common.toolbar([texts.PK_PLAN, texts.PK_COMPLETE], "packaging")
        if pressed == texts.PK_PLAN and common.need_selection(selected):
            if not any(not p.is_deleted for p in page.snapshot.packaging_items):
                st.warning(texts.NO_PACKAGING_ITEMS)
            else:
                common.open_dialog("plan_form", order_id=selected)
        elif pressed == texts.PK_COMPLETE and common.need_selection(selected):
            common.open_dialog("packaging_complete", order_id=selected)


# ---------------------------------------------------------------- plan dialog


def _initial_steps(page: Page, order_id: int) -> list[dict[str, Any]]:
    steps = sorted((s for s in page.snapshot.packaging_steps if s.order_id == order_id), key=lambda s: s.position)
    extras: dict[int, list[tuple[int, Decimal]]] = {}
    for extra in page.snapshot.packaging_step_extras:
        extras.setdefault(extra.step_id, []).append((extra.packaging_item_id, Decimal(extra.quantity_per_unit)))
    if not steps:
        return [{"token": common.new_token(), "kind": StepKind.LEVEL, "role": StepRole.PRIMARY, "item": None,
                 "units_per": None, "comes_ready": False, "speed": None, "extras": []}]
    return [{"token": common.new_token(), "kind": s.kind, "role": s.role, "item": s.packaging_item_id,
             "units_per": s.units_per, "comes_ready": s.comes_ready, "speed": s.speed_per_min,
             "extras": extras.get(s.id, [])} for s in steps]


def _container_choice(page: Page, params: dict[str, Any], row: dict[str, Any], inner_item: int | None,
                      fields: Fields) -> int | None:
    """Units per carton or pallet: one of the placements of section 9.4, or the user's own number.

    Boxes go into a carton by the carton's inner dimensions; cartons go on a
    pallet by their outer dimensions and the pallet's base and maximum load height.
    """
    items = {p.id: p for p in page.snapshot.packaging_items}
    on_pallet = row["role"] is StepRole.PALLET
    inner = items.get(inner_item)
    container = items.get(row["item"])
    if on_pallet:
        unit = texts.UNIT_CARTONS
        unit_dims = inner.outer_dimensions_mm if inner else None
        space = container.outer_dimensions_mm if container else None
    else:
        unit = texts.UNIT_BOXES
        unit_dims = inner.dimensions_mm if inner else None
        space = container.dimensions_mm if container else None
    fits = carton_fits(unit_dims, space) if unit_dims and space else ()
    if not fits:
        return fields.whole(texts.F_CONTAINS, widget_key(params, f"step{row['token']}:contains"), row["units_per"],
                            unit)
    labels = [texts.fit_option(" × ".join(format_cm(v) for v in fit.orientation),
                               " × ".join(str(v) for v in fit.per_axis), format_int(fit.boxes), unit) for fit in fits]
    options = list(range(len(fits))) + [-1]
    best = fits.index(best_carton_fit(fits))
    current = next((i for i, fit in enumerate(fits) if fit.boxes == row["units_per"]), None)
    index = options.index(current if current is not None else (best if row["units_per"] is None else -1))
    choice = st.radio(texts.F_FIT_PALLET if on_pallet else texts.F_FIT, options, index=index,
                      format_func=lambda i: texts.CUSTOM_NUMBER if i == -1 else labels[i],
                      key=widget_key(params, f"step{row['token']}:fit:{row['item']}"))
    if choice == -1:
        return fields.whole(texts.CUSTOM_NUMBER, widget_key(params, f"step{row['token']}:custom"), row["units_per"],
                            unit)
    return fits[choice].boxes


def _item_options(page: Page, types: frozenset[PackagingItemType]) -> dict[int, str]:
    """Packaging items of the given types, by name, deleted ones left out."""
    return {p.id: f"{p.name} ({p.code})" for p in sorted(page.snapshot.packaging_items, key=lambda p: p.name.casefold())
            if not p.is_deleted and p.item_type in types}


def _step_editor(page: Page, params: dict[str, Any], steps: list[dict[str, Any]], fields: Fields) -> None:
    extra_options = _item_options(page, actions.EXTRA_TYPES)
    box_item = carton_item = None
    for number, row in enumerate(list(steps), start=1):
        with st.container(border=True):
            head = st.columns([2, 2, 3, 1], vertical_alignment="bottom")
            head[0].markdown(f"**{texts.step_number(number)}**")
            row["kind"] = head[1].selectbox(texts.F_STEP_KIND, list(StepKind), index=list(StepKind).index(row["kind"]),
                                            format_func=KIND_LABELS.get, key=widget_key(params, f"step{row['token']}:kind"))
            if row["kind"] is StepKind.LEVEL:
                roles = list(StepRole)
                row["role"] = head[2].selectbox(
                    texts.F_ROLE, roles, index=roles.index(row["role"]) if row["role"] in roles else 0,
                    format_func=ROLE_LABELS.get, key=widget_key(params, f"step{row['token']}:role"),
                )
            else:
                row["role"] = None
            if head[3].button(texts.REMOVE, key=widget_key(params, f"step{row['token']}:remove")):
                steps.pop(number - 1)
                st.rerun(scope="fragment")

            # The item list follows the role: labels, cartons, pallets or ordinary packaging.
            item_type = actions.step_item_type(row["kind"], row["role"])
            options = _item_options(page, frozenset({item_type}))
            option_ids = list(options)
            body = st.columns([3, 2, 1, 2], vertical_alignment="top")
            row["item"] = body[0].selectbox(
                texts.ITEM_FIELD_LABELS[item_type.value], option_ids,
                index=option_ids.index(row["item"]) if row["item"] in option_ids else None,
                format_func=options.get, key=widget_key(params, f"step{row['token']}:item:{item_type.value}"),
                placeholder=texts.ITEM_FIELD_LABELS[item_type.value],
            )
            if row["kind"] is StepKind.LEVEL:
                if row["role"] is StepRole.CARTON:
                    with body[1]:
                        row["units_per"] = _container_choice(page, params, row, box_item, fields)
                elif row["role"] is StepRole.PALLET:
                    with body[1]:
                        row["units_per"] = _container_choice(page, params, row, carton_item, fields)
                else:
                    unit = texts.UNIT_PIECES if number == 1 else ""
                    row["units_per"] = fields.whole(texts.F_CONTAINS, widget_key(params, f"step{row['token']}:contains"),
                                                    row["units_per"], unit, container=body[1])
                if row["role"] is StepRole.BOX:
                    box_item = row["item"]
                if row["role"] is StepRole.CARTON:
                    carton_item = row["item"]
            else:
                row["units_per"] = None
            row["comes_ready"] = body[2].checkbox(texts.F_COMES_READY, value=row["comes_ready"],
                                                  key=widget_key(params, f"step{row['token']}:ready"))
            speed = fields.decimal(texts.F_SPEED, widget_key(params, f"step{row['token']}:speed"),
                                   None if row["comes_ready"] else row["speed"], decimals=2, container=body[3],
                                   disabled=row["comes_ready"])
            row["speed"] = None if row["comes_ready"] else speed
            if row["kind"] is StepKind.LEVEL:
                st.caption(texts.F_EXTRAS)
                extras = common.line_editor(params, f"step{row['token']}:extras", extra_options, row["extras"], fields,
                                            texts.F_PACKAGING_ITEM, texts.F_EXTRA_QUANTITY, texts.ADD_EXTRA,
                                            decimals=0, whole=True)
                row["extras_now"] = [(i, int(q)) for i, q in extras if i is not None and q is not None]
            else:
                row["extras_now"] = []
    if len(steps) >= MAX_STEPS:
        st.caption(texts.MAX_STEPS_NOTE)
    elif st.button(texts.ADD_STEP, key=widget_key(params, "add_step")):
        steps.append({"token": common.new_token(), "kind": StepKind.LEVEL, "role": StepRole.OTHER, "item": None,
                      "units_per": None, "comes_ready": False, "speed": None, "extras": []})
        st.rerun(scope="fragment")


def _specs(steps: list[dict[str, Any]]) -> list[actions.StepSpec] | None:
    if any(row["item"] is None for row in steps):
        return None
    return [actions.StepSpec(row["kind"], row["item"], row["role"], row["units_per"], row["comes_ready"],
                             row["speed"], tuple(row.get("extras_now", []))) for row in steps]


def _preview_models(order_id: int, specs: list[actions.StepSpec]) -> tuple[list[PackagingStep], list[PackagingStepExtra]]:
    """The plan being edited as stored models with negative ids, for the live preview."""
    steps, extras = [], []
    for position, spec in enumerate(specs, start=1):
        step_id = -position
        level = spec.kind is StepKind.LEVEL
        steps.append(PackagingStep(step_id, order_id, position, spec.kind, spec.packaging_item_id,
                                   spec.role if level else None, spec.units_per if level else None,
                                   spec.comes_ready, None if spec.comes_ready else spec.speed_per_min))
        extras.extend(PackagingStepExtra(step_id, item_id, quantity) for item_id, quantity in spec.extras)
    return steps, extras


def _preview(page: Page, params: dict[str, Any], order_id: int, specs: list[actions.StepSpec],
             hours: Decimal, utilization: int) -> None:
    """Steps table, requirements, limiting item, time and estimates, before saving (9.5)."""
    steps, extras = _preview_models(order_id, specs)
    order_state = preview_packaging_plan(page.snapshot, order_id, hours, utilization, steps, extras)
    if order_state.packaging_issues:
        for issue in order_state.packaging_issues:
            st.warning(texts.PLAN_ISSUES[issue.value])
        return
    result = order_state.packaging
    if result is None:
        st.info(texts.NO_PIECES)
        return
    names = {p.id: p.name for p in page.snapshot.packaging_items}
    st.markdown(f"**{texts.STEPS_TABLE}**")
    table = Table([texts.COL_STEP, texts.COL_CONTAINS, texts.COL_COMES_READY, texts.COL_UNITS, texts.COL_REMAINDER,
                   texts.COL_PER_MINUTE, texts.COL_NET_TIME])
    table.formats = {texts.COL_UNITS: common.int_format, texts.COL_PER_MINUTE: common.time_format,
                     texts.COL_NET_TIME: lambda v: f"{common.time_format(v)} {texts.UNIT_HOURS}"}
    previous_name: str | None = None
    for spec, step in zip(specs, result.steps):
        name = names[spec.packaging_item_id]
        extra_text = "".join(f", {q} {names[i]}" for i, q in spec.extras)
        if spec.kind is StepKind.LEVEL:
            contains = (texts.contains_pieces(format_int(spec.units_per or 0)) if previous_name is None
                        else texts.contains_units(format_int(spec.units_per or 0), previous_name)) + extra_text
            leftover_unit = texts.UNIT_PIECES if previous_name is None else previous_name
            leftover = f"{format_int(step.leftover)} {leftover_unit}" if step.leftover is not None else ""
            if step.last_unit_contents:
                leftover = texts.last_pallet_note(format_int(step.last_unit_contents))
            label = name
        else:
            contains = texts.contains_units("1", name)
            leftover = ""
            label = texts.labelling_of(name)
        table.add(step.position, [
            label, contains, texts.YES if spec.comes_ready else texts.NO, step.units, leftover,
            common.as_number(spec.speed_per_min if not spec.comes_ready else None),
            common.as_number(step.net_minutes / 60) if step.net_minutes is not None else None,
        ])
        if spec.kind is StepKind.LEVEL:
            previous_name = name
    common.show_table(page, f"plan_steps:{params['_token']}", table, selectable=False)

    st.markdown(f"**{texts.NEEDS_TABLE}**")
    common.needs_table(page, f"plan_needs:{params['_token']}", order_state.packaging_lines, texts.COL_ITEM)
    if order_state.packable_boxes is not None and order_state.packaging_limiting:
        limiting = ", ".join(common.item_name(page, key) for key in order_state.packaging_limiting)
        st.warning(texts.limiting_packaging(limiting, format_int(order_state.packable_boxes)))
    st.write(texts.sequential_time(format_time(result.sequential_days)))
    st.write(texts.inline_time(format_time(result.inline_days)))
    if order_state.readiness is not None:
        st.write(texts.readiness_estimate(format_date(order_state.readiness)))
        if order_state.arrival is not None:
            st.write(texts.arrival_estimate(format_date(order_state.arrival)))
    else:
        st.caption(texts.NO_START)
    for warning in order_state.warnings:
        if warning.code is WarningCode.ARRIVAL_AFTER_DELIVERY:
            st.warning(texts.warn_arrival_after_delivery(format_date(warning.day), format_date(warning.other_day)))
    st.caption(BASIS_NOTES[order_state.pieces_basis])


@common.dialog("plan_form", "T_PLAN", width="large")
def plan_form(page: Page, params: dict[str, Any]) -> None:
    """Define the packaging steps of one order. Everything updates on every change, before saving."""
    if common.confirmation_pending(page, params):
        return
    order = next(o for o in page.snapshot.orders if o.id == params["order_id"])
    plan = next((p for p in page.snapshot.packaging_plans if p.order_id == order.id), None)
    settings = page.snapshot.settings
    st.caption(order.name)
    fields = Fields()
    left, right = st.columns(2)
    hours = fields.decimal(texts.F_PACK_HOURS, widget_key(params, "hours"),
                           plan.hours_per_day if plan else settings.packaging_hours_per_day, texts.UNIT_HOURS, 2,
                           container=left)
    utilization = fields.stored(texts.F_PACK_UTILIZATION, widget_key(params, "utilization"), percent_to_bp,
                                bp_to_percent, plan.utilization_bp if plan else settings.packaging_utilization_bp,
                                "%", 2, container=right)
    steps_key = widget_key(params, "steps")
    if steps_key not in st.session_state:
        st.session_state[steps_key] = _initial_steps(page, order.id)
    steps: list[dict[str, Any]] = st.session_state[steps_key]
    _step_editor(page, params, steps, fields)
    specs = _specs(steps)
    if specs and hours and utilization and not fields.errors:
        try:
            _preview(page, params, order.id, specs, hours, utilization)
        except (PlanError, ValueError):
            pass
    if common.form_buttons(params, texts.SAVE_PLAN) and fields.ok():
        if specs is None:
            st.error(texts.field_required(texts.F_PACKAGING_ITEM))
            return
        common.run_action(page, params, actions.save_packaging_plan, order.id, hours_per_day=hours,
                          utilization_bp=utilization, steps=specs)


@common.dialog("packaging_complete", "T_COMPLETE_PACKAGING")
def packaging_complete(page: Page, params: dict[str, Any]) -> None:
    """Confirmation with the quantities that will be taken from stock (9.7)."""
    if common.confirmation_pending(page, params):
        return
    order = next(o for o in page.snapshot.orders if o.id == params["order_id"])
    order_state = page.state.orders[order.id]
    result = order_state.packaging
    if result is not None:
        st.write(texts.WILL_DEDUCT)
        for key, quantity in result.requirements.items():
            st.write(f"{common.item_name(page, key)}: {common.quantity_text(key, quantity)}")
        st.write(texts.WILL_SHELVE)
        st.write(texts.shelf_preview(format_int(result.boxes), format_int(result.pieces_per_box),
                                     format_int(result.boxes_per_carton or 0)))
        if result.pallets:
            last = next((s.last_unit_contents for s in result.steps if s.role is StepRole.PALLET), None)
            st.write(texts.pallets_cell(format_int(result.pallets), format_int(last) if last else None))
    if common.form_buttons(params, texts.PK_COMPLETE):
        common.run_action(page, params, actions.complete_packaging, order.id)
