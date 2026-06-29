"""Parent-side notification integration boundary."""

from backend.notifications.gateway_adapter import (
    GatewayBindings,
    GatewayNotificationSettings,
    NotificationGatewayAdapter,
)
from backend.notifications.notification_client import (
    NotificationClient,
    NotificationClientResult,
    NotificationRequest,
    SafeNotificationClient,
    send_test_notification,
)

__all__ = [
    "GatewayBindings",
    "GatewayNotificationSettings",
    "NotificationClient",
    "NotificationClientResult",
    "NotificationGatewayAdapter",
    "NotificationRequest",
    "SafeNotificationClient",
    "send_test_notification",
]
