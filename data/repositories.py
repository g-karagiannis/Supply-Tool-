"""Reading the whole database into a Snapshot, and row-level writes.

Every write goes through a Writer, which keeps the image of each changed row
before and after the change. Those images are what history.py stores and what
undo restores.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from core import dates
from core.models import (
    HistoryEntry,
    ItemKind,
    Machine,
    Material,
    MaterialCategory,
    MaterialLot,
    Order,
    OrderAssignment,
    OrderRecipeLine,
    PackagingItem,
    PackagingItemComponent,
    PackagingItemType,
    PackagingPlan,
    PackagingStep,
    PackagingStepExtra,
    Product,
    Receipt,
    RecipeLine,
    Settings,
    ShelfLine,
    ShelfTransfer,
    Shipment,
    Snapshot,
    StepKind,
    StepRole,
)
from data.db import transaction

Row = dict[str, Any]

# Primary key columns of every table that actions write. Tables not listed use "id".
TABLE_KEYS: dict[str, tuple[str, ...]] = {
    "settings": ("key",),
    "packaging_item_components": ("packaging_item_id", "material_id"),
    "recipe_lines": ("product_id", "material_id"),
    "order_recipe_lines": ("order_id", "material_id"),
    "packaging_plans": ("order_id",),
    "packaging_step_extras": ("step_id", "packaging_item_id"),
}

WRITABLE_TABLES = frozenset({
    "settings", "materials", "material_lots", "packaging_items", "packaging_item_components",
    "products", "recipe_lines", "machines", "orders", "order_recipe_lines", "order_assignments",
    "packaging_plans", "packaging_steps", "packaging_step_extras", "shelf_lines",
    "shelf_transfers", "receipts", "shipments",
})

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def key_columns(table: str) -> tuple[str, ...]:
    return TABLE_KEYS.get(table, ("id",))


def _check_identifiers(table: str, columns: list[str]) -> None:
    if table not in WRITABLE_TABLES:
        raise ValueError(f"Unknown table: {table}")
    for column in columns:
        if not _IDENTIFIER.match(column):
            raise ValueError(f"Invalid column name: {column}")


@dataclass(frozen=True, slots=True)
class Change:
    """One changed row. before is None for an insert, after is None for a delete."""

    table: str
    key: Row
    before: Row | None
    after: Row | None

    def to_json(self) -> Row:
        return {"table": self.table, "key": self.key, "before": self.before, "after": self.after}

    @staticmethod
    def from_json(data: Row) -> Change:
        return Change(data["table"], data["key"], data["before"], data["after"])


def fetch_row(conn: sqlite3.Connection, table: str, key: Row) -> Row | None:
    """The full row with the given key, or None."""
    _check_identifiers(table, list(key))
    where = " AND ".join(f"{column} = ?" for column in key)
    row = conn.execute(f"SELECT * FROM {table} WHERE {where}", tuple(key.values())).fetchone()
    return dict(row) if row is not None else None


def insert_raw(conn: sqlite3.Connection, table: str, values: Row) -> int:
    _check_identifiers(table, list(values))
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    cursor = conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(values.values()))
    return int(cursor.lastrowid)


def update_raw(conn: sqlite3.Connection, table: str, key: Row, values: Row) -> None:
    _check_identifiers(table, list(key) + list(values))
    assignments = ", ".join(f"{column} = ?" for column in values)
    where = " AND ".join(f"{column} = ?" for column in key)
    conn.execute(f"UPDATE {table} SET {assignments} WHERE {where}", tuple(values.values()) + tuple(key.values()))


def delete_raw(conn: sqlite3.Connection, table: str, key: Row) -> None:
    _check_identifiers(table, list(key))
    where = " AND ".join(f"{column} = ?" for column in key)
    conn.execute(f"DELETE FROM {table} WHERE {where}", tuple(key.values()))


class Writer:
    """Row writes inside one action, recording the before and after image of each row."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.changes: list[Change] = []

    def insert(self, table: str, values: Row) -> int:
        """Insert a row and return its id (or 0 for tables keyed by other columns)."""
        row_id = insert_raw(self.conn, table, values)
        columns = key_columns(table)
        key = {"id": row_id} if columns == ("id",) else {c: values[c] for c in columns}
        self.changes.append(Change(table, key, None, fetch_row(self.conn, table, key)))
        return row_id if columns == ("id",) else 0

    def update(self, table: str, key: Row, values: Row) -> None:
        """Update one existing row. Records nothing if no column actually changes."""
        before = fetch_row(self.conn, table, key)
        if before is None:
            raise LookupError(f"No row in {table} with key {key}")
        update_raw(self.conn, table, key, values)
        after = fetch_row(self.conn, table, key)
        if after != before:
            self.changes.append(Change(table, key, before, after))

    def delete(self, table: str, key: Row) -> None:
        before = fetch_row(self.conn, table, key)
        if before is None:
            raise LookupError(f"No row in {table} with key {key}")
        delete_raw(self.conn, table, key)
        self.changes.append(Change(table, key, before, None))


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None and value != "" else None


def iso(value: date | datetime | None) -> str | None:
    """Store a date as YYYY-MM-DD and a timestamp as ISO text with seconds."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value.isoformat()


def decimal_text(value: Decimal | None) -> str | None:
    """Store a Decimal as plain text, without exponent and without trailing zeros."""
    if value is None:
        return None
    text = format(value.normalize(), "f")
    return text


def load_settings(conn: sqlite3.Connection) -> Settings:
    values = dict(conn.execute("SELECT key, value FROM settings WHERE key <> 'language'").fetchall())
    defaults = Settings()
    working = values.get("working_days")
    return Settings(
        yellow_days=int(values.get("yellow_days", defaults.yellow_days)),
        red_days=int(values.get("red_days", defaults.red_days)),
        working_days=(
            frozenset(int(part) for part in working.split(",") if part != "")
            if working is not None else defaults.working_days
        ),
        machine_hours_per_day=Decimal(values.get("machine_hours_per_day", defaults.machine_hours_per_day)),
        default_transit_days=int(values.get("default_transit_days", defaults.default_transit_days)),
        packaging_hours_per_day=Decimal(values.get("packaging_hours_per_day", defaults.packaging_hours_per_day)),
        packaging_utilization_bp=int(values.get("packaging_utilization_bp", defaults.packaging_utilization_bp)),
    )


def settings_rows(settings: Settings) -> dict[str, str]:
    """The settings table values for a Settings object."""
    return {
        "yellow_days": str(settings.yellow_days),
        "red_days": str(settings.red_days),
        "working_days": ",".join(str(day) for day in sorted(settings.working_days)),
        "machine_hours_per_day": decimal_text(settings.machine_hours_per_day) or "0",
        "default_transit_days": str(settings.default_transit_days),
        "packaging_hours_per_day": decimal_text(settings.packaging_hours_per_day) or "0",
        "packaging_utilization_bp": str(settings.packaging_utilization_bp),
    }


def _rows(conn: sqlite3.Connection, sql: str) -> list[sqlite3.Row]:
    return conn.execute(sql).fetchall()


def load_snapshot(conn: sqlite3.Connection, today: date | None = None) -> Snapshot:
    """Read every stored row into one Snapshot, the input of compute_state()."""
    return Snapshot(
        today=today or dates.today(),
        settings=load_settings(conn),
        materials=tuple(
            Material(r["id"], r["code"], r["name"], MaterialCategory(r["category"]), r["description"],
                     _datetime(r["deleted_at"]))
            for r in _rows(conn, "SELECT * FROM materials ORDER BY id")
        ),
        lots=tuple(
            MaterialLot(r["id"], r["material_id"], r["lot_number"], r["quantity_mg"], date.fromisoformat(r["expiry_date"]))
            for r in _rows(conn, "SELECT * FROM material_lots ORDER BY id")
        ),
        packaging_items=tuple(
            PackagingItem(
                r["id"], r["code"], r["name"], r["quantity_pcs"], r["description"],
                r["length_mm"], r["width_mm"], r["height_mm"], r["unit_weight_mg"], _datetime(r["deleted_at"]),
                item_type=PackagingItemType(r["item_type"]), outer_length_mm=r["outer_length_mm"],
                outer_width_mm=r["outer_width_mm"], outer_height_mm=r["outer_height_mm"],
            )
            for r in _rows(conn, "SELECT * FROM packaging_items ORDER BY id")
        ),
        packaging_components=tuple(
            PackagingItemComponent(r["packaging_item_id"], r["material_id"], r["percent_bp"])
            for r in _rows(conn, "SELECT * FROM packaging_item_components ORDER BY rowid")
        ),
        products=tuple(
            Product(r["id"], r["name"], r["unit_weight_mg"])
            for r in _rows(conn, "SELECT * FROM products ORDER BY id")
        ),
        recipe_lines=tuple(
            RecipeLine(r["product_id"], r["material_id"], r["percent_bp"])
            for r in _rows(conn, "SELECT * FROM recipe_lines ORDER BY rowid")
        ),
        machines=tuple(
            Machine(
                r["id"], r["name"], r["batch_size_mg"], Decimal(r["cycle_time_min"]), r["utilization_bp"],
                Decimal(r["hours_per_day"]), r["max_batch_mg"], _decimal(r["min_cycle_time_min"]),
                _datetime(r["deleted_at"]),
            )
            for r in _rows(conn, "SELECT * FROM machines ORDER BY id")
        ),
        orders=tuple(
            Order(
                r["id"], r["name"], r["product_id"], r["quantity_mg"], r["unit_weight_mg"], r["destination"],
                date.fromisoformat(r["delivery_date"]), r["transit_days"], r["sequence"],
                datetime.fromisoformat(r["created_at"]), _datetime(r["cancelled_at"]),
            )
            for r in _rows(conn, "SELECT * FROM orders ORDER BY id")
        ),
        order_recipe_lines=tuple(
            OrderRecipeLine(r["order_id"], r["material_id"], r["percent_bp"])
            for r in _rows(conn, "SELECT * FROM order_recipe_lines ORDER BY rowid")
        ),
        assignments=tuple(
            OrderAssignment(
                r["id"], r["order_id"], r["machine_id"], r["quantity_mg"], r["batch_size_mg"],
                Decimal(r["cycle_time_min"]), r["defect_bp"], _date(r["start_date"]),
                _datetime(r["completed_at"]), r["actual_pieces"],
            )
            for r in _rows(conn, "SELECT * FROM order_assignments ORDER BY id")
        ),
        packaging_plans=tuple(
            PackagingPlan(
                r["order_id"], Decimal(r["hours_per_day"]), r["utilization_bp"],
                datetime.fromisoformat(r["saved_at"]), _datetime(r["completed_at"]),
            )
            for r in _rows(conn, "SELECT * FROM packaging_plans ORDER BY order_id")
        ),
        packaging_steps=tuple(
            PackagingStep(
                r["id"], r["order_id"], r["position"], StepKind(r["kind"]), r["packaging_item_id"],
                StepRole(r["role"]) if r["role"] else None, r["units_per"], bool(r["comes_ready"]),
                _decimal(r["speed_per_min"]),
            )
            for r in _rows(conn, "SELECT * FROM packaging_steps ORDER BY order_id, position")
        ),
        packaging_step_extras=tuple(
            PackagingStepExtra(r["step_id"], r["packaging_item_id"], r["quantity_per_unit"])
            for r in _rows(conn, "SELECT * FROM packaging_step_extras ORDER BY rowid")
        ),
        shelf_lines=tuple(
            ShelfLine(
                r["id"], r["order_id"], r["boxes"], r["pieces_per_box"], r["box_item_id"],
                datetime.fromisoformat(r["created_at"]), r["boxes_per_carton"], r["carton_item_id"],
                _datetime(r["deleted_at"]), r["cartons_per_pallet"], r["pallet_item_id"],
            )
            for r in _rows(conn, "SELECT * FROM shelf_lines ORDER BY id")
        ),
        shelf_transfers=tuple(
            ShelfTransfer(r["id"], r["from_line_id"], r["to_line_id"], r["boxes"], date.fromisoformat(r["transferred_on"]))
            for r in _rows(conn, "SELECT * FROM shelf_transfers ORDER BY id")
        ),
        receipts=tuple(
            Receipt(
                r["id"], ItemKind(r["kind"]), r["quantity"], date.fromisoformat(r["receipt_date"]),
                r["material_id"], r["packaging_item_id"], _datetime(r["received_at"]),
                r["received_quantity"], r["lot_id"],
            )
            for r in _rows(conn, "SELECT * FROM receipts ORDER BY id")
        ),
        shipments=tuple(
            Shipment(
                r["id"], r["shelf_line_id"], r["boxes"], _date(r["completion_date"]),
                _date(r["shipment_date"]), _datetime(r["shipped_at"]),
            )
            for r in _rows(conn, "SELECT * FROM shipments ORDER BY id")
        ),
        last_history_id=data_version(conn)[0],
    )


def data_version(conn: sqlite3.Connection) -> tuple[int | None, int]:
    """(latest history id, number of undone entries). Changes after every action and undo."""
    row = conn.execute("SELECT MAX(id), COUNT(undone_at) FROM history").fetchone()
    return (row[0], row[1])


def _history_entry(row: sqlite3.Row) -> HistoryEntry:
    return HistoryEntry(
        row["id"], datetime.fromisoformat(row["created_at"]), row["action_code"], row["description"],
        row["changes_json"], _datetime(row["undone_at"]),
    )


def list_history(conn: sqlite3.Connection) -> list[HistoryEntry]:
    """Every history entry, most recent first."""
    return [_history_entry(r) for r in conn.execute("SELECT * FROM history ORDER BY id DESC")]


def last_undoable(conn: sqlite3.Connection) -> HistoryEntry | None:
    """The most recent action that has not been undone."""
    row = conn.execute("SELECT * FROM history WHERE undone_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
    return _history_entry(row) if row is not None else None


LANGUAGE_KEY = "language"


def get_language(conn: sqlite3.Connection, default: str = "el") -> str:
    """The language the application opens in; Greek until the user picks another."""
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (LANGUAGE_KEY,)).fetchone()
    return row[0] if row else default


def set_language(conn: sqlite3.Connection, code: str) -> None:
    """Remember the chosen language.

    A display preference, not an action: it is not written to the history and
    the undo button never touches it.
    """
    with transaction(conn):
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (LANGUAGE_KEY, code),
        )


def wipe_all_data(conn: sqlite3.Connection) -> None:
    """Delete every stored row, history included, and restore the default settings.

    Runs in one transaction: either everything is cleared or nothing is. The
    schema and its version stay, so the application starts as on its first
    run. This is the one change that is not recorded and cannot be undone;
    callers take a backup first.
    """
    with transaction(conn):
        for table in sorted(WRITABLE_TABLES | {"history"}):
            if table == "settings":
                # The chosen language is a display preference and survives a wipe.
                conn.execute("DELETE FROM settings WHERE key <> ?", (LANGUAGE_KEY,))
            else:
                conn.execute(f"DELETE FROM {table}")
        for key, value in settings_rows(Settings()).items():
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
