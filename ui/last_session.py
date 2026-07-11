from __future__ import annotations

import json
import logging
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, MutableMapping

LOGGER = logging.getLogger(__name__)

SCHEMA_VERSION = 1
CLIENT_QUERY_KEY = "client"
CLIENT_ID_PREFIX = "smai_client_"
CLIENT_SESSION_TTL = timedelta(minutes=30)
DEFAULT_CLIENT_SESSION_DIR = Path("data/user_state/clients")
MAX_SNAPSHOT_BYTES = 16 * 1024
RESTORE_NOTICE_KEY = "smai_last_session_restore_notice"
RESTORE_APPLIED_KEY = "smai_last_session_restore_applied"
CLIENT_ID_STATE_KEY = "smai_client_id"

ALLOWED_PAGES = frozenset(
    {"cockpit", "ranking", "news", "watchlist", "copilot", "rebalance", "settings"}
)
RANKING_STATE_KEYS = (
    "market_data_ranking_region",
    "market_data_ranking_product_type",
    "market_data_ranking_policy",
    "market_data_ranking_purpose",
    "market_data_ranking_fetch_limit",
    "market_data_ranking_period",
    "market_data_ranking_market",
    "market_data_ranking_asset_type",
    "market_data_ranking_currency",
    "market_data_ranking_dividend",
    "market_data_ranking_min_dividend",
    "market_data_ranking_market_cap",
    "market_data_ranking_index_family",
    "market_data_ranking_max_expense",
    "market_data_ranking_complexity",
    "market_data_ranking_nisa",
    "market_data_ranking_risk_band",
    "market_data_ranking_official_sector",
    "market_data_ranking_theme",
    "market_data_ranking_symbol_query",
    "market_data_ranking_per_enabled",
    "market_data_ranking_per_min",
    "market_data_ranking_per_max",
    "market_data_ranking_pbr_enabled",
    "market_data_ranking_pbr_min",
    "market_data_ranking_pbr_max",
    "market_data_ranking_dividend_enabled",
    "market_data_ranking_dividend_min",
    "market_data_ranking_dividend_max",
    "market_data_ranking_roe_enabled",
    "market_data_ranking_roe_min",
    "market_data_ranking_roe_max",
    "market_data_ranking_consensus_enabled",
    "market_data_ranking_consensus_min",
    "market_data_ranking_consensus_max",
)
PROVIDER_STATE_KEYS = (
    "market_data_provider_live_first",
    "market_data_ranking_provider_live_first",
)
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_CLIENT_ID = re.compile(r"^smai_client_[a-f0-9]{24}$")
_RESTORED_STATE_KEYS = (
    "smai_current_user_id",
    "sidemenu_page",
    "market_data_symbol_candidate",
    "market_data_ranking_handoff_symbol",
    *RANKING_STATE_KEYS,
    *PROVIDER_STATE_KEYS,
)


def generate_client_id() -> str:
    return f"{CLIENT_ID_PREFIX}{secrets.token_hex(12)}"


def valid_client_id(value: object) -> bool:
    return isinstance(value, str) and _CLIENT_ID.fullmatch(value) is not None


def ensure_client_id(
    session_state: MutableMapping[str, Any],
    query_params: MutableMapping[str, Any] | None,
) -> str:
    """Resolve a safe per-browser identifier and reflect it in the URL."""
    query_value = _query_value(query_params, CLIENT_QUERY_KEY)
    state_value = session_state.get(CLIENT_ID_STATE_KEY)
    if valid_client_id(query_value):
        client_id = query_value
    elif valid_client_id(state_value):
        client_id = str(state_value)
    else:
        client_id = generate_client_id()
    session_state[CLIENT_ID_STATE_KEY] = client_id
    if query_params is not None and query_value != client_id:
        try:
            query_params[CLIENT_QUERY_KEY] = client_id
        except (TypeError, AttributeError):
            LOGGER.warning(
                "Client id could not be added to query params.",
                exc_info=True,
            )
    return client_id


def client_session_path(
    client_id: str,
    directory: Path = DEFAULT_CLIENT_SESSION_DIR,
) -> Path | None:
    if not valid_client_id(client_id):
        return None
    return directory / f"{client_id}.json"


def load_client_session(path: Path) -> dict[str, Any] | None:
    """Load a small, validated snapshot without making startup fragile."""
    try:
        if not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        LOGGER.warning("Client-session snapshot could not be loaded.", exc_info=True)
        return None
    return _validated_snapshot(raw)


def save_client_session(snapshot: Mapping[str, Any], path: Path) -> bool:
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
        LOGGER.warning("Client-session snapshot could not be saved.", exc_info=True)
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def restore_client_session(
    session_state: MutableMapping[str, Any],
    *,
    client_id: str,
    valid_user_ids: set[str],
    query_params: Mapping[str, Any] | None = None,
    directory: Path = DEFAULT_CLIENT_SESSION_DIR,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Restore allowlisted values once, without starting fetches or calculations."""
    if session_state.get(RESTORE_APPLIED_KEY):
        return None
    session_state[RESTORE_APPLIED_KEY] = True
    path = client_session_path(client_id, directory)
    if path is None:
        return None
    snapshot = load_client_session(path)
    if snapshot is None:
        return None
    current_time = _as_utc(now or datetime.now(UTC))
    last_seen = _parse_datetime(snapshot.get("last_seen_at"))
    if last_seen is None or current_time - last_seen > CLIENT_SESSION_TTL:
        _delete_path(path)
        clear_restored_session_state(session_state)
        session_state[RESTORE_APPLIED_KEY] = True
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
    elif user_id not in valid_user_ids:
        _delete_path(path)
        clear_restored_session_state(session_state)
        session_state[RESTORE_APPLIED_KEY] = True
        return None

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

    for section, allowed_keys in (
        ("ranking_filters", RANKING_STATE_KEYS),
        ("settings", PROVIDER_STATE_KEYS),
    ):
        values = snapshot.get(section)
        if isinstance(values, dict):
            for key in allowed_keys:
                value = values.get(key)
                if key not in session_state and _safe_value(value):
                    session_state[key] = value

    if restored:
        session_state[RESTORE_NOTICE_KEY] = restored
        return restored
    return None


def snapshot_from_session_state(
    session_state: Mapping[str, Any],
    *,
    client_id: str,
    selected_symbol: str = "",
    now: datetime | None = None,
) -> dict[str, Any] | None:
    user_id = str(session_state.get("smai_current_user_id") or "")
    active_page = str(session_state.get("sidemenu_page") or "")
    if (
        not valid_client_id(client_id)
        or not _safe_value(user_id)
        or active_page not in ALLOWED_PAGES
    ):
        return None
    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "client_id": client_id,
        "selected_user_id": user_id,
        "active_page": active_page,
        "last_seen_at": _as_utc(now or datetime.now(UTC)).isoformat(),
    }
    if _safe_value(selected_symbol):
        snapshot["selected_symbol"] = selected_symbol
    for section, allowed_keys in (
        ("ranking_filters", RANKING_STATE_KEYS),
        ("settings", PROVIDER_STATE_KEYS),
    ):
        values = {
            key: session_state[key]
            for key in allowed_keys
            if key in session_state and _safe_value(session_state[key])
        }
        if values:
            snapshot[section] = values
    return snapshot


def save_client_session_if_changed(
    session_state: Mapping[str, Any],
    *,
    client_id: str,
    selected_symbol: str = "",
    directory: Path = DEFAULT_CLIENT_SESSION_DIR,
    now: datetime | None = None,
    force_write: bool = False,
) -> bool:
    snapshot = snapshot_from_session_state(
        session_state,
        client_id=client_id,
        selected_symbol=selected_symbol,
        now=now,
    )
    path = client_session_path(client_id, directory)
    if snapshot is None or path is None:
        return False
    current = load_client_session(path)
    comparable = {key: value for key, value in snapshot.items() if key != "last_seen_at"}
    current_comparable = (
        {key: value for key, value in current.items() if key != "last_seen_at"}
        if current is not None
        else None
    )
    if comparable == current_comparable and not force_write:
        return False
    return save_client_session(snapshot, path)


def clear_client_session(
    session_state: MutableMapping[str, Any],
    *,
    client_id: str,
    directory: Path = DEFAULT_CLIENT_SESSION_DIR,
) -> bool:
    path = client_session_path(client_id, directory)
    deleted = _delete_path(path) if path is not None else False
    clear_restored_session_state(session_state)
    session_state[CLIENT_ID_STATE_KEY] = client_id
    session_state[RESTORE_APPLIED_KEY] = True
    return deleted


def clear_restored_session_state(session_state: MutableMapping[str, Any]) -> None:
    for key in (*_RESTORED_STATE_KEYS, RESTORE_NOTICE_KEY):
        session_state.pop(key, None)


def _validated_snapshot(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        return None
    client_id = value.get("client_id")
    user_id = value.get("selected_user_id")
    active_page = value.get("active_page")
    last_seen_at = value.get("last_seen_at")
    if (
        not valid_client_id(client_id)
        or not _safe_value(user_id)
        or active_page not in ALLOWED_PAGES
        or _parse_datetime(last_seen_at) is None
    ):
        return None
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "client_id": str(client_id),
        "selected_user_id": str(user_id),
        "active_page": str(active_page),
        "last_seen_at": str(last_seen_at),
    }
    symbol = value.get("selected_symbol")
    if _safe_value(symbol):
        result["selected_symbol"] = str(symbol)
    for section, allowed_keys in (
        ("ranking_filters", RANKING_STATE_KEYS),
        ("settings", PROVIDER_STATE_KEYS),
    ):
        source = value.get(section)
        if isinstance(source, dict):
            cleaned = {
                key: source[key]
                for key in allowed_keys
                if key in source and _safe_value(source[key])
            }
            if cleaned:
                result[section] = cleaned
    return result


def _safe_value(value: object) -> bool:
    if isinstance(value, bool):
        return True
    return isinstance(value, str) and _SAFE_VALUE.fullmatch(value) is not None


def _query_value(params: Mapping[str, Any] | None, key: str) -> str:
    if params is None:
        return ""
    try:
        value = params.get(key)
    except AttributeError:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


def _has_query_value(params: Mapping[str, Any], *keys: str) -> bool:
    return any(_query_value(params, key) for key in keys)


def _parse_datetime(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _delete_path(path: Path) -> bool:
    try:
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed
    except OSError:
        LOGGER.warning("Client-session snapshot could not be deleted.", exc_info=True)
        return False
