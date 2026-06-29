"""Parent-side notification integration boundary."""

from backend.notifications.content_renderer import render_in_app, render_ntfy
from backend.notifications.gateway_adapter import (
    GatewayBindings,
    GatewayNotificationSettings,
    NotificationGatewayAdapter,
)
from backend.notifications.history_repository import AppNotification, NotificationHistoryRepository
from backend.notifications.notification_client import (
    NotificationClient,
    NotificationClientResult,
    NotificationRequest,
    SafeNotificationClient,
    send_test_notification,
)
from backend.notifications.notification_service import NotificationService
from backend.notifications.settings_repository import (
    NotificationSetting,
    NotificationSettingsRepository,
)
from backend.notifications.trusted_devices import TrustedDevice, TrustedDeviceRepository

__all__ = [
    "GatewayBindings",
    "AppNotification",
    "GatewayNotificationSettings",
    "NotificationClient",
    "NotificationClientResult",
    "NotificationGatewayAdapter",
    "NotificationHistoryRepository",
    "NotificationService",
    "NotificationRequest",
    "NotificationSetting",
    "NotificationSettingsRepository",
    "render_in_app",
    "render_ntfy",
    "SafeNotificationClient",
    "TrustedDevice",
    "TrustedDeviceRepository",
    "send_test_notification",
]
