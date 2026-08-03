from __future__ import annotations

from datetime import UTC, datetime

from backend.notifications.events import (
    ReportArtifactCompletionEvent,
    ReportArtifactCompletionNotificationPublisher,
    ReportArtifactCompletionPublishResult,
)
from backend.notifications.history_repository import NotificationHistoryRepository
from backend.notifications.notification_client import (
    NotificationClientResult,
    NotificationRequest,
)
from backend.notifications.settings_repository import (
    NotificationSetting,
    NotificationSettingsRepository,
)
from backend.reporting import (
    archive_assistant_decision_report_draft,
    build_decision_report_context,
    build_report_section,
)
from ui.notification_events import publish_assistant_report_artifact_completion


class RecordingClient:
    def __init__(self, history: NotificationHistoryRepository) -> None:
        self.history = history
        self.requests: list[NotificationRequest] = []
        self.history_exists_before_send = False

    def send(self, request: NotificationRequest) -> NotificationClientResult:
        self.requests.append(request)
        self.history_exists_before_send = (
            self.history.get(request.user_id, request.event_id) is not None
        )
        return NotificationClientResult(
            event_id=request.event_id,
            status="sent",
            success=True,
            reason="ok",
        )


def _context(*, title: str = "Decision Report: NVDA"):
    return build_decision_report_context(
        title=title,
        sections=[
            build_report_section(
                title="確認材料",
                source_kind="research",
                symbol="nvda",
                summary={"summary": "確認済み資料を整理しました。"},
            )
        ],
        created_at=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
    )


def _archive(
    tmp_path,
    *,
    markdown: str = "# NVDA\n\n確認材料を保存しました。\n",
    include_zip: bool = True,
):
    return archive_assistant_decision_report_draft(
        _context(),
        tmp_path,
        markdown=markdown,
        include_zip=include_zip,
        archived_at=datetime(2026, 8, 3, 10, 5, tzinfo=UTC),
    )


def test_report_artifact_publisher_saves_before_delivery_and_dedupes(tmp_path) -> None:
    database_path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(database_path)
    settings.save(NotificationSetting(user_id="yuki"))
    history = NotificationHistoryRepository(str(database_path))
    client = RecordingClient(history)
    publisher = ReportArtifactCompletionNotificationPublisher(
        history,
        settings,
        client_factory=lambda _user_id: client,
    )
    archive = _archive(tmp_path / "reports")
    event = ReportArtifactCompletionEvent.from_archive(
        user_id="yuki",
        context=_context(),
        archive=archive,
        occurred_at=datetime(2026, 8, 3, 10, 6, tzinfo=UTC),
    )

    first = publisher.publish(event)
    duplicate = publisher.publish(event)

    assert first.status == "created"
    assert duplicate.status == "skipped"
    assert client.history_exists_before_send
    assert len(client.requests) == 1
    assert client.requests[0].source == "assistant_report_archive"
    assert client.requests[0].symbol == "NVDA"
    assert str(archive.markdown_path) not in str(client.requests[0].metadata)
    saved = history.list("yuki")
    assert len(saved) == 1
    assert saved[0].summary == "NVDAのレポートを保存しました。"
    assert saved[0].metadata is not None
    assert saved[0].metadata["what_happened"] == "セクション 1件を保存しました。"
    assert str(archive.markdown_path) not in str(saved[0].metadata)


def test_report_artifact_event_changes_when_sanitized_content_changes(tmp_path) -> None:
    first = ReportArtifactCompletionEvent.from_archive(
        user_id="yuki",
        context=_context(),
        archive=_archive(tmp_path / "one", markdown="# NVDA\n\nfirst\n"),
    )
    second = ReportArtifactCompletionEvent.from_archive(
        user_id="yuki",
        context=_context(),
        archive=_archive(tmp_path / "two", markdown="# NVDA\n\nsecond\n"),
    )

    assert first.dedupe_key != second.dedupe_key


def test_report_artifact_publisher_respects_default_and_category_setting(tmp_path) -> None:
    database_path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(database_path)
    history = NotificationHistoryRepository(str(database_path))
    archive = _archive(tmp_path / "reports")
    default_event = ReportArtifactCompletionEvent.from_archive(
        user_id="default",
        context=_context(),
        archive=archive,
    )
    publisher = ReportArtifactCompletionNotificationPublisher(history, settings)

    assert publisher.publish(default_event).reason == "default_user"
    assert history.list("default") == []

    settings.save(NotificationSetting(user_id="yuki", enabled_categories=("FAVORITE",)))
    disabled_event = ReportArtifactCompletionEvent.from_archive(
        user_id="yuki",
        context=_context(),
        archive=archive,
    )
    assert publisher.publish(disabled_event).status == "skipped"
    assert history.list("yuki") == []


def test_ui_adapter_only_publishes_a_completed_archive(tmp_path) -> None:
    context = _context()
    archive = _archive(tmp_path / "reports")
    published: list[ReportArtifactCompletionEvent] = []

    def record(event: ReportArtifactCompletionEvent) -> ReportArtifactCompletionPublishResult:
        published.append(event)
        return ReportArtifactCompletionPublishResult("created", "ok")

    unavailable = publish_assistant_report_artifact_completion(
        {"smai_current_user_id": "yuki"},
        context,
        None,
        publish=record,
    )
    completed = publish_assistant_report_artifact_completion(
        {"smai_current_user_id": "yuki", "unrelated": "not-for-notification"},
        context,
        archive,
        publish=record,
    )

    assert unavailable.reason == "archive_unavailable"
    assert completed.status == "created"
    assert len(published) == 1
    assert published[0].user_id == "yuki"
    assert published[0].symbol == "NVDA"


def test_ui_adapter_skips_an_archive_without_its_zip_artifact(tmp_path) -> None:
    published: list[ReportArtifactCompletionEvent] = []

    def record(event: ReportArtifactCompletionEvent) -> ReportArtifactCompletionPublishResult:
        published.append(event)
        return ReportArtifactCompletionPublishResult("created", "ok")

    result = publish_assistant_report_artifact_completion(
        {"smai_current_user_id": "yuki"},
        _context(),
        _archive(tmp_path / "reports", include_zip=False),
        publish=record,
    )

    assert result.reason == "archive_unavailable"
    assert published == []
