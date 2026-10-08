"""Section 12.10: fail if any project file contains an emoji character.

The ranges are written as escapes so this file does not contain the
characters it looks for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCANNED_SUFFIXES = {".py", ".md", ".sql", ".toml", ".txt"}
SKIPPED_DIRS = {"__pycache__", ".pytest_cache", ".venv", "venv", ".git", "backups"}

# Unicode blocks that hold emoji and pictographic icon characters.
EMOJI_RANGES: tuple[tuple[int, int], ...] = (
    (0x1F000, 0x1FAFF),  # Mahjong tiles through Symbols and Pictographs Extended-A
    (0x2600, 0x27BF),    # Miscellaneous Symbols, Dingbats (includes check marks)
    (0x2300, 0x23FF),    # Miscellaneous Technical (watch, hourglass, media keys)
    (0x2B00, 0x2BFF),    # Miscellaneous Symbols and Arrows (stars, large squares)
    (0xFE00, 0xFE0F),    # Variation selectors that force emoji presentation
    (0x20E3, 0x20E3),    # Combining enclosing keycap
    (0xE0020, 0xE007F),  # Tag characters used in flag sequences
)


def is_emoji(char: str) -> bool:
    """Return True if the character falls in one of the emoji ranges."""
    code = ord(char)
    return any(low <= code <= high for low, high in EMOJI_RANGES)


def find_emoji(text: str) -> list[tuple[int, int, str]]:
    """Return (line, column, U+XXXX) for every emoji character in the text."""
    hits = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for col, char in enumerate(line, start=1):
            if is_emoji(char):
                hits.append((line_no, col, f"U+{ord(char):04X}"))
    return hits


def project_files() -> list[Path]:
    """Every scanned file of the project, skipping caches and backups."""
    return sorted(
        path
        for path in PROJECT_ROOT.rglob("*")
        if path.is_file()
        and path.suffix in SCANNED_SUFFIXES
        and not SKIPPED_DIRS.intersection(path.relative_to(PROJECT_ROOT).parts)
    )


def test_detector_finds_emoji() -> None:
    sample = "Αποθήκη " + chr(0x1F4E6) + "\nOK " + chr(0x2705)
    assert find_emoji(sample) == [(1, 9, "U+1F4E6"), (2, 4, "U+2705")]


def test_detector_accepts_greek_and_symbols_used_in_texts() -> None:
    assert find_emoji("Κουτί 10 × 6 × 3 cm, −20%, 16.041, 128,332 kg") == []


def test_project_has_files_to_scan() -> None:
    assert any(path.name == "app.py" for path in project_files())


@pytest.mark.parametrize(
    "path", project_files(), ids=lambda p: str(p.relative_to(PROJECT_ROOT))
)
def test_file_has_no_emoji(path: Path) -> None:
    hits = find_emoji(path.read_text(encoding="utf-8"))
    assert hits == [], f"{path.relative_to(PROJECT_ROOT)} contains emoji at {hits}"
