"""Step 1 acceptance: the database is created, migrated and seeded with defaults."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from data import db

EXPECTED_TABLES = {
    "settings",
    "materials",
    "material_lots",
    "packaging_items",
    "packaging_item_components",
    "products",
    "recipe_lines",
    "machines",
    "orders",
    "order_recipe_lines",
    "order_assignments",
    "packaging_plans",
    "packaging_steps",
    "packaging_step_extras",
    "shelf_lines",
    "shelf_transfers",
    "receipts",
    "shipments",
    "history",
    "schema_version",
}

DEFAULT_SETTINGS = {
    "yellow_days": "120",
    "red_days": "30",
    "working_days": "0,1,2,3,4",
    "default_transit_days": "5",
    "machine_hours_per_day": "8",
    "packaging_hours_per_day": "8",
    "packaging_utilization_bp": "10000",
}


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    path = db.init_db(tmp_path / "app.db")
    connection = db.connect(path)
    yield connection
    connection.close()


def test_init_creates_file_and_all_tables(tmp_path: Path) -> None:
    path = db.init_db(tmp_path / "nested" / "app.db")
    assert path.exists()
    connection = db.connect(path)
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    connection.close()
    assert EXPECTED_TABLES <= tables


def test_default_settings_written(conn: sqlite3.Connection) -> None:
    rows = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    assert rows == DEFAULT_SETTINGS


def test_schema_version_recorded(conn: sqlite3.Connection) -> None:
    latest = db.available_migrations()[-1][0]
    assert db.current_version(conn) == latest


def test_init_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    db.init_db(path)
    db.init_db(path)
    connection = db.connect(path)
    versions = connection.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    settings = connection.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    connection.close()
    assert versions == len(db.available_migrations())
    assert settings == len(DEFAULT_SETTINGS)


def test_foreign_keys_enforced(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO material_lots (material_id, lot_number, quantity_mg, expiry_date)"
            " VALUES (999, 'L-001', 1000, '2027-06-30')"
        )


def test_negative_quantity_rejected(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO materials (code, name, category) VALUES ('M-1', 'Έκδοχο Α', 'excipient')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO material_lots (material_id, lot_number, quantity_mg, expiry_date)"
            " VALUES (1, 'L-001', -1, '2027-06-30')"
        )


def test_failed_migration_rolls_back(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_ok.sql").write_text("CREATE TABLE a (x INTEGER);", encoding="utf-8")
    (migrations / "0002_bad.sql").write_text(
        "CREATE TABLE b (x INTEGER); INSERT INTO missing VALUES (1);", encoding="utf-8"
    )
    connection = db.connect(tmp_path / "app.db")
    with pytest.raises(db.MigrationError):
        db.migrate(connection, migrations)
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert db.current_version(connection) == 1
    assert "a" in tables and "b" not in tables
    connection.close()


def test_migration_numbering_must_be_contiguous(tmp_path: Path) -> None:
    (tmp_path / "0001_a.sql").write_text("", encoding="utf-8")
    (tmp_path / "0003_c.sql").write_text("", encoding="utf-8")
    with pytest.raises(db.MigrationError):
        db.available_migrations(tmp_path)
