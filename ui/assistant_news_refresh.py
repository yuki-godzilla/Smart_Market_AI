from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from backend.news import (
    NewsRefreshResult,
    build_standard_news_dashboard_snapshot,
    refresh_news_dashboard_cache,
)


def refresh_news_for_assistant_action(
    *,
    allow_network: bool = True,
    force: bool = True,
    context: Mapping[str, object] | None = None,
) -> NewsRefreshResult:
    """Connect a confirmed Assistant action to the existing News Radar refresh path."""
    _ = context
    now = datetime.now(UTC)
    return refresh_news_dashboard_cache(
        lambda: build_standard_news_dashboard_snapshot(
            allow_network=allow_network,
            now=now,
            fallback_to_demo=False,
        ),
        now=now,
        force=force,
    )
