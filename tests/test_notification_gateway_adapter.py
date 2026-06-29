from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.notifications import (
    GatewayBindings,
    GatewayNotificationSettings,
    NotificationGatewayAdapter,
    NotificationRequest,
)


@dataclass
class FakeGatewayEvent:
    event_id: str
    user_id: str
    event_type: str
    category: str
    severity: str
    title: str
    message: str
    symbol: str | None
    source: str | None
    action_url: str | None
    metadata: dict[str, Any]
    created_at: datetime


@dataclass
class FakeGatewaySetting:
    user_id: str
    ntfy_enabled: bool
    ntfy_server_url: str
    ntfy_topic: str | None
    severity_threshold: str
    quiet_hours_enabled: bool
    quiet_hours_start: str | None
    quiet_hours_end: str | None


@dataclass
class FakeGatewayResult:
    event_id: str
    channel: str = "ntfy"
    status: str = "sent"
    reason: str = "sent"
    success: bool = True
    status_code: int | None = 200
    error_message: str | None = None


class FakeGatewayDispatcher:
    def __init__(
        self,
        result: FakeGatewayResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[object, object]] = []

    def dispatch_ntfy(self, event: object, setting: object) -> object:
        self.calls.append((event, setting))
        if self.error is not None:
            raise self.error
        return self.result or FakeGatewayResult(event_id=getattr(event, "event_id"))


def _request() -> NotificationRequest:
    return NotificationRequest(
        event_id="evt-n3a",
        user_id="yuki",
        event_type="test_notification",
        category="SYSTEM",
        severity="high",
        title="SMAI テスト通知",
        message="通知adapterのテストです。",
        symbol="7203.T",
        source="notification_settings",
        action_url="/settings",
        metadata={"test_notification": True},
        created_at=datetime(2026, 6, 29, 15, 0, tzinfo=UTC),
    )


def _bindings(dispatcher: FakeGatewayDispatcher) -> GatewayBindings:
    return GatewayBindings(
        event_factory=FakeGatewayEvent,
        setting_factory=FakeGatewaySetting,
        category_factory=lambda value: value,
        severity_factory=lambda value: value,
        dispatcher_factory=lambda: dispatcher,
    )


def test_adapter_converts_parent_request_and_minimal_settings() -> None:
    dispatcher = FakeGatewayDispatcher()
    settings = GatewayNotificationSettings(
        ntfy_enabled=True,
        ntfy_server_url="https://ntfy.example",
        ntfy_topic="secret-topic",
        severity_threshold="medium",
        quiet_hours_enabled=True,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
    )
    adapter = NotificationGatewayAdapter(
        settings,
        bindings_loader=lambda: _bindings(dispatcher),
    )

    result = adapter.send(_request())

    assert result.status == "sent"
    assert result.success
    assert len(dispatcher.calls) == 1
    event, setting = dispatcher.calls[0]
    assert isinstance(event, FakeGatewayEvent)
    assert event.event_id == "evt-n3a"
    assert event.category == "SYSTEM"
    assert event.severity == "high"
    assert event.metadata == {"test_notification": True}
    assert isinstance(setting, FakeGatewaySetting)
    assert setting.ntfy_enabled
    assert setting.ntfy_topic == "secret-topic"
    assert setting.severity_threshold == "medium"
    assert setting.quiet_hours_start == "22:00"
    assert setting.quiet_hours_end == "07:00"


def test_adapter_returns_safe_failure_when_gateway_import_fails() -> None:
    def missing_gateway() -> GatewayBindings:
        raise ModuleNotFoundError("notification_gateway secret-topic")

    result = NotificationGatewayAdapter(
        GatewayNotificationSettings(),
        bindings_loader=missing_gateway,
    ).send(_request())

    assert result.status == "failed"
    assert result.reason == "gateway_unavailable"
    assert result.error_message == "Notification gateway is unavailable."
    assert "secret-topic" not in (result.error_message or "")


def test_adapter_sanitizes_gateway_dispatch_exception() -> None:
    dispatcher = FakeGatewayDispatcher(
        error=OSError("Authorization https://ntfy.example/secret-topic")
    )
    adapter = NotificationGatewayAdapter(
        GatewayNotificationSettings(
            ntfy_enabled=True,
            ntfy_topic="secret-topic",
        ),
        bindings_loader=lambda: _bindings(dispatcher),
    )

    result = adapter.send(_request())

    assert result.status == "failed"
    assert result.reason == "gateway_error"
    assert result.error_message == "Notification gateway failed."
    assert "secret-topic" not in (result.error_message or "")
    assert "https://" not in (result.error_message or "")
    assert "Authorization" not in (result.error_message or "")


def test_adapter_resanitizes_failed_gateway_result() -> None:
    dispatcher = FakeGatewayDispatcher(
        result=FakeGatewayResult(
            event_id="evt-n3a",
            status="failed",
            reason="transport_error",
            success=False,
            status_code=503,
            error_message="Authorization https://ntfy.example/secret-topic",
        )
    )
    adapter = NotificationGatewayAdapter(
        GatewayNotificationSettings(),
        bindings_loader=lambda: _bindings(dispatcher),
    )

    result = adapter.send(_request())

    assert result.status == "failed"
    assert result.reason == "transport_error"
    assert result.status_code == 503
    assert result.error_message == "Notification delivery failed."


def test_adapter_preserves_non_delivery_status_without_error_message() -> None:
    dispatcher = FakeGatewayDispatcher(
        result=FakeGatewayResult(
            event_id="evt-n3a",
            status="filtered",
            reason="quiet_hours",
            success=False,
            status_code=None,
        )
    )
    adapter = NotificationGatewayAdapter(
        GatewayNotificationSettings(),
        bindings_loader=lambda: _bindings(dispatcher),
    )

    result = adapter.send(_request())

    assert result.status == "filtered"
    assert not result.success
    assert result.reason == "quiet_hours"
    assert result.error_message is None


def test_adapter_rejects_mismatched_event_id() -> None:
    dispatcher = FakeGatewayDispatcher(result=FakeGatewayResult(event_id="wrong-event"))
    adapter = NotificationGatewayAdapter(
        GatewayNotificationSettings(),
        bindings_loader=lambda: _bindings(dispatcher),
    )

    result = adapter.send(_request())

    assert result.status == "failed"
    assert result.reason == "invalid_response"
