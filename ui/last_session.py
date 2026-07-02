from __future__ import annotations

import json
import logging
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, MutableMapping

LOGGER = logging.getLogger(__name__)

SCHEMA_VERSION = 1
DEFAULT_LAST_SESSION_PATH = Path("data/user_state/last_session.json")
MAX_SNAPSHOT_BYTES = 16 * 1024
RESTORE_NOTICE_KEY = "smai_last_session_restore_notice"
RESTORE_APPLIED_KEY = "smai_last_session_restore_applied"

ALLOWED_PAGES = frozenset(
    {"cockpit", "ranking", "news", "watchlist", "copilot", "rebalance", "settings"}
)
RANKING_STATE_KEYS = (
    "market_data_ranking_region",
    "market_data_ranking_product_type",
    "market_data_ranking_policy",
    "market_data_ranking_fetch_limit",
)
PROVIDER_STATE_KEYS = (
    "market_data_provider_live_first",
    "market_data_ranking_provider_live_first",
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def load_last_session(path: Path = DEFAULT_LAST_SESSION_PATH) -> dict[str, Any] | None:
    """Load a small, validated snapshot without making app startup fragile."""
    try:
        if not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        LOGGER.warning("Last-session snapshot could not be loaded.", exc_info=True)
        return None
    return _validated_snapshot(raw)


def save_last_session(
    snapshot: Mapping[str, Any],
    path: Path = DEFAULT_LAST_SESSION_PATH,
) -> bool:
    """Atomically save a snapshot, returning False instead of breaking the UI."""
    validated = _validated_snapshot(dict(snapshot))
    if validated is None:
        return False
    payload = json.dumps(validated, ensure_ascii=False, indent=2) + "\n"
    if len(payload.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        return False
    temporary_path = path.with_suffix(f"{path.suffix}.{secrets.token_hex(4)}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(payload, encoding="utf-8")
        os.replace(temporary_path, path)
    except OSError:
        LOGGER.warning("Last-session snapshot could not be saved.", exc_info=True)
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def restore_last_session(
    session_state: MutableMapping[str, Any],
    *,
    valid_user_ids: set[str],
    query_params: Mapping[str, Any] | None = None,
    path: Path = DEFAULT_LAST_SESSION_PATH,
) -> dict[str, Any] | None:
    """Restore lightweight values once per Streamlit session.

    Explicit URL values win over persisted values. No data fetch or calculation is
    triggered here.
    """
    if session_state.get(RESTORE_APPLIED_KEY):
        return None
    session_state[RESTORE_APPLIED_KEY] = True
    snapshot = load_last_session(path)
    if snapshot is None:
        return None

    params = query_params or {}
    restored: dict[str, Any] = {}
    user_id = str(snapshot.get("selected_user_id") or "")
    if (
        not _has_query_value(params, "smai_start_profile", "smai_profile")
        and "smai_current_user_id" not in session_state
        and user_id in valid_user_ids
    ):
        session_state["smai_current_user_id"] = user_id
        restored["selected_user_id"] = user_id

    active_page = str(snapshot.get("active_page") or "")
    if (
        not _has_query_value(params, "smai_page")
        and "sidemenu_page" not in session_state
        and active_page in ALLOWED_PAGES
    ):
        session_state["sidemenu_page"] = active_page
        restored["active_page"] = active_page

    symbol = str(snapshot.get("selected_symbol") or "")
    if (
        not _has_query_value(params, "smai_symbol")
        and "market_data_symbol_candidate" not in session_state
        and _safe_value(symbol)
    ):
        session_state["market_data_symbol_candidate"] = symbol
        session_state["market_data_ranking_handoff_symbol"] = symbol
        restored["selected_symbol"] = symbol

    ranking_filters = snapshot.get("ranking_filters")
    if isinstance(ranking_filters, dict):
        for key in RANKING_STATE_KEYS:
            value = ranking_filters.get(key)
            if key not in session_state and _safe_value(value):
                session_state[key] = value

    settings = snapshot.get("settings")
    if isinstance(settings, dict):
        for key in PROVIDER_STATE_KEYS:
            value = settings.get(key)
            if key not in session_state and _safe_value(value):
                session_state[key] = value

    if restored:
        session_state[RESTORE_NOTICE_KEY] = restored
        return restored
    return None


def snapshot_from_session_state(
    session_state: Mapping[str, Any],
    *,
    selected_symbol: str = "",
) -> dict[str, Any] | None:
    user_id = str(session_state.get("smai_current_user_id") or "")
    active_page = str(session_state.get("sidemenu_page") or "")
    if not _safe_value(user_id) or active_page not in ALLOWED_PAGES:
        return None
    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": datetime.now(UTC).isoformat(),
        "selected_user_id": user_id,
        "active_page": active_page,
    }
    if _safe_value(selected_symbol):
        snapshot["selected_symbol"] = selected_symbol
    ranking_filters = {
        key: session_state[key]
        for key in RANKING_STATE_KEYS
        if key in session_state and _safe_value(session_state[key])
    }
    if ranking_filters:
        snapshot["ranking_filters"] = ranking_filters
    settings = {
        key: session_state[key]
        for key in PROVIDER_STATE_KEYS
        if key in session_state and _safe_value(session_state[key])
    }
    if settings:
        snapshot["settings"] = settings
    return snapshot


def save_last_session_if_changed(
    session_state: Mapping[str, Any],
    *,
    selected_symbol: str = "",
    path: Path = DEFAULT_LAST_SESSION_PATH,
) -> bool:
    snapshot = snapshot_from_session_state(session_state, selected_symbol=selected_symbol)
    if snapshot is None:
        return False
    current = load_last_session(path)
    comparable = {key: value for key, value in snapshot.items() if key != "updated_at"}
    current_comparable = (
        {key: value for key, value in current.items() if key != "updated_at"}
        if current is not None
        else None
    )
    if comparable == current_comparable:
        return False
    return save_last_session(snapshot, path)


def _validated_snapshot(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        return None
    user_id = value.get("selected_user_id")
    active_page = value.get("active_page")
    if not _safe_value(user_id) or active_page not in ALLOWED_PAGES:
        return None
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": str(value.get("updated_at") or ""),
        "selected_user_id": str(user_id),
        "active_page": str(active_page),
    }
    symbol = value.get("selected_symbol")
    if _safe_value(symbol):
        result["selected_symbol"] = str(symbol)
    for section, allowed_keys in (
        ("ranking_filters", RANKING_STATE_KEYS),
        ("settings", PROVIDER_STATE_KEYS),
    ):
        source = value.get(section)
        if not isinstance(source, dict):
            continue
        cleaned = {
            key: source[key] for key in allowed_keys if key in source and _safe_value(source[key])
        }
        if cleaned:
            result[section] = cleaned
    return result


def _safe_value(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if not isinstance(value, str):
        return False
    return bool(_SAFE_ID.fullmatch(value))


def _has_query_value(params: Mapping[str, Any], *keys: str) -> bool:
    for key in keys:
        value = params.get(key)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        if str(value or "").strip():
            return True
    return False
