from __future__ import annotations

import os
from datetime import datetime

from backend.news.radar_market import (
    RADAR_MARKET_FRESHNESS_MINUTES,
    RadarMarketSnapshot,
    radar_market_snapshot_is_stale,
)

NEWS_RADAR_MARKET_AUTO_REFRESH_MINUTES = RADAR_MARKET_FRESHNESS_MINUTES


def radar_market_snapshot_needs_refresh(
    snapshot: RadarMarketSnapshot | None,
    *,
    lookback_sessions: int,
    now: datetime | None = None,
) -> bool:
    """Return whether page entry should refresh the bounded daily-price snapshot."""

    if snapshot is None or snapshot.lookback_sessions != lookback_sessions:
        return True
    return radar_market_snapshot_is_stale(
        snapshot,
        now=now,
        max_age_minutes=NEWS_RADAR_MARKET_AUTO_REFRESH_MINUTES,
    )


def radar_market_auto_fetch_enabled() -> bool:
    return os.getenv("SMAI_RADAR_AUTO_FETCH", "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }
