from __future__ import annotations

from datetime import UTC, datetime

from backend.notifications.catalog import NOTIFICATION_TEMPLATES, get_notification_template
from backend.notifications.history_repository import NotificationHistoryRepository
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
