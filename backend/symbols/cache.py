from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from typing import Final

from pydantic import TypeAdapter

from backend.core.runtime_paths import CACHE_DIR_ENV, runtime_path_from_env
from backend.symbols.contracts import (
    SymbolRefreshStatus,
    SymbolRefreshTask,
    SymbolRefreshTaskStatus,
)

SYMBOL_CACHE_DIR: Final[Path] = runtime_path_from_env(CACHE_DIR_ENV, "data/cache")
SYMBOL_REFRESH_QUEUE_FILENAME: Final[str] = "symbol_refresh_queue.json"
SYMBOL_REFRESH_QUEUE_TMP_FILENAME: Final[str] = "symbol_refresh_queue.tmp.json"
SYMBOL_REFRESH_STATUS_FILENAME: Final[str] = "symbol_refresh_status.json"
SYMBOL_REFRESH_STATUS_TMP_FILENAME: Final[str] = "symbol_refresh_status.tmp.json"
SYMBOL_REFRESH_LOCK_FILENAME: Final[str] = "symbol_refresh.lock"

MAX_PERSISTED_REFRESH_TASKS = 100
MAX_STATUS_SYMBOLS = 20
MAX_TASK_RETRY = 1
STALE_LOCK_MINUTES = 30
ATOMIC_REPLACE_RETRY_COUNT = 5
ATOMIC_REPLACE_RETRY_DELAY_SECONDS = 0.05

_TASK_LIST_ADAPTER = TypeAdapter(list[SymbolRefreshTask])


def load_symbol_refresh_queue(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> list[SymbolRefreshTask]:
    """Load the lightweight pending/retryable refresh queue."""

    queue_file = _cache_path(cache_dir, SYMBOL_REFRESH_QUEUE_FILENAME)
    if not queue_file.exists():
        return []
    try:
        return _TASK_LIST_ADAPTER.validate_json(queue_file.read_text(encoding="utf-8"))
    except ValueError:
        return []


def save_symbol_refresh_queue(
    tasks: Sequence[SymbolRefreshTask],
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> list[SymbolRefreshTask]:
    """Atomically persist a bounded queue without history arrays."""

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_queue(tasks)
    queue_file = _cache_path(cache_root, SYMBOL_REFRESH_QUEUE_FILENAME)
    tmp_file = _cache_path(cache_root, SYMBOL_REFRESH_QUEUE_TMP_FILENAME)
    try:
        tmp_file.write_text(
            _TASK_LIST_ADAPTER.dump_json(normalized, indent=2).decode("utf-8"),
            encoding="utf-8",
        )
        _TASK_LIST_ADAPTER.validate_json(tmp_file.read_text(encoding="utf-8"))
        _replace_with_retry(tmp_file, queue_file)
    finally:
        if tmp_file.exists():
            tmp_file.unlink()
    return normalized


def load_symbol_refresh_status(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> SymbolRefreshStatus:
    """Load latest-only refresh status, falling back to an empty status."""

    status_file = _cache_path(cache_dir, SYMBOL_REFRESH_STATUS_FILENAME)
    if not status_file.exists():
        return SymbolRefreshStatus()
    try:
        return SymbolRefreshStatus.model_validate_json(status_file.read_text(encoding="utf-8"))
    except ValueError:
        return SymbolRefreshStatus()


def save_symbol_refresh_status(
    status: SymbolRefreshStatus,
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> SymbolRefreshStatus:
    """Atomically save the latest-only refresh status."""

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    normalized = status.model_copy(
        update={
            "last_refreshed_symbols": _dedupe_symbols(status.last_refreshed_symbols)[
                :MAX_STATUS_SYMBOLS
            ],
        }
    )
    status_file = _cache_path(cache_root, SYMBOL_REFRESH_STATUS_FILENAME)
    tmp_file = _cache_path(cache_root, SYMBOL_REFRESH_STATUS_TMP_FILENAME)
    try:
        tmp_file.write_text(normalized.model_dump_json(indent=2), encoding="utf-8")
        SymbolRefreshStatus.model_validate_json(tmp_file.read_text(encoding="utf-8"))
        _replace_with_retry(tmp_file, status_file)
    finally:
        if tmp_file.exists():
            tmp_file.unlink()
    return normalized


def recover_interrupted_symbol_refresh_tasks(
    tasks: Sequence[SymbolRefreshTask],
    *,
    now: datetime,
    fresh_symbols: set[str] | None = None,
    max_retry: int = MAX_TASK_RETRY,
) -> list[SymbolRefreshTask]:
    """Convert leftover in_progress tasks into retryable/pending-safe tasks."""

    fresh_symbols = _normalize_symbol_set(fresh_symbols)
    recovered: list[SymbolRefreshTask] = []
    for task in tasks:
        if task.status != "in_progress":
            recovered.append(task)
            continue
        if task.symbol in fresh_symbols:
            recovered.append(task.model_copy(update={"status": "skipped", "finished_at": now}))
            continue
        retry_count = task.retry_count + 1
        status: SymbolRefreshTaskStatus = "retryable" if retry_count <= max_retry else "failed"
        recovered.append(
            task.model_copy(
                update={
                    "status": status,
                    "started_at": None,
                    "finished_at": now if status == "failed" else None,
                    "retry_count": retry_count,
                    "last_error_type": "interrupted",
                }
            )
        )
    return recovered


def acquire_symbol_refresh_lock(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    now: datetime,
    stale_lock_minutes: int = STALE_LOCK_MINUTES,
) -> bool:
    """Acquire a lightweight file lock; stale locks are replaced."""

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    lock_file = _cache_path(cache_root, SYMBOL_REFRESH_LOCK_FILENAME)
    if lock_file.exists():
        lock_created_at = _read_lock_created_at(lock_file)
        if lock_created_at and now - lock_created_at <= timedelta(minutes=stale_lock_minutes):
            return False
        lock_file.unlink()
    lock_file.write_text(now.isoformat(), encoding="utf-8")
    return True


def release_symbol_refresh_lock(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> None:
    """Release the refresh lock if it exists."""

    lock_file = _cache_path(cache_dir, SYMBOL_REFRESH_LOCK_FILENAME)
    if lock_file.exists():
        lock_file.unlink()


def cleanup_symbol_refresh_artifacts(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    now: datetime,
    stale_lock_minutes: int = STALE_LOCK_MINUTES,
) -> list[Path]:
    """Remove only bounded, known symbol-refresh temporary artifacts."""

    cache_root = Path(cache_dir)
    if not cache_root.exists():
        return []

    deleted: list[Path] = []
    for path in cache_root.iterdir():
        if not path.is_file():
            continue
        if _should_delete_artifact(path, now=now, stale_lock_minutes=stale_lock_minutes):
            path.unlink()
            deleted.append(path)
    return deleted


def _normalize_queue(tasks: Sequence[SymbolRefreshTask]) -> list[SymbolRefreshTask]:
    kept_statuses: set[SymbolRefreshTaskStatus] = {
        "pending",
        "in_progress",
        "retryable",
    }
    normalized: list[SymbolRefreshTask] = []
    seen: set[str] = set()
    for task in tasks:
        symbol = task.symbol.strip().upper()
        if not symbol or symbol in seen or task.status not in kept_statuses:
            continue
        seen.add(symbol)
        normalized.append(task.model_copy(update={"symbol": symbol}))
        if len(normalized) >= MAX_PERSISTED_REFRESH_TASKS:
            break
    return normalized


def _should_delete_artifact(
    path: Path,
    *,
    now: datetime,
    stale_lock_minutes: int,
) -> bool:
    name = path.name
    if name in {SYMBOL_REFRESH_QUEUE_TMP_FILENAME, SYMBOL_REFRESH_STATUS_TMP_FILENAME}:
        return True
    if name == SYMBOL_REFRESH_LOCK_FILENAME:
        lock_created_at = _read_lock_created_at(path)
        return lock_created_at is None or now - lock_created_at > timedelta(
            minutes=stale_lock_minutes
        )
    return (
        name.startswith("symbol_refresh_debug")
        or name.startswith("symbol_refresh_queue.prev")
        or name.startswith("symbol_refresh_queue.copy")
        or name.startswith("symbols_cache.tmp")
    )


def _read_lock_created_at(path: Path) -> datetime | None:
    try:
        return datetime.fromisoformat(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _cache_path(cache_dir: Path | str, filename: str) -> Path:
    return Path(cache_dir) / filename


def _replace_with_retry(source: Path, target: Path) -> None:
    for attempt in range(ATOMIC_REPLACE_RETRY_COUNT):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt >= ATOMIC_REPLACE_RETRY_COUNT - 1:
                raise
            sleep(ATOMIC_REPLACE_RETRY_DELAY_SECONDS)


def _normalize_symbol_set(symbols: set[str] | None) -> set[str]:
    if not symbols:
        return set()
    return {symbol.strip().upper() for symbol in symbols if symbol.strip()}


def _dedupe_symbols(symbols: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
