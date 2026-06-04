from datetime import UTC, datetime, timedelta

from backend.news.background import run_news_background_refresh_once
from backend.news.cache import save_cached_news_dashboard_snapshot, save_news_update_status
from backend.news.contracts import NewsUpdateStatus
from backend.news.dashboard import build_demo_news_dashboard_snapshot


def test_news_background_refresh_updates_stale_cache(tmp_path):
    stale_snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 8, 0, tzinfo=UTC)
    ).model_copy(update={"generated_at": datetime(2026, 6, 4, 6, 0, tzinfo=UTC)})
    fresh_snapshot = build_demo_news_dashboard_snapshot(now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC))
    save_cached_news_dashboard_snapshot(stale_snapshot, cache_dir=tmp_path)

    result = run_news_background_refresh_once(
        cache_dir=tmp_path,
        startup_delay_seconds=0,
        build_snapshot=lambda: fresh_snapshot,
    )

    assert result.refreshed is True
    assert result.snapshot is not None
    assert result.snapshot.generated_at == fresh_snapshot.generated_at


def test_news_background_refresh_skips_fresh_cache(tmp_path):
    now = datetime.now(UTC)
    cached_snapshot = build_demo_news_dashboard_snapshot(now=now)
    save_cached_news_dashboard_snapshot(cached_snapshot, cache_dir=tmp_path)
    save_news_update_status(
        NewsUpdateStatus(last_attempt_at=cached_snapshot.generated_at - timedelta(minutes=5)),
        cache_dir=tmp_path,
    )
    called = False

    def build_snapshot():
        nonlocal called
        called = True
        return build_demo_news_dashboard_snapshot(now=now + timedelta(hours=1))

    result = run_news_background_refresh_once(
        cache_dir=tmp_path,
        startup_delay_seconds=0,
        build_snapshot=build_snapshot,
    )

    assert result.skipped is True
    assert called is False
