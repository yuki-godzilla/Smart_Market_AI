from __future__ import annotations

from datetime import datetime, timedelta

from backend.symbols.cache import (
    MAX_PERSISTED_REFRESH_TASKS,
    acquire_symbol_refresh_lock,
    cleanup_symbol_refresh_artifacts,
    load_symbol_refresh_queue,
    load_symbol_refresh_status,
    recover_interrupted_symbol_refresh_tasks,
    release_symbol_refresh_lock,
    save_symbol_refresh_queue,
    save_symbol_refresh_status,
)
from backend.symbols.contracts import SymbolRefreshStatus, SymbolRefreshTask


def test_symbol_refresh_queue_is_bounded_deduped_and_atomic(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    tasks = [_task(f"sym{i}", now) for i in range(MAX_PERSISTED_REFRESH_TASKS + 5)]
    tasks.append(_task("SYM1", now))
    tasks.append(_task("DONE", now, status="succeeded"))

    saved = save_symbol_refresh_queue(tasks, cache_dir=tmp_path)
    loaded = load_symbol_refresh_queue(cache_dir=tmp_path)

    assert len(saved) == MAX_PERSISTED_REFRESH_TASKS
    assert len(loaded) == MAX_PERSISTED_REFRESH_TASKS
    assert loaded[1].symbol == "SYM1"
    assert not (tmp_path / "symbol_refresh_queue.tmp.json").exists()
    assert all(task.status in {"pending", "in_progress", "retryable"} for task in loaded)


def test_symbol_refresh_status_is_latest_only_and_bounded(tmp_path) -> None:
    status = SymbolRefreshStatus(
        last_refreshed_symbols=["7203", "7203", *[f"S{i}" for i in range(30)]],
        refresh_queue_size=3,
        is_refreshing=True,
    )

    saved = save_symbol_refresh_status(status, cache_dir=tmp_path)
    loaded = load_symbol_refresh_status(cache_dir=tmp_path)

    assert saved.last_refreshed_symbols[:2] == ["7203", "S0"]
    assert len(saved.last_refreshed_symbols) == 20
    assert loaded.refresh_queue_size == 3
    assert loaded.is_refreshing is True
    assert not (tmp_path / "symbol_refresh_status.tmp.json").exists()


def test_recover_interrupted_tasks_moves_in_progress_to_retryable_or_failed() -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    tasks = [
        _task("7203", now, status="in_progress", retry_count=0),
        _task("AAPL", now, status="in_progress", retry_count=1),
        _task("NVDA", now, status="in_progress", retry_count=0),
    ]

    recovered = recover_interrupted_symbol_refresh_tasks(
        tasks,
        now=now + timedelta(minutes=5),
        fresh_symbols={"NVDA"},
    )

    assert recovered[0].status == "retryable"
    assert recovered[0].retry_count == 1
    assert recovered[0].last_error_type == "interrupted"
    assert recovered[1].status == "failed"
    assert recovered[2].status == "skipped"


def test_symbol_refresh_lock_blocks_parallel_runs_and_replaces_stale_lock(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)

    assert acquire_symbol_refresh_lock(cache_dir=tmp_path, now=now) is True
    assert acquire_symbol_refresh_lock(cache_dir=tmp_path, now=now + timedelta(minutes=1)) is False
    assert acquire_symbol_refresh_lock(cache_dir=tmp_path, now=now + timedelta(minutes=31)) is True

    release_symbol_refresh_lock(cache_dir=tmp_path)
    assert not (tmp_path / "symbol_refresh.lock").exists()


def test_cleanup_symbol_refresh_artifacts_only_deletes_known_symbol_files(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    (tmp_path / "symbol_refresh_queue.tmp.json").write_text("[]", encoding="utf-8")
    (tmp_path / "symbol_refresh_status.tmp.json").write_text("{}", encoding="utf-8")
    (tmp_path / "symbol_refresh_debug_dump.json").write_text("{}", encoding="utf-8")
    (tmp_path / "symbol_refresh.lock").write_text(
        (now - timedelta(minutes=31)).isoformat(),
        encoding="utf-8",
    )
    keep_file = tmp_path / "news_dashboard_snapshot.json"
    keep_file.write_text("{}", encoding="utf-8")

    deleted = cleanup_symbol_refresh_artifacts(cache_dir=tmp_path, now=now)

    assert {path.name for path in deleted} == {
        "symbol_refresh_queue.tmp.json",
        "symbol_refresh_status.tmp.json",
        "symbol_refresh_debug_dump.json",
        "symbol_refresh.lock",
    }
    assert keep_file.exists()


def _task(
    symbol: str,
    requested_at: datetime,
    *,
    status: str = "pending",
    retry_count: int = 0,
) -> SymbolRefreshTask:
    return SymbolRefreshTask(
        symbol=symbol,
        priority=10,
        refresh_priority_score=10,
        reason="startup_refresh",
        status=status,
        requested_at=requested_at,
        retry_count=retry_count,
    )
