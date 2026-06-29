from __future__ import annotations

from backend.notifications.content_models import NotificationContent
from backend.notifications.history_repository import AppNotification, NotificationHistoryRepository
from backend.notifications.notification_client import (
    NotificationClient,
    NotificationClientResult,
    NotificationRequest,
)
from backend.notifications.settings_repository import NotificationSettingsError


class NotificationService:
    def __init__(self, repository: NotificationHistoryRepository) -> None:
        self.repository = repository

    def create(
        self,
        request: NotificationRequest,
        content: NotificationContent,
        *,
        client: NotificationClient | None = None,
    ) -> tuple[AppNotification, NotificationClientResult | None]:
        metadata = dict(request.metadata)
        asset_references = {
            "icon_asset_id": content.icon_asset_id,
            "thumbnail_asset_id": content.thumbnail_asset_id,
            "hero_asset_id": content.hero_asset_id,
        }
        metadata.update({key: value for key, value in asset_references.items() if value})
        item = AppNotification(
            event_id=request.event_id,
            user_id=request.user_id,
            technical_category=request.category,
            presentation_category=content.presentation_category,
            severity=request.severity,
            title=content.headline,
            summary=content.summary,
            symbol=request.symbol,
            source=request.source,
            action_url=request.action_url,
            metadata=metadata,
            content_version=content.content_version,
            created_at=request.created_at,
        )
        if not self.repository.save(item):
            return item, None
        result = None
        if client is not None:
            try:
                result = client.send(request)
            except Exception:
                result = NotificationClientResult(
                    event_id=request.event_id,
                    status="failed",
                    success=False,
                    reason="client_error",
                    error_message="Notification delivery failed.",
                )
            try:
                self.repository.save_delivery(result)
            except NotificationSettingsError:
                pass
        return item, result


def test_notification_content() -> NotificationContent:
    return NotificationContent(
        presentation_category="SYSTEM",
        icon_key="bell",
        headline="SMAI テスト通知",
        summary="アプリ内通知の保存を確認しました。",
        what_happened="通知設定からテスト通知を実行しました。",
        next_check="通知センターとスマホ通知の受信状態を確認してください。",
        icon_asset_id="smai_navi_default",
    )
