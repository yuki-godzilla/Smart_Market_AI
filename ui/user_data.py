from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

import streamlit as st

LOGGER = logging.getLogger(__name__)
DEFAULT_USER_ID = "default"
PROFILE_ROOT = Path("data/user/profiles")
MIGRATION_ROOT = Path("data/user/migrations")
LEGACY_USER_ROOT = Path("data/user")
SAFE_USER_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def current_user_id() -> str | None:
    value = st.session_state.get("smai_current_user_id")
    return str(value) if value else None


def is_default_session_user() -> bool:
    return current_user_id() == DEFAULT_USER_ID


def profile_data_path(filename: str, *, user_id: str | None = None) -> Path | None:
    resolved = user_id or current_user_id()
    if not resolved or resolved == DEFAULT_USER_ID:
        return None
    if not SAFE_USER_ID.fullmatch(resolved) or resolved in {".", ".."}:
        raise ValueError("Invalid user identifier.")
    return PROFILE_ROOT / resolved / filename


def session_payload(key: str, default: Any) -> Any:
    scoped_key = f"smai_default_user_{key}"
    if scoped_key not in st.session_state:
        st.session_state[scoped_key] = default
    return st.session_state[scoped_key]


def set_session_payload(key: str, value: Any) -> None:
    st.session_state[f"smai_default_user_{key}"] = value


def migrate_legacy_user_data(user_ids: list[str]) -> None:
    """Copy legacy shared data once to the first existing non-system profile."""
    marker = MIGRATION_ROOT / "user_profile_favorites_v1.done"
    if marker.exists():
        return
    target_user = "local_user" if "local_user" in user_ids else (user_ids[0] if user_ids else None)
    if not target_user:
        return
    pairs = (
        (
            LEGACY_USER_ROOT / "favorites.json",
            profile_data_path("favorites.json", user_id=target_user),
        ),
        (
            LEGACY_USER_ROOT / "watchlist_snapshots.json",
            profile_data_path("watchlist_snapshots.json", user_id=target_user),
        ),
    )
    try:
        for source, target in pairs:
            if target is None or not source.is_file() or target.exists():
                continue
            json.loads(source.read_text(encoding="utf-8"))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        MIGRATION_ROOT.mkdir(parents=True, exist_ok=True)
        marker.write_text("completed\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError):
        LOGGER.warning("Legacy user data migration could not be completed.", exc_info=True)
