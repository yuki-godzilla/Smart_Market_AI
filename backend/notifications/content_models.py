from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PresentationCategory = Literal[
    "FAVORITE", "MARKET_TREND", "INVESTMENT_NEWS", "SMAI_INSIGHT", "SYSTEM"
]


@dataclass(frozen=True, slots=True)
class NotificationMetric:
    label: str
    value: str
    previous_value: str | None = None
    direction: str | None = None


@dataclass(frozen=True, slots=True)
class NotificationAction:
    label: str
    page: str
    symbol: str | None = None


@dataclass(frozen=True, slots=True)
class NotificationContent:
    presentation_category: PresentationCategory
    icon_key: str
    headline: str
    summary: str
    what_happened: str
    why_it_matters: str | None = None
    smai_assessment: str | None = None
    next_check: str | None = None
    metrics: tuple[NotificationMetric, ...] = ()
    cta: NotificationAction | None = None
    content_version: str = "notification_content.v1"
