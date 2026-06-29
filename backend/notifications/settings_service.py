from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from backend.notifications.gateway_adapter import (
    GatewayNotificationSettings,
    NotificationGatewayAdapter,
)
from backend.notifications.notification_client import (
    NotificationClient,
    NotificationClientResult,
    NotificationSeverity,
    send_test_notification,
)
from backend.notifications.settings_repository import (
    NotificationSetting,
    NotificationSettingsError,
    NotificationSettingsRepository,
)

SEVERITY_OPTIONS: tuple[NotificationSeverity, ...] = (
    "critical",
    "high",
    "medium",
    "low",
    "silent",
)


class NotificationSettingValidationError(ValueError):
    """User-correctable notification setting error."""


@dataclass(frozen=True, slots=True)
class NotificationSettingUpdate:
    app_enabled: bool
    ntfy_enabled: bool
    ntfy_server_url: str
    topic_input: str = ""
    severity_threshold: NotificationSeverity = "medium"
    quiet_hours_enabled: bool = False
    quiet_hours_start: str | time | None = None
    quiet_hours_end: str | time | None = None


@dataclass(frozen=True, slots=True)
class NotificationSettingLoadResult:
    setting: NotificationSetting
    warning: bool = False


def load_notification_setting_safe(
    repository: NotificationSettingsRepository,
    *,
    user_id: str,
) -> NotificationSettingLoadResult:
    try:
        return NotificationSettingLoadResult(repository.load(user_id))
    except NotificationSettingsError:
        return NotificationSettingLoadResult(
            NotificationSetting(user_id=user_id),
            warning=True,
        )


def save_notification_setting(
    repository: NotificationSettingsRepository,
    *,
    user_id: str,
    update: NotificationSettingUpdate,
) -> NotificationSetting:
    current = repository.load(user_id)
    server_url = normalize_ntfy_server_url(update.ntfy_server_url)
    threshold = validate_severity_threshold(update.severity_threshold)
    start = _normalize_quiet_time(update.quiet_hours_start)
    end = _normalize_quiet_time(update.quiet_hours_end)
    if update.quiet_hours_enabled:
        if not start or not end:
            raise NotificationSettingValidationError("Quiet hoursの開始と終了を指定してください。")
        if start == end:
            raise NotificationSettingValidationError(
                "Quiet hoursの開始と終了は異なる時刻を指定してください。"
            )
    topic_input = update.topic_input.strip()
    topic = topic_input if topic_input else current.ntfy_topic
    return repository.save(
        NotificationSetting(
            user_id=user_id,
            app_enabled=update.app_enabled,
            ntfy_enabled=update.ntfy_enabled,
            ntfy_server_url=server_url,
            ntfy_topic=topic,
            severity_threshold=threshold,
            quiet_hours_enabled=update.quiet_hours_enabled,
            quiet_hours_start=start if update.quiet_hours_enabled else None,
            quiet_hours_end=end if update.quiet_hours_enabled else None,
        )
    )


def clear_saved_topic(
    repository: NotificationSettingsRepository,
    *,
    user_id: str,
) -> NotificationSetting:
    return repository.clear_topic(user_id)


def send_saved_test_notification(
    setting: NotificationSetting,
    *,
    client_factory: Callable[[GatewayNotificationSettings], NotificationClient] = (
        NotificationGatewayAdapter
    ),
) -> NotificationClientResult:
    gateway_setting = GatewayNotificationSettings(
        ntfy_enabled=setting.ntfy_enabled,
        ntfy_server_url=setting.ntfy_server_url,
        ntfy_topic=setting.ntfy_topic,
        severity_threshold=setting.severity_threshold,
        quiet_hours_enabled=setting.quiet_hours_enabled,
        quiet_hours_start=setting.quiet_hours_start,
        quiet_hours_end=setting.quiet_hours_end,
    )
    return send_test_notification(client_factory(gateway_setting), user_id=setting.user_id)


def notification_result_message(result: NotificationClientResult) -> tuple[str, str]:
    if result.status == "sent":
        return "success", "テスト通知を送信しました。"
    if result.status == "disabled":
        if result.reason == "topic_not_configured":
            return "warning", "保存済みtopicがありません。topicを設定してください。"
        return "warning", "ntfy通知がOFFです。"
    if result.status == "filtered":
        return "info", "重要度またはQuiet hoursの設定により送信されませんでした。"
    if result.status == "skipped":
        return "info", "この通知は外部送信の対象外です。"
    return "error", "テスト通知を送信できませんでした。設定を確認してください。"


def normalize_ntfy_server_url(value: str) -> str:
    raw_value = value.strip() or "https://ntfy.sh"
    parsed = urlsplit(raw_value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise NotificationSettingValidationError("ntfy server URLを確認してください。")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise NotificationSettingValidationError("ntfy server URLを確認してください。")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise NotificationSettingValidationError(
            "httpはlocalhostまたは127.0.0.1でのみ使用できます。"
        )
    normalized_path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))


def validate_severity_threshold(value: str) -> NotificationSeverity:
    if value not in SEVERITY_OPTIONS:
        raise NotificationSettingValidationError("通知する重要度を確認してください。")
    return value  # type: ignore[return-value]


def _normalize_quiet_time(value: str | time | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, time):
        return value.strftime("%H:%M")
    stripped = value.strip()
    if not stripped:
        return None
    try:
        parsed = time.fromisoformat(stripped)
    except ValueError as exc:
        raise NotificationSettingValidationError("Quiet hoursの時刻を確認してください。") from exc
    return parsed.strftime("%H:%M")
