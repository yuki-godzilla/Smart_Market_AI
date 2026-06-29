from datetime import datetime

from notification_gateway.channels.base import HttpResponse
from notification_gateway.channels.ntfy import NtfyChannel
from notification_gateway.dispatcher import NotificationDispatcher
from notification_gateway.models import (
    DeliveryReason,
    DeliveryStatus,
    NotificationCategory,
    NotificationEvent,
    Severity,
    UserNotificationSetting,
)


class CountingFakeTransport:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def post(self, url: str, **kwargs: object) -> HttpResponse:
        self.calls += 1
        if self.fail:
            raise OSError("secret-topic https://ntfy.example/secret-topic")
        return HttpResponse(status_code=200)


def _event(severity: Severity) -> NotificationEvent:
    return NotificationEvent(
        event_id="evt-1",
        user_id="yuki",
        event_type="test",
        category=NotificationCategory.SYSTEM,
        severity=severity,
        title="テスト通知",
        message="通知テストです。",
    )


def _setting(
    *,
    ntfy_enabled: bool = True,
    quiet_hours_enabled: bool = False,
    quiet_hours_start: str | None = None,
    quiet_hours_end: str | None = None,
) -> UserNotificationSetting:
    return UserNotificationSetting(
        user_id="yuki",
        ntfy_enabled=ntfy_enabled,
        ntfy_topic="secret-topic",
        quiet_hours_enabled=quiet_hours_enabled,
        quiet_hours_start=quiet_hours_start,
        quiet_hours_end=quiet_hours_end,
    )


def test_dispatcher_returns_skipped_without_transport_call_for_silent() -> None:
    transport = CountingFakeTransport()
    dispatcher = NotificationDispatcher(
        NtfyChannel(transport),
        clock=lambda: datetime(2026, 6, 29, 12, 0),
    )

    result = dispatcher.dispatch_ntfy(_event(Severity.SILENT), _setting())

    assert result.status is DeliveryStatus.SKIPPED
    assert result.reason is DeliveryReason.SILENT
    assert transport.calls == 0


def test_dispatcher_distinguishes_disabled_and_filtered() -> None:
    transport = CountingFakeTransport()
    dispatcher = NotificationDispatcher(
        NtfyChannel(transport),
        clock=lambda: datetime(2026, 6, 29, 23, 0),
    )

    disabled = dispatcher.dispatch_ntfy(
        _event(Severity.HIGH),
        _setting(ntfy_enabled=False),
    )
    filtered = dispatcher.dispatch_ntfy(
        _event(Severity.HIGH),
        _setting(
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
        ),
    )

    assert disabled.status is DeliveryStatus.DISABLED
    assert filtered.status is DeliveryStatus.FILTERED
    assert transport.calls == 0


def test_dispatcher_returns_sent_or_failed_without_raising() -> None:
    sent_transport = CountingFakeTransport()
    failed_transport = CountingFakeTransport(fail=True)

    def clock() -> datetime:
        return datetime(2026, 6, 29, 12, 0)

    sent = NotificationDispatcher(NtfyChannel(sent_transport), clock=clock).dispatch_ntfy(
        _event(Severity.HIGH),
        _setting(),
    )
    failed = NotificationDispatcher(NtfyChannel(failed_transport), clock=clock).dispatch_ntfy(
        _event(Severity.HIGH),
        _setting(),
    )

    assert sent.status is DeliveryStatus.SENT
    assert failed.status is DeliveryStatus.FAILED
    assert failed.error_message == "Notification transport failed."
