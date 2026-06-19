from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.assistant.loading_headlines import load_assistant_loading_headlines
from backend.news import build_demo_news_dashboard_snapshot, save_cached_news_dashboard_snapshot


def test_loading_headlines_use_cache_and_bound_items(tmp_path):
    now = datetime(2026, 6, 19, 15, 30, tzinfo=UTC)
    save_cached_news_dashboard_snapshot(
        build_demo_news_dashboard_snapshot(now=now),
        cache_dir=tmp_path,
    )

    result = load_assistant_loading_headlines(cache_dir=tmp_path, max_items=3, now=now)

    assert result.source == "cache"
    assert len(result.items) == 3
    assert result.stale is False


def test_loading_headlines_uses_news_cache_default_when_directory_is_omitted(monkeypatch):
    calls = 0

    def fake_load_default():
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(
        "backend.assistant.loading_headlines.load_cached_news_dashboard_snapshot",
        fake_load_default,
    )

    result = load_assistant_loading_headlines()

    assert calls == 1
    assert result.source == "sample"


def test_loading_headlines_use_sample_for_missing_or_malformed_cache(tmp_path):
    now = datetime(2026, 6, 19, 15, 30, tzinfo=UTC)
    (tmp_path / "news_dashboard_snapshot.json").write_text("{bad", encoding="utf-8")

    result = load_assistant_loading_headlines(cache_dir=tmp_path, now=now)

    assert result.source == "sample"
    assert result.items


def test_loading_headlines_mark_old_cache_stale(tmp_path):
    now = datetime(2026, 6, 19, 15, 30, tzinfo=UTC)
    save_cached_news_dashboard_snapshot(
        build_demo_news_dashboard_snapshot(now=now - timedelta(days=2)),
        cache_dir=tmp_path,
    )

    result = load_assistant_loading_headlines(
        cache_dir=tmp_path,
        max_age_hours=24,
        now=now,
    )

    assert result.stale is True
