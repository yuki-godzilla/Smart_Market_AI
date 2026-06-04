from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import sleep

from backend.news.cache import NEWS_CACHE_DIR
from backend.news.contracts import NewsDashboardSnapshot
from backend.news.logging_utils import configure_news_update_logger
from backend.news.sources import build_standard_news_dashboard_snapshot
from backend.news.update_manager import NewsRefreshResult, refresh_news_dashboard_cache

NEWS_BACKGROUND_STARTUP_DELAY_SECONDS = 2.0

_WORKER_LOCK = threading.Lock()
_WORKER_THREAD: threading.Thread | None = None


def start_news_background_refresh_worker(
    *,
    cache_dir: Path | str = NEWS_CACHE_DIR,
    startup_delay_seconds: float = NEWS_BACKGROUND_STARTUP_DELAY_SECONDS,
    delay_scale: float = 1.0,
    logger: logging.Logger | None = None,
) -> threading.Thread:
    """Start one process-wide daemon worker for the Investment Radar news cache."""

    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            return _WORKER_THREAD
        worker = threading.Thread(
            target=run_news_background_refresh_once,
            kwargs={
                "cache_dir": cache_dir,
                "startup_delay_seconds": startup_delay_seconds,
                "delay_scale": delay_scale,
                "logger": logger,
            },
            name="smai-news-background-refresh",
            daemon=True,
        )
        worker.start()
        _WORKER_THREAD = worker
        return worker


def run_news_background_refresh_once(
    *,
    cache_dir: Path | str = NEWS_CACHE_DIR,
    startup_delay_seconds: float = NEWS_BACKGROUND_STARTUP_DELAY_SECONDS,
    delay_scale: float = 1.0,
    build_snapshot: Callable[[], NewsDashboardSnapshot] | None = None,
    wait: Callable[[float], None] = sleep,
    logger: logging.Logger | None = None,
) -> NewsRefreshResult:
    """Refresh the news cache once without depending on the News page being open."""

    logger = logger or configure_news_update_logger()
    delay_seconds = max(0.0, startup_delay_seconds) * max(0.0, delay_scale)
    if delay_seconds:
        wait(delay_seconds)
    builder = build_snapshot or (
        lambda: build_standard_news_dashboard_snapshot(
            allow_network=True,
            now=datetime.now(UTC),
            fallback_to_demo=False,
        )
    )
    result = refresh_news_dashboard_cache(
        builder,
        cache_dir=cache_dir,
        logger=logger,
        force=False,
    )
    logger.info(
        "background refresh finished refreshed=%s skipped=%s fallback=%s message=%s",
        result.refreshed,
        result.skipped,
        result.used_fallback_cache,
        result.message,
    )
    return result
