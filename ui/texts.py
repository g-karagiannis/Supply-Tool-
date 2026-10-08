"""User-interface strings in the current language: Greek (default) or English.

Every screen and every data action reads its words as texts.NAME. The value
is looked up at that moment in ui/texts_el.py or ui/texts_en.py, which define
the same names, so changing the language takes effect on the next run of the
page without restarting the application.
"""

from __future__ import annotations

from types import ModuleType

from ui import texts_el, texts_en

LANGUAGES: dict[str, ModuleType] = {"el": texts_el, "en": texts_en}
LANGUAGE_LABELS = {"el": "ΕΛ", "en": "EN"}
DEFAULT_LANGUAGE = "el"

_current = DEFAULT_LANGUAGE


def set_language(code: str) -> None:
    """Switch every following text lookup to a language; unknown codes fall back to Greek."""
    global _current
    _current = code if code in LANGUAGES else DEFAULT_LANGUAGE


def language() -> str:
    """The code of the current language."""
    return _current


def __getattr__(name: str):
    """texts.NAME: the string or function of that name in the current language."""
    return getattr(LANGUAGES[_current], name)
