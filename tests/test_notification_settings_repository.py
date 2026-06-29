import sqlite3

import pytest

from backend.notifications.settings_repository import (
    DEFAULT_NOTIFICATION_CATEGORIES,
    SCHEMA_VERSION,
    NotificationSetting,
    NotificationSettingsError,
    NotificationSettingsRepository,
)


def test_repository_creates_database_schema_and_default_setting(tmp_path) -> None:
    database = tmp_path / "user" / "notifications.sqlite"
    repository = NotificationSettingsRepository(database)

    setting = repository.load("yuki")

    assert database.exists()
    assert not setting.ntfy_enabled
    assert setting.ntfy_server_url == "https://ntfy.sh"
    assert setting.severity_threshold == "medium"
    assert setting.enabled_categories == DEFAULT_NOTIFICATION_CATEGORIES
    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT value FROM notification_meta WHERE key = 'schema_version'"
        ).fetchone()
    assert version == (str(SCHEMA_VERSION),)


def test_repository_saves_users_separately_and_clears_topic(tmp_path) -> None:
    repository = NotificationSettingsRepository(tmp_path / "notifications.sqlite")
    repository.save(
        NotificationSetting(
            user_id="yuki",
            ntfy_enabled=True,
            ntfy_server_url="https://ntfy.sh",
            ntfy_topic="secret-yuki",
            severity_threshold="high",
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            enabled_categories=("FAVORITE", "SYSTEM"),
        )
    )
    repository.save(
        NotificationSetting(
            user_id="family",
            ntfy_enabled=True,
            ntfy_topic="secret-family",
        )
    )

    yuki = repository.load("yuki")
    family = repository.load("family")
    cleared = repository.clear_topic("yuki")

    assert yuki.ntfy_topic == "secret-yuki"
    assert yuki.enabled_categories == ("FAVORITE", "SYSTEM")
    assert family.ntfy_topic == "secret-family"
    assert cleared.ntfy_topic is None
    assert not cleared.ntfy_enabled
    assert repository.load("family").ntfy_topic == "secret-family"


def test_repository_reports_corrupt_database_without_exposing_path(tmp_path) -> None:
    database = tmp_path / "notifications.sqlite"
    database.write_bytes(b"not a sqlite database")
    repository = NotificationSettingsRepository(database)

    with pytest.raises(NotificationSettingsError) as exc_info:
        repository.load("yuki")

    assert str(database) not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_repository_rejects_future_schema_version_safely(tmp_path) -> None:
    database = tmp_path / "notifications.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE notification_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO notification_meta (key, value) VALUES ('schema_version', '999')"
        )

    with pytest.raises(NotificationSettingsError):
        NotificationSettingsRepository(database).load("yuki")
