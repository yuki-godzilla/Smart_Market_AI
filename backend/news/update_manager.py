from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from logging import Logger
from pathlib import Path
from time import perf_counter

from backend.news.cache import (
    MAX_HEATMAP_CELLS,
    NEWS_CACHE_DIR,
    cleanup_news_cache_files,
    get_news_cache_file_size,
    load_cached_news_dashboard_snapshot,
    load_news_update_status,
    news_snapshot_item_count,
    save_cached_news_dashboard_snapshot,
    save_news_update_status,
)
from backend.news.contracts import NewsDashboardSnapshot, NewsUpdateStatus
from backend.news.logging_utils import configure_news_update_logger

MIN_REFRESH_INTERVAL_MINUTES = 30
NEWS_CACHE_FRESH_HOURS = 3
NEWS_CACHE_EXPIRED_HOURS = 24
MAX_REFRESH_RETRY = 1


class NewsRefreshResult:
    """Small result object for refresh orchestration without UI coupling."""

    def __init__(
        self,
        *,
        snapshot: NewsDashboardSnapshot | None,
        status: NewsUpdateStatus,
        refreshed: bool,
        skipped: bool,
        used_fallback_cache: bool,
        message: str,
    ) -> None:
        self.snapshot = snapshot
        self.status = status
        self.refreshed = refreshed
        self.skipped = skipped
        self.used_fallback_cache = used_fallback_cache
        self.message = message


def refresh_news_dashboard_cache(
    build_snapshot: Callable[[], NewsDashboardSnapshot],
    *,
    cache_dir: Path | str = NEWS_CACHE_DIR,
    logger: Logger | None = None,
    now: datetime | None = None,
    force: bool = False,
    min_refresh_interval_minutes: int = MIN_REFRESH_INTERVAL_MINUTES,
    fresh_hours: int = NEWS_CACHE_FRESH_HOURS,
    max_refresh_retry: int = MAX_REFRESH_RETRY,
) -> NewsRefreshResult:
    """Refresh the news snapshot cache with TTL, bounded retry, and fallback."""

    current_time = now or datetime.now(UTC)
    cache_root = Path(cache_dir)
    cleanup_news_cache_files(cache_dir=cache_root)
    logger = logger or configure_news_update_logger()
    status = load_news_update_status(cache_dir=cache_root)
    cached_snapshot = load_cached_news_dashboard_snapshot(cache_dir=cache_root)

    if not force and _should_skip_refresh(
        status=status,
        snapshot=cached_snapshot,
        now=current_time,
        min_refresh_interval_minutes=min_refresh_interval_minutes,
        fresh_hours=fresh_hours,
    ):
        status = status.model_copy(
            update={
                "is_refreshing": False,
                "cache_file_size_bytes": get_news_cache_file_size(cache_dir=cache_root),
            }
        )
        status = save_news_update_status(status, cache_dir=cache_root)
        logger.info(
            "refresh skipped because cache is fresh generated_at=%s " "cache_file_size_bytes=%s",
            cached_snapshot.generated_at.isoformat() if cached_snapshot else None,
            status.cache_file_size_bytes,
        )
        return NewsRefreshResult(
            snapshot=cached_snapshot,
            status=status,
            refreshed=False,
            skipped=True,
            used_fallback_cache=False,
            message="cache is fresh",
        )

    status = save_news_update_status(
        status.model_copy(update={"last_attempt_at": current_time, "is_refreshing": True}),
        cache_dir=cache_root,
    )
    logger.info("refresh started last_attempt_at=%s", current_time.isoformat())

    attempts = max(1, 1 + max_refresh_retry)
    last_error: Exception | None = None
    started = perf_counter()
    for _ in range(attempts):
        try:
            snapshot = build_snapshot()
            saved_snapshot = save_cached_news_dashboard_snapshot(
                snapshot,
                cache_dir=cache_root,
            )
            status = save_news_update_status(
                status.model_copy(
                    update={
                        "last_success_at": current_time,
                        "last_error_at": None,
                        "last_error_type": None,
                        "consecutive_failures": 0,
                        "is_refreshing": False,
                    }
                ),
                cache_dir=cache_root,
            )
            elapsed_ms = int((perf_counter() - started) * 1000)
            logger.info(
                "refresh succeeded generated_at=%s fetched_at=%s news_count=%s "
                "heatmap_cell_count=%s category_lane_count=%s elapsed_ms=%s",
                saved_snapshot.generated_at.isoformat(),
                saved_snapshot.fetched_at.isoformat() if saved_snapshot.fetched_at else None,
                news_snapshot_item_count(saved_snapshot),
                min(len(saved_snapshot.heatmap_cells), MAX_HEATMAP_CELLS),
                len(saved_snapshot.category_lanes),
                elapsed_ms,
            )
            return NewsRefreshResult(
                snapshot=saved_snapshot,
                status=status,
                refreshed=True,
                skipped=False,
                used_fallback_cache=False,
                message="refresh succeeded",
            )
        except Exception as exc:
            last_error = exc

    assert last_error is not None
    error_type = type(last_error).__name__
    status = save_news_update_status(
        status.model_copy(
            update={
                "last_error_at": current_time,
                "last_error_type": error_type,
                "consecutive_failures": status.consecutive_failures + 1,
                "is_refreshing": False,
            }
        ),
        cache_dir=cache_root,
    )
    fallback_snapshot = load_cached_news_dashboard_snapshot(cache_dir=cache_root)
    elapsed_ms = int((perf_counter() - started) * 1000)
    logger.error(
        "refresh failed error_type=%s consecutive_failures=%s elapsed_ms=%s "
        "used_fallback_cache=%s",
        error_type,
        status.consecutive_failures,
        elapsed_ms,
        fallback_snapshot is not None,
    )
    return NewsRefreshResult(
        snapshot=fallback_snapshot,
        status=status,
        refreshed=False,
        skipped=False,
        used_fallback_cache=fallback_snapshot is not None,
        message=(
            "refresh failed; fallback cache used"
            if fallback_snapshot is not None
            else "refresh failed"
        ),
    )


def _should_skip_refresh(
    *,
    status: NewsUpdateStatus,
    snapshot: NewsDashboardSnapshot | None,
    now: datetime,
    min_refresh_interval_minutes: int,
    fresh_hours: int,
) -> bool:
    if snapshot is None:
        return False
    if status.last_attempt_at is not None and now - status.last_attempt_at < timedelta(
        minutes=min_refresh_interval_minutes
    ):
        return True
    return now - snapshot.generated_at < timedelta(hours=fresh_hours)
