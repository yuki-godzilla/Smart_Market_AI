from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import pytest

from backend.notifications.gateway_adapter import (
    GatewayNotificationSettings,
    NotificationGatewayAdapter,
)
from backend.notifications.history_repository import (
    AppNotification,
    NotificationHistoryRepository,
)
from backend.notifications.notification_client import NotificationRequest
from backend.notifications.producer import CatalogNotificationProducer
from backend.notifications.settings_repository import (
    NotificationSetting,
    NotificationSettingsError,
    NotificationSettingsRepository,
)
from backend.users import UserRepository
from ui import favorites, user_data, watchlist_snapshots
from ui.notification_center import trusted_device_bootstrap_html
from ui.watchlist_snapshots import WatchlistSnapshot


def test_user_repository_creates_safe_independent_profile(tmp_path) -> None:
    database = tmp_path / "notifications.sqlite"
    repository = UserRepository(str(database))

    created = repository.create_user("  春の投資メモ  ", "smai_navi_default")

    assert re.fullmatch(r"u_[a-z0-9_-]{8,32}", created.user_id)
    assert created.display_name == "春の投資メモ"
    assert repository.get_user(created.user_id) == created
    assert NotificationSettingsRepository(database).load(created.user_id).app_enabled


@pytest.mark.parametrize("name", ["", "   ", "bad\nname", "x" * 33])
def test_user_repository_rejects_invalid_display_name(tmp_path, name) -> None:
    repository = UserRepository(str(tmp_path / "notifications.sqlite"))
    with pytest.raises(ValueError):
        repository.create_user(name, "smai_navi_default")


def test_default_user_cannot_be_edited_or_save_notification_settings(tmp_path) -> None:
    database = tmp_path / "notifications.sqlite"
    users = UserRepository(str(database))
    with pytest.raises(ValueError):
        users.update_user_profile("default", "変更", "smai_navi_default")
    with pytest.raises(NotificationSettingsError):
        NotificationSettingsRepository(database).save(NotificationSetting(user_id="default"))


def test_favorites_and_snapshots_are_scoped_by_active_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(user_data, "PROFILE_ROOT", tmp_path / "profiles")
    state: dict[str, object] = {"smai_current_user_id": "user_a"}
    monkeypatch.setattr(user_data.st, "session_state", state)

    favorites.add_favorite("7203.T", {"memo": "A"})
    watchlist_snapshots.upsert_watchlist_snapshot(WatchlistSnapshot(symbol="7203.T", price=100.0))
    state["smai_current_user_id"] = "user_b"

    assert favorites.load_favorites() == []
    assert watchlist_snapshots.load_watchlist_snapshots() == {}
    favorites.add_favorite("AAPL", {"memo": "B"})

    state["smai_current_user_id"] = "user_a"
    assert [item.symbol for item in favorites.load_favorites()] == ["7203.T"]
    assert watchlist_snapshots.get_watchlist_snapshot("7203.T").price == 100.0


def test_default_favorites_are_session_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(user_data, "PROFILE_ROOT", tmp_path / "profiles")
    state: dict[str, object] = {"smai_current_user_id": "default"}
    monkeypatch.setattr(user_data.st, "session_state", state)

    favorites.add_favorite("NVDA")
    watchlist_snapshots.upsert_watchlist_snapshot(WatchlistSnapshot(symbol="NVDA", price=200.0))

    assert favorites.is_favorite("NVDA")
    assert watchlist_snapshots.get_watchlist_snapshot("NVDA") is not None
    assert not (tmp_path / "profiles" / "default").exists()

    monkeypatch.setattr(user_data.st, "session_state", {"smai_current_user_id": "default"})
    assert favorites.load_favorites() == []
    assert watchlist_snapshots.load_watchlist_snapshots() == {}


def test_legacy_data_migrates_once_without_overwrite(tmp_path, monkeypatch) -> None:
    legacy = tmp_path / "legacy"
    profiles = tmp_path / "profiles"
    migrations = tmp_path / "migrations"
    legacy.mkdir()
    (legacy / "favorites.json").write_text(
        json.dumps({"favorites": [{"symbol": "7203.T"}]}), encoding="utf-8"
    )
    monkeypatch.setattr(user_data, "LEGACY_USER_ROOT", legacy)
    monkeypatch.setattr(user_data, "PROFILE_ROOT", profiles)
    monkeypatch.setattr(user_data, "MIGRATION_ROOT", migrations)

    user_data.migrate_legacy_user_data(["local_user"])
    target = profiles / "local_user" / "favorites.json"
    assert target.exists()
    target.write_text('{"favorites": [{"symbol": "AAPL"}]}', encoding="utf-8")
    user_data.migrate_legacy_user_data(["local_user"])
    assert "AAPL" in target.read_text(encoding="utf-8")
    assert not (profiles / "default").exists()


def test_default_notification_history_is_rejected(tmp_path) -> None:
    repository = NotificationHistoryRepository(str(tmp_path / "notifications.sqlite"))
    item = AppNotification(
        event_id="default-event",
        user_id="default",
        technical_category="system",
        presentation_category="SYSTEM",
        severity="medium",
        title="title",
        summary="summary",
        created_at=datetime.now(UTC),
    )
    assert not repository.save(item)
    assert repository.list("default") == []


def test_default_notification_producer_and_gateway_are_disabled(tmp_path) -> None:
    database = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(database)
    history = NotificationHistoryRepository(str(database))
    producer = CatalogNotificationProducer(history, settings)
    assert producer.produce("favorite_daily_report", user_id="default") is None

    adapter = NotificationGatewayAdapter(
        GatewayNotificationSettings(),
        bindings_loader=lambda: (_ for _ in ()).throw(AssertionError("must not load gateway")),
    )
    result = adapter.send(
        NotificationRequest(
            user_id="default",
            event_type="test",
            category="SYSTEM",
            severity="medium",
            title="test",
            message="test",
        )
    )
    assert result.status == "skipped"
    assert result.reason == "default_user_notifications_disabled"


def test_default_user_area_does_not_append_bell() -> None:
    html = trusted_device_bootstrap_html(
        display_name="SMAIデフォルト",
        user_id="default",
        notifications_enabled=False,
    )
    assert "const notificationsEnabled = false" in html
    assert "if (notificationsEnabled) button.append(bell)" in html
