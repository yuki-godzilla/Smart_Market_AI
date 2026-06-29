from __future__ import annotations

from dataclasses import dataclass

from backend.notifications.content_models import NotificationContent
from backend.notifications.notification_client import NotificationRequest


@dataclass(frozen=True, slots=True)
class InAppNotificationView:
    icon_key: str
    title: str
    summary: str
    assessment: str | None
    next_check: str | None
    cta_label: str | None


@dataclass(frozen=True, slots=True)
class NtfyNotificationView:
    title: str
    body: str


def render_in_app(content: NotificationContent) -> InAppNotificationView:
    return InAppNotificationView(
        icon_key=content.icon_key,
        title=content.headline,
        summary=content.summary,
        assessment=content.smai_assessment,
        next_check=content.next_check,
        cta_label=content.cta.label if content.cta else None,
    )


def render_ntfy(request: NotificationRequest, content: NotificationContent) -> NtfyNotificationView:
    target = request.symbol or content.presentation_category
    lines = [target, content.what_happened]
    if content.next_check:
        lines.append(f"次に見る: {content.next_check}")
    return NtfyNotificationView(title="SMAI", body="\n".join(lines)[:400])
