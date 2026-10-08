"""Entry point: page setup, the undo bar and the seven navigation options.

Run with ``streamlit run app.py`` from the project folder.

Every run loads the whole database once, computes the state once, and draws
the open tab from that state, so no screen can show an old number.
"""

from __future__ import annotations

import streamlit as st

from core.state import compute_state
from data import db, history
from data.repositories import data_version, get_language, last_undoable, load_snapshot, set_language
from ui import common, movements, orders, packaging, production, products, settings, texts, warehouse

# In the order of texts.NAV_LABELS, so they follow the current language.
PAGES = (
    warehouse.render,
    products.render,
    orders.render,
    production.render,
    packaging.render,
    movements.render,
    settings.render,
)


def _connection():
    """One SQLite connection per browser session, opened after the schema is up to date."""
    if "conn" not in st.session_state:
        db.init_db(db.DEFAULT_DB_PATH)
        st.session_state["conn"] = db.connect(db.DEFAULT_DB_PATH, shared=True)
    return st.session_state["conn"]


@common.dialog("undo", "UNDO", width="small")
def _undo_dialog(page: common.Page, params: dict) -> None:
    entry = last_undoable(page.conn)
    if entry is None:
        st.write(texts.NOTHING_TO_UNDO)
        return
    st.write(texts.undo_confirm(entry.description))
    left, right = st.columns(2)
    if left.button(texts.CONTINUE, key=common.widget_key(params, "yes"), type="primary", width="stretch"):
        try:
            history.undo_last(page.conn)
        except history.NothingToUndo:
            st.error(texts.NOTHING_TO_UNDO)
            return
        common.flash(texts.UNDONE)
        common.close_dialog()
        st.rerun()
    if right.button(texts.CANCEL, key=common.widget_key(params, "no"), width="stretch"):
        common.close_dialog()
        st.rerun()


def _language_changed(conn) -> None:
    """Switch language, remember it, and keep the user on the same tab under its new name."""
    # The tabs get new labels, so Streamlit treats them as a new widget that opens
    # on its default; main() makes the tab open before the switch that default.
    st.session_state["nav_default"] = st.session_state.get("nav_open", 0)
    code = st.session_state["language"]
    texts.set_language(code)
    set_language(conn, code)


def _language_switch(conn) -> None:
    """ΕΛ | EN, at the top right of every page."""
    st.session_state.setdefault("language", texts.language())
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.segmented_control(
            "language", list(texts.LANGUAGES), format_func=texts.LANGUAGE_LABELS.get, key="language",
            label_visibility="collapsed", required=True, on_change=_language_changed, args=(conn,),
        )


def _undo_bar(page: common.Page) -> None:
    """The undo button and the description of what it will undo, above every tab."""
    entry = last_undoable(page.conn)
    with st.container(key="undo_bar", horizontal=True, vertical_alignment="center"):
        if st.button(texts.UNDO, key="undo_button", disabled=entry is None):
            common.open_dialog("undo")
        st.caption(texts.undo_label(entry.description) if entry else texts.NOTHING_TO_UNDO)


def main() -> None:
    """Build the page. Streamlit calls this on every rerun."""
    conn = _connection()
    texts.set_language(get_language(conn))
    st.set_page_config(page_title=texts.PAGE_TITLE, layout="wide")
    common.apply_theme()
    snapshot = load_snapshot(conn)
    version = "{}-{}".format(*data_version(conn))
    page = common.Page(conn=conn, snapshot=snapshot, state=compute_state(snapshot), version=version)

    title, switch = st.columns([6, 1], vertical_alignment="center")
    title.title(texts.PAGE_TITLE, anchor=False)
    with switch:
        _language_switch(conn)
    _undo_bar(page)
    common.show_flash()

    # Stateful tabs: the selected label lives in st.session_state["nav"], so the
    # user stays on the same tab after every action, and only that tab runs.
    default = texts.NAV_LABELS[st.session_state.get("nav_default", 0)]
    tabs = st.tabs(list(texts.NAV_LABELS), key="nav", default=default, on_change="rerun")
    for index, (render, tab) in enumerate(zip(PAGES, tabs)):
        if tab.open:
            st.session_state["nav_open"] = index
            with tab:
                render(page)
    common.show_dialog(page)


main()
