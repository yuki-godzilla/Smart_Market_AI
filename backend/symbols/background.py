from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Final

from backend.symbols.cache import SYMBOL_CACHE_DIR
from backend.symbols.contracts import SymbolStartupRefreshSummary
from backend.symbols.logging_utils import configure_symbol_refresh_logger
from backend.symbols.refresh_priority import MAX_SYMBOL_REFRESH_PER_RUN
from backend.symbols.startup import SYMBOL_UNIVERSE_CSV, run_symbol_database_startup_refresh


@dataclass(frozen=True)
class SymbolBackgroundRefreshStep:
    delay_minutes: int
    max_items: int


BACKGROUND_REFRESH_STEPS: Final[tuple[SymbolBackgroundRefreshStep, ...]] = (
    SymbolBackgroundRefreshStep(delay_minutes=3, max_items=40),
    SymbolBackgroundRefreshStep(delay_minutes=8, max_items=40),
)
STARTUP_BACKGROUND_REFRESH_MAX_ITEMS: Final[int] = MAX_SYMBOL_REFRESH_PER_RUN
BACKGROUND_REFRESH_INTERVAL_MINUTES: Final[int] = 5
BACKGROUND_REFRESH_MAX_ITEMS: Final[int] = 30
MAX_SYMBOL_REFRESH_PER_SESSION: Final[int] = 500

_WORKER_LOCK = threading.Lock()
_WORKER_THREAD: threading.Thread | None = None


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
    if max_items <= 0:
        return run_symbol_database_startup_refresh(
            cache_dir=cache_dir,
            symbol_universe_csv=symbol_universe_csv,
            now=now,
            max_items=0,
            min_interval_hours=0,
            force=True,
        )
    summary = run_symbol_database_startup_refresh(
        cache_dir=cache_dir,
        symbol_universe_csv=symbol_universe_csv,
        now=now,
        max_items=max_items,
        min_interval_hours=0,
        force=True,
    )
    logger.info(
        "background refresh batch attempted=%s succeeded=%s failed=%s records=%s",
        summary.attempted_count,
        summary.succeeded_count,
        summary.failed_count,
        summary.record_count,
    )
    return summary


def _wait_minutes(
    minutes: int,
    *,
    delay_scale: float,
    wait: Callable[[float], None],
) -> None:
    seconds = max(0.0, minutes * 60 * delay_scale)
    if seconds:
        wait(seconds)
