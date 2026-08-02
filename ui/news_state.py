"""User-scoped transient-state rules for the Investment Radar view."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

NEWS_RADAR_SESSION_OWNER_STATE_KEY = "investment_radar_session_owner_user_id"


def clear_news_radar_user_transient_state(
    session_state: MutableMapping[str, Any],
    *,
    refresh_state_key: str,
    watchlist_state_key: str,
) -> None:
    """Clear transient Radar state without touching durable user data."""

    removable_keys = (
        refresh_state_key,
        watchlist_state_key,
        "investment_news_watchlist_source",
    )
    for key in tuple(session_state):
        name = str(key)
        if (
            name.startswith("investment_radar_")
            or name.startswith("investment_news_filter_")
            or name in removable_keys
        ):
            session_state.pop(key, None)


def ensure_news_radar_user_scope(
    session_state: MutableMapping[str, Any],
    *,
    user_id: str,
    refresh_state_key: str,
    watchlist_state_key: str,
) -> bool:
    """Adopt a user scope and report whether old transient state was cleared."""

    active_user_id = user_id or "default"
    if session_state.get(NEWS_RADAR_SESSION_OWNER_STATE_KEY) == active_user_id:
        return False
    clear_news_radar_user_transient_state(
        session_state,
        refresh_state_key=refresh_state_key,
        watchlist_state_key=watchlist_state_key,
    )
    session_state[NEWS_RADAR_SESSION_OWNER_STATE_KEY] = active_user_id
    return True
