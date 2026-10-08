"""Settings, action history and backup (sections 11.3 and 11.5)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.models import Settings
from core.units import bp_to_percent, percent_to_bp
from data import actions, db
from data.repositories import list_history, wipe_all_data
from ui import common, texts
from ui.common import Fields, Page, Table


def render(page: Page) -> None:
    _settings(page)
    st.divider()
    _backup()
    st.divider()
    _wipe()
    st.divider()
    _history(page)


def _settings(page: Page) -> None:
    st.subheader(texts.ST_SETTINGS, anchor=False)
    current = page.snapshot.settings
    key = f"settings:{page.version}"
    fields = Fields()
    left, right = st.columns(2)
    yellow = fields.whole(texts.F_YELLOW, f"{key}:yellow", current.yellow_days, texts.UNIT_DAYS, container=left)
    red = fields.whole(texts.F_RED, f"{key}:red", current.red_days, texts.UNIT_DAYS, container=right)
    days = st.multiselect(texts.F_WORKING_DAYS, list(range(7)), default=sorted(current.working_days),
                          format_func=lambda d: texts.WEEKDAYS[d], key=f"{key}:days")
    machine_hours = fields.decimal(texts.F_MACHINE_HOURS, f"{key}:machine_hours", current.machine_hours_per_day,
                                   texts.UNIT_HOURS, 2, help=texts.F_MACHINE_HOURS_HELP)
    transit = fields.whole(texts.F_DEFAULT_TRANSIT, f"{key}:transit", current.default_transit_days, texts.UNIT_DAYS,
                           help=texts.F_DEFAULT_TRANSIT_HELP)
    left, right = st.columns(2)
    hours = fields.decimal(texts.F_PACKAGING_HOURS, f"{key}:hours", current.packaging_hours_per_day, texts.UNIT_HOURS,
                           2, container=left, help=texts.F_PACKAGING_DEFAULTS_HELP)
    utilization = fields.stored(texts.F_PACKAGING_UTILIZATION, f"{key}:utilization", percent_to_bp, bp_to_percent,
                                current.packaging_utilization_bp, "%", 2, container=right,
                                help=texts.F_PACKAGING_DEFAULTS_HELP)
    if st.button(texts.SAVE_SETTINGS, key=f"{key}:save", type="primary") and fields.ok():
        if None in (yellow, red, machine_hours, transit, hours, utilization):
            st.error(texts.field_required(texts.ST_SETTINGS))
            return
        updated = Settings(yellow_days=yellow, red_days=red, working_days=frozenset(days),
                           machine_hours_per_day=machine_hours, default_transit_days=transit, packaging_hours_per_day=hours,
                           packaging_utilization_bp=utilization)
        try:
            actions.update_settings(page.conn, updated)
        except actions.ActionError as error:
            st.error(str(error))
            return
        common.flash(texts.SAVED)
        st.rerun()


def _backup() -> None:
    st.subheader(texts.ST_BACKUP, anchor=False)
    if st.button(texts.ST_BACKUP, key="backup"):
        target = db.backup_database(db.DEFAULT_DB_PATH, db.BACKUPS_DIR)
        st.success(texts.backup_done(str(target)))


def _wipe() -> None:
    st.subheader(texts.ST_WIPE, anchor=False)
    st.caption(texts.WIPE_NOTE)
    if st.button(texts.ST_WIPE, key="wipe"):
        common.open_dialog("wipe_all")


@common.dialog("wipe_all", "ST_WIPE", width="small")
def wipe_dialog(page: Page, params: dict) -> None:
    """Take a backup, then delete every row and restore the default settings."""
    st.write(texts.WIPE_CONFIRM)
    left, right = st.columns(2)
    if left.button(texts.CONTINUE, key=common.widget_key(params, "yes"), type="primary", width="stretch"):
        target = db.backup_database(db.DEFAULT_DB_PATH, db.BACKUPS_DIR)
        wipe_all_data(page.conn)
        # Forget table selections of the old data, so no row of the new data starts selected.
        for key in [k for k in st.session_state if str(k).startswith("table:")]:
            del st.session_state[key]
        common.flash(texts.wipe_done(str(target)))
        common.close_dialog()
        st.rerun()
    if right.button(texts.CANCEL, key=common.widget_key(params, "no"), width="stretch"):
        common.close_dialog()
        st.rerun()


def _history(page: Page) -> None:
    st.subheader(texts.ST_HISTORY, anchor=False)
    table = Table([texts.COL_WHEN, texts.COL_ACTION, texts.COL_DESCRIPTION, texts.COL_UNDONE],
                  checkboxes=(texts.COL_UNDONE,))
    table.formats = {texts.COL_WHEN: lambda v: v.strftime("%d/%m/%Y %H:%M")}
    for entry in list_history(page.conn):
        table.add(entry.id, [pd.Timestamp(entry.created_at), texts.ACTION_LABELS.get(entry.action_code, entry.action_code),
                             entry.description, entry.undone_at is not None])
    common.show_table(page, "history", table, selectable=False)
