from datetime import UTC, datetime, timedelta
from logging.handlers import RotatingFileHandler

from backend.news import (
    MAX_REFRESH_RETRY,
    NEWS_UPDATE_LOG_BACKUP_COUNT,
    NEWS_UPDATE_LOG_FILENAME,
    NEWS_UPDATE_LOG_MAX_BYTES,
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    configure_news_update_logger,
    load_news_update_status,
    refresh_news_dashboard_cache,
    save_cached_news_dashboard_snapshot,
)


def _snapshot(title: str = "ニュース") -> NewsDashboardSnapshot:
    return NewsDashboardSnapshot(
        generated_at=datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
        fetched_at=datetime(2026, 6, 3, 9, 55, tzinfo=UTC),
        freshness_status="latest",
        stream_headlines=[
            NewsHeadlineCard(
                title=title,
                summary="短い要約",
                source_type="news",
                category="国内株",
                material_type="earnings",
                url="https://example.com/news",
            )
        ],
    )


def test_configure_news_update_logger_uses_rotating_file_handler(tmp_path):
    logger = configure_news_update_logger(
        log_dir=tmp_path,
        logger_name="tests.news.update.rotating",
    )

    handlers = [handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)]

    assert len(handlers) == 1
    assert handlers[0].baseFilename.endswith(NEWS_UPDATE_LOG_FILENAME)
    assert handlers[0].maxBytes == NEWS_UPDATE_LOG_MAX_BYTES
    assert handlers[0].backupCount == NEWS_UPDATE_LOG_BACKUP_COUNT


def test_refresh_news_dashboard_cache_skips_when_cache_is_fresh(tmp_path):
    cached = save_cached_news_dashboard_snapshot(_snapshot("cached"), cache_dir=tmp_path)
    logger = configure_news_update_logger(
        log_dir=tmp_path / "logs",
        logger_name="tests.news.update.skip",
    )
    calls = 0

    def build_snapshot():
        nonlocal calls
        calls += 1
        return _snapshot("new")

    result = refresh_news_dashboard_cache(
        build_snapshot,
        cache_dir=tmp_path,
        logger=logger,
        now=cached.generated_at + timedelta(minutes=10),
    )

    assert calls == 0
    assert result.skipped is True
    assert result.refreshed is False
    assert result.snapshot == cached
    assert load_news_update_status(cache_dir=tmp_path).cache_file_size_bytes is not None


def test_refresh_news_dashboard_cache_force_refreshes_and_updates_status(tmp_path):
    logger = configure_news_update_logger(
        log_dir=tmp_path / "logs",
        logger_name="tests.news.update.success",
    )

    result = refresh_news_dashboard_cache(
        lambda: _snapshot("fresh"),
        cache_dir=tmp_path,
        logger=logger,
        now=datetime(2026, 6, 3, 10, 30, tzinfo=UTC),
        force=True,
    )

    assert result.refreshed is True
    assert result.skipped is False
    assert result.status.consecutive_failures == 0
    assert result.status.last_success_at == datetime(2026, 6, 3, 10, 30, tzinfo=UTC)
    log_text = (tmp_path / "logs" / NEWS_UPDATE_LOG_FILENAME).read_text(encoding="utf-8")
    assert "refresh succeeded" in log_text
    assert "短い要約" not in log_text


def test_refresh_news_dashboard_cache_failure_uses_existing_cache_without_raw_log(tmp_path):
    cached = save_cached_news_dashboard_snapshot(_snapshot("cached"), cache_dir=tmp_path)
    logger = configure_news_update_logger(
        log_dir=tmp_path / "logs",
        logger_name="tests.news.update.failure",
    )
    calls = 0
    huge_raw_payload = "RAW_HTML_BODY_" * 1000

    def fail_snapshot():
        nonlocal calls
        calls += 1
        raise RuntimeError(huge_raw_payload)

    result = refresh_news_dashboard_cache(
        fail_snapshot,
        cache_dir=tmp_path,
        logger=logger,
        now=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
        force=True,
    )

    assert calls == 1 + MAX_REFRESH_RETRY
    assert result.refreshed is False
    assert result.used_fallback_cache is True
    assert result.snapshot == cached
    assert result.status.consecutive_failures == 1
    assert result.status.last_error_type == "RuntimeError"
    log_text = (tmp_path / "logs" / NEWS_UPDATE_LOG_FILENAME).read_text(encoding="utf-8")
    assert "refresh failed" in log_text
    assert "RuntimeError" in log_text
    assert "RAW_HTML_BODY" not in log_text
