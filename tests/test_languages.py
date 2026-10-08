"""Greek and English versions of the application (added 07/10/2026)."""

from __future__ import annotations

import inspect
import sqlite3
from types import ModuleType

import pytest

from data import actions
from data.repositories import get_language, last_undoable, list_history, set_language, wipe_all_data
from data_helpers import conn  # noqa: F401
from ui import texts, texts_el, texts_en


def public(module: ModuleType) -> dict[str, object]:
    return {name: value for name, value in vars(module).items()
            if not name.startswith("_") and name != "annotations"}


def test_both_languages_define_the_same_texts() -> None:
    greek, english = public(texts_el), public(texts_en)
    assert set(greek) == set(english)
    for name, value in greek.items():
        other = english[name]
        assert type(value) is type(other), name
        if callable(value):
            assert list(inspect.signature(value).parameters) == list(inspect.signature(other).parameters), name
        if isinstance(value, dict):
            assert set(value) == set(other), name
        if isinstance(value, tuple):
            assert len(value) == len(other), name


def test_texts_follow_the_current_language() -> None:
    assert texts.NAV_WAREHOUSE == "Αποθήκη"
    texts.set_language("en")
    assert texts.NAV_WAREHOUSE == "Warehouse"
    assert texts.field_required(texts.FIELDS["code"]) == "The field \u201cCode\u201d is required."
    texts.set_language("xx")
    assert texts.language() == "el"


def test_action_messages_and_history_use_the_current_language(conn: sqlite3.Connection) -> None:
    from core.models import MaterialCategory

    texts.set_language("en")
    actions.create_material(conn, code="A", name="Excipient A", category=MaterialCategory.EXCIPIENT)
    with pytest.raises(actions.ActionError, match="The code A already exists"):
        actions.create_material(conn, code="A", name="Other", category=MaterialCategory.EXCIPIENT)
    texts.set_language("el")
    actions.create_material(conn, code="B", name="Έκδοχο Β", category=MaterialCategory.EXCIPIENT)
    # Each entry keeps the language it was written in.
    assert [e.description for e in list_history(conn)] == ["Νέο υλικό: Έκδοχο Β", "New material: Excipient A"]


def test_language_preference_is_not_an_action(conn: sqlite3.Connection) -> None:
    assert get_language(conn) == "el"
    set_language(conn, "en")
    assert get_language(conn) == "en"
    assert last_undoable(conn) is None
    wipe_all_data(conn)
    assert get_language(conn) == "en"
