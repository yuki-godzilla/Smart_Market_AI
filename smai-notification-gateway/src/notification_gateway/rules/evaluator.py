from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from notification_gateway.models import (
    DeliveryReason,
    DeliveryStatus,
    NotificationEvent,
    Severity,
    UserNotificationSetting,
)

_SEVERITY_RANK = {
    Severity.SILENT: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


@dataclass(frozen=True, slots=True)
class DeliveryDecision:
    should_send: bool
    status: DeliveryStatus
    reason: DeliveryReason


def evaluate_ntfy_delivery(
    event: NotificationEvent,
    setting: UserNotificationSetting,
    *,
    now: datetime,
) -> DeliveryDecision:
    if not setting.ntfy_enabled:
        return _decision(DeliveryStatus.DISABLED, DeliveryReason.CHANNEL_DISABLED)
    if not setting.ntfy_topic or not setting.ntfy_topic.strip():
        return _decision(DeliveryStatus.DISABLED, DeliveryReason.TOPIC_NOT_CONFIGURED)
    if event.severity is Severity.SILENT:
        return _decision(DeliveryStatus.SKIPPED, DeliveryReason.SILENT)
    if _SEVERITY_RANK[event.severity] < _SEVERITY_RANK[setting.severity_threshold]:
        return _decision(
            DeliveryStatus.FILTERED,
            DeliveryReason.BELOW_SEVERITY_THRESHOLD,
        )
    if setting.quiet_hours_enabled and is_quiet_time(
        now.time(),
        start=parse_clock_time(setting.quiet_hours_start or ""),
        end=parse_clock_time(setting.quiet_hours_end or ""),
    ):
        return _decision(DeliveryStatus.FILTERED, DeliveryReason.QUIET_HOURS)
    return DeliveryDecision(
        should_send=True,
        status=DeliveryStatus.SENT,
        reason=DeliveryReason.SENT,
    )


def parse_clock_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("quiet hour must use HH:MM or HH:MM:SS") from exc


def is_quiet_time(current: time, *, start: time, end: time) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= current < end
    return current >= start or current < end


def _decision(status: DeliveryStatus, reason: DeliveryReason) -> DeliveryDecision:
    return DeliveryDecision(should_send=False, status=status, reason=reason)
