from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from backend.symbols.background import (
    BACKGROUND_REFRESH_MAX_ITEMS,
    BACKGROUND_REFRESH_STEPS,
    MAX_SYMBOL_REFRESH_PER_SESSION,
    STARTUP_BACKGROUND_REFRESH_MAX_ITEMS,
    SymbolBackgroundRefreshStep,
    clear_symbol_background_refresh_targets,
    request_symbol_background_refresh,
    run_symbol_background_refresh_cycle,
)
from backend.symbols.repository import load_symbol_record, load_symbol_records


def test_background_refresh_cycle_runs_short_session_plan(tmp_path) -> None:
    csv_path = _write_symbol_universe(tmp_path, symbol_count=70)
    waits: list[float] = []
    current_time = datetime(2026, 6, 3, 12, 0, 0)
    steps = (
        SymbolBackgroundRefreshStep(delay_minutes=3, max_items=4),
        SymbolBackgroundRefreshStep(delay_minutes=8, max_items=4),
    )

    def now_provider() -> datetime:
        nonlocal current_time
        value = current_time
        current_time += timedelta(minutes=1)
        return value

    summaries = run_symbol_background_refresh_cycle(
        cache_dir=tmp_path,
        symbol_universe_csv=csv_path,
        startup_max_items=8,
        steps=steps,
        max_items_per_session=16,
        wait=waits.append,
        now_provider=now_provider,
    )

    assert STARTUP_BACKGROUND_REFRESH_MAX_ITEMS == 150
    assert MAX_SYMBOL_REFRESH_PER_SESSION == 1000
    assert waits == [180.0, 300.0]
    assert sum(summary.succeeded_count for summary in summaries) == 16
    assert len(load_symbol_records(cache_dir=tmp_path)) == 16
    assert summaries[0].succeeded_count == 8
    assert summaries[1].succeeded_count == steps[0].max_items
    assert summaries[2].succeeded_count == steps[1].max_items
    assert all(summary.pending_like_count == 0 for summary in summaries)


def test_background_refresh_cycle_stops_when_no_stale_symbols_remain(tmp_path) -> None:
    csv_path = _write_symbol_universe(tmp_path, symbol_count=50)
    waits: list[float] = []
    now = datetime(2026, 6, 3, 12, 0, 0)

    summaries = run_symbol_background_refresh_cycle(
        cache_dir=tmp_path,
        symbol_universe_csv=csv_path,
        startup_max_items=80,
        wait=waits.append,
        now_provider=lambda: now,
    )

    assert len(summaries) == 1
    assert summaries[0].succeeded_count == 50
    assert len(load_symbol_records(cache_dir=tmp_path)) == 50
    assert waits == []


def test_background_refresh_cycle_uses_recurring_batches_after_eight_minutes(
    tmp_path,
) -> None:
    csv_path = _write_symbol_universe(tmp_path, symbol_count=50)
    waits: list[float] = []
    now = datetime(2026, 6, 3, 12, 0, 0)
    steps = (
        SymbolBackgroundRefreshStep(delay_minutes=3, max_items=4),
        SymbolBackgroundRefreshStep(delay_minutes=8, max_items=4),
    )

    summaries = run_symbol_background_refresh_cycle(
        cache_dir=tmp_path,
        symbol_universe_csv=csv_path,
        startup_max_items=8,
        steps=steps,
        recurring_max_items=3,
        max_items_per_session=19,
        wait=waits.append,
        now_provider=lambda: now,
    )

    assert waits == [180.0, 300.0, 300.0]
    assert BACKGROUND_REFRESH_STEPS[0].max_items == 75
    assert BACKGROUND_REFRESH_STEPS[1].max_items == 75
    assert BACKGROUND_REFRESH_MAX_ITEMS == 50
    assert summaries[-1].succeeded_count == 3
    assert sum(summary.succeeded_count for summary in summaries) == 19


def test_background_refresh_cycle_prioritizes_requested_ranking_symbol(tmp_path) -> None:
    csv_path = _write_symbol_universe(tmp_path, symbol_count=50)
    now = datetime(2026, 6, 3, 12, 0, 0)
    clear_symbol_background_refresh_targets()

    try:
        requested_symbols = request_symbol_background_refresh(
            [" t0049 ", ""],
            source="ranking",
            start_worker=False,
        )
        summaries = run_symbol_background_refresh_cycle(
            cache_dir=tmp_path,
            symbol_universe_csv=csv_path,
            startup_max_items=1,
            steps=(),
            recurring_max_items=0,
            max_items_per_session=1,
            now_provider=lambda: now,
        )
    finally:
        clear_symbol_background_refresh_targets()

    assert requested_symbols == ["T0049"]
    assert summaries[0].refreshed_symbols == ["T0049"]
    assert load_symbol_record("T0049", cache_dir=tmp_path) is not None


def _write_symbol_universe(tmp_path: Path, *, symbol_count: int) -> Path:
    csv_path = tmp_path / "symbol_universe.csv"
    fields = [
        "symbol",
        "name",
        "market",
        "asset_type",
        "currency",
        "metadata_source",
        "metadata_updated_at",
        "is_active",
        "tags",
    ]
    lines = [",".join(fields)]
    for index in range(symbol_count):
        symbol = f"T{index:04d}"
        values = {
            "symbol": symbol,
            "name": f"Test {index:04d}",
            "market": "us",
            "asset_type": "stock",
            "currency": "USD",
            "metadata_source": "fixture",
            "metadata_updated_at": "2026-06-01T00:00:00",
            "is_active": "true",
            "tags": "",
        }
        lines.append(",".join(values[field] for field in fields))
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path
