"""Make the project root importable regardless of where pytest is started."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def greek_texts():
    """Every test starts in Greek, the default language, and leaves it that way."""
    from ui import texts

    texts.set_language("el")
    yield
    texts.set_language("el")
