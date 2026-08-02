"""Configured notification-client construction for non-UI producers."""

from __future__ import annotations

from backend.notifications.gateway_adapter import (
    GatewayNotificationSettings,
    NotificationGatewayAdapter,
)
from backend.notifications.notification_client import NotificationClient
from backend.notifications.settings_repository import NotificationSettingsRepository


def configured_notification_client(
    settings_repository: NotificationSettingsRepository,
    user_id: str,
) -> NotificationClient | None:
    """Return an opt-in gateway client, never constructing one for disabled users."""

    setting = settings_repository.load(user_id)
    if user_id == "default" or not setting.ntfy_enabled or not setting.ntfy_topic:
        return None
    return NotificationGatewayAdapter(
        GatewayNotificationSettings(
            ntfy_enabled=setting.ntfy_enabled,
            ntfy_server_url=setting.ntfy_server_url,
            ntfy_topic=setting.ntfy_topic,
            severity_threshold=setting.severity_threshold,
            quiet_hours_enabled=setting.quiet_hours_enabled,
            quiet_hours_start=setting.quiet_hours_start,
            quiet_hours_end=setting.quiet_hours_end,
        )
    )
