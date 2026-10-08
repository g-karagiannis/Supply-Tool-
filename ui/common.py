"""Shared UI pieces: page styling, dialogs, tables, input fields and running actions.

Screens never compute: they read the AppState that app.py computes once per run,
and they change data only by calling data/actions.py through run_action().
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st

from core.expiry import STATUS_BACKGROUND, ExpiryStatus, LotExpiry
from core.models import ItemKind, MaterialCategory, Snapshot
from core.state import AppState, ExpectedReceipt, OrderFlag, OrderState, OrderStatus, WarningCode
from core.units import (
    UnitError,
    format_date,
    format_int,
    format_kg,
    format_number,
    format_time,
    parse_decimal,
    parse_whole,
)
from data.actions import ActionError, NeedsConfirmation
from data.db import Connection
from ui import texts

# Dark theme details that .streamlit/config.toml cannot express: tight
# tracking, weights capped at 590, hairline borders instead of shadows, and
# neutral outline buttons so that the accent colour marks only primary actions.
_THEME_CSS = """
<style>
:root {
    --void: #08090a; --carbon: #0f1011; --obsidian: #161718;
    --graphite: #23252a; --smoke: #383b3f; --ash: #62666d; --fog: #8a8f98;
    --mist: #d0d6e0; --paper: #ffffff; --lime: #e4f222;
}
html, body, .stApp {
    background: var(--void);
    font-feature-settings: "cv01" on, "ss03" on, "zero" on;
}
.stApp { color: var(--mist); letter-spacing: -0.010em; }

h1, h2, h3, h4, h5, h6 { color: var(--paper) !important; font-weight: 510 !important; }
h1 { font-size: 2rem !important; letter-spacing: -0.022em !important; line-height: 1.1 !important; }
h2, h3 { letter-spacing: -0.012em !important; }
strong, b { color: var(--paper); font-weight: 590; }
[data-testid="stCaptionContainer"], small { color: var(--fog) !important; }

.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    background: transparent;
    border: 1px solid var(--graphite);
    color: var(--mist);
    font-weight: 400; font-size: 13px; letter-spacing: -0.010em;
    box-shadow: none; transition: border-color .12s, background .12s;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
    background: rgba(255,255,255,0.04);
    border-color: var(--smoke);
    color: var(--paper);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background: var(--lime); color: var(--void); border-color: var(--lime);
    font-weight: 510; font-size: 14px; letter-spacing: -0.011em;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
    background: #eef55a; color: var(--void);
}
.stButton > button:disabled { opacity: 0.4; }

div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {
    background: rgba(255,255,255,0.02) !important;
    border-color: rgba(255,255,255,0.08) !important;
}
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="textarea"]:focus-within {
    border-color: var(--mist) !important;
}

[data-baseweb="tag"] { background: var(--graphite) !important; }
[data-baseweb="tag"] span { color: var(--mist) !important; }
[data-testid="stTab"] { color: var(--fog) !important; }
[data-testid="stTab"] p { font-size: 13px !important; }
[data-testid="stTab"]:hover { color: var(--mist) !important; }
[data-testid="stTab"][aria-selected="true"] { color: var(--paper) !important; }

[data-testid="stExpander"] details {
    background: var(--carbon);
    border: none !important;
    box-shadow: rgb(35,37,42) 0 0 0 1px inset;
    border-radius: 12px;
}
[data-testid="stDataFrame"] { border: 1px solid var(--graphite); border-radius: 6px; }
/* Tables sort by clicking a header and nothing else: no search box, no download (11.1). */
[data-testid="stElementToolbar"] { display: none !important; }

[data-testid="stAlertContainer"] {
    background: var(--obsidian) !important;
    box-shadow: rgb(35,37,42) 0 0 0 1px inset;
    border-left: 2px solid var(--fog);
}
[data-testid="stAlertContainer"] * { color: var(--mist) !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"])    { border-left-color: #02b8cc; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) { border-left-color: #27a644; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) { border-left-color: #f2994a; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"])   { border-left-color: #eb5757; }

div[role="dialog"] { background: var(--carbon); box-shadow: rgb(35,37,42) 0 0 0 1px inset; }
code { font-size: 0.85em; letter-spacing: -0.013em; }
hr { border-color: var(--graphite) !important; }
.st-key-undo_bar { border-bottom: 1px solid var(--graphite); padding-bottom: 8px; }
</style>
"""

# Background colours that accompany order and receipt status words.
STATUS_COLOURS = {
    "ok": "#12301c",
    "warn": "#3a3510",
    "bad": "#4a1616",
    "neutral": "#23252a",
    "info": "#0f2a33",
    "progress": "#1c2550",
}


def apply_theme() -> None:
    """Inject the page CSS. Call once per run, before any other element."""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


class Lazy(Mapping):
    """A label table built anew on every read, so it always speaks the current language."""

    def __init__(self, build: Callable[[], dict]) -> None:
        self._build = build

    def __getitem__(self, key: Any) -> Any:
        return self._build()[key]

    def __iter__(self):
        return iter(self._build())

    def __len__(self) -> int:
        return len(self._build())


@dataclass
class Page:
    """Everything a screen needs in one run: the connection and one computed state."""

    conn: Connection
    snapshot: Snapshot
    state: AppState
    version: str


# ---------------------------------------------------------------- dialogs

_DIALOG_KEY = "open_dialog"
_FLASH_KEY = "flash"
_DialogFunc = Callable[[Page, dict[str, Any]], None]
_DIALOGS: dict[str, tuple[str | Callable[[Page, dict[str, Any]], str], str, _DialogFunc]] = {}
_tokens = itertools.count(1)


def dialog(name: str, title: str | Callable[[Page, dict[str, Any]], str], width: str = "medium"):
    """Register a dialog body under a name, so that open_dialog(name) can show it.

    title is either a function of the page and parameters, or the name of a
    text in ui/texts (e.g. "T_TRANSFER"), read when the dialog opens.
    """
    def register(func: _DialogFunc) -> _DialogFunc:
        _DIALOGS[name] = (title, width, func)
        return func
    return register


def open_dialog(name: str, **params: Any) -> None:
    """Open a registered dialog with parameters, on the next run."""
    params["_token"] = next(_tokens)
    st.session_state[_DIALOG_KEY] = {"name": name, "params": params}
    st.rerun()


def close_dialog() -> None:
    st.session_state.pop(_DIALOG_KEY, None)


def _dismissed() -> None:
    active = st.session_state.pop(_DIALOG_KEY, None)
    if active:
        st.session_state.pop(f"pending:{active['params']['_token']}", None)


def show_dialog(page: Page) -> None:
    """Show the open dialog, if any. Called once per run, after the page."""
    active = st.session_state.get(_DIALOG_KEY)
    if not active or active["name"] not in _DIALOGS:
        return
    title, width, func = _DIALOGS[active["name"]]
    heading = title(page, active["params"]) if callable(title) else getattr(texts, title)
    st.dialog(heading, width=width, on_dismiss=_dismissed)(func)(page, active["params"])


def new_token() -> int:
    """A fresh number for keys of rows that can be added and removed."""
    return next(_tokens)


def widget_key(params: dict[str, Any], name: str) -> str:
    """A widget key unique to one opening of a dialog, so old values never leak in."""
    return f"d{params['_token']}:{name}"


def flash(message: str) -> None:
    st.session_state[_FLASH_KEY] = message


def show_flash() -> None:
    message = st.session_state.pop(_FLASH_KEY, None)
    if message:
        st.toast(message)


# ---------------------------------------------------------------- running actions


def run_action(page: Page, params: dict[str, Any] | None, func: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
    """Call a data action. On success close the dialog and rerun the whole page.

    If the action needs a confirmation, the messages are kept and shown by
    confirmation_pending() in the same dialog. A rejection is shown right here,
    next to the button that caused it, and False is returned.
    """
    try:
        func(page.conn, *args, **kwargs)
    except NeedsConfirmation as asked:
        if params is None:
            raise
        st.session_state[f"pending:{params['_token']}"] = (func, args, kwargs, asked.messages)
        st.rerun(scope="fragment")
    except ActionError as error:
        st.error(str(error))
        return False
    flash(texts.SAVED)
    close_dialog()
    st.rerun()
    return True


def confirmation_pending(page: Page, params: dict[str, Any]) -> bool:
    """Show a pending confirmation with "Συνέχεια" and "Ακύρωση". True while one is pending."""
    key = f"pending:{params['_token']}"
    pending = st.session_state.get(key)
    if pending is None:
        return False
    func, args, kwargs, messages = pending
    for message in messages:
        st.warning(message)
    left, right = st.columns(2)
    if left.button(texts.CONTINUE, key=widget_key(params, "confirm_yes"), type="primary", width="stretch"):
        st.session_state.pop(key, None)
        run_action(page, params, func, *args, **{**kwargs, "confirm": True})
    if right.button(texts.CANCEL, key=widget_key(params, "confirm_no"), width="stretch"):
        st.session_state.pop(key, None)
        st.rerun(scope="fragment")
    return True


@dialog("confirm", lambda page, params: params["title"], width="small")
def _confirm_dialog(page: Page, params: dict[str, Any]) -> None:
    """A plain "are you sure" dialog in front of an action."""
    if confirmation_pending(page, params):
        return
    st.write(params["message"])
    left, right = st.columns(2)
    if left.button(texts.CONTINUE, key=widget_key(params, "yes"), type="primary", width="stretch"):
        run_action(page, params, params["func"], *params.get("args", ()), **params.get("kwargs", {}))
    if right.button(texts.CANCEL, key=widget_key(params, "no"), width="stretch"):
        close_dialog()
        st.rerun()


def confirm_action(title: str, message: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Ask "Συνέχεια" or "Ακύρωση" before running an action."""
    open_dialog("confirm", title=title, message=message, func=func, args=args, kwargs=kwargs)


def form_buttons(params: dict[str, Any], save_label: str = texts.SAVE) -> bool:
    """"Αποθήκευση" and "Ακύρωση" at the bottom of a dialog. True when save is pressed."""
    left, right = st.columns(2)
    saved = left.button(save_label, key=widget_key(params, "save"), type="primary", width="stretch")
    if right.button(texts.CANCEL, key=widget_key(params, "cancel"), width="stretch"):
        close_dialog()
        st.rerun()
    return saved


# ---------------------------------------------------------------- tables


@dataclass
class Table:
    """A sortable table: one DataFrame row per item, with the item ids alongside.

    Values keep their real type (numbers, dates) so that clicking a header
    sorts them correctly; the Greek format is applied only for display.
    """

    columns: list[str]
    rows: list[list[Any]] = field(default_factory=list)
    ids: list[Any] = field(default_factory=list)
    formats: dict[str, Callable[[Any], str]] = field(default_factory=dict)
    colours: dict[str, list[str | None]] = field(default_factory=dict)
    checkboxes: tuple[str, ...] = ()
    row_formats: list[dict[str, Callable[[Any], str]]] = field(default_factory=list)

    def add(
        self,
        item_id: Any,
        values: Sequence[Any],
        colours: dict[str, str | None] | None = None,
        formats: dict[str, Callable[[Any], str]] | None = None,
    ) -> None:
        """Add a row. formats overrides column formats for this row only, e.g. kg or pieces."""
        self.ids.append(item_id)
        self.rows.append(list(values))
        self.row_formats.append(formats or {})
        for column in self.colours:
            self.colours[column].append((colours or {}).get(column))

    def colour_column(self, column: str) -> None:
        self.colours.setdefault(column, [None] * len(self.rows))

    def sort(self, key: Callable[[list[Any]], Any]) -> None:
        """Initial order of the rows. Sorting by clicking a header only changes the display."""
        order = sorted(range(len(self.rows)), key=lambda i: key(self.rows[i]))
        self.rows = [self.rows[i] for i in order]
        self.ids = [self.ids[i] for i in order]
        self.row_formats = [self.row_formats[i] for i in order]
        for column, values in self.colours.items():
            self.colours[column] = [values[i] for i in order]


def kg_format(value: Any) -> str:
    return format_kg(int(value))


def pallets_format(last_pallet_cartons: int | None) -> Callable[[Any], str]:
    """E.g. "13 παλέτες (η τελευταία με 5 κιβώτια)"; the number stays sortable."""
    last = format_int(last_pallet_cartons) if last_pallet_cartons else None
    return lambda value: texts.pallets_cell(format_int(int(value)), last)


def kg_unit_format(value: Any) -> str:
    return f"{format_kg(int(value))} {texts.UNIT_KG}"


def int_format(value: Any) -> str:
    return format_int(int(value))


def time_format(value: Any) -> str:
    return format_time(Decimal(str(value)))


def date_format(value: Any) -> str:
    return format_date(value.date() if isinstance(value, (pd.Timestamp, datetime)) else value)


def text_format(value: Any) -> str:
    return str(value)


def as_date(value: date | None) -> pd.Timestamp | None:
    """A date column value: real dates sort chronologically."""
    return pd.Timestamp(value) if value is not None else None


def as_number(value: int | Decimal | None) -> float | int | None:
    if value is None:
        return None
    return float(value) if isinstance(value, Decimal) else value


def show_table(page: Page, name: str, table: Table, height: int | str = "auto", selectable: bool = True) -> Any | None:
    """Draw a table and return the id of the selected row. Read-only tables pass selectable=False."""
    if not table.rows:
        st.caption(texts.NO_ROWS)
        return None
    frame = pd.DataFrame(table.rows, columns=table.columns)
    for column in table.columns:
        if column in table.checkboxes:
            frame[column] = frame[column].astype(bool)
    styler = frame.style.format(
        {c: f for c, f in table.formats.items() if c in frame.columns and c not in table.checkboxes},
        na_rep="",
    )
    groups: dict[tuple[str, Callable[[Any], str]], list[int]] = {}
    for index, formats in enumerate(table.row_formats):
        for column, formatter in formats.items():
            groups.setdefault((column, formatter), []).append(index)
    for (column, formatter), indices in groups.items():
        styler = styler.format(formatter, subset=pd.IndexSlice[indices, [column]], na_rep="")
    for column, colours in table.colours.items():
        css = [f"background-color: {c}" if c else "" for c in colours]
        styler = styler.apply(lambda _col, css=css: css, subset=[column])
    config = {c: st.column_config.CheckboxColumn(c, disabled=True) for c in table.checkboxes}
    event = st.dataframe(
        styler,
        key=f"table:{name}:{page.version}",
        on_select="rerun" if selectable else "ignore",
        selection_mode="single-row",
        hide_index=True,
        width="stretch",
        column_config=config or None,
        height=height,
        placeholder="",
    )
    if not selectable:
        return None
    rows = event.selection.rows
    return table.ids[rows[0]] if rows and rows[0] < len(table.ids) else None


def toolbar(labels: Sequence[str], key: str) -> str | None:
    """A row of buttons above a table. Returns the label of the pressed button."""
    pressed = None
    with st.container(horizontal=True, gap="small"):
        for label in labels:
            if st.button(label, key=f"{key}:{label}"):
                pressed = label
    return pressed


def need_selection(selected: Any | None) -> bool:
    """True if a row is selected; otherwise show "Επίλεξε πρώτα μια γραμμή"."""
    if selected is None:
        st.warning(texts.SELECT_ROW_FIRST)
        return False
    return True


# ---------------------------------------------------------------- input fields


def input_text(value: Decimal | int | None) -> str:
    """How a stored value is prefilled in a text field: plain digits, decimal comma, no grouping."""
    if value is None:
        return ""
    text = format(Decimal(value).normalize(), "f")
    return text.replace(".", ",")


@dataclass
class Fields:
    """Collects the problems of typed numbers in one form, so saving can be blocked."""

    errors: list[str] = field(default_factory=list)

    def decimal(
        self,
        label: str,
        key: str,
        default: Decimal | None = None,
        unit: str = "",
        decimals: int = 3,
        whole: bool = False,
        container: Any = None,
        disabled: bool = False,
        help: str | None = None,
    ) -> Decimal | None:
        """A number typed with comma or dot. Shows how it was read, e.g. "= 1.000 kg"."""
        area = container or st
        text = area.text_input(label, value=input_text(default), key=key, disabled=disabled, help=help)
        if not text.strip():
            return None
        try:
            value = parse_decimal(text)
        except UnitError:
            area.caption(texts.NOT_A_NUMBER)
            self.errors.append(texts.NOT_A_NUMBER)
            return None
        if whole and value != value.to_integral_value():
            area.caption(texts.field_whole(label))
            self.errors.append(texts.field_whole(label))
            return None
        area.caption(texts.parsed_as(format_number(value, decimals), unit))
        return value

    def stored(
        self,
        label: str,
        key: str,
        to_storage: Callable[[Decimal], int],
        from_storage: Callable[[int], Decimal],
        default: int | None = None,
        unit: str = "",
        decimals: int = 3,
        container: Any = None,
        disabled: bool = False,
        help: str | None = None,
    ) -> int | None:
        """A typed number converted to its storage unit, e.g. kg to mg."""
        value = self.decimal(label, key, from_storage(default) if default is not None else None, unit,
                             decimals, container=container, disabled=disabled, help=help)
        if value is None:
            return None
        try:
            return to_storage(value)
        except UnitError:
            self.errors.append(texts.field_decimals(label))
            (container or st).caption(texts.field_decimals(label))
            return None

    def whole(self, label: str, key: str, default: int | None = None, unit: str = "",
              container: Any = None, disabled: bool = False, help: str | None = None) -> int | None:
        """A whole number. Dots group thousands here, so "385.000" means 385000."""
        area = container or st
        text = area.text_input(label, value=input_text(default), key=key, disabled=disabled, help=help)
        if not text.strip():
            return None
        try:
            value = parse_whole(text)
        except UnitError:
            area.caption(texts.field_whole(label))
            self.errors.append(texts.field_whole(label))
            return None
        area.caption(texts.parsed_as(format_int(value), unit))
        return value

    def ok(self) -> bool:
        if self.errors:
            st.error(self.errors[0])
            return False
        return True


def text_or_empty(value: str | None) -> str:
    return value or ""


def date_field(label: str, key: str, default: date | None = None, required: bool = True,
               container: Any = None, disabled: bool = False) -> date | None:
    """A date shown as DD/MM/YYYY. Optional dates start empty."""
    area = container or st
    value = area.date_input(label, value=default if (default or not required) else "today",
                            key=key, format="DD/MM/YYYY", disabled=disabled)
    return value if isinstance(value, date) else None


def line_editor(
    params: dict[str, Any],
    name: str,
    options: dict[int, str],
    initial: Sequence[tuple[int | None, Decimal | None]],
    fields: Fields,
    item_label: str,
    value_label: str,
    add_label: str,
    unit: str = "",
    decimals: int = 2,
    whole: bool = False,
) -> list[tuple[int | None, Decimal | None]]:
    """Rows of (item, number), e.g. recipe lines of material and percentage.

    The rows live in session state for as long as the dialog is open; each
    row has a remove button, and add_label appends an empty row.
    """
    rows_key = widget_key(params, f"{name}:rows")
    if rows_key not in st.session_state:
        tokens = [next(_tokens) for _ in initial]
        st.session_state[rows_key] = tokens
        st.session_state[rows_key + ":initial"] = dict(zip(tokens, initial))
    tokens: list[int] = st.session_state[rows_key]
    initial_values: dict[int, tuple[int | None, Decimal | None]] = st.session_state[rows_key + ":initial"]
    option_ids = list(options)
    result: list[tuple[int | None, Decimal | None]] = []
    for token in list(tokens):
        item_id, value = initial_values.get(token, (None, None))
        left, middle, right = st.columns([4, 2, 1], vertical_alignment="top")
        chosen = left.selectbox(
            item_label, option_ids, index=option_ids.index(item_id) if item_id in option_ids else None,
            format_func=lambda i: options.get(i, ""), key=widget_key(params, f"{name}:{token}:item"),
            placeholder=item_label,
        )
        number = fields.decimal(value_label, widget_key(params, f"{name}:{token}:value"), value, unit,
                                decimals, whole=whole, container=middle)
        right.write("")
        if right.button(texts.REMOVE, key=widget_key(params, f"{name}:{token}:remove")):
            tokens.remove(token)
            st.rerun(scope="fragment")
        result.append((chosen, number))
    if st.button(add_label, key=widget_key(params, f"{name}:add")):
        tokens.append(next(_tokens))
        st.rerun(scope="fragment")
    return result


# ---------------------------------------------------------------- labels for computed values

CATEGORY_LABELS = Lazy(lambda: {
    MaterialCategory.RAW_MATERIAL: texts.CATEGORY_RAW_MATERIAL,
    MaterialCategory.EXCIPIENT: texts.CATEGORY_EXCIPIENT,
    MaterialCategory.PACKAGING_MATERIAL: texts.CATEGORY_PACKAGING_MATERIAL,
})

ORDER_STATUS = Lazy(lambda: {
    OrderStatus.CANCELLED: (texts.STATUS_CANCELLED, STATUS_COLOURS["neutral"]),
    OrderStatus.SHIPPED: (texts.STATUS_SHIPPED, STATUS_COLOURS["neutral"]),
    OrderStatus.TRANSFERRED: (texts.STATUS_TRANSFERRED, STATUS_COLOURS["neutral"]),
    OrderStatus.ON_SHELF: (texts.STATUS_ON_SHELF, STATUS_COLOURS["info"]),
    OrderStatus.IN_PACKAGING: (texts.STATUS_IN_PACKAGING, STATUS_COLOURS["info"]),
    OrderStatus.IN_PRODUCTION: (texts.STATUS_IN_PRODUCTION, STATUS_COLOURS["progress"]),
    OrderStatus.READY_FOR_PRODUCTION: (texts.STATUS_READY, STATUS_COLOURS["ok"]),
    OrderStatus.WAITING_MATERIALS: (texts.STATUS_WAITING, STATUS_COLOURS["bad"]),
})

FLAG_LABELS = Lazy(lambda: {
    OrderFlag.NO_MACHINE: texts.FLAG_NO_MACHINE,
    OrderFlag.NO_PACKAGING_PLAN: texts.FLAG_NO_PACKAGING_PLAN,
    OrderFlag.MISSING_PACKAGING: texts.FLAG_MISSING_PACKAGING,
})


def expiry_label(expiry: LotExpiry) -> tuple[str, str]:
    """Status word and background colour of a LOT (section 4.1)."""
    if expiry.status is ExpiryStatus.DEPLETED:
        text = texts.DEPLETED
    elif expiry.status is ExpiryStatus.EXPIRED:
        text = texts.EXPIRY_EXPIRED
    elif expiry.status is ExpiryStatus.GREEN:
        text = texts.EXPIRY_VALID
    else:
        text = texts.expires_in(expiry.days_left)
    return text, STATUS_BACKGROUND[expiry.status]


def order_status_label(order_state: OrderState) -> tuple[str, str]:
    """Status word with its indications, and its background colour (section 4.10)."""
    text, colour = ORDER_STATUS[order_state.status]
    flags = [FLAG_LABELS[flag] for flag in order_state.flags]
    return (", ".join([text] + flags), colour)


def expected_text(expected: Sequence[ExpectedReceipt], kind: ItemKind) -> str:
    """E.g. "+200 kg στις 14/10/2026, +50 kg στις 20/10/2026"."""
    parts = []
    for receipt in expected:
        if kind is ItemKind.MATERIAL:
            quantity = f"{format_kg(receipt.quantity)} {texts.UNIT_KG}"
        else:
            quantity = format_int(receipt.quantity)
        parts.append(texts.expected_entry(quantity, format_date(receipt.receipt_date)))
    return ", ".join(parts)


def item_name(page: Page, key: tuple[ItemKind, int]) -> str:
    """Name of a material or packaging item by stock key."""
    kind, item_id = key
    items = page.snapshot.materials if kind is ItemKind.MATERIAL else page.snapshot.packaging_items
    return next((i.name for i in items if i.id == item_id), "")


def quantity_text(key: tuple[ItemKind, int], quantity: int) -> str:
    """kg for a material, pieces for a packaging item."""
    if key[0] is ItemKind.MATERIAL:
        return f"{format_kg(quantity)} {texts.UNIT_KG}"
    return f"{format_int(quantity)} {texts.UNIT_PCS}"


def warning_texts(page: Page, order_state: OrderState, short: bool = False) -> list[str]:
    """The warnings of section 4.12 for one order, in full or as short labels for tables."""
    lots = {lot.id: lot for lot in page.snapshot.lots}
    result = []
    for warning in order_state.warnings:
        code = warning.code
        if code is WarningCode.START_BEFORE_RECEIPT:
            result.append(texts.WARN_SHORT_START if short else texts.warn_start_before_receipt(
                item_name(page, warning.item_key), format_date(warning.day)))
        elif code is WarningCode.NO_COVERING_RECEIPT:
            name = item_name(page, warning.item_key)
            result.append(texts.warn_short_no_receipt(name) if short else texts.warn_no_covering_receipt(
                name, quantity_text(warning.item_key, warning.quantity or 0)))
        elif code is WarningCode.ARRIVAL_AFTER_DELIVERY:
            result.append(texts.WARN_SHORT_ARRIVAL if short else texts.warn_arrival_after_delivery(
                format_date(warning.day), format_date(warning.other_day)))
        elif code is WarningCode.RED_LOT:
            lot = lots[warning.lot_id]
            result.append(texts.WARN_SHORT_RED_LOT if short else texts.warn_red_lot(
                lot.lot_number, item_name(page, warning.item_key), warning.days or 0))
    if short:
        result = list(dict.fromkeys(result))
    return result


def needs_table(page: Page, name: str, lines: Sequence[Any], first_column: str = texts.COL_MATERIAL) -> None:
    """Shortage table: need, available at the order's turn, missing, and expected receipts."""
    table = Table([first_column, texts.COL_NEED, texts.COL_AVAILABLE, texts.COL_MISSING, texts.COL_EXPECTED])
    numbers = (texts.COL_NEED, texts.COL_AVAILABLE, texts.COL_MISSING)
    for line in lines:
        stock = page.state.stock(line.key)
        formatter = kg_unit_format if line.key[0] is ItemKind.MATERIAL else int_format
        table.add(line.key, [
            item_name(page, line.key), line.need, line.pool, line.shortage,
            expected_text(stock.expected, line.key[0]) if stock else "",
        ], formats={column: formatter for column in numbers})
    show_table(page, name, table, selectable=False)
