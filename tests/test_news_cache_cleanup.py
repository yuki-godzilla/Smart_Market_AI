from datetime import UTC, datetime

import pytest

import backend.news.cache as news_cache
from backend.news import (
    NEWS_PREVIOUS_SNAPSHOT_FILENAME,
    NEWS_SNAPSHOT_FILENAME,
    NEWS_TMP_SNAPSHOT_FILENAME,
    NEWS_UPDATE_STATUS_FILENAME,
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    cleanup_news_cache_files,
    get_news_cache_file_size,
    load_cached_news_dashboard_snapshot,
    load_news_update_status,
    save_cached_news_dashboard_snapshot,
    save_news_update_status,
)
from backend.news.contracts import NewsUpdateStatus


def _snapshot(title: str = "ニュース") -> NewsDashboardSnapshot:
    return NewsDashboardSnapshot(
        generated_at=datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
        fetched_at=datetime(2026, 6, 3, 9, 55, tzinfo=UTC),
        freshness_status="latest",
        stream_headlines=[
            NewsHeadlineCard(
                title=title,
                source_type="news",
                category="国内株",
                material_type="earnings",
                url="https://example.com/news",
            )
        ],
    )


def test_save_cached_news_dashboard_snapshot_uses_latest_and_one_previous_backup(
    tmp_path,
):
    first = save_cached_news_dashboard_snapshot(_snapshot("first"), cache_dir=tmp_path)
    second = save_cached_news_dashboard_snapshot(
        _snapshot("second"),
        cache_dir=tmp_path,
    )

    cache_file = tmp_path / NEWS_SNAPSHOT_FILENAME
    previous_file = tmp_path / NEWS_PREVIOUS_SNAPSHOT_FILENAME

    assert cache_file.exists()
    assert previous_file.exists()
    assert not (tmp_path / NEWS_TMP_SNAPSHOT_FILENAME).exists()
    assert load_cached_news_dashboard_snapshot(cache_dir=tmp_path) == second
    previous = NewsDashboardSnapshot.model_validate_json(previous_file.read_text(encoding="utf-8"))
    assert previous == first
    assert list(tmp_path.glob("news_dashboard_snapshot.prev.*.json")) == []


def test_cleanup_news_cache_files_removes_only_news_dashboard_temp_and_extra_files(
    tmp_path,
):
    keep_cache = tmp_path / NEWS_SNAPSHOT_FILENAME
    keep_prev = tmp_path / NEWS_PREVIOUS_SNAPSHOT_FILENAME
    keep_status = tmp_path / NEWS_UPDATE_STATUS_FILENAME
    keep_other = tmp_path / "other_feature.tmp.json"
    delete_paths = [
        tmp_path / NEWS_TMP_SNAPSHOT_FILENAME,
        tmp_path / "news_dashboard_snapshot.prev.1.json",
        tmp_path / "news_dashboard_snapshot.copy-20260603.json",
        tmp_path / "news_dashboard_debug_dump.json",
    ]
    for path in [keep_cache, keep_prev, keep_status, keep_other, *delete_paths]:
        path.write_text("{}", encoding="utf-8")

    deleted = cleanup_news_cache_files(cache_dir=tmp_path)

    assert sorted(path.name for path in deleted) == sorted(path.name for path in delete_paths)
    assert keep_cache.exists()
    assert keep_prev.exists()
    assert keep_status.exists()
    assert keep_other.exists()
    assert all(not path.exists() for path in delete_paths)


def test_save_failure_keeps_existing_cache_and_removes_tmp(tmp_path, monkeypatch):
    existing = save_cached_news_dashboard_snapshot(
        _snapshot("existing"),
        cache_dir=tmp_path,
    )

    def fail_rotate(*, cache_dir):
        raise RuntimeError("rotate failed")

    monkeypatch.setattr(news_cache, "rotate_previous_snapshot", fail_rotate)

    with pytest.raises(RuntimeError):
        save_cached_news_dashboard_snapshot(_snapshot("new"), cache_dir=tmp_path)

    assert load_cached_news_dashboard_snapshot(cache_dir=tmp_path) == existing
    assert not (tmp_path / NEWS_TMP_SNAPSHOT_FILENAME).exists()


def test_update_status_is_latest_only_and_reports_cache_size(tmp_path):
    save_cached_news_dashboard_snapshot(_snapshot(), cache_dir=tmp_path)
    status = save_news_update_status(
        NewsUpdateStatus(
            last_attempt_at=datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
            consecutive_failures=2,
        ),
        cache_dir=tmp_path,
    )
    loaded = load_news_update_status(cache_dir=tmp_path)

    assert status.cache_file_size_bytes == get_news_cache_file_size(cache_dir=tmp_path)
    assert loaded == status
    assert loaded.consecutive_failures == 2
    status_payload = (tmp_path / NEWS_UPDATE_STATUS_FILENAME).read_text(encoding="utf-8")
    assert "[" not in status_payload
