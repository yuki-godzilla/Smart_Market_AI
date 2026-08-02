from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from backend.notifications.events import (
    ResearchCompletionEvent,
    ResearchCompletionNotificationPublisher,
    ResearchCompletionPublishResult,
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
from backend.research.contracts import (
    CompanyResearchReport,
    ResearchDataQuality,
    ResearchEvidence,
    ResearchSummaryPoint,
)
from ui.notification_events import publish_cockpit_research_completion, publish_research_completion


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


def _report(*, chunk_id: str = "chunk-1") -> CompanyResearchReport:
    evidence = ResearchEvidence(
        symbol="NVDA",
        document_id="doc-1",
        chunk_id=chunk_id,
        title="Quarterly results",
        source_type="earnings_report",
        excerpt="Revenue and product demand were discussed in the quarterly materials.",
        relevance_score=Decimal("0.8"),
        reliability=Decimal("0.9"),
    )
    return CompanyResearchReport(
        symbol="nvda",
        as_of=date(2026, 8, 3),
        summary="確認材料を整理しました。",
        points=[
            ResearchSummaryPoint(
                category="growth",
                label="成長材料",
                summary="決算資料を確認します。",
                evidence=[evidence],
            )
        ],
        evidence=[evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            document_count=1,
            evidence_count=1,
        ),
    )


def test_research_completion_publisher_saves_before_opt_in_delivery_and_dedupes(tmp_path) -> None:
    path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(path)
    settings.save(NotificationSetting(user_id="yuki"))
    history = NotificationHistoryRepository(str(path))
    client = RecordingClient(history)
    publisher = ResearchCompletionNotificationPublisher(
        history,
        settings,
        client_factory=lambda _user_id: client,
    )
    event = ResearchCompletionEvent.from_report(
        user_id="yuki",
        report=_report(),
        occurred_at=datetime(2026, 8, 3, 9, 0, tzinfo=UTC),
    )

    first = publisher.publish(event)
    duplicate = publisher.publish(event)

    assert first.status == "created"
    assert duplicate.status == "skipped"
    assert client.history_exists_before_send
    assert len(client.requests) == 1
    assert client.requests[0].source == "cockpit_manual_research"
    saved = history.list("yuki")
    assert len(saved) == 1
    assert saved[0].symbol == "NVDA"
    assert saved[0].summary == "NVDAの確認材料を整理しました。"
    assert saved[0].metadata is not None
    assert saved[0].metadata["what_happened"] == "根拠候補 1件、資料 1件を確認できます。"


def test_research_completion_event_changes_dedupe_key_when_evidence_changes() -> None:
    first = ResearchCompletionEvent.from_report(user_id="yuki", report=_report(chunk_id="one"))
    second = ResearchCompletionEvent.from_report(user_id="yuki", report=_report(chunk_id="two"))

    assert first.dedupe_key != second.dedupe_key


def test_research_completion_publisher_respects_default_user_and_category_setting(tmp_path) -> None:
    path = tmp_path / "notifications.sqlite"
    settings = NotificationSettingsRepository(path)
    history = NotificationHistoryRepository(str(path))
    publisher = ResearchCompletionNotificationPublisher(history, settings)
    default_event = ResearchCompletionEvent.from_report(user_id="default", report=_report())

    assert publisher.publish(default_event).reason == "default_user"
    assert history.list("default") == []

    settings.save(NotificationSetting(user_id="yuki", enabled_categories=("FAVORITE",)))
    blocked_event = ResearchCompletionEvent.from_report(user_id="yuki", report=_report())
    assert publisher.publish(blocked_event).status == "skipped"
    assert history.list("yuki") == []


def test_ui_adapter_only_publishes_a_report_from_the_explicit_action() -> None:
    published: list[ResearchCompletionEvent] = []

    def record(event: ResearchCompletionEvent) -> ResearchCompletionPublishResult:
        published.append(event)
        return ResearchCompletionPublishResult("created", "ok")

    no_report = publish_cockpit_research_completion(
        user_id="yuki",
        report=None,
        publish=record,
    )
    completed = publish_cockpit_research_completion(
        user_id="yuki",
        report=_report(),
        publish=record,
    )

    assert no_report.reason == "report_unavailable"
    assert completed.status == "created"
    assert len(published) == 1
    assert published[0].user_id == "yuki"
    assert published[0].symbol == "NVDA"


def test_ui_adapter_reads_only_the_active_user_identifier() -> None:
    state = {"smai_current_user_id": "yuki", "unrelated": "not-for-notification"}

    result = publish_research_completion(state, None)

    assert result.reason == "report_unavailable"
