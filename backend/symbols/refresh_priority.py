from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from backend.symbols.contracts import (
    SymbolDataFreshness,
    SymbolFreshnessStatus,
    SymbolImportanceMeta,
    SymbolRefreshPriority,
    SymbolRefreshTask,
    SymbolUsageStats,
)

SYMBOL_PRICE_FRESH_HOURS = 24
SYMBOL_EXPIRED_DAYS = 7
MAX_SYMBOL_REFRESH_PER_RUN = 150

STALE_SCORES: dict[SymbolFreshnessStatus, int] = {
    "missing": 100,
    "expired": 60,
    "stale": 30,
    "fresh": 0,
}
FRESHNESS_SORT_ORDER: dict[SymbolFreshnessStatus, int] = {
    "missing": 0,
    "expired": 1,
    "stale": 2,
    "fresh": 3,
}


def evaluate_symbol_freshness(
    symbol_record: Mapping[str, object] | SymbolDataFreshness | None,
    *,
    symbol: str,
    now: datetime,
) -> SymbolDataFreshness:
    """Classify stored symbol data into missing/fresh/stale/expired."""

    last_refreshed_at = _extract_last_refreshed_at(symbol_record)
    if last_refreshed_at is None:
        return SymbolDataFreshness(
            symbol=symbol,
            last_refreshed_at=None,
            data_freshness_status="missing",
            should_refresh=True,
            reason="missing_data",
        )

    age = now - last_refreshed_at
    if age <= timedelta(hours=SYMBOL_PRICE_FRESH_HOURS):
        status: SymbolFreshnessStatus = "fresh"
        should_refresh = False
    elif age <= timedelta(days=SYMBOL_EXPIRED_DAYS):
        status = "stale"
        should_refresh = True
    else:
        status = "expired"
        should_refresh = True

    return SymbolDataFreshness(
        symbol=symbol,
        last_price_updated_at=_extract_datetime(symbol_record, "last_price_updated_at"),
        last_fundamental_updated_at=_extract_datetime(
            symbol_record,
            "last_fundamental_updated_at",
        ),
        last_refreshed_at=last_refreshed_at,
        data_freshness_status=status,
        should_refresh=should_refresh,
        reason=f"{status}_data",
    )


def calculate_symbol_refresh_priority(
    freshness: SymbolDataFreshness,
    *,
    usage_stats: SymbolUsageStats | None = None,
    importance_meta: SymbolImportanceMeta | None = None,
    now: datetime,
    reason: str | None = None,
    currently_visible_in_ranking: bool = False,
    ranking_candidate: bool = False,
    manual_refresh: bool = False,
) -> SymbolRefreshPriority:
    """Calculate a deterministic priority score for one symbol."""

    usage_score = min(usage_stats.view_count_last_30_days, 20) if usage_stats else 0
    importance_score = _importance_score(importance_meta)
    stale_score = STALE_SCORES[freshness.data_freshness_status]
    recent_view_bonus = _recent_view_bonus(usage_stats, now)
    ranking_candidate_bonus = 30 if currently_visible_in_ranking else 0
    if not ranking_candidate_bonus and ranking_candidate:
        ranking_candidate_bonus = 15
    manual_refresh_bonus = 100 if manual_refresh else 0
    refresh_priority_score = (
        usage_score
        + importance_score
        + stale_score
        + recent_view_bonus
        + ranking_candidate_bonus
        + manual_refresh_bonus
    )

    return SymbolRefreshPriority(
        symbol=freshness.symbol,
        data_freshness_status=freshness.data_freshness_status,
        usage_score=usage_score,
        importance_score=importance_score,
        stale_score=stale_score,
        recent_view_bonus=recent_view_bonus,
        ranking_candidate_bonus=ranking_candidate_bonus,
        manual_refresh_bonus=manual_refresh_bonus,
        refresh_priority_score=refresh_priority_score,
        reason=reason or freshness.reason,
        last_refreshed_at=freshness.last_refreshed_at,
    )


def build_symbol_refresh_queue(
    symbols: Iterable[str],
    *,
    symbol_records: Mapping[str, Mapping[str, object] | SymbolDataFreshness] | None = None,
    usage_stats: Mapping[str, SymbolUsageStats] | None = None,
    importance_meta: Mapping[str, SymbolImportanceMeta] | None = None,
    now: datetime,
    reason: str = "startup_refresh",
    force: bool = False,
    manual_symbols: set[str] | None = None,
    ranking_candidates: set[str] | None = None,
    currently_visible_symbols: set[str] | None = None,
    max_items: int = MAX_SYMBOL_REFRESH_PER_RUN,
) -> list[SymbolRefreshTask]:
    """Build a bounded refresh queue from freshness and priority signals."""

    manual_symbols = _normalize_symbol_set(manual_symbols)
    ranking_candidates = _normalize_symbol_set(ranking_candidates)
    currently_visible_symbols = _normalize_symbol_set(currently_visible_symbols)
    symbol_records = symbol_records or {}
    usage_stats = usage_stats or {}
    importance_meta = importance_meta or {}

    tasks: list[SymbolRefreshTask] = []
    for raw_symbol in symbols:
        symbol = _normalize_symbol(raw_symbol)
        if not symbol:
            continue
        freshness = evaluate_symbol_freshness(
            symbol_records.get(symbol),
            symbol=symbol,
            now=now,
        )
        is_manual = symbol in manual_symbols
        if freshness.data_freshness_status == "fresh" and not (force or is_manual):
            continue

        priority = calculate_symbol_refresh_priority(
            freshness,
            usage_stats=usage_stats.get(symbol),
            importance_meta=importance_meta.get(symbol),
            now=now,
            reason="manual_refresh" if is_manual else reason,
            currently_visible_in_ranking=symbol in currently_visible_symbols,
            ranking_candidate=symbol in ranking_candidates,
            manual_refresh=is_manual or force,
        )
        tasks.append(_priority_to_task(priority, requested_at=now))

    return sort_symbol_refresh_queue(tasks)[:max_items]


def sort_symbol_refresh_queue(tasks: Iterable[SymbolRefreshTask]) -> list[SymbolRefreshTask]:
    """Sort tasks by priority, freshness urgency, age, then symbol."""

    return sorted(
        tasks,
        key=lambda task: (
            -task.refresh_priority_score,
            FRESHNESS_SORT_ORDER[task.data_freshness_status],
            task.last_refreshed_at or datetime.min,
            task.symbol,
        ),
    )


def _priority_to_task(
    priority: SymbolRefreshPriority,
    *,
    requested_at: datetime,
) -> SymbolRefreshTask:
    return SymbolRefreshTask(
        symbol=priority.symbol,
        priority=priority.refresh_priority_score,
        refresh_priority_score=priority.refresh_priority_score,
        reason=priority.reason or "startup_refresh",
        status="pending",
        data_freshness_status=priority.data_freshness_status,
        requested_at=requested_at,
        last_refreshed_at=priority.last_refreshed_at,
    )


def _importance_score(meta: SymbolImportanceMeta | None) -> int:
    if meta is None:
        return 0
    score = 0
    if meta.is_major_symbol:
        score += 30
    if meta.is_ranking_base_symbol:
        score += 20
    if meta.is_core_etf:
        score += 15
    if meta.importance_rank is not None:
        score += max(0, 10 - min(meta.importance_rank, 10))
    return score


def _recent_view_bonus(usage_stats: SymbolUsageStats | None, now: datetime) -> int:
    if usage_stats is None or usage_stats.last_viewed_at is None:
        return 0
    age = now - usage_stats.last_viewed_at
    if age <= timedelta(hours=1):
        return 40
    if age <= timedelta(days=1):
        return 25
    if age <= timedelta(days=7):
        return 10
    return 0


def _extract_last_refreshed_at(
    symbol_record: Mapping[str, object] | SymbolDataFreshness | None,
) -> datetime | None:
    return (
        _extract_datetime(symbol_record, "last_refreshed_at")
        or _extract_datetime(symbol_record, "last_price_updated_at")
        or _extract_datetime(symbol_record, "last_fundamental_updated_at")
        or _extract_datetime(symbol_record, "updated_at")
    )


def _extract_datetime(
    symbol_record: Mapping[str, object] | SymbolDataFreshness | None,
    field_name: str,
) -> datetime | None:
    if symbol_record is None:
        return None
    if isinstance(symbol_record, SymbolDataFreshness):
        value = getattr(symbol_record, field_name, None)
    else:
        value = symbol_record.get(field_name)
    if isinstance(value, datetime):
        return value
    return None


def _normalize_symbol_set(symbols: set[str] | None) -> set[str]:
    if not symbols:
        return set()
    return {_normalize_symbol(symbol) for symbol in symbols if _normalize_symbol(symbol)}


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()
