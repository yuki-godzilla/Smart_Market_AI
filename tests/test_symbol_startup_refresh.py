from __future__ import annotations

from datetime import datetime
from pathlib import Path

from backend.symbols.startup import (
    find_pending_symbol_refresh_tasks,
    run_symbol_database_startup_refresh,
)


def test_startup_refresh_updates_next_missing_symbols_without_pending_leftovers(tmp_path) -> None:
    csv_path = _write_symbol_universe(
        tmp_path,
        [
            {"symbol": "7203", "name": "Toyota", "market": "jp", "asset_type": "stock"},
            {"symbol": "AAPL", "name": "Apple", "market": "us", "asset_type": "stock"},
            {"symbol": "NVDA", "name": "Nvidia", "market": "us", "asset_type": "stock"},
        ],
    )
    now = datetime(2026, 6, 3, 12, 0, 0)

    first = run_symbol_database_startup_refresh(
        cache_dir=tmp_path,
        symbol_universe_csv=csv_path,
        now=now,
        max_items=2,
    )
    second = run_symbol_database_startup_refresh(
        cache_dir=tmp_path,
        symbol_universe_csv=csv_path,
        now=now,
        max_items=2,
        force=True,
    )

    assert first.attempted_count == 2
    assert first.succeeded_count == 2
    assert first.pending_like_count == 0
    assert second.attempted_count == 1
    assert second.succeeded_count == 1
    assert second.record_count == 3
    assert find_pending_symbol_refresh_tasks(cache_dir=tmp_path) == []


def test_startup_refresh_skips_when_all_symbols_are_fresh(tmp_path) -> None:
    csv_path = _write_symbol_universe(
        tmp_path,
        [{"symbol": "7203", "name": "Toyota", "market": "jp", "asset_type": "stock"}],
    )
    now = datetime(2026, 6, 3, 12, 0, 0)

    first = run_symbol_database_startup_refresh(
        cache_dir=tmp_path,
        symbol_universe_csv=csv_path,
        now=now,
    )
    second = run_symbol_database_startup_refresh(
        cache_dir=tmp_path,
        symbol_universe_csv=csv_path,
        now=now,
        force=True,
    )

    assert first.succeeded_count == 1
    assert second.attempted_count == 0
    assert second.pending_like_count == 0


def test_startup_refresh_skips_when_recent_batch_succeeded(tmp_path) -> None:
    csv_path = _write_symbol_universe(
        tmp_path,
        [
            {"symbol": "7203", "name": "Toyota", "market": "jp", "asset_type": "stock"},
            {"symbol": "AAPL", "name": "Apple", "market": "us", "asset_type": "stock"},
        ],
    )
    now = datetime(2026, 6, 3, 12, 0, 0)

    first = run_symbol_database_startup_refresh(
        cache_dir=tmp_path,
        symbol_universe_csv=csv_path,
        now=now,
        max_items=1,
    )
    second = run_symbol_database_startup_refresh(
        cache_dir=tmp_path,
        symbol_universe_csv=csv_path,
        now=now,
        max_items=1,
    )

    assert first.succeeded_count == 1
    assert second.attempted_count == 0
    assert second.skipped_count == 1
    assert second.record_count == 1


def test_startup_refresh_default_batch_caps_at_one_hundred_fifty_symbols(
    tmp_path,
) -> None:
    csv_path = _write_symbol_universe(
        tmp_path,
        [
            {
                "symbol": f"T{index:04d}",
                "name": f"Test {index:04d}",
                "market": "us",
                "asset_type": "stock",
            }
            for index in range(200)
        ],
    )

    summary = run_symbol_database_startup_refresh(
        cache_dir=tmp_path,
        symbol_universe_csv=csv_path,
        now=datetime(2026, 6, 3, 12, 0, 0),
    )

    assert summary.succeeded_count == 150
    assert summary.record_count == 150


def _write_symbol_universe(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
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
    for row in rows:
        values = {
            "currency": "JPY",
            "metadata_source": "fixture",
            "metadata_updated_at": "2026-06-01T00:00:00",
            "is_active": "true",
            "tags": "",
            **row,
        }
        lines.append(",".join(values.get(field, "") for field in fields))
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path
