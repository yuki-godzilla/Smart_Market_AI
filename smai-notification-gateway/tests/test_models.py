from datetime import UTC, datetime

import pytest

from notification_gateway.models import (
    DeliveryReason,
    DeliveryResult,
    DeliveryStatus,
    NotificationCategory,
    NotificationEvent,
    Severity,
    UserNotificationSetting,
)


def test_notification_event_builds_with_lightweight_contracts() -> None:
    event = NotificationEvent(
        event_id="evt-1",
        user_id="yuki",
        event_type="research_completed",
        category=NotificationCategory.RESEARCH,
        severity=Severity.HIGH,
        title="AI調査完了",
        message="7203.T のAI調査が完了しました。",
        symbol="7203.T",
        metadata={"source_count": 4},
        created_at=datetime(2026, 6, 29, tzinfo=UTC),
    )

    assert event.category is NotificationCategory.RESEARCH
    assert event.severity is Severity.HIGH
    assert event.metadata == {"source_count": 4}


def test_notification_event_rejects_blank_required_text() -> None:
    with pytest.raises(ValueError, match="title"):
        NotificationEvent(
            user_id="yuki",
            event_type="test",
            category=NotificationCategory.SYSTEM,
            severity=Severity.MEDIUM,
            title=" ",
            message="message",
        )


def test_delivery_result_distinguishes_non_delivery_from_failure() -> None:
    result = DeliveryResult(
        event_id="evt-1",
        channel="ntfy",
        status=DeliveryStatus.SKIPPED,
        reason=DeliveryReason.SILENT,
        success=False,
    )

    assert result.status is DeliveryStatus.SKIPPED
    assert result.reason is DeliveryReason.SILENT
    assert result.error_message is None


def test_notification_setting_accepts_severity_threshold() -> None:
    setting = UserNotificationSetting(user_id="yuki", severity_threshold=Severity.HIGH)

    assert setting.severity_threshold is Severity.HIGH
