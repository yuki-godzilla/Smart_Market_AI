"""Parent-side notification integration boundary."""

from backend.notifications.notification_client import (
    NotificationClient,
    NotificationClientResult,
    NotificationRequest,
    SafeNotificationClient,
    send_test_notification,
)

__all__ = [
    "NotificationClient",
    "NotificationClientResult",
    "NotificationRequest",
    "SafeNotificationClient",
    "send_test_notification",
]
