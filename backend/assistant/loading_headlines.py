from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.news import (
    build_demo_news_dashboard_snapshot,
    load_cached_news_dashboard_snapshot,
)


@dataclass(frozen=True)
class AssistantLoadingHeadline:
    title: str
    category: str
    source: str


@dataclass(frozen=True)
class AssistantLoadingHeadlines:
    items: tuple[AssistantLoadingHeadline, ...]
    updated_at: datetime
    source: str
    stale: bool


def load_assistant_loading_headlines(
    *,
    cache_dir: str | Path | None = None,
    max_items: int = 5,
    max_age_hours: int = 24,
    now: datetime | None = None,
) -> AssistantLoadingHeadlines:
    current = now or datetime.now(UTC)
    snapshot = load_cached_news_dashboard_snapshot(cache_dir=cache_dir)
    source = "cache"
    if snapshot is None or not snapshot.stream_headlines:
        snapshot = build_demo_news_dashboard_snapshot(now=current)
        source = "sample"
    updated_at = snapshot.fetched_at or snapshot.generated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    stale = current - updated_at > timedelta(hours=max_age_hours)
    items = tuple(
        AssistantLoadingHeadline(
            title=card.title.strip(),
            category=card.category.strip(),
            source=(card.source_name or card.source_type).strip(),
        )
        for card in snapshot.stream_headlines[: max(1, max_items)]
        if card.title.strip()
    )
    return AssistantLoadingHeadlines(
        items=items,
        updated_at=updated_at,
        source=source,
        stale=stale,
    )
