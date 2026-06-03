from __future__ import annotations

from datetime import datetime, timedelta

from backend.symbols.contracts import (
    SymbolFreshnessStatus,
    SymbolImportanceMeta,
    SymbolRefreshTask,
    SymbolUsageStats,
)
from backend.symbols.refresh_priority import (
    build_symbol_refresh_queue,
    calculate_symbol_refresh_priority,
    evaluate_symbol_freshness,
    sort_symbol_refresh_queue,
)


def test_evaluate_symbol_freshness_classifies_age() -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)

    assert evaluate_symbol_freshness(None, symbol="7203", now=now).data_freshness_status == (
        "missing"
    )
    assert (
        evaluate_symbol_freshness(
            {"last_refreshed_at": now - timedelta(hours=12)},
            symbol="7203",
            now=now,
        ).data_freshness_status
        == "fresh"
    )
    assert (
        evaluate_symbol_freshness(
            {"last_refreshed_at": now - timedelta(days=3)},
            symbol="7203",
            now=now,
        ).data_freshness_status
        == "stale"
    )
    assert (
        evaluate_symbol_freshness(
            {"last_refreshed_at": now - timedelta(days=8)},
            symbol="7203",
            now=now,
        ).data_freshness_status
        == "expired"
    )


def test_build_symbol_refresh_queue_skips_fresh_without_force() -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)

    queue = build_symbol_refresh_queue(
        ["7203", "AAPL"],
        symbol_records={
            "7203": {"last_refreshed_at": now - timedelta(hours=2)},
            "AAPL": {"last_refreshed_at": now - timedelta(days=8)},
        },
        now=now,
    )

    assert [task.symbol for task in queue] == ["AAPL"]
    assert queue[0].data_freshness_status == "expired"


def test_priority_score_combines_usage_importance_recent_and_manual() -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    freshness = evaluate_symbol_freshness(
        {"last_refreshed_at": now - timedelta(days=9)},
        symbol="NVDA",
        now=now,
    )

    priority = calculate_symbol_refresh_priority(
        freshness,
        usage_stats=SymbolUsageStats(
            symbol="NVDA",
            view_count_last_30_days=99,
            last_viewed_at=now - timedelta(minutes=30),
        ),
        importance_meta=SymbolImportanceMeta(
            symbol="NVDA",
            is_major_symbol=True,
            is_ranking_base_symbol=True,
        ),
        now=now,
        currently_visible_in_ranking=True,
        manual_refresh=True,
    )

    assert priority.usage_score == 20
    assert priority.importance_score == 50
    assert priority.stale_score == 60
    assert priority.recent_view_bonus == 40
    assert priority.ranking_candidate_bonus == 30
    assert priority.manual_refresh_bonus == 100
    assert priority.refresh_priority_score == 300


def test_sort_queue_uses_score_freshness_age_then_symbol() -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    tasks = [
        _task("CCC", 10, "stale", now - timedelta(days=2), now),
        _task("BBB", 10, "expired", now - timedelta(days=1), now),
        _task("AAA", 10, "expired", now - timedelta(days=3), now),
        _task("ZZZ", 99, "fresh", now, now),
    ]

    sorted_tasks = sort_symbol_refresh_queue(tasks)

    assert [task.symbol for task in sorted_tasks] == ["ZZZ", "AAA", "BBB", "CCC"]


def test_build_queue_applies_max_items_and_manual_refresh_for_fresh_symbol() -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)

    queue = build_symbol_refresh_queue(
        ["7203", "AAPL", "NVDA"],
        symbol_records={
            "7203": {"last_refreshed_at": now - timedelta(hours=1)},
            "AAPL": {"last_refreshed_at": now - timedelta(days=9)},
            "NVDA": {"last_refreshed_at": now - timedelta(days=4)},
        },
        manual_symbols={"7203"},
        now=now,
        max_items=2,
    )

    assert len(queue) == 2
    assert queue[0].symbol == "7203"
    assert queue[0].reason == "manual_refresh"


def _task(
    symbol: str,
    score: int,
    freshness: SymbolFreshnessStatus,
    last_refreshed_at: datetime,
    requested_at: datetime,
) -> SymbolRefreshTask:
    return SymbolRefreshTask(
        symbol=symbol,
        priority=score,
        refresh_priority_score=score,
        reason="startup_refresh",
        data_freshness_status=freshness,
        requested_at=requested_at,
        last_refreshed_at=last_refreshed_at,
    )
