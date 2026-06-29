from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.notifications import (
    NotificationClientResult,
    NotificationRequest,
    SafeNotificationClient,
    send_test_notification,
)


class FakeNotificationClient:
    def __init__(
        self,
        *,
        result: NotificationClientResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.requests: list[NotificationRequest] = []

    def send(self, request: NotificationRequest) -> NotificationClientResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return NotificationClientResult(
            event_id=request.event_id,
            status="sent",
            success=True,
            reason="sent",
            status_code=200,
        )


def _request() -> NotificationRequest:
    return NotificationRequest(
        event_id="evt-1",
        user_id="yuki",
        event_type="test_notification",
        category="SYSTEM",
        severity="medium",
        title="SMAI テスト通知",
        message="通知テストです。",
        created_at=datetime(2026, 6, 29, tzinfo=UTC),
    )


def test_notification_request_is_lightweight_and_validated() -> None:
    request = _request()

    assert request.category == "SYSTEM"
    assert request.severity == "medium"
    assert request.metadata == {}

    with pytest.raises(ValueError, match="user_id"):
        NotificationRequest(
            user_id=" ",
            event_type="test",
            category="SYSTEM",
            severity="medium",
            title="test",
            message="test",
        )


def test_safe_client_returns_sender_result() -> None:
    sender = FakeNotificationClient()

    result = SafeNotificationClient(sender).send(_request())

    assert result.status == "sent"
    assert result.success
    assert len(sender.requests) == 1


@pytest.mark.parametrize(
    ("error", "reason", "message"),
    [
        (
            TimeoutError("https://ntfy.example/secret-topic"),
            "timeout",
            "Notification request timed out.",
        ),
        (
            RuntimeError("Authorization secret-topic"),
            "client_error",
            "Notification delivery failed.",
        ),
    ],
)
def test_safe_client_sanitizes_sender_exceptions(
    error: Exception,
    reason: str,
    message: str,
) -> None:
    result = SafeNotificationClient(FakeNotificationClient(error=error)).send(_request())

    assert result.status == "failed"
    assert not result.success
    assert result.reason == reason
    assert result.error_message == message
    assert "secret-topic" not in (result.error_message or "")
    assert "https://" not in (result.error_message or "")
    assert "Authorization" not in (result.error_message or "")


def test_safe_client_rejects_mismatched_event_id() -> None:
    sender = FakeNotificationClient(
        result=NotificationClientResult(
            event_id="wrong-event",
            status="sent",
            success=True,
            reason="sent",
        )
    )

    result = SafeNotificationClient(sender).send(_request())

    assert result.status == "failed"
    assert result.reason == "invalid_response"


def test_safe_client_resanitizes_failed_sender_result() -> None:
    sender = FakeNotificationClient(
        result=NotificationClientResult(
            event_id="evt-1",
            status="failed",
            success=False,
            reason="transport_error",
            error_message="Authorization secret-topic at https://ntfy.example/secret-topic",
        )
    )

    result = SafeNotificationClient(sender).send(_request())

    assert result.status == "failed"
    assert result.reason == "transport_error"
    assert result.error_message == "Notification delivery failed."


def test_send_test_notification_builds_system_event_only_when_called() -> None:
    sender = FakeNotificationClient()
    created_at = datetime(2026, 6, 29, 12, 30, tzinfo=UTC)

    assert sender.requests == []

    result = send_test_notification(
        sender,
        user_id="yuki",
        created_at=created_at,
        event_id="test-event-1",
    )

    assert result.success
    assert len(sender.requests) == 1
    request = sender.requests[0]
    assert request.event_id == "test-event-1"
    assert request.event_type == "test_notification"
    assert request.category == "SYSTEM"
    assert request.severity == "medium"
    assert request.metadata == {"test_notification": True}
    assert request.created_at == created_at


def test_send_test_notification_never_raises_delivery_failure() -> None:
    result = send_test_notification(
        FakeNotificationClient(error=OSError("secret-topic")),
        user_id="yuki",
        event_id="test-event-2",
    )

    assert result.status == "failed"
    assert result.reason == "client_error"
