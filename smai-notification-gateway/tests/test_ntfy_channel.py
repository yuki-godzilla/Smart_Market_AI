from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from notification_gateway.channels.base import HttpResponse
from notification_gateway.channels.ntfy import NtfyChannel, ntfy_priority
from notification_gateway.models import (
    DeliveryReason,
    DeliveryStatus,
    NotificationCategory,
    NotificationEvent,
    Severity,
)


@dataclass
class FakeTransport:
    response: HttpResponse | None = None
    error: Exception | None = None
    request: dict[str, object] | None = None

    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        self.request = {
            "url": url,
            "data": data,
            "headers": dict(headers),
            "timeout": timeout,
        }
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


def _event(severity: Severity = Severity.HIGH) -> NotificationEvent:
    return NotificationEvent(
        event_id="evt-1",
        user_id="yuki",
        event_type="test",
        category=NotificationCategory.SYSTEM,
        severity=severity,
        title="テスト通知",
        message="通知テストです。",
    )


@pytest.mark.parametrize(
    ("severity", "priority"),
    [
        (Severity.CRITICAL, "urgent"),
        (Severity.HIGH, "high"),
        (Severity.MEDIUM, "default"),
        (Severity.LOW, "low"),
        (Severity.SILENT, "min"),
    ],
)
def test_ntfy_priority_mapping(severity: Severity, priority: str) -> None:
    assert ntfy_priority(severity) == priority


def test_ntfy_success_uses_injected_fake_transport() -> None:
    transport = FakeTransport(response=HttpResponse(status_code=200))
    result = NtfyChannel(transport).send(
        _event(),
        server_url="https://ntfy.example",
        topic="secret-topic",
    )

    assert result.success
    assert result.status is DeliveryStatus.SENT
    assert transport.request == {
        "url": "https://ntfy.example/secret-topic",
        "data": "通知テストです。".encode(),
        "headers": {"Title": "テスト通知", "Priority": "high", "Tags": "system"},
        "timeout": 10.0,
    }


@pytest.mark.parametrize(
    ("error", "reason", "message"),
    [
        (TimeoutError("https://ntfy.example/secret-topic"), DeliveryReason.TIMEOUT, "timed out"),
        (
            OSError("Authorization secret-topic"),
            DeliveryReason.TRANSPORT_ERROR,
            "transport failed",
        ),
    ],
)
def test_ntfy_failure_is_sanitized(
    error: Exception,
    reason: DeliveryReason,
    message: str,
) -> None:
    result = NtfyChannel(FakeTransport(error=error)).send(
        _event(),
        server_url="https://ntfy.example",
        topic="secret-topic",
    )

    assert not result.success
    assert result.status is DeliveryStatus.FAILED
    assert result.reason is reason
    assert message in (result.error_message or "")
    assert "secret-topic" not in (result.error_message or "")
    assert "https://" not in (result.error_message or "")
    assert "Authorization" not in (result.error_message or "")


def test_ntfy_http_error_does_not_include_full_url_or_topic() -> None:
    result = NtfyChannel(FakeTransport(response=HttpResponse(status_code=503))).send(
        _event(),
        server_url="https://ntfy.example",
        topic="secret-topic",
    )

    assert result.status is DeliveryStatus.FAILED
    assert result.reason is DeliveryReason.HTTP_ERROR
    assert result.status_code == 503
    assert result.error_message == "Notification service returned an error."
