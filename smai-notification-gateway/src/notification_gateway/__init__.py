"""Independent notification delivery contracts and dispatcher."""

from notification_gateway.dispatcher import NotificationDispatcher
from notification_gateway.models import (
    DeliveryReason,
    DeliveryResult,
    DeliveryStatus,
    NotificationCategory,
    NotificationEvent,
    Severity,
    UserNotificationSetting,
)

__all__ = [
    "DeliveryReason",
    "DeliveryResult",
    "DeliveryStatus",
    "NotificationCategory",
    "NotificationDispatcher",
    "NotificationEvent",
    "Severity",
    "UserNotificationSetting",
]
