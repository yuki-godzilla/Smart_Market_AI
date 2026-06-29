from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from notification_gateway.channels.base import NotificationChannel
from notification_gateway.models import (
    DeliveryResult,
    NotificationEvent,
    UserNotificationSetting,
)
from notification_gateway.rules.evaluator import evaluate_ntfy_delivery


class NotificationDispatcher:
    def __init__(
        self,
        ntfy_channel: NotificationChannel,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ntfy_channel = ntfy_channel
        self._clock = clock or (lambda: datetime.now(UTC))

    def dispatch_ntfy(
        self,
        event: NotificationEvent,
        setting: UserNotificationSetting,
    ) -> DeliveryResult:
        decision = evaluate_ntfy_delivery(event, setting, now=self._clock())
        if not decision.should_send:
            return DeliveryResult(
                event_id=event.event_id,
                channel=self._ntfy_channel.name,
                status=decision.status,
                reason=decision.reason,
                success=False,
            )
        return self._ntfy_channel.send(
            event,
            server_url=setting.ntfy_server_url,
            topic=setting.ntfy_topic or "",
        )
