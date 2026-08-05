from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.news.cache import load_cached_news_dashboard_snapshot


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
    snapshot = (
        load_cached_news_dashboard_snapshot()
        if cache_dir is None
        else load_cached_news_dashboard_snapshot(cache_dir=cache_dir)
    )
    source = "cache"
    if snapshot is None or not snapshot.stream_headlines:
        return AssistantLoadingHeadlines(
            items=(),
            updated_at=current,
            source="unavailable",
            stale=False,
        )
    updated_at = snapshot.fetched_at or snapshot.generated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    stale = current - updated_at > timedelta(hours=max_age_hours)
    candidates = sorted(
        snapshot.stream_headlines,
        key=lambda card: _headline_priority(card.category),
    )
    items = tuple(
        AssistantLoadingHeadline(
            title=card.title.strip(),
            category=card.category.strip(),
            source=(card.source_name or card.source_type).strip(),
        )
        for card in candidates[: min(5, max(1, max_items))]
        if card.title.strip()
    )
    return AssistantLoadingHeadlines(
        items=items,
        updated_at=updated_at,
        source=source,
        stale=stale,
    )


def _headline_priority(category: str) -> int:
    normalized = category.casefold()
    priorities = (
        (("地政学", "マクロ", "市場全体"), 0),
        (("国内株", "日本株", "米国株"), 1),
        (("決算", "業績", "修正"), 2),
        (("為替", "金利"), 3),
    )
    for keywords, priority in priorities:
        if any(keyword.casefold() in normalized for keyword in keywords):
            return priority
    return 4
