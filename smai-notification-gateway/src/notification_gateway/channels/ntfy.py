from __future__ import annotations

from datetime import UTC, datetime
from urllib.error import HTTPError, URLError

from notification_gateway.channels.base import HttpTransport
from notification_gateway.models import (
    DeliveryReason,
    DeliveryResult,
    DeliveryStatus,
    NotificationEvent,
    Severity,
)

_PRIORITIES = {
    Severity.CRITICAL: "urgent",
    Severity.HIGH: "high",
    Severity.MEDIUM: "default",
    Severity.LOW: "low",
    Severity.SILENT: "min",
}


def ntfy_priority(severity: Severity) -> str:
    return _PRIORITIES[Severity(severity)]


class NtfyChannel:
    name = "ntfy"

    def __init__(self, transport: HttpTransport, *, timeout_seconds: float = 10.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    def send(self, event: NotificationEvent, *, server_url: str, topic: str) -> DeliveryResult:
        url = f"{server_url.rstrip('/')}/{topic.lstrip('/')}"
        try:
            response = self._transport.post(
                url,
                data=event.message.encode("utf-8"),
                headers={
                    "Title": event.title,
                    "Priority": ntfy_priority(event.severity),
                    "Tags": event.category.value.lower(),
                },
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            return self._failed(event, DeliveryReason.TIMEOUT, "Notification request timed out.")
        except (HTTPError, URLError, OSError):
            return self._failed(
                event,
                DeliveryReason.TRANSPORT_ERROR,
                "Notification transport failed.",
            )
        except Exception:
            return self._failed(
                event,
                DeliveryReason.TRANSPORT_ERROR,
                "Notification transport failed.",
            )

        if not 200 <= response.status_code < 300:
            return DeliveryResult(
                event_id=event.event_id,
                channel=self.name,
                status=DeliveryStatus.FAILED,
                reason=DeliveryReason.HTTP_ERROR,
                success=False,
                status_code=response.status_code,
                error_message="Notification service returned an error.",
            )
        return DeliveryResult(
            event_id=event.event_id,
            channel=self.name,
            status=DeliveryStatus.SENT,
            reason=DeliveryReason.SENT,
            success=True,
            status_code=response.status_code,
            delivered_at=datetime.now(UTC),
        )

    def _failed(
        self,
        event: NotificationEvent,
        reason: DeliveryReason,
        message: str,
    ) -> DeliveryResult:
        return DeliveryResult(
            event_id=event.event_id,
            channel=self.name,
            status=DeliveryStatus.FAILED,
            reason=reason,
            success=False,
            error_message=message,
        )
