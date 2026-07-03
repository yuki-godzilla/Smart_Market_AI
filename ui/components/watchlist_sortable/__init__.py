from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_BUILD_DIR = Path(__file__).with_name("frontend") / "build"
_component = components.declare_component("smai_watchlist_sortable", path=str(_BUILD_DIR))


def watchlist_sortable(
    containers: list[dict[str, Any]],
    *,
    custom_style: str,
    key: str,
) -> dict[str, Any]:
    return _component(
        containers=containers,
        customStyle=custom_style,
        default={"type": "ready", "containers": containers},
        key=key,
    )
