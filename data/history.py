"""The action log and undo (sections 11.3 and 11.4).

Each action writes one history entry whose changes_json holds, for every row it
changed, the table, the key, and the images before and after. Undo restores the
"before" images in reverse order, in one transaction, and marks the entry as
undone. Undo always goes from the most recent action backwards, so an
intermediate action is never undone on its own and stock never turns negative.
There is no redo.
"""

from __future__ import annotations

import json
import sqlite3

from core import dates
from core.models import HistoryEntry
from data.db import transaction
from data.repositories import Change, delete_raw, insert_raw, iso, last_undoable, update_raw


class NothingToUndo(LookupError):
    """Raised when every recorded action has already been undone."""


def record(conn: sqlite3.Connection, action_code: str, description: str, changes: list[Change]) -> int:
    """Write one history entry for an action, inside the action's transaction."""
    cursor = conn.execute(
        "INSERT INTO history (created_at, action_code, description, changes_json) VALUES (?, ?, ?, ?)",
        (
            iso(dates.now()),
            action_code,
            description,
            json.dumps([change.to_json() for change in changes], ensure_ascii=False),
        ),
    )
    return int(cursor.lastrowid)


def _restore(conn: sqlite3.Connection, change: Change) -> None:
    if change.before is None:
        delete_raw(conn, change.table, change.key)
    elif change.after is None:
        insert_raw(conn, change.table, change.before)
    else:
        values = {column: value for column, value in change.before.items() if column not in change.key}
        update_raw(conn, change.table, change.key, values)


def undo_last(conn: sqlite3.Connection) -> HistoryEntry:
    """Undo the most recent action that has not been undone, and return it."""
    with transaction(conn):
        entry = last_undoable(conn)
        if entry is None:
            raise NothingToUndo()
        changes = [Change.from_json(item) for item in json.loads(entry.changes_json)]
        for change in reversed(changes):
            _restore(conn, change)
        conn.execute("UPDATE history SET undone_at = ? WHERE id = ?", (iso(dates.now()), entry.id))
    return entry
