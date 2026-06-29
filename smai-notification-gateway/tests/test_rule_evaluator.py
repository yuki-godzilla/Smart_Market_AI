from datetime import datetime

import pytest

from notification_gateway.models import (
    DeliveryReason,
    DeliveryStatus,
    NotificationCategory,
    NotificationEvent,
    Severity,
    UserNotificationSetting,
)
from notification_gateway.rules.evaluator import evaluate_ntfy_delivery


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
    severity_threshold: Severity = Severity.MEDIUM,
    quiet_hours_enabled: bool = False,
    quiet_hours_start: str | None = None,
    quiet_hours_end: str | None = None,
) -> UserNotificationSetting:
    return UserNotificationSetting(
        user_id="yuki",
        ntfy_enabled=ntfy_enabled,
        ntfy_topic="secret-topic",
        severity_threshold=severity_threshold,
        quiet_hours_enabled=quiet_hours_enabled,
        quiet_hours_start=quiet_hours_start,
        quiet_hours_end=quiet_hours_end,
    )


@pytest.mark.parametrize(
    ("severity", "expected"),
    [
        (Severity.CRITICAL, True),
        (Severity.HIGH, True),
        (Severity.MEDIUM, True),
        (Severity.LOW, False),
        (Severity.SILENT, False),
    ],
)
def test_severity_order_and_silent_rule(severity: Severity, expected: bool) -> None:
    decision = evaluate_ntfy_delivery(
        _event(severity),
        _setting(),
        now=datetime(2026, 6, 29, 12, 0),
    )

    assert decision.should_send is expected
    if severity is Severity.SILENT:
        assert decision.status is DeliveryStatus.SKIPPED
        assert decision.reason is DeliveryReason.SILENT
    elif not expected:
        assert decision.status is DeliveryStatus.FILTERED
        assert decision.reason is DeliveryReason.BELOW_SEVERITY_THRESHOLD


@pytest.mark.parametrize(
    ("hour", "expected"),
    [(21, True), (22, False), (23, False), (0, False), (6, False), (7, True)],
)
def test_quiet_hours_cross_midnight(hour: int, expected: bool) -> None:
    decision = evaluate_ntfy_delivery(
        _event(Severity.HIGH),
        _setting(
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
        ),
        now=datetime(2026, 6, 29, hour, 0),
    )

    assert decision.should_send is expected
    if not expected:
        assert decision.reason is DeliveryReason.QUIET_HOURS


def test_disabled_setting_is_distinct_from_filtered() -> None:
    decision = evaluate_ntfy_delivery(
        _event(Severity.HIGH),
        _setting(ntfy_enabled=False),
        now=datetime(2026, 6, 29, 12, 0),
    )

    assert decision.status is DeliveryStatus.DISABLED
    assert decision.reason is DeliveryReason.CHANNEL_DISABLED
