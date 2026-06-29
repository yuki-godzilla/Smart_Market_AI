import sqlite3
from datetime import UTC, datetime

from backend.notifications.content_models import NotificationContent
from backend.notifications.content_renderer import render_in_app, render_ntfy
from backend.notifications.history_repository import (
    AppNotification,
    NotificationHistoryRepository,
)
from backend.notifications.notification_client import (
    NotificationClientResult,
    NotificationRequest,
)
from backend.notifications.notification_service import NotificationService


class RecordingClient:
    def __init__(self, repository: NotificationHistoryRepository) -> None:
        self.repository = repository
        self.saved_before_send = False
        self.calls = 0

    def send(self, request: NotificationRequest) -> NotificationClientResult:
        self.calls += 1
        self.saved_before_send = bool(self.repository.list(request.user_id))
        return NotificationClientResult(
            event_id=request.event_id,
            status="failed",
            success=False,
            reason="transport_error",
            error_message="secret topic full URL",
        )


def _item(event_id: str, user_id: str = "yuki") -> AppNotification:
    return AppNotification(
        event_id=event_id,
        user_id=user_id,
        technical_category="SYSTEM",
        presentation_category="SYSTEM",
        severity="high",
        title="通知",
        summary="確認してください。",
        created_at=datetime.now(UTC),
    )


def test_history_migrates_v1_without_losing_settings(tmp_path) -> None:
    from backend.notifications.settings_repository import (
        NotificationSettingsRepository,
    )

    path = tmp_path / "notifications.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE notification_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO notification_meta VALUES ('schema_version', '1')")
        connection.execute(
            """CREATE TABLE notification_settings (
            user_id TEXT PRIMARY KEY, app_enabled INTEGER NOT NULL,
            ntfy_enabled INTEGER NOT NULL, ntfy_server_url TEXT NOT NULL,
            ntfy_topic TEXT, severity_threshold TEXT NOT NULL,
            quiet_hours_enabled INTEGER NOT NULL, quiet_hours_start TEXT,
            quiet_hours_end TEXT, updated_at TEXT NOT NULL)"""
        )
        connection.execute(
            """INSERT INTO notification_settings VALUES
            ('yuki', 1, 0, 'https://ntfy.sh', 'secret', 'medium', 0, NULL, NULL, ?)""",
            (datetime.now(UTC).isoformat(),),
        )
    settings = NotificationSettingsRepository(path)
    history = NotificationHistoryRepository(str(path))

    assert history.save(_item("evt-1"))
    assert settings.load("yuki").ntfy_topic == "secret"


def test_renderers_keep_channel_content_small_and_safe() -> None:
    request = NotificationRequest(
        event_id="evt-render",
        user_id="yuki",
        event_type="test",
        category="SYSTEM",
        severity="medium",
        title="test",
        message="test",
        symbol="NVDA",
        metadata={"topic": "secret"},
    )
    content = NotificationContent(
        presentation_category="SYSTEM",
        icon_key="bell",
        headline="確認通知",
        summary="確認しました。",
        what_happened="AI総合が変化しました。",
        next_check="根拠資料",
    )

    assert render_in_app(content).title == "確認通知"
    ntfy = render_ntfy(request, content)
    assert ntfy.title == "SMAI"
    assert "NVDA" in ntfy.body
    assert "secret" not in ntfy.body


def test_history_dedupes_filters_and_updates_state(tmp_path) -> None:
    repository = NotificationHistoryRepository(str(tmp_path / "notifications.sqlite"))
    assert repository.save(_item("evt-1"))
    assert not repository.save(_item("evt-1"))
    repository.save(_item("evt-2", "family"))

    assert repository.unread_count("yuki") == 1
    repository.mark_read("yuki", "evt-1")
    assert len(repository.list("yuki", state="read")) == 1
    repository.archive("yuki", "evt-1")
    assert len(repository.list("yuki", state="archived")) == 1
    assert repository.list("family")[0].event_id == "evt-2"
    assert repository.list("family", severity="high")[0].event_id == "evt-2"
    assert repository.list("family", severity="low") == []


def test_service_saves_before_failed_delivery_and_sanitizes_result(tmp_path) -> None:
    repository = NotificationHistoryRepository(str(tmp_path / "notifications.sqlite"))
    client = RecordingClient(repository)
    request = NotificationRequest(
        event_id="evt-service",
        user_id="yuki",
        event_type="test",
        category="SYSTEM",
        severity="medium",
        title="test",
        message="test",
    )
    _, result = NotificationService(repository).create(
        request,
        NotificationContent(
            presentation_category="SYSTEM",
            icon_key="bell",
            headline="test",
            summary="test",
            what_happened="test",
        ),
        client=client,
    )

    assert client.calls == 1
    assert client.saved_before_send
    assert result is not None and result.status == "failed"
    assert repository.unread_count("yuki") == 1


def test_service_keeps_history_when_client_raises(tmp_path) -> None:
    class RaisingClient:
        def send(self, request: NotificationRequest) -> NotificationClientResult:
            raise OSError("topic https://ntfy.example/secret")

    repository = NotificationHistoryRepository(str(tmp_path / "notifications.sqlite"))
    request = NotificationRequest(
        event_id="evt-raise",
        user_id="yuki",
        event_type="test",
        category="SYSTEM",
        severity="medium",
        title="test",
        message="test",
    )
    _, result = NotificationService(repository).create(
        request,
        NotificationContent(
            presentation_category="SYSTEM",
            icon_key="bell",
            headline="test",
            summary="test",
            what_happened="test",
        ),
        client=RaisingClient(),
    )

    assert repository.unread_count("yuki") == 1
    assert result is not None
    assert result.error_message == "Notification delivery failed."
