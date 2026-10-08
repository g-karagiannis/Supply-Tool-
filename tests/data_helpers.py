"""Fixtures and seed helpers for tests of the data layer."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from core import dates
from core.models import MaterialCategory
from core.state import AppState, compute_state
from data import actions, db
from data.repositories import iso, load_snapshot

TODAY = date(2026, 10, 5)
NOW = datetime(2026, 10, 5, 10, 0)


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    """A fresh migrated database, with the clock fixed at Monday 05/10/2026."""
    monkeypatch.setattr(dates, "today", lambda: TODAY)
    monkeypatch.setattr(dates, "now", lambda: NOW)
    path = db.init_db(tmp_path / "app.db")
    connection = db.connect(path)
    yield connection
    connection.close()


def state(conn: sqlite3.Connection) -> AppState:
    return compute_state(load_snapshot(conn))


def kg(value: str | int) -> int:
    return int(Decimal(str(value)) * 1_000_000)


def material(conn: sqlite3.Connection, code: str, name: str, *lots: tuple[str, str | int, date]) -> int:
    """Create a material and its LOTs, given as (lot number, kg, expiry)."""
    material_id = actions.create_material(conn, code=code, name=name, category=MaterialCategory.EXCIPIENT).value
    for number, quantity, expiry in lots:
        actions.add_lot(conn, material_id, lot_number=number, quantity_mg=kg(quantity), expiry_date=expiry)
    return material_id


def lot_quantities(conn: sqlite3.Connection, material_id: int) -> dict[str, int]:
    rows = conn.execute("SELECT lot_number, quantity_mg FROM material_lots WHERE material_id = ?", (material_id,))
    return {row["lot_number"]: row["quantity_mg"] for row in rows}


def seed_shelf(conn: sqlite3.Connection, lines: list[tuple[str, int]], product: str = "Depon") -> list[int]:
    """Shelf lines of one product, as left by completed packaging; (destination, boxes) each.

    Written directly, since producing them through every step is what the
    end-to-end test covers.
    """
    product_id = conn.execute("INSERT INTO products (name, unit_weight_mg) VALUES (?, 500)", (product,)).lastrowid
    box_id = conn.execute(
        "INSERT INTO packaging_items (code, name, quantity_pcs, length_mm, width_mm, height_mm)"
        " VALUES ('BOX', 'Κουτί', 0, 100, 60, 30)"
    ).lastrowid
    ids = []
    for number, (destination, boxes) in enumerate(lines, start=1):
        order_id = conn.execute(
            "INSERT INTO orders (name, product_id, quantity_mg, unit_weight_mg, destination, delivery_date,"
            " transit_days, sequence, created_at) VALUES (?, ?, ?, 500, ?, '2026-10-26', 5, ?, ?)",
            (f"ΠΑΡ-{number:03d}", product_id, kg(200), destination, number, iso(NOW)),
        ).lastrowid
        conn.execute(
            "INSERT INTO packaging_plans (order_id, hours_per_day, utilization_bp, saved_at, completed_at)"
            " VALUES (?, '8', 10000, ?, ?)", (order_id, iso(NOW), iso(NOW)),
        )
        ids.append(conn.execute(
            "INSERT INTO shelf_lines (order_id, boxes, pieces_per_box, boxes_per_carton, box_item_id, created_at)"
            " VALUES (?, ?, 24, 160, ?, ?)", (order_id, boxes, box_id, iso(NOW)),
        ).lastrowid)
    return ids
