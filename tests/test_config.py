"""The Streamlit configuration keeps the application reachable from this computer only."""

from __future__ import annotations

import tomllib

from conftest import PROJECT_ROOT


def test_server_listens_on_localhost_only() -> None:
    with open(PROJECT_ROOT / ".streamlit" / "config.toml", "rb") as handle:
        config = tomllib.load(handle)
    assert config.get("server", {}).get("address") == "localhost"
