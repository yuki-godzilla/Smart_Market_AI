from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from uuid import uuid4

NotificationCategory = Literal[
    "MARKET",
    "RESEARCH",
    "NEWS",
    "SYSTEM",
    "MY_RADAR",
    "AI_SCORE",
    "PRICE_ALERT",
    "DATA_REFRESH",
    "LLM",
]
NotificationSeverity = Literal["critical", "high", "medium", "low", "silent"]
NotificationDeliveryStatus = Literal["skipped", "disabled", "filtered", "sent", "failed"]


@dataclass(frozen=True, slots=True)
class NotificationRequest:
    """Small parent-side contract passed to a notification client."""

    user_id: str
    event_type: str
    category: NotificationCategory
    severity: NotificationSeverity
    title: str
    message: str
    event_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str | None = None
    source: str | None = None
    action_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        for name in ("event_id", "user_id", "event_type", "title", "message"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be blank")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class NotificationClientResult:
    """Safe result returned to SMAI without leaking gateway exception details."""

    event_id: str
    status: NotificationDeliveryStatus
    success: bool
    reason: str
    channel: str = "ntfy"
    status_code: int | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.success != (self.status == "sent"):
            raise ValueError("success must be true only when status is sent")
        if self.status != "failed" and self.error_message is not None:
            raise ValueError("error_message is only valid for failed delivery")


class NotificationClient(Protocol):
    """Provider-neutral boundary implemented by a future gateway adapter."""

    def send(self, request: NotificationRequest) -> NotificationClientResult:
        """Send one already-approved notification request."""


class SafeNotificationClient:
    """Prevent notification delivery failures from stopping an SMAI workflow."""

    def __init__(self, sender: NotificationClient) -> None:
        self._sender = sender

    def send(self, request: NotificationRequest) -> NotificationClientResult:
        try:
            result = self._sender.send(request)
        except TimeoutError:
            return _failed_result(
                request,
                reason="timeout",
                message="Notification request timed out.",
            )
        except Exception:
            return _failed_result(
                request,
                reason="client_error",
                message="Notification delivery failed.",
            )
        if result.event_id != request.event_id:
            return _failed_result(
                request,
                reason="invalid_response",
                message="Notification service returned an invalid response.",
            )
        if result.status == "failed":
            return NotificationClientResult(
                event_id=result.event_id,
                channel=result.channel,
                status="failed",
                success=False,
                reason=result.reason,
                status_code=result.status_code,
                error_message="Notification delivery failed.",
            )
        return result


def send_test_notification(
    client: NotificationClient,
    *,
    user_id: str,
    created_at: datetime | None = None,
    event_id: str | None = None,
) -> NotificationClientResult:
    """Send a test event only when this function is called explicitly."""

    request = NotificationRequest(
        event_id=event_id or str(uuid4()),
        user_id=user_id,
        event_type="test_notification",
        category="SYSTEM",
        severity="medium",
        title="SMAI テスト通知",
        message="SMAI の通知設定を確認するためのテスト通知です。",
        source="notification_settings",
        metadata={"test_notification": True},
        created_at=created_at or datetime.now(UTC),
    )
    return SafeNotificationClient(client).send(request)


def _failed_result(
    request: NotificationRequest,
    *,
    reason: str,
    message: str,
) -> NotificationClientResult:
    return NotificationClientResult(
        event_id=request.event_id,
        status="failed",
        success=False,
        reason=reason,
        error_message=message,
    )
