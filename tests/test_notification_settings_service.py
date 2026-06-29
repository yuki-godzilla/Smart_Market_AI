from __future__ import annotations

from datetime import time

import pytest

from backend.notifications.gateway_adapter import GatewayNotificationSettings
from backend.notifications.notification_client import (
    NotificationClientResult,
    NotificationRequest,
)
from backend.notifications.settings_repository import (
    NotificationSetting,
    NotificationSettingsRepository,
)
from backend.notifications.settings_service import (
    NotificationSettingUpdate,
    NotificationSettingValidationError,
    clear_saved_topic,
    load_notification_setting_safe,
    normalize_ntfy_server_url,
    notification_result_message,
    save_notification_setting,
    send_saved_test_notification,
    validate_severity_threshold,
)


class FakeNotificationClient:
    def __init__(self, result: NotificationClientResult) -> None:
        self.result = result
        self.requests: list[NotificationRequest] = []

    def send(self, request: NotificationRequest) -> NotificationClientResult:
        self.requests.append(request)
        return NotificationClientResult(
            event_id=request.event_id,
            status=self.result.status,
            success=self.result.success,
            reason=self.result.reason,
            channel=self.result.channel,
            status_code=self.result.status_code,
            error_message=self.result.error_message,
        )


def test_empty_topic_input_preserves_existing_topic(tmp_path) -> None:
    repository = NotificationSettingsRepository(tmp_path / "notifications.sqlite")
    repository.save(
        NotificationSetting(
            user_id="yuki",
            ntfy_enabled=True,
            ntfy_topic="existing-secret",
        )
    )

    saved = save_notification_setting(
        repository,
        user_id="yuki",
        update=NotificationSettingUpdate(
            app_enabled=True,
            ntfy_enabled=True,
            ntfy_server_url="https://ntfy.sh/",
            topic_input="",
            severity_threshold="high",
        ),
    )

    assert saved.ntfy_topic == "existing-secret"
    assert saved.ntfy_server_url == "https://ntfy.sh"


def test_topic_is_removed_only_by_explicit_clear(tmp_path) -> None:
    repository = NotificationSettingsRepository(tmp_path / "notifications.sqlite")
    repository.save(
        NotificationSetting(
            user_id="yuki",
            ntfy_enabled=True,
            ntfy_topic="existing-secret",
        )
    )

    cleared = clear_saved_topic(repository, user_id="yuki")

    assert cleared.ntfy_topic is None
    assert not cleared.ntfy_enabled


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://ntfy.sh/", "https://ntfy.sh"),
        ("https://push.example/base/", "https://push.example/base"),
        ("http://localhost:8080/", "http://localhost:8080"),
        ("http://127.0.0.1:8080/", "http://127.0.0.1:8080"),
    ],
)
def test_server_url_normalization(value: str, expected: str) -> None:
    assert normalize_ntfy_server_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "http://example.com",
        "ftp://ntfy.example",
        "https://user:password@ntfy.example",
        "https://ntfy.example?topic=secret",
    ],
)
def test_server_url_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(NotificationSettingValidationError):
        normalize_ntfy_server_url(value)


def test_equal_quiet_hours_are_rejected(tmp_path) -> None:
    repository = NotificationSettingsRepository(tmp_path / "notifications.sqlite")

    with pytest.raises(NotificationSettingValidationError, match="異なる時刻"):
        save_notification_setting(
            repository,
            user_id="yuki",
            update=NotificationSettingUpdate(
                app_enabled=True,
                ntfy_enabled=True,
                ntfy_server_url="https://ntfy.sh",
                quiet_hours_enabled=True,
                quiet_hours_start=time(22, 0),
                quiet_hours_end=time(22, 0),
            ),
        )


def test_severity_threshold_is_fixed() -> None:
    assert validate_severity_threshold("critical") == "critical"
    with pytest.raises(NotificationSettingValidationError):
        validate_severity_threshold("urgent")


@pytest.mark.parametrize(
    ("status", "reason", "level", "text"),
    [
        ("sent", "sent", "success", "送信しました"),
        ("disabled", "channel_disabled", "warning", "OFF"),
        ("filtered", "quiet_hours", "info", "送信されませんでした"),
        ("failed", "transport_error", "error", "送信できませんでした"),
    ],
)
def test_notification_result_messages_are_safe_japanese(
    status: str,
    reason: str,
    level: str,
    text: str,
) -> None:
    result = NotificationClientResult(
        event_id="evt",
        status=status,  # type: ignore[arg-type]
        success=status == "sent",
        reason=reason,
        error_message="Notification delivery failed." if status == "failed" else None,
    )

    actual_level, message = notification_result_message(result)

    assert actual_level == level
    assert text in message
    assert "topic-value" not in message
    assert "https://" not in message


def test_test_notification_uses_fake_client_once() -> None:
    created_clients: list[FakeNotificationClient] = []
    received_settings: list[GatewayNotificationSettings] = []

    def factory(settings: GatewayNotificationSettings) -> FakeNotificationClient:
        received_settings.append(settings)
        client = FakeNotificationClient(
            NotificationClientResult(
                event_id="placeholder",
                status="sent",
                success=True,
                reason="sent",
            )
        )
        created_clients.append(client)
        return client

    result = send_saved_test_notification(
        NotificationSetting(
            user_id="yuki",
            ntfy_enabled=True,
            ntfy_topic="secret-topic",
        ),
        client_factory=factory,
    )

    assert result.status == "sent"
    assert len(created_clients) == 1
    assert len(created_clients[0].requests) == 1
    assert received_settings[0].ntfy_topic == "secret-topic"


def test_safe_load_returns_disabled_default_for_repository_error(tmp_path) -> None:
    database = tmp_path / "notifications.sqlite"
    database.write_bytes(b"broken")

    result = load_notification_setting_safe(
        NotificationSettingsRepository(database),
        user_id="yuki",
    )

    assert result.warning
    assert not result.setting.ntfy_enabled
