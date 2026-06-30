from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Mapping

from backend.notifications.catalog import get_notification_template
from backend.notifications.content_models import NotificationAction, NotificationContent
from backend.notifications.history_repository import AppNotification, NotificationHistoryRepository
from backend.notifications.notification_client import NotificationClient, NotificationRequest
from backend.notifications.notification_service import NotificationService
from backend.notifications.settings_repository import NotificationSettingsRepository


class CatalogNotificationProducer:
    def __init__(
        self,
        history: NotificationHistoryRepository,
        settings: NotificationSettingsRepository,
    ) -> None:
        self.history = history
        self.settings = settings

    def produce(
        self,
        template_id: str,
        *,
        user_id: str,
        values: Mapping[str, str] | None = None,
        dedupe_key: str | None = None,
        client: NotificationClient | None = None,
        now: datetime | None = None,
    ) -> AppNotification | None:
        if user_id == "default":
            return None
        template = get_notification_template(template_id)
        setting = self.settings.load(user_id)
        if (
            not setting.app_enabled
            or template.presentation_category not in setting.enabled_categories
        ):
            return None
        data = dict(template.sample_data)
        data.update(values or {})
        created_at = now or datetime.now(UTC)
        stable_key = dedupe_key or f"{template_id}:{user_id}:{created_at.date().isoformat()}"
        event_id = "catalog-" + sha256(stable_key.encode("utf-8")).hexdigest()[:24]
        if self.history.get(user_id, event_id) is not None:
            return None
        title = template.title_template.format_map(_SafeFormat(data))
        summary = template.summary_template.format_map(_SafeFormat(data))
        detail = data.get("detail", summary)
        content = NotificationContent(
            template_id=template.template_id,
            presentation_category=template.presentation_category,
            icon_key=template.presentation_category.lower(),
            headline=title,
            summary=summary,
            what_happened=detail,
            why_it_matters="確認材料に変化があるため、関連画面で背景を確認してください。",
            smai_assessment="SMAIの確認候補です。売買判断ではありません。",
            next_check=template.cta_label,
            cta=NotificationAction(template.cta_label, template.cta_page, data.get("symbol")),
            icon_asset_id=template.icon_asset_id,
            thumbnail_asset_id=template.thumbnail_asset_id,
            hero_asset_id=template.hero_asset_id,
            content_version=template.content_version,
        )
        request = NotificationRequest(
            event_id=event_id,
            user_id=user_id,
            event_type=template.template_id,
            category=template.technical_category,
            severity=template.default_severity,
            title=title,
            message=summary,
            symbol=data.get("symbol"),
            source="notification_catalog",
            action_url=f"?page={template.cta_page}",
            metadata={
                "template_id": template.template_id,
                "dedupe_key": stable_key,
                "what_happened": content.what_happened,
                "why_it_matters": content.why_it_matters or "",
                "smai_assessment": content.smai_assessment or "",
                "next_check": content.next_check or "",
            },
            created_at=created_at,
        )
        item, _ = NotificationService(self.history).create(request, content, client=client)
        return item


class _SafeFormat(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
