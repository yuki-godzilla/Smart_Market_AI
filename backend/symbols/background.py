from __future__ import annotations

import csv
import logging
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Final

from backend.server_ops.maintenance import maintenance_operation
from backend.symbols.cache import SYMBOL_CACHE_DIR
from backend.symbols.cache_sync import (
    prune_symbol_metrics_against_universe,
    sync_symbol_cache_to_official_metrics,
)
from backend.symbols.contracts import SymbolStartupRefreshSummary
from backend.symbols.logging_utils import configure_symbol_refresh_logger
from backend.symbols.metrics_repository import SYMBOL_METRICS_DIR
from backend.symbols.refresh_priority import MAX_SYMBOL_REFRESH_PER_RUN
from backend.symbols.startup import SYMBOL_UNIVERSE_CSV, run_symbol_database_startup_refresh


@dataclass(frozen=True)
class SymbolBackgroundRefreshStep:
    delay_minutes: int
    max_items: int


BACKGROUND_REFRESH_STEPS: Final[tuple[SymbolBackgroundRefreshStep, ...]] = (
    SymbolBackgroundRefreshStep(delay_minutes=3, max_items=75),
    SymbolBackgroundRefreshStep(delay_minutes=8, max_items=75),
)
STARTUP_BACKGROUND_REFRESH_MAX_ITEMS: Final[int] = MAX_SYMBOL_REFRESH_PER_RUN
BACKGROUND_REFRESH_INTERVAL_MINUTES: Final[int] = 5
BACKGROUND_REFRESH_MAX_ITEMS: Final[int] = 50
MAX_SYMBOL_REFRESH_PER_SESSION: Final[int] = 1000
TARGET_BACKGROUND_REFRESH_MAX_ITEMS: Final[int] = 50
MAX_SYMBOL_REFRESH_TARGET_HINTS: Final[int] = 500

_WORKER_LOCK = threading.Lock()
_WORKER_THREAD: threading.Thread | None = None
_TARGET_LOCK = threading.Lock()
_TARGET_WORKER_THREAD: threading.Thread | None = None
_CURRENTLY_VISIBLE_SYMBOLS: set[str] = set()
_RANKING_CANDIDATE_SYMBOLS: set[str] = set()


def start_symbol_background_refresh_worker(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    symbol_universe_csv: Path | str = SYMBOL_UNIVERSE_CSV,
    delay_scale: float = 1.0,
    logger: logging.Logger | None = None,
) -> threading.Thread:
    """Start one process-wide daemon worker for bounded symbol DB maintenance."""

    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            return _WORKER_THREAD
        worker = threading.Thread(
            target=run_symbol_background_refresh_cycle,
            kwargs={
                "cache_dir": cache_dir,
                "symbol_universe_csv": symbol_universe_csv,
                "delay_scale": delay_scale,
                "logger": logger,
            },
            name="smai-symbol-background-refresh",
            daemon=True,
        )
        worker.start()
        _WORKER_THREAD = worker
        return worker


def request_symbol_background_refresh(
    symbols: Iterable[str],
    *,
    source: str,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    symbol_universe_csv: Path | str = SYMBOL_UNIVERSE_CSV,
    max_items: int = TARGET_BACKGROUND_REFRESH_MAX_ITEMS,
    start_worker: bool = True,
    logger: logging.Logger | None = None,
) -> list[str]:
    """Register UI-context symbols so the background worker refreshes them first."""

    normalized_symbols = _normalize_symbol_list(symbols)
    if not normalized_symbols:
        return []

    with _TARGET_LOCK:
        if source == "ranking":
            _merge_target_symbols(_RANKING_CANDIDATE_SYMBOLS, normalized_symbols)
        else:
            _merge_target_symbols(_CURRENTLY_VISIBLE_SYMBOLS, normalized_symbols)

    if start_worker:
        _start_symbol_target_refresh_worker(
            cache_dir=cache_dir,
            symbol_universe_csv=symbol_universe_csv,
            max_items=max_items,
            logger=logger,
        )
    return normalized_symbols


def clear_symbol_background_refresh_targets() -> None:
    """Clear transient UI-context refresh hints."""

    with _TARGET_LOCK:
        _CURRENTLY_VISIBLE_SYMBOLS.clear()
        _RANKING_CANDIDATE_SYMBOLS.clear()


def run_symbol_background_target_refresh_once(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    symbol_universe_csv: Path | str = SYMBOL_UNIVERSE_CSV,
    max_items: int = TARGET_BACKGROUND_REFRESH_MAX_ITEMS,
    now_provider: Callable[[], datetime] = datetime.utcnow,
    logger: logging.Logger | None = None,
) -> SymbolStartupRefreshSummary:
    """Run one non-blocking priority pass for symbols currently used by the UI."""

    logger = logger or configure_symbol_refresh_logger()
    currently_visible_symbols, ranking_candidates = _target_symbol_snapshot()
    summary = run_symbol_database_startup_refresh(
        cache_dir=cache_dir,
        symbol_universe_csv=symbol_universe_csv,
        now=now_provider(),
        max_items=max(0, max_items),
        min_interval_hours=0,
        currently_visible_symbols=currently_visible_symbols,
        ranking_candidates=ranking_candidates,
    )
    sync_result = sync_symbol_cache_to_official_metrics(
        cache_dir=cache_dir,
        now=now_provider(),
        max_items=max(0, max_items),
    )
    prune_deleted_count = _prune_metrics_after_background_sync(
        symbol_universe_csv=symbol_universe_csv,
        metrics_dir=_background_metrics_dir(cache_dir),
    )
    logger.info(
        "target refresh batch attempted=%s succeeded=%s failed=%s records=%s "
        "promoted=%s deleted=%s pruned=%s",
        summary.attempted_count,
        summary.succeeded_count,
        summary.failed_count,
        summary.record_count,
        sync_result.promoted_count,
        sync_result.deleted_count,
        prune_deleted_count,
    )
    return summary


def run_symbol_background_refresh_cycle(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    symbol_universe_csv: Path | str = SYMBOL_UNIVERSE_CSV,
    startup_max_items: int = STARTUP_BACKGROUND_REFRESH_MAX_ITEMS,
    steps: Sequence[SymbolBackgroundRefreshStep] = BACKGROUND_REFRESH_STEPS,
    recurring_interval_minutes: int = BACKGROUND_REFRESH_INTERVAL_MINUTES,
    recurring_max_items: int = BACKGROUND_REFRESH_MAX_ITEMS,
    max_items_per_session: int = MAX_SYMBOL_REFRESH_PER_SESSION,
    delay_scale: float = 1.0,
    wait: Callable[[float], None] = sleep,
    now_provider: Callable[[], datetime] = datetime.utcnow,
    logger: logging.Logger | None = None,
) -> list[SymbolStartupRefreshSummary]:
    """Run the short-session background plan without depending on UI actions."""

    with maintenance_operation("symbol_background_refresh"):
        return _run_symbol_background_refresh_cycle(
            cache_dir=cache_dir,
            symbol_universe_csv=symbol_universe_csv,
            startup_max_items=startup_max_items,
            steps=steps,
            recurring_interval_minutes=recurring_interval_minutes,
            recurring_max_items=recurring_max_items,
            max_items_per_session=max_items_per_session,
            delay_scale=delay_scale,
            wait=wait,
            now_provider=now_provider,
            logger=logger,
        )


def _run_symbol_background_refresh_cycle(
    *,
    cache_dir: Path | str,
    symbol_universe_csv: Path | str,
    startup_max_items: int,
    steps: Sequence[SymbolBackgroundRefreshStep],
    recurring_interval_minutes: int,
    recurring_max_items: int,
    max_items_per_session: int,
    delay_scale: float,
    wait: Callable[[float], None],
    now_provider: Callable[[], datetime],
    logger: logging.Logger | None,
) -> list[SymbolStartupRefreshSummary]:
    logger = logger or configure_symbol_refresh_logger()
    summaries: list[SymbolStartupRefreshSummary] = []
    refreshed_count = 0
    previous_delay_minutes = 0
    startup_limit = min(startup_max_items, max_items_per_session)
    if startup_limit > 0:
        summary = _run_background_batch(
            cache_dir=cache_dir,
            symbol_universe_csv=symbol_universe_csv,
            now=now_provider(),
            max_items=startup_limit,
            logger=logger,
        )
        summaries.append(summary)
        refreshed_count += summary.succeeded_count
        if summary.attempted_count < startup_limit:
            return summaries

    for step in steps:
        if refreshed_count >= max_items_per_session:
            return summaries
        step_limit = min(step.max_items, max_items_per_session - refreshed_count)
        delay_minutes = max(0, step.delay_minutes - previous_delay_minutes)
        _wait_minutes(delay_minutes, delay_scale=delay_scale, wait=wait)
        summary = _run_background_batch(
            cache_dir=cache_dir,
            symbol_universe_csv=symbol_universe_csv,
            now=now_provider(),
            max_items=step_limit,
            logger=logger,
        )
        summaries.append(summary)
        refreshed_count += summary.succeeded_count
        previous_delay_minutes = step.delay_minutes
        if summary.attempted_count < step_limit:
            return summaries

    while refreshed_count < max_items_per_session:
        batch_limit = min(recurring_max_items, max_items_per_session - refreshed_count)
        _wait_minutes(recurring_interval_minutes, delay_scale=delay_scale, wait=wait)
        summary = _run_background_batch(
            cache_dir=cache_dir,
            symbol_universe_csv=symbol_universe_csv,
            now=now_provider(),
            max_items=batch_limit,
            logger=logger,
        )
        summaries.append(summary)
        refreshed_count += summary.succeeded_count
        if summary.attempted_count < batch_limit:
            break

    return summaries


def _run_background_batch(
    *,
    cache_dir: Path | str,
    symbol_universe_csv: Path | str,
    now: datetime,
    max_items: int,
    logger: logging.Logger,
) -> SymbolStartupRefreshSummary:
    currently_visible_symbols, ranking_candidates = _target_symbol_snapshot()
    if max_items <= 0:
        return run_symbol_database_startup_refresh(
            cache_dir=cache_dir,
            symbol_universe_csv=symbol_universe_csv,
            now=now,
            max_items=0,
            min_interval_hours=0,
            force=True,
            currently_visible_symbols=currently_visible_symbols,
            ranking_candidates=ranking_candidates,
        )
    summary = run_symbol_database_startup_refresh(
        cache_dir=cache_dir,
        symbol_universe_csv=symbol_universe_csv,
        now=now,
        max_items=max_items,
        min_interval_hours=0,
        force=True,
        currently_visible_symbols=currently_visible_symbols,
        ranking_candidates=ranking_candidates,
    )
    sync_result = sync_symbol_cache_to_official_metrics(
        cache_dir=cache_dir,
        now=datetime.utcnow(),
        max_items=max_items,
    )
    prune_deleted_count = _prune_metrics_after_background_sync(
        symbol_universe_csv=symbol_universe_csv,
        metrics_dir=_background_metrics_dir(cache_dir),
    )
    logger.info(
        "background refresh batch attempted=%s succeeded=%s failed=%s records=%s "
        "promoted=%s deleted=%s pruned=%s",
        summary.attempted_count,
        summary.succeeded_count,
        summary.failed_count,
        summary.record_count,
        sync_result.promoted_count,
        sync_result.deleted_count,
        prune_deleted_count,
    )
    return summary


def _start_symbol_target_refresh_worker(
    *,
    cache_dir: Path | str,
    symbol_universe_csv: Path | str,
    max_items: int,
    logger: logging.Logger | None,
) -> threading.Thread:
    global _TARGET_WORKER_THREAD
    with _TARGET_LOCK:
        if _TARGET_WORKER_THREAD is not None and _TARGET_WORKER_THREAD.is_alive():
            return _TARGET_WORKER_THREAD
        worker = threading.Thread(
            target=run_symbol_background_target_refresh_once,
            kwargs={
                "cache_dir": cache_dir,
                "symbol_universe_csv": symbol_universe_csv,
                "max_items": max_items,
                "logger": logger,
            },
            name="smai-symbol-target-refresh",
            daemon=True,
        )
        worker.start()
        _TARGET_WORKER_THREAD = worker
        return worker


def _target_symbol_snapshot() -> tuple[set[str], set[str]]:
    with _TARGET_LOCK:
        return set(_CURRENTLY_VISIBLE_SYMBOLS), set(_RANKING_CANDIDATE_SYMBOLS)


def _merge_target_symbols(target: set[str], symbols: Sequence[str]) -> None:
    target.update(symbols)
    if len(target) <= MAX_SYMBOL_REFRESH_TARGET_HINTS:
        return
    kept_symbols = sorted(target)[:MAX_SYMBOL_REFRESH_TARGET_HINTS]
    target.clear()
    target.update(kept_symbols)


def _prune_metrics_after_background_sync(
    *,
    symbol_universe_csv: Path | str,
    metrics_dir: Path | str,
) -> int:
    rows = _load_symbol_universe_rows_for_prune(Path(symbol_universe_csv))
    if not rows:
        return 0
    result = prune_symbol_metrics_against_universe(rows, metrics_dir=metrics_dir)
    return result.deleted_count


def _load_symbol_universe_rows_for_prune(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [
            {str(key): (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
            if (row.get("symbol") or "").strip()
        ]


def _background_metrics_dir(cache_dir: Path | str) -> Path | str:
    if Path(cache_dir) == Path(SYMBOL_CACHE_DIR):
        return SYMBOL_METRICS_DIR
    return cache_dir


def _normalize_symbol_list(symbols: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        normalized.append(normalized_symbol)
        if len(normalized) >= MAX_SYMBOL_REFRESH_TARGET_HINTS:
            break
    return normalized


def _wait_minutes(
    minutes: int,
    *,
    delay_scale: float,
    wait: Callable[[float], None],
) -> None:
    seconds = max(0.0, minutes * 60 * delay_scale)
    if seconds:
        wait(seconds)
