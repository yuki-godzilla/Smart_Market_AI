from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from zoneinfo import ZoneInfo

from backend.news.cache import save_cached_news_dashboard_snapshot
from backend.news.contracts import (
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    NewsHeatmapCell,
)
from backend.notifications.catalog import NOTIFICATION_TEMPLATES, get_notification_template
from backend.notifications.history_repository import NotificationHistoryRepository
from backend.notifications.live_data import (
    CachedNotificationDataSource,
    NotificationSourceValues,
)
from backend.notifications.producer import CatalogNotificationProducer
from backend.notifications.scheduler import (
    NotificationScheduler,
    NotificationScheduleRepository,
    NotificationScheduleSetting,
    registered_template_ids,
)
from backend.notifications.settings_repository import (
    NotificationSetting,
    NotificationSettingsRepository,
)
from ui.user_icon_assets import load_user_icon_assets


def test_catalog_templates_have_valid_assets_and_safe_wording() -> None:
    asset_ids = {asset.icon_id for asset in load_user_icon_assets()}
    prohibited = ("買うべき", "売るべき", "必ず上がる", "損切り推奨")

    assert len(NOTIFICATION_TEMPLATES) >= 8
    assert {
        "favorite_daily_report",
        "favorite_move_alert",
        "favorite_news_digest",
        "investment_news_digest",
        "sector_momentum_digest",
    } <= set(registered_template_ids())
    for template in NOTIFICATION_TEMPLATES:
        assert template.icon_asset_id in asset_ids
        assert template.thumbnail_asset_id is None or template.thumbnail_asset_id in asset_ids
        assert not any(
            word in template.title_template + template.summary_template for word in prohibited
        )
        assert get_notification_template(template.template_id) is template


def test_producer_respects_user_settings_and_dedupes(tmp_path) -> None:
    path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(path)
    history = NotificationHistoryRepository(str(path))
    producer = CatalogNotificationProducer(history, settings)
    settings.save(NotificationSetting(user_id="yuki", enabled_categories=("FAVORITE",)))

    first = producer.produce(
        "favorite_daily_report",
        user_id="yuki",
        dedupe_key="favorite_daily_report:yuki:2026-06-30",
    )
    duplicate = producer.produce(
        "favorite_daily_report",
        user_id="yuki",
        dedupe_key="favorite_daily_report:yuki:2026-06-30",
    )
    disabled_category = producer.produce(
        "investment_news_digest",
        user_id="yuki",
        dedupe_key="investment_news:yuki:2026-06-30",
    )

    assert first is not None
    assert duplicate is None
    assert disabled_category is None
    assert history.unread_count("yuki") == 1
    assert first.metadata and first.metadata["template_id"] == "favorite_daily_report"


def test_scheduler_is_opt_in_deduped_and_logs_runs(tmp_path) -> None:
    path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(path)
    history = NotificationHistoryRepository(str(path))
    schedules = NotificationScheduleRepository(str(path))
    producer = CatalogNotificationProducer(history, settings)
    scheduler = NotificationScheduler(schedules, producer)
    settings.save(NotificationSetting(user_id="yuki"))
    schedules.save(
        NotificationScheduleSetting(
            user_id="yuki",
            enabled=True,
            favorite_daily_time="07:30",
            investment_news_time="09:00",
            sector_momentum_time="09:30",
            weekdays_only=True,
        )
    )
    now = datetime(2026, 6, 30, 7, 30, tzinfo=UTC)

    assert scheduler.run_due(["yuki"], now=now) == 1
    assert scheduler.run_due(["yuki"], now=now) == 0
    assert history.unread_count("yuki") == 1
    logs = schedules.logs("yuki")
    assert len(logs) == 1
    assert logs[0].status == "created"


def test_interval_jobs_are_registered_and_respect_slots(tmp_path) -> None:
    path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(path)
    history = NotificationHistoryRepository(str(path))
    schedules = NotificationScheduleRepository(str(path))
    scheduler = NotificationScheduler(schedules, CatalogNotificationProducer(history, settings))
    settings.save(NotificationSetting(user_id="yuki"))
    schedules.save(
        NotificationScheduleSetting(
            user_id="yuki",
            enabled=True,
            favorite_daily_time="07:30",
            investment_news_time="08:00",
            sector_momentum_time="08:30",
            favorite_move_interval_minutes=15,
            favorite_news_interval_minutes=60,
            weekdays_only=True,
        )
    )

    produced = scheduler.run_due(["yuki"], now=datetime(2026, 6, 30, 12, 0, tzinfo=UTC))

    assert produced == 2
    assert {item.metadata["template_id"] for item in history.list("yuki") if item.metadata} == {
        "favorite_move_alert",
        "favorite_news_digest",
    }


def test_cached_data_source_uses_profile_scoped_favorites_and_fresh_news_cache(
    tmp_path,
) -> None:
    observed_at = datetime(2026, 7, 1, 16, 0, tzinfo=UTC)
    profile_root = tmp_path / "profiles"
    profile = profile_root / "yuki"
    profile.mkdir(parents=True)
    (profile / "favorites.json").write_text(
        json.dumps(
            {
                "favorites": [
                    {"symbol": "NVDA", "market": "NASDAQ", "asset_type": "stock"},
                    {"symbol": "7203.T", "market": "TSE", "asset_type": "stock"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (profile / "watchlist_snapshots.json").write_text(
        json.dumps(
            {
                "snapshots": {
                    "NVDA": {
                        "status": "ok",
                        "price_change_1d": 5.4,
                        "last_price_at": observed_at.isoformat(),
                    },
                    "7203.T": {
                        "status": "ok",
                        "price_change_1d": 1.2,
                        "last_price_at": observed_at.isoformat(),
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    save_cached_news_dashboard_snapshot(
        NewsDashboardSnapshot(
            generated_at=datetime(2026, 7, 1, tzinfo=UTC),
            freshness_status="latest",
            stream_headlines=[
                NewsHeadlineCard(
                    title="NVIDIA material",
                    source_type="news",
                    category="AI・半導体",
                    material_type="theme",
                    related_symbols=["NVDA"],
                )
            ],
            heatmap_cells=[
                NewsHeatmapCell(
                    category="AI・半導体",
                    news_count=3,
                    risk_count=0,
                    positive_count=1,
                    official_source_count=0,
                    freshness_ratio=1.0,
                    heat_score=4.2,
                )
            ],
        ),
        cache_dir=cache_dir,
    )
    source = CachedNotificationDataSource(
        profile_root=profile_root,
        news_cache_dir=cache_dir,
        now_provider=lambda: observed_at,
    )

    assert source.values_for("favorite_daily_report", user_id="yuki").values == {
        "count": "2",
        "detail": "直近36時間以内に確認できた価格計測: 2/2銘柄。登録済み: NVDA、7203.T",
    }
    assert source.values_for("favorite_move_alert", user_id="yuki").values == {
        "count": "1",
        "detail": "NVDA +5.4%",
    }
    assert source.values_for("favorite_news_digest", user_id="yuki").values == {
        "count": "1",
        "detail": "NVDA に関する確認材料を整理しました。",
    }
    assert source.values_for("investment_news_digest", user_id="yuki").values == {
        "count": "1",
        "detail": "AI・半導体 のニュースキャッシュを確認できます。",
    }
    assert source.values_for("sector_momentum_digest", user_id="yuki").values == {
        "count": "1",
        "detail": "AI・半導体（材料3件）",
    }
    assert (
        source.values_for("favorite_daily_report", user_id="default").reason == "unsupported_user"
    )


def test_daily_report_skips_when_all_marketdata_measurements_are_stale(tmp_path) -> None:
    now = datetime(2026, 7, 3, 7, 30, tzinfo=UTC)
    profile_root = tmp_path / "profiles"
    profile = profile_root / "yuki"
    profile.mkdir(parents=True)
    (profile / "favorites.json").write_text(
        json.dumps({"favorites": [{"symbol": "NVDA"}]}),
        encoding="utf-8",
    )
    (profile / "watchlist_snapshots.json").write_text(
        json.dumps(
            {
                "snapshots": {
                    "NVDA": {
                        "status": "ok",
                        "price": 120.5,
                        "last_price_at": (now - timedelta(hours=37)).isoformat(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    source = CachedNotificationDataSource(profile_root=profile_root, now_provider=lambda: now)

    result = source.values_for("favorite_daily_report", user_id="yuki")

    assert result.values is None
    assert result.reason == "no_fresh_marketdata_measurement"

    path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(path)
    history = NotificationHistoryRepository(str(path))
    schedules = NotificationScheduleRepository(str(path))
    settings.save(NotificationSetting(user_id="yuki"))
    schedules.save(
        NotificationScheduleSetting(
            user_id="yuki",
            enabled=True,
            favorite_move_interval_minutes=17,
            favorite_news_interval_minutes=17,
        )
    )
    scheduler = NotificationScheduler(
        schedules,
        CatalogNotificationProducer(history, settings),
        data_source=source,
    )

    assert scheduler.run_due(["yuki"], now=now) == 0
    assert history.list("yuki") == []
    assert schedules.logs("yuki")[0].reason == "no_fresh_marketdata_measurement"


def test_scheduler_dedupes_identical_fresh_marketdata_measurements(tmp_path) -> None:
    now = datetime(2026, 6, 30, 16, 0, tzinfo=UTC)
    profile_root = tmp_path / "profiles"
    profile = profile_root / "yuki"
    profile.mkdir(parents=True)
    (profile / "favorites.json").write_text(
        json.dumps({"favorites": [{"symbol": "NVDA", "market": "NASDAQ"}]}),
        encoding="utf-8",
    )
    snapshots_path = profile / "watchlist_snapshots.json"
    snapshots_path.write_text(
        json.dumps(
            {
                "snapshots": {
                    "NVDA": {
                        "status": "ok",
                        "price_change_1d": 5.4,
                        "last_price_at": now.isoformat(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(path)
    history = NotificationHistoryRepository(str(path))
    schedules = NotificationScheduleRepository(str(path))
    settings.save(NotificationSetting(user_id="yuki"))
    schedules.save(
        NotificationScheduleSetting(
            user_id="yuki",
            enabled=True,
            favorite_move_interval_minutes=15,
            favorite_news_interval_minutes=17,
        )
    )
    source = CachedNotificationDataSource(profile_root=profile_root, now_provider=lambda: now)
    scheduler = NotificationScheduler(
        schedules,
        CatalogNotificationProducer(history, settings),
        data_source=source,
    )

    assert scheduler.run_due(["yuki"], now=now) == 1
    assert scheduler.run_due(["yuki"], now=now.replace(minute=15)) == 0
    assert len(history.list("yuki")) == 1
    assert schedules.logs("yuki")[0].reason == "disabled_or_duplicate"

    updated_at = now.replace(minute=30)
    snapshots_path.write_text(
        json.dumps(
            {
                "snapshots": {
                    "NVDA": {
                        "status": "ok",
                        "price_change_1d": 6.1,
                        "last_price_at": updated_at.isoformat(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    source.now_provider = lambda: updated_at

    assert scheduler.run_due(["yuki"], now=updated_at) == 1
    assert len(history.list("yuki")) == 2


def test_scheduler_preview_due_has_no_notification_or_run_log_side_effects(tmp_path) -> None:
    class FreshData:
        def values_for(
            self, template_id: str, *, user_id: str, evaluated_at: datetime | None = None
        ) -> NotificationSourceValues:
            assert template_id == "favorite_daily_report"
            assert user_id == "yuki"
            assert evaluated_at == datetime(2026, 6, 30, 7, 30, tzinfo=UTC)
            return NotificationSourceValues({"count": "1", "detail": "登録済み: NVDA"})

    path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(path)
    history = NotificationHistoryRepository(str(path))
    schedules = NotificationScheduleRepository(str(path))
    settings.save(NotificationSetting(user_id="yuki"))
    schedules.save(
        NotificationScheduleSetting(
            user_id="yuki",
            enabled=True,
            favorite_move_interval_minutes=17,
            favorite_news_interval_minutes=17,
        )
    )
    scheduler = NotificationScheduler(
        schedules,
        CatalogNotificationProducer(history, settings),
        data_source=FreshData(),
    )

    previews = scheduler.preview_due(["yuki"], now=datetime(2026, 6, 30, 7, 30, tzinfo=UTC))

    assert [(item.template_id, item.status, item.reason) for item in previews] == [
        ("favorite_daily_report", "ready", "ok")
    ]
    assert history.list("yuki") == []
    assert schedules.logs("yuki") == []


def test_scheduler_with_live_data_source_skips_instead_of_using_sample_payload(tmp_path) -> None:
    class NoFavoriteData:
        def values_for(
            self, template_id: str, *, user_id: str, evaluated_at: datetime | None = None
        ) -> NotificationSourceValues:
            assert template_id == "favorite_daily_report"
            assert user_id == "yuki"
            assert evaluated_at == datetime(2026, 6, 30, 7, 30, tzinfo=UTC)
            return NotificationSourceValues(None, "no_favorites")

    path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(path)
    history = NotificationHistoryRepository(str(path))
    schedules = NotificationScheduleRepository(str(path))
    settings.save(NotificationSetting(user_id="yuki"))
    schedules.save(
        NotificationScheduleSetting(
            user_id="yuki",
            enabled=True,
            favorite_move_interval_minutes=17,
            favorite_news_interval_minutes=17,
        )
    )
    scheduler = NotificationScheduler(
        schedules,
        CatalogNotificationProducer(history, settings),
        data_source=NoFavoriteData(),
    )

    assert scheduler.run_due(["yuki"], now=datetime(2026, 6, 30, 7, 30, tzinfo=UTC)) == 0
    assert history.list("yuki") == []
    logs = schedules.logs("yuki")
    assert len(logs) == 1
    assert logs[0].status == "skipped"
    assert logs[0].reason == "no_favorites"


def test_favorite_move_uses_market_calendar_when_server_timezone_is_on_a_weekend(tmp_path) -> None:
    now = datetime(2026, 6, 27, 4, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    profile_root = tmp_path / "profiles"
    profile = profile_root / "yuki"
    profile.mkdir(parents=True)
    (profile / "favorites.json").write_text(
        json.dumps({"favorites": [{"symbol": "NVDA", "market": "NASDAQ"}]}),
        encoding="utf-8",
    )
    (profile / "watchlist_snapshots.json").write_text(
        json.dumps(
            {
                "snapshots": {
                    "NVDA": {
                        "status": "ok",
                        "price_change_1d": 5.4,
                        "last_price_at": now.isoformat(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(path)
    history = NotificationHistoryRepository(str(path))
    schedules = NotificationScheduleRepository(str(path))
    settings.save(NotificationSetting(user_id="yuki"))
    schedules.save(
        NotificationScheduleSetting(
            user_id="yuki",
            enabled=True,
            favorite_move_interval_minutes=15,
            favorite_news_interval_minutes=17,
            weekdays_only=True,
        )
    )
    scheduler = NotificationScheduler(
        schedules,
        CatalogNotificationProducer(history, settings),
        data_source=CachedNotificationDataSource(profile_root=profile_root),
    )

    assert now.weekday() == 5
    assert scheduler.run_due(["yuki"], now=now) == 1
    item = history.list("yuki")[0]
    assert item.metadata is not None
    assert item.metadata["template_id"] == "favorite_move_alert"
