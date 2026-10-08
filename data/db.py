"""SQLite connection and schema migrations.

The database is a single file, ``data/app.db``. Schema changes are numbered SQL
scripts in ``data/migrations`` (``0001_initial.sql``, ``0002_...``), applied in
order and recorded in the ``schema_version`` table. Each script runs in its own
transaction together with its version row, so a failed script leaves the
database at the previous version.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = DATA_DIR / "app.db"
MIGRATIONS_DIR = DATA_DIR / "migrations"
BACKUPS_DIR = DATA_DIR.parent / "backups"

# The connection type, for layers that must not import sqlite3 themselves.
Connection = sqlite3.Connection

_MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


class MigrationError(RuntimeError):
    """Raised when the migration scripts are inconsistent or one of them fails."""


def connect(db_path: Path | str = DEFAULT_DB_PATH, shared: bool = False) -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and rows addressable by name.

    The connection runs in autocommit mode (``isolation_level=None``); callers
    open transactions explicitly with ``BEGIN`` so that every user action is
    exactly one transaction. shared=True lets the one connection of a Streamlit
    session be used from the threads Streamlit runs its reruns in.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=not shared)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def available_migrations(migrations_dir: Path = MIGRATIONS_DIR) -> list[tuple[int, Path]]:
    """Return ``(version, path)`` for every migration script, sorted by version.

    Raises ``MigrationError`` if a file name does not follow the
    ``NNNN_name.sql`` pattern or if the numbering has gaps or duplicates.
    """
    found: list[tuple[int, Path]] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        match = _MIGRATION_NAME.match(path.name)
        if match is None:
            raise MigrationError(f"Invalid migration file name: {path.name}")
        found.append((int(match.group(1)), path))
    versions = [version for version, _ in found]
    if versions != list(range(1, len(versions) + 1)):
        raise MigrationError(f"Migration numbers must be 1..N without gaps, got {versions}")
    return found


def current_version(conn: sqlite3.Connection) -> int:
    """Return the highest applied schema version, or 0 for a new database."""
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return int(row[0]) if row[0] is not None else 0


def migrate(conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> int:
    """Apply every migration newer than the current version and return the new version.

    Foreign keys are switched off while scripts run, as SQLite requires for
    rebuilding a table, and every script is checked with foreign_key_check
    before it commits, so a migration can never leave a dangling reference.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        " version INTEGER PRIMARY KEY,"
        " applied_at TEXT NOT NULL)"
    )
    version = current_version(conn)
    pending = [(n, p) for n, p in available_migrations(migrations_dir) if n > version]
    if not pending:
        return version
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        for number, path in pending:
            sql = path.read_text(encoding="utf-8")
            applied_at = datetime.now().isoformat(timespec="seconds")
            # executescript() cannot take parameters; both values are generated
            # here (an int and an ISO timestamp), never taken from user input.
            script = (
                "BEGIN;\n"
                f"{sql}\n"
                f"INSERT INTO schema_version (version, applied_at) VALUES ({number}, '{applied_at}');\n"
            )
            try:
                conn.executescript(script)
                broken = conn.execute("PRAGMA foreign_key_check").fetchall()
                if broken:
                    raise sqlite3.IntegrityError(f"foreign key check failed: {[tuple(r) for r in broken][:5]}")
                conn.execute("COMMIT")
            except sqlite3.Error as exc:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise MigrationError(f"Migration {path.name} failed: {exc}") from exc
            version = number
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    return version


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block as one transaction: commit on success, roll back on any error.

    Deferred foreign keys are checked at COMMIT; a violation there also rolls back.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def backup_database(db_path: Path | str = DEFAULT_DB_PATH, backups_dir: Path = BACKUPS_DIR) -> Path:
    """Copy the database to backups/ with the date and time in the file name.

    Uses SQLite's online backup, so the copy is consistent even while the
    application has the database open.
    """
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backups_dir / f"app_{stamp}.db"
    counter = 1
    while target.exists():
        target = backups_dir / f"app_{stamp}_{counter}.db"
        counter += 1
    source = connect(db_path)
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    """Create the database file if needed and bring its schema up to date.

    Called on every application start. On the first start this creates all
    tables and writes the default settings.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        migrate(conn)
    finally:
        conn.close()
    return path
