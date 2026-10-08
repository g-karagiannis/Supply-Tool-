"""Section 2: the three layers never import what they are not allowed to."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_IMPORTS: dict[str, set[str]] = {
    "core": {"streamlit", "sqlite3", "data", "ui"},
    "data": {"streamlit", "ui"},
    "ui": {"sqlite3"},
}

# The data layer writes Greek history descriptions and messages, which live in
# ui/texts.py. That module holds only strings, so it is the one allowed import.
ALLOWED_IMPORTS: dict[str, set[str]] = {"data": {"ui.texts"}}


def imported_modules(path: Path) -> set[str]:
    """Dotted names imported by a Python file: "import a.b" gives a.b, "from a import b" gives a.b."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def is_forbidden(module: str, layer: str) -> bool:
    allowed = ALLOWED_IMPORTS.get(layer, set())
    if any(module == a or module.startswith(a + ".") for a in allowed):
        return False
    return module.split(".")[0] in FORBIDDEN_IMPORTS[layer]


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_IMPORTS))
def test_layer_imports(layer: str) -> None:
    for path in sorted((PROJECT_ROOT / layer).rglob("*.py")):
        bad = {m for m in imported_modules(path) if is_forbidden(m, layer)}
        assert not bad, f"{path.relative_to(PROJECT_ROOT)} imports {sorted(bad)}"


def test_ui_texts_has_no_dependencies() -> None:
    """The text modules hold only strings, so the data layer may use them."""
    assert imported_modules(PROJECT_ROOT / "ui" / "texts.py") <= {
        "__future__.annotations", "types.ModuleType", "ui.texts_el", "ui.texts_en",
    }
    for name in ("texts_el.py", "texts_en.py"):
        assert imported_modules(PROJECT_ROOT / "ui" / name) <= {"__future__.annotations"}
