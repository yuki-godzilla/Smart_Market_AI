"""Thin UI-side adapters for explicit notification-producing user actions."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from backend.notifications.events import (
    ResearchCompletionEvent,
    ResearchCompletionNotificationPublisher,
    ResearchCompletionPublishResult,
)
from backend.notifications.history_repository import NotificationHistoryRepository
from backend.notifications.settings_repository import NotificationSettingsRepository
from backend.research.contracts import CompanyResearchReport

ResearchCompletionPublisher = Callable[[ResearchCompletionEvent], ResearchCompletionPublishResult]
LOGGER = logging.getLogger(__name__)


def publish_cockpit_research_completion(
    *,
    user_id: str,
    report: CompanyResearchReport | None,
    occurred_at: datetime | None = None,
    publish: ResearchCompletionPublisher | None = None,
) -> ResearchCompletionPublishResult:
    """Publish only a report produced by an explicit Cockpit refresh action."""

    if not isinstance(report, CompanyResearchReport):
        return ResearchCompletionPublishResult("skipped", "report_unavailable")
    event = ResearchCompletionEvent.from_report(
        user_id=user_id,
        report=report,
        occurred_at=occurred_at,
    )
    publisher = (
        publish
        or ResearchCompletionNotificationPublisher(
            NotificationHistoryRepository(),
            NotificationSettingsRepository(),
        ).publish
    )
    result = publisher(event)
    if result.status == "failed":
        LOGGER.warning(
            "Cockpit research completion notification was not recorded: %s",
            result.reason,
        )
    return result


def publish_research_completion(
    session_state: object,
    report: CompanyResearchReport | None,
) -> ResearchCompletionPublishResult:
    """Publish from the active Streamlit user without exposing session details to backend code."""

    session_get = getattr(session_state, "get", None)
    user_id = session_get("smai_current_user_id") if callable(session_get) else None
    return publish_cockpit_research_completion(
        user_id=str(user_id or "default"),
        report=report,
    )
