from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class NotificationCategory(str, Enum):
    MARKET = "MARKET"
    RESEARCH = "RESEARCH"
    NEWS = "NEWS"
    SYSTEM = "SYSTEM"
    MY_RADAR = "MY_RADAR"
    AI_SCORE = "AI_SCORE"
    PRICE_ALERT = "PRICE_ALERT"
    DATA_REFRESH = "DATA_REFRESH"
    LLM = "LLM"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SILENT = "silent"


class DeliveryStatus(str, Enum):
    SKIPPED = "skipped"
    DISABLED = "disabled"
    FILTERED = "filtered"
    SENT = "sent"
    FAILED = "failed"


class DeliveryReason(str, Enum):
    SENT = "sent"
    SILENT = "silent"
    CHANNEL_DISABLED = "channel_disabled"
    TOPIC_NOT_CONFIGURED = "topic_not_configured"
    BELOW_SEVERITY_THRESHOLD = "below_severity_threshold"
    QUIET_HOURS = "quiet_hours"
    TRANSPORT_ERROR = "transport_error"
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"


@dataclass(frozen=True, slots=True)
class NotificationEvent:
    user_id: str
    event_type: str
    category: NotificationCategory
    severity: Severity
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
        if not isinstance(self.category, NotificationCategory):
            object.__setattr__(self, "category", NotificationCategory(self.category))
        if not isinstance(self.severity, Severity):
            object.__setattr__(self, "severity", Severity(self.severity))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    event_id: str
    channel: str
    status: DeliveryStatus
    reason: DeliveryReason
    success: bool
    status_code: int | None = None
    error_message: str | None = None
    delivered_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, DeliveryStatus):
            object.__setattr__(self, "status", DeliveryStatus(self.status))
        if not isinstance(self.reason, DeliveryReason):
            object.__setattr__(self, "reason", DeliveryReason(self.reason))
        if self.success != (self.status is DeliveryStatus.SENT):
            raise ValueError("success must be true only when status is sent")
        if self.status is not DeliveryStatus.FAILED and self.error_message is not None:
            raise ValueError("error_message is only valid for failed delivery")


@dataclass(frozen=True, slots=True)
class UserNotificationSetting:
    user_id: str
    app_enabled: bool = True
    ntfy_enabled: bool = False
    ntfy_server_url: str = "https://ntfy.sh"
    ntfy_topic: str | None = None
    severity_threshold: Severity = Severity.MEDIUM
    quiet_hours_enabled: bool = False
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("user_id must not be blank")
        if not isinstance(self.severity_threshold, Severity):
            object.__setattr__(
                self,
                "severity_threshold",
                Severity(self.severity_threshold),
            )
        if self.quiet_hours_enabled and (
            not self.quiet_hours_start or not self.quiet_hours_end
        ):
            raise ValueError("quiet hour start and end are required when enabled")
