"""Tab 4: Machines and production. Capacity, assignments, inverse calculation, completion (section 8)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st

from core import dates
from core.production_calc import Infeasibility, Lever, inverse_calculation, production_estimate, split_equally
from core.state import OrderStatus
from core.units import (
    bp_to_percent,
    format_date,
    format_int,
    format_kg,
    format_number,
    format_time,
    kg_to_mg,
    mg_to_kg,
    percent_to_bp,
)
from data import actions
from ui import common, texts
from ui.common import Fields, Page, Table, widget_key

TO_PRODUCE = frozenset({OrderStatus.WAITING_MATERIALS, OrderStatus.READY_FOR_PRODUCTION, OrderStatus.IN_PRODUCTION})


def render(page: Page) -> None:
    _machines(page)
    st.divider()
    _to_produce(page)
    st.divider()
    _completed(page)


# ---------------------------------------------------------------- machines


def _machines(page: Page) -> None:
    st.subheader(texts.MA_TITLE, anchor=False)
    bar = st.container()
    table = Table([texts.COL_NAME, texts.COL_BATCH_KG, texts.COL_CYCLE, texts.COL_UTILIZATION,
                   texts.COL_HOURS_PER_DAY, texts.COL_MAX_BATCH, texts.COL_MIN_CYCLE])
    table.formats = {texts.COL_BATCH_KG: common.kg_format, texts.COL_CYCLE: common.time_format,
                     texts.COL_UTILIZATION: common.time_format, texts.COL_HOURS_PER_DAY: common.time_format,
                     texts.COL_MAX_BATCH: common.kg_format, texts.COL_MIN_CYCLE: common.time_format}
    for machine in page.snapshot.machines:
        if machine.is_deleted:
            continue
        table.add(machine.id, [
            machine.name, machine.batch_size_mg, common.as_number(machine.cycle_time_min),
            common.as_number(bp_to_percent(machine.utilization_bp)), common.as_number(machine.hours_per_day),
            machine.max_batch_mg, common.as_number(machine.min_cycle_time_min),
        ])
    table.sort(lambda row: row[0].casefold())
    selected = common.show_table(page, "machines", table)
    with bar:
        pressed = common.toolbar([texts.MA_ADD, texts.EDIT, texts.DELETE], "machines")
        if pressed == texts.MA_ADD:
            common.open_dialog("machine_form")
        elif pressed == texts.EDIT and common.need_selection(selected):
            common.open_dialog("machine_form", machine_id=selected)
        elif pressed == texts.DELETE and common.need_selection(selected):
            machine = next(m for m in page.snapshot.machines if m.id == selected)
            common.confirm_action(texts.CONFIRM_DELETE_TITLE, texts.confirm_delete(machine.name),
                                  actions.delete_machine, selected)


def _machine_title(page: Page, params: dict[str, Any]) -> str:
    return texts.T_EDIT_MACHINE if params.get("machine_id") else texts.T_NEW_MACHINE


@common.dialog("machine_form", _machine_title)
def machine_form(page: Page, params: dict[str, Any]) -> None:
    """Capacity data of a machine, all typed by the user."""
    if common.confirmation_pending(page, params):
        return
    machine = next((m for m in page.snapshot.machines if m.id == params.get("machine_id")), None)
    fields = Fields()
    name = st.text_input(texts.F_MACHINE_NAME, value=machine.name if machine else "", key=widget_key(params, "name"))
    batch = fields.stored(texts.F_BATCH, widget_key(params, "batch"), kg_to_mg, mg_to_kg,
                          machine.batch_size_mg if machine else None, texts.UNIT_KG)
    cycle = fields.decimal(texts.F_CYCLE, widget_key(params, "cycle"), machine.cycle_time_min if machine else None,
                           texts.UNIT_MINUTES, 2)
    utilization = fields.stored(texts.F_UTILIZATION, widget_key(params, "utilization"), percent_to_bp, bp_to_percent,
                                machine.utilization_bp if machine else None, "%", 2, help=texts.UTILIZATION_HELP)
    st.caption(texts.UTILIZATION_HELP)
    # A new machine starts from the default of the settings; an existing one keeps its own hours.
    default_hours = machine.hours_per_day if machine else page.snapshot.settings.machine_hours_per_day
    hours = fields.decimal(texts.F_HOURS, widget_key(params, "hours"), default_hours,
                           texts.UNIT_HOURS, 2)
    max_batch = fields.stored(texts.F_MAX_BATCH, widget_key(params, "max_batch"), kg_to_mg, mg_to_kg,
                              machine.max_batch_mg if machine else None, texts.UNIT_KG)
    min_cycle = fields.decimal(texts.F_MIN_CYCLE, widget_key(params, "min_cycle"),
                               machine.min_cycle_time_min if machine else None, texts.UNIT_MINUTES, 2)
    if common.form_buttons(params) and fields.ok():
        data = actions.MachineInput(name, batch, cycle, utilization, hours, max_batch, min_cycle)
        if machine is None:
            common.run_action(page, params, actions.create_machine, data)
        else:
            common.run_action(page, params, actions.update_machine, machine.id, data)


# ---------------------------------------------------------------- orders to produce


def _to_produce(page: Page) -> None:
    st.subheader(texts.PO_TITLE, anchor=False)
    bar = st.container()
    products = {p.id: p.name for p in page.snapshot.products}
    machines = {m.id: m.name for m in page.snapshot.machines}
    assignments = {a.id: a for a in page.snapshot.assignments}
    table = Table([texts.COL_ORDER, texts.COL_PRODUCT, texts.COL_DESTINATION, texts.COL_QUANTITY_KG, texts.COL_STATUS,
                   texts.COL_MACHINE, texts.COL_ASSIGNED_KG, texts.COL_START, texts.COL_BATCHES, texts.COL_TIME_HOURS,
                   texts.COL_PRODUCTION_DAYS, texts.COL_PRODUCTION_END, texts.COL_PLANNED, texts.COL_EXPECTED_PIECES])
    table.formats = {texts.COL_QUANTITY_KG: common.kg_format, texts.COL_ASSIGNED_KG: common.kg_format,
                     texts.COL_START: common.date_format, texts.COL_BATCHES: common.time_format,
                     texts.COL_TIME_HOURS: common.time_format, texts.COL_PRODUCTION_DAYS: common.time_format,
                     texts.COL_PRODUCTION_END: common.date_format, texts.COL_PLANNED: common.int_format,
                     texts.COL_EXPECTED_PIECES: common.int_format}
    table.colour_column(texts.COL_STATUS)
    for order in page.snapshot.orders:
        order_state = page.state.orders[order.id]
        if order_state.status not in TO_PRODUCE:
            continue
        status, colour = common.order_status_label(order_state)
        base = [order.name, products[order.product_id], order.destination, order.quantity_mg, status]
        open_assignments = [s for s in order_state.assignments if not s.completed]
        if not open_assignments:
            table.add(("order", order.id), base + [None] * 9, {texts.COL_STATUS: colour})
        for assignment_state in open_assignments:
            assignment = assignments[assignment_state.assignment_id]
            estimate = assignment_state.estimate
            table.add(("assignment", assignment.id), base + [
                machines[assignment.machine_id], assignment.quantity_mg, common.as_date(assignment.start_date),
                common.as_number(estimate.batches), common.as_number(estimate.operating_hours),
                common.as_number(estimate.production_days), common.as_date(assignment_state.end_date),
                estimate.planned_pieces, estimate.expected_pieces,
            ], {texts.COL_STATUS: colour})
    table.sort(lambda row: (row[0], row[5] or ""))
    selected = common.show_table(page, "to_produce", table)
    with bar:
        pressed = common.toolbar([texts.PO_ASSIGN, texts.PO_INVERSE, texts.PO_COMPLETE], "to_produce")
        if pressed is None:
            return
        if not common.need_selection(selected):
            return
        kind, row_id = selected
        order_id = row_id if kind == "order" else assignments[row_id].order_id
        if pressed == texts.PO_ASSIGN:
            if not any(not m.is_deleted for m in page.snapshot.machines):
                st.warning(texts.NO_MACHINES)
            else:
                common.open_dialog("assign_form", order_id=order_id)
        elif kind != "assignment":
            st.warning(texts.SELECT_ASSIGNMENT_FIRST)
        elif pressed == texts.PO_INVERSE:
            common.open_dialog("inverse_form", assignment_id=row_id)
        elif pressed == texts.PO_COMPLETE:
            common.open_dialog("complete_form", assignment_id=row_id)


def _results(page: Page, order_unit_weight: int | None, machine_id: int, quantity: int, batch: int,
             cycle: Decimal, defect_bp: int, start: Any) -> None:
    """The results of section 8.3 for one share, recomputed on every field change."""
    machine = next(m for m in page.snapshot.machines if m.id == machine_id)
    try:
        estimate = production_estimate(quantity, batch, cycle, machine.utilization_bp, machine.hours_per_day,
                                       order_unit_weight, defect_bp)
    except ValueError:
        return
    rows = [
        (texts.R_BATCHES, format_time(estimate.batches)),
        (texts.R_NET, f"{format_time(estimate.net_hours)} {texts.UNIT_HOURS}"),
        (texts.R_OPERATING, f"{format_time(estimate.operating_hours)} {texts.UNIT_HOURS}"),
        (texts.R_DAYS, format_time(estimate.production_days)),
    ]
    if estimate.planned_pieces is not None:
        rows += [
            (texts.R_PER_BATCH, format_int(estimate.pieces_per_batch or 0)),
            (texts.R_PLANNED, format_int(estimate.planned_pieces)),
            (texts.R_EXPECTED, format_int(estimate.expected_pieces or 0)),
            (texts.R_DEFECTS, format_int(estimate.expected_defects or 0)),
        ]
    if start is not None:
        end = dates.assignment_end(start, estimate.production_days, page.snapshot.settings.working_days)
        rows.append((texts.R_END, f"{texts.WEEKDAYS[end.weekday()]} {format_date(end)}"))
    frame = pd.DataFrame({texts.COL_VALUE: [value for _, value in rows]}, index=[label for label, _ in rows])
    frame.index.name = texts.COL_RESULT
    st.table(frame)


@common.dialog("assign_form", "T_ASSIGN", width="large")
def assign_form(page: Page, params: dict[str, Any]) -> None:
    """Assign an order to one or more machines; the shares must add up to the quantity to produce."""
    if common.confirmation_pending(page, params):
        return
    order = next(o for o in page.snapshot.orders if o.id == params["order_id"])
    existing = [a for a in page.snapshot.assignments if a.order_id == order.id]
    remaining = order.quantity_mg - sum(a.quantity_mg for a in existing if a.is_completed)
    machines = {m.id: m for m in page.snapshot.machines if not m.is_deleted}
    machine_ids = list(machines)
    st.caption(f"{order.name}. {texts.remaining_note(format_kg(remaining))}")

    shares_key = widget_key(params, "shares")
    if shares_key not in st.session_state:
        open_existing = [a for a in existing if not a.is_completed]
        st.session_state[shares_key] = {"split": 0, "rows": [
            {"token": common.new_token(), "id": a.id, "machine": a.machine_id, "quantity": a.quantity_mg, "batch": a.batch_size_mg,
             "cycle": a.cycle_time_min, "defect": a.defect_bp, "start": a.start_date}
            for a in open_existing
        ] or [{"token": common.new_token(), "id": None, "machine": machine_ids[0], "quantity": remaining, "batch": None, "cycle": None,
               "defect": 0, "start": None}]}
    shares = st.session_state[shares_key]
    fields = Fields()
    inputs: list[actions.AssignmentInput | None] = []
    for number, row in enumerate(shares["rows"], start=1):
        st.markdown(f"**{texts.share_title(number)}**")
        top = st.columns([3, 2, 2, 2])
        machine_id = top[0].selectbox(
            texts.F_MACHINE, machine_ids, index=machine_ids.index(row["machine"]) if row["machine"] in machine_ids else 0,
            format_func=lambda i: machines[i].name, key=widget_key(params, f"share{row['token']}:machine"),
        )
        machine = machines[machine_id]
        key = f"share{row['token']}:{machine_id}:{shares['split']}"
        quantity = fields.stored(texts.F_ORDER_QUANTITY, widget_key(params, f"{key}:quantity"), kg_to_mg, mg_to_kg,
                                 row["quantity"], texts.UNIT_KG, container=top[1])
        same_machine = row["machine"] == machine_id
        batch = fields.stored(texts.F_BATCH, widget_key(params, f"{key}:batch"), kg_to_mg, mg_to_kg,
                              row["batch"] if same_machine and row["batch"] else machine.batch_size_mg,
                              texts.UNIT_KG, container=top[2])
        cycle = fields.decimal(texts.F_CYCLE, widget_key(params, f"{key}:cycle"),
                               row["cycle"] if same_machine and row["cycle"] else machine.cycle_time_min,
                               texts.UNIT_MINUTES, 2, container=top[3])
        bottom = st.columns([2, 2, 1])
        defect = fields.stored(texts.F_DEFECTS, widget_key(params, f"share{row['token']}:defect"), percent_to_bp,
                               bp_to_percent, row["defect"], "%", 2, container=bottom[0], help=texts.DEFECTS_HELP)
        start = common.date_field(texts.F_START, widget_key(params, f"share{row['token']}:start"), row["start"],
                                  required=False, container=bottom[1])
        bottom[2].write("")
        if len(shares["rows"]) > 1 and bottom[2].button(texts.REMOVE, key=widget_key(params, f"share{row['token']}:remove")):
            shares["rows"].pop(number - 1)
            st.rerun(scope="fragment")
        if quantity and batch and cycle:
            _results(page, order.unit_weight_mg, machine_id, quantity, batch, cycle, defect or 0, start)
        row.update({"machine": machine_id, "quantity": quantity, "batch": batch, "cycle": cycle,
                    "defect": defect or 0, "start": start})
        if None in (quantity, batch, cycle):
            inputs.append(None)
        else:
            inputs.append(actions.AssignmentInput(machine_id, quantity, batch, cycle, defect or 0, start, row["id"]))
        st.divider()
    if st.button(texts.ADD_MACHINE_SHARE, key=widget_key(params, "add_share")):
        shares["rows"].append({"token": common.new_token(), "id": None, "machine": machine_ids[0], "quantity": 0, "batch": None,
                               "cycle": None, "defect": 0, "start": None})
        for row, share in zip(shares["rows"], split_equally(remaining, len(shares["rows"]))):
            row["quantity"] = share
        shares["split"] += 1
        st.rerun(scope="fragment")
    if common.form_buttons(params) and fields.ok():
        if any(i is None for i in inputs):
            st.error(texts.field_required(texts.F_ORDER_QUANTITY))
            return
        common.run_action(page, params, actions.set_assignments, order.id, inputs)


# ---------------------------------------------------------------- inverse calculation


def _lever_value(lever: Lever, value: Decimal) -> str:
    if lever is Lever.BATCH_SIZE:
        return f"{format_number(mg_to_kg(value), 2)} {texts.UNIT_KG}"
    if lever is Lever.CYCLE_TIME:
        return f"{format_time(value)} {texts.UNIT_MINUTES}"
    return format_time(value)


@common.dialog("inverse_form", "T_INVERSE", width="large")
def inverse_form(page: Page, params: dict[str, Any]) -> None:
    """Three alternatives that finish in the wanted days, each changing one parameter only (8.4)."""
    assignment = next(a for a in page.snapshot.assignments if a.id == params["assignment_id"])
    machine = next(m for m in page.snapshot.machines if m.id == assignment.machine_id)
    order_state = page.state.orders[assignment.order_id]
    estimate = next(s.estimate for s in order_state.assignments if s.assignment_id == assignment.id)
    st.caption(texts.current_days(format_time(estimate.production_days)))
    fields = Fields()
    target = fields.decimal(texts.F_TARGET_DAYS, widget_key(params, "target"), unit=texts.UNIT_DAYS, decimals=2)
    if target is None or target <= 0:
        return
    options = inverse_calculation(estimate.production_days, target, assignment.cycle_time_min,
                                  assignment.batch_size_mg, machine.hours_per_day, machine.max_batch_mg,
                                  machine.min_cycle_time_min)
    labels = {Lever.CYCLE_TIME: texts.LEVER_CYCLE, Lever.BATCH_SIZE: texts.LEVER_BATCH,
              Lever.HOURS_PER_DAY: texts.LEVER_HOURS}
    reasons = {Infeasibility.ABOVE_24_HOURS: texts.REASON_24, Infeasibility.ABOVE_MAX_BATCH: texts.REASON_MAX_BATCH,
               Infeasibility.BELOW_MIN_CYCLE: texts.REASON_MIN_CYCLE}
    rows = []
    for option in options:
        change = format_number(option.change_percent, 2)
        limit = ""
        if option.limit is not None:
            prefix = texts.LIMIT_MIN if option.lever is Lever.CYCLE_TIME else texts.LIMIT_MAX
            limit = f"{prefix} {_lever_value(option.lever, option.limit)}"
        result = texts.FEASIBLE if option.feasible else f"{texts.INFEASIBLE}: {reasons[option.reason]}"
        rows.append({
            texts.COL_IF_ONLY: labels[option.lever],
            texts.COL_FROM: _lever_value(option.lever, option.current),
            texts.COL_TO: _lever_value(option.lever, option.new),
            texts.COL_CHANGE: f"+{change}%" if option.change_percent > 0 else f"{change}%",
            texts.COL_LIMIT: limit,
            texts.COL_RESULT: result,
        })
    st.table(pd.DataFrame(rows).set_index(texts.COL_IF_ONLY))
    st.caption(texts.INVERSE_NOTE)


# ---------------------------------------------------------------- completion


@common.dialog("complete_form", "T_COMPLETE_PRODUCTION")
def complete_form(page: Page, params: dict[str, Any]) -> None:
    """Planned and expected pieces are shown; the user writes the actual pieces (8.5)."""
    if common.confirmation_pending(page, params):
        return
    assignment = next(a for a in page.snapshot.assignments if a.id == params["assignment_id"])
    order_state = page.state.orders[assignment.order_id]
    estimate = next(s.estimate for s in order_state.assignments if s.assignment_id == assignment.id)
    st.text_input(texts.R_PLANNED, value=format_int(estimate.planned_pieces or 0), disabled=True,
                  key=widget_key(params, "planned"))
    st.text_input(texts.R_EXPECTED, value=format_int(estimate.expected_pieces or 0), disabled=True,
                  key=widget_key(params, "expected"))
    fields = Fields()
    actual = fields.whole(texts.F_ACTUAL_PIECES, widget_key(params, "actual"), unit=texts.UNIT_PIECES)
    if common.form_buttons(params, texts.PO_COMPLETE) and fields.ok():
        if actual is None:
            st.error(texts.field_required(texts.F_ACTUAL_PIECES))
            return
        common.run_action(page, params, actions.complete_assignment, assignment.id, actual_pieces=actual)


def _completed(page: Page) -> None:
    st.subheader(texts.PO_DONE_TITLE, anchor=False)
    orders = {o.id: o.name for o in page.snapshot.orders}
    machines = {m.id: m.name for m in page.snapshot.machines}
    table = Table([texts.COL_ORDER, texts.COL_MACHINE, texts.COL_QUANTITY_KG, texts.COL_PLANNED,
                   texts.COL_EXPECTED_PIECES, texts.COL_ACTUAL, texts.COL_COMPLETED_ON])
    table.formats = {texts.COL_QUANTITY_KG: common.kg_format, texts.COL_PLANNED: common.int_format,
                     texts.COL_EXPECTED_PIECES: common.int_format, texts.COL_ACTUAL: common.int_format,
                     texts.COL_COMPLETED_ON: common.date_format}
    for assignment in page.snapshot.assignments:
        if not assignment.is_completed:
            continue
        estimate = next(s.estimate for s in page.state.orders[assignment.order_id].assignments
                        if s.assignment_id == assignment.id)
        table.add(assignment.id, [
            orders[assignment.order_id], machines[assignment.machine_id], assignment.quantity_mg,
            estimate.planned_pieces, estimate.expected_pieces, assignment.actual_pieces,
            common.as_date(assignment.completed_at.date() if assignment.completed_at else None),
        ])
    table.sort(lambda row: (row[0], row[1]))
    common.show_table(page, "completed", table, selectable=False)
