from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from time import perf_counter

from backend.symbols.cache import (
    MAX_TASK_RETRY,
    SYMBOL_CACHE_DIR,
    acquire_symbol_refresh_lock,
    load_symbol_refresh_queue,
    load_symbol_refresh_status,
    recover_interrupted_symbol_refresh_tasks,
    release_symbol_refresh_lock,
    save_symbol_refresh_queue,
    save_symbol_refresh_status,
)
from backend.symbols.contracts import (
    SymbolRecord,
    SymbolRefreshItemResult,
    SymbolRefreshResult,
    SymbolRefreshStatus,
    SymbolRefreshTask,
)
from backend.symbols.logging_utils import configure_symbol_refresh_logger
from backend.symbols.refresh_priority import MAX_SYMBOL_REFRESH_PER_RUN, sort_symbol_refresh_queue
from backend.symbols.repository import save_symbol_record

SymbolRefreshProvider = Callable[[SymbolRefreshTask], SymbolRecord | None]


def refresh_symbols_if_needed(
    *,
    provider: SymbolRefreshProvider,
    tasks: Sequence[SymbolRefreshTask] | None = None,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    now: datetime | None = None,
    force: bool = False,
    max_items: int = MAX_SYMBOL_REFRESH_PER_RUN,
    logger: logging.Logger | None = None,
) -> SymbolRefreshResult:
    """Run a bounded symbol refresh loop, committing one symbol at a time."""

    started_at = now or datetime.utcnow()
    logger = logger or configure_symbol_refresh_logger()
    if not acquire_symbol_refresh_lock(cache_dir=cache_dir, now=started_at):
        return _skipped_result(started_at, "lock_active")

    status = load_symbol_refresh_status(cache_dir=cache_dir)
    status = status.model_copy(update={"last_attempt_at": started_at, "is_refreshing": True})
    save_symbol_refresh_status(
        status,
        cache_dir=cache_dir,
    )
    logger.info("refresh started max_items=%s force=%s", max_items, force)

    items: list[SymbolRefreshItemResult] = []
    queue = list(tasks) if tasks is not None else load_symbol_refresh_queue(cache_dir=cache_dir)
    queue = sort_symbol_refresh_queue(
        recover_interrupted_symbol_refresh_tasks(queue, now=started_at)
    )

    try:
        for task in queue[:max_items]:
            if task.status not in {"pending", "retryable"} and not force:
                items.append(
                    SymbolRefreshItemResult(
                        symbol=task.symbol,
                        success=True,
                        skipped_reason=f"status_{task.status}",
                    )
                )
                continue
            in_progress = task.model_copy(
                update={"status": "in_progress", "started_at": started_at}
            )
            queue = _replace_task(queue, in_progress)
            save_symbol_refresh_queue(queue, cache_dir=cache_dir)
            result = refresh_single_symbol(
                in_progress,
                provider=provider,
                cache_dir=cache_dir,
                now=started_at,
                logger=logger,
            )
            items.append(result)
            queue = _replace_task(queue, _task_after_result(task, result, started_at))
            save_symbol_refresh_queue(queue, cache_dir=cache_dir)

        finished_at = datetime.utcnow()
        summary = _build_result(started_at, finished_at, items)
        save_symbol_refresh_status(
            _status_after_result(status, summary, queue),
            cache_dir=cache_dir,
        )
        logger.info(
            "refresh succeeded attempted=%s succeeded=%s failed=%s skipped=%s",
            summary.attempted_count,
            summary.succeeded_count,
            summary.failed_count,
            summary.skipped_count,
        )
        return summary
    except Exception as exc:
        finished_at = datetime.utcnow()
        summary = _build_result(started_at, finished_at, items)
        save_symbol_refresh_status(
            status.model_copy(
                update={
                    "last_error_at": finished_at,
                    "last_error_type": type(exc).__name__,
                    "consecutive_failures": status.consecutive_failures + 1,
                    "refresh_queue_size": len(queue),
                    "is_refreshing": False,
                }
            ),
            cache_dir=cache_dir,
        )
        logger.error("refresh failed error_type=%s attempted=%s", type(exc).__name__, len(items))
        raise
    finally:
        release_symbol_refresh_lock(cache_dir=cache_dir)


def refresh_single_symbol(
    task: SymbolRefreshTask,
    *,
    provider: SymbolRefreshProvider,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    now: datetime | None = None,
    logger: logging.Logger | None = None,
) -> SymbolRefreshItemResult:
    """Refresh one symbol and atomically save its normalized record."""

    logger = logger or configure_symbol_refresh_logger()
    started = perf_counter()
    started_at = now or datetime.utcnow()
    in_progress = task.model_copy(update={"status": "in_progress", "started_at": started_at})
    try:
        record = provider(in_progress)
        elapsed_ms = int((perf_counter() - started) * 1000)
        if record is None:
            logger.info("symbol skipped symbol=%s reason=provider_returned_none", task.symbol)
            return SymbolRefreshItemResult(
                symbol=task.symbol,
                success=True,
                skipped_reason="provider_returned_none",
                elapsed_ms=elapsed_ms,
            )
        saved = save_symbol_record(record, cache_dir=cache_dir)
        updated_fields = sorted(saved.normalized_fields.keys())
        logger.info(
            "symbol refresh succeeded symbol=%s provider=%s updated_field_count=%s elapsed_ms=%s",
            saved.symbol,
            saved.provider,
            len(updated_fields),
            elapsed_ms,
        )
        return SymbolRefreshItemResult(
            symbol=saved.symbol,
            success=True,
            provider=saved.provider,
            updated_fields=updated_fields,
            elapsed_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = int((perf_counter() - started) * 1000)
        logger.error(
            "symbol refresh failed symbol=%s error_type=%s elapsed_ms=%s",
            task.symbol,
            type(exc).__name__,
            elapsed_ms,
        )
        return SymbolRefreshItemResult(
            symbol=task.symbol,
            success=False,
            error_type=type(exc).__name__,
            elapsed_ms=elapsed_ms,
        )


def _task_after_result(
    task: SymbolRefreshTask,
    result: SymbolRefreshItemResult,
    finished_at: datetime,
) -> SymbolRefreshTask:
    if result.success and result.skipped_reason:
        return task.model_copy(update={"status": "skipped", "finished_at": finished_at})
    if result.success:
        return task.model_copy(
            update={
                "status": "succeeded",
                "finished_at": finished_at,
                "last_error_type": None,
                "last_refreshed_at": finished_at,
            }
        )
    retry_count = task.retry_count + 1
    status = "retryable" if retry_count <= MAX_TASK_RETRY else "failed"
    return task.model_copy(
        update={
            "status": status,
            "finished_at": finished_at,
            "retry_count": retry_count,
            "last_error_type": result.error_type,
        }
    )


def _replace_task(
    tasks: Sequence[SymbolRefreshTask],
    updated_task: SymbolRefreshTask,
) -> list[SymbolRefreshTask]:
    return [updated_task if task.symbol == updated_task.symbol else task for task in tasks]


def _status_after_result(
    previous: SymbolRefreshStatus,
    summary: SymbolRefreshResult,
    queue: Sequence[SymbolRefreshTask],
) -> SymbolRefreshStatus:
    succeeded_symbols = [
        item.symbol for item in summary.items if item.success and item.updated_fields
    ]
    return previous.model_copy(
        update={
            "last_success_at": (
                summary.finished_at if summary.failed_count == 0 else previous.last_success_at
            ),
            "last_error_at": (
                summary.finished_at if summary.failed_count else previous.last_error_at
            ),
            "last_error_type": "item_failed" if summary.failed_count else None,
            "consecutive_failures": (
                previous.consecutive_failures + 1 if summary.failed_count else 0
            ),
            "last_refreshed_symbols": succeeded_symbols,
            "refresh_queue_size": len(
                [task for task in queue if task.status in {"pending", "retryable", "in_progress"}]
            ),
            "is_refreshing": False,
        }
    )


def _build_result(
    started_at: datetime,
    finished_at: datetime,
    items: Sequence[SymbolRefreshItemResult],
) -> SymbolRefreshResult:
    failed_count = len([item for item in items if not item.success])
    skipped_count = len([item for item in items if item.skipped_reason])
    succeeded_count = len(items) - failed_count - skipped_count
    return SymbolRefreshResult(
        started_at=started_at,
        finished_at=finished_at,
        attempted_count=len(items),
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        items=list(items),
    )


def _skipped_result(started_at: datetime, reason: str) -> SymbolRefreshResult:
    finished_at = datetime.utcnow()
    return SymbolRefreshResult(
        started_at=started_at,
        finished_at=finished_at,
        attempted_count=1,
        succeeded_count=0,
        failed_count=0,
        skipped_count=1,
        items=[
            SymbolRefreshItemResult(
                symbol="__refresh__",
                success=True,
                skipped_reason=reason,
            )
        ],
    )
