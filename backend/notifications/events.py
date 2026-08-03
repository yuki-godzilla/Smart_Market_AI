"""Event-specific notification publishers for explicit SMAI operations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Callable, Literal

from backend.notifications.delivery import configured_notification_client
from backend.notifications.history_repository import AppNotification, NotificationHistoryRepository
from backend.notifications.notification_client import NotificationClient
from backend.notifications.producer import CatalogNotificationProducer
from backend.notifications.settings_repository import (
    NotificationSettingsError,
    NotificationSettingsRepository,
)
from backend.reporting import AssistantDecisionReportArchiveResult, DecisionReportContext
from backend.research.contracts import CompanyResearchReport

ResearchCompletionPublishStatus = Literal["created", "skipped", "failed"]
NotificationClientFactory = Callable[[str], NotificationClient | None]


@dataclass(frozen=True, slots=True)
class ResearchCompletionEvent:
    """Bounded, user-scoped facts from one explicit Cockpit Research refresh."""

    user_id: str
    symbol: str
    as_of: date
    schema_version: str
    document_count: int
    evidence_count: int
    result_fingerprint: str
    occurred_at: datetime

    @classmethod
    def from_report(
        cls,
        *,
        user_id: str,
        report: CompanyResearchReport,
        occurred_at: datetime | None = None,
    ) -> "ResearchCompletionEvent":
        symbol = report.symbol.strip().upper()
        evidence_keys = sorted(
            f"{evidence.document_id}:{evidence.chunk_id}" for evidence in report.evidence
        )
        fingerprint_payload = "|".join(
            (
                report.schema_version,
                symbol,
                report.as_of.isoformat(),
                str(report.data_quality.document_count),
                str(report.data_quality.evidence_count),
                *evidence_keys,
            )
        )
        return cls(
            user_id=user_id,
            symbol=symbol,
            as_of=report.as_of,
            schema_version=report.schema_version,
            document_count=report.data_quality.document_count,
            evidence_count=report.data_quality.evidence_count,
            result_fingerprint=hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()[:24],
            occurred_at=occurred_at or datetime.now(UTC),
        )

    @property
    def dedupe_key(self) -> str:
        return (
            "research-complete:"
            f"{self.user_id}:{self.symbol}:{self.schema_version}:"
            f"{self.as_of.isoformat()}:{self.result_fingerprint}"
        )

    @property
    def catalog_values(self) -> dict[str, str]:
        return {
            "symbol": self.symbol,
            "detail": (
                f"根拠候補 {self.evidence_count}件、"
                f"資料 {self.document_count}件を確認できます。"
            ),
        }


@dataclass(frozen=True, slots=True)
class ResearchCompletionPublishResult:
    status: ResearchCompletionPublishStatus
    reason: str
    item: AppNotification | None = None


class ResearchCompletionNotificationPublisher:
    """Publish one completed manual Research refresh without affecting that refresh."""

    def __init__(
        self,
        history: NotificationHistoryRepository,
        settings: NotificationSettingsRepository,
        *,
        client_factory: NotificationClientFactory | None = None,
    ) -> None:
        self._history = history
        self._settings = settings
        self._client_factory = client_factory or (
            lambda user_id: configured_notification_client(self._settings, user_id)
        )

    def publish(self, event: ResearchCompletionEvent) -> ResearchCompletionPublishResult:
        if event.user_id == "default":
            return ResearchCompletionPublishResult("skipped", "default_user")
        try:
            item = CatalogNotificationProducer(self._history, self._settings).produce(
                "smai_analysis_complete",
                user_id=event.user_id,
                values=event.catalog_values,
                dedupe_key=event.dedupe_key,
                client=self._client_factory(event.user_id),
                now=event.occurred_at,
                source="cockpit_manual_research",
            )
        except NotificationSettingsError:
            return ResearchCompletionPublishResult("failed", "notification_storage_unavailable")
        except Exception:
            return ResearchCompletionPublishResult("failed", "notification_publish_failed")
        if item is None:
            return ResearchCompletionPublishResult("skipped", "disabled_or_duplicate")
        return ResearchCompletionPublishResult("created", "ok", item)


@dataclass(frozen=True, slots=True)
class ReportArtifactCompletionEvent:
    """Bounded facts from one successfully persisted Assistant Report artifact."""

    user_id: str
    draft_id: str
    subject: str
    symbol: str | None
    report_schema_version: str
    section_count: int
    source_count: int
    content_fingerprint: str
    occurred_at: datetime

    @classmethod
    def from_archive(
        cls,
        *,
        user_id: str,
        context: DecisionReportContext,
        archive: AssistantDecisionReportArchiveResult,
        occurred_at: datetime | None = None,
    ) -> "ReportArtifactCompletionEvent":
        entry = archive.entry
        symbol = _normalized_optional_symbol(entry.get("symbol"))
        fingerprint = str(entry.get("markdown_sha256", "")).strip()
        if not fingerprint:
            fingerprint = hashlib.sha256(archive.draft_id.encode("utf-8")).hexdigest()
        return cls(
            user_id=user_id,
            draft_id=archive.draft_id,
            subject=symbol or "Decision Report",
            symbol=symbol,
            report_schema_version=context.schema_version,
            section_count=len(context.sections),
            source_count=_nonnegative_int(entry.get("source_count")),
            content_fingerprint=fingerprint,
            occurred_at=occurred_at or datetime.now(UTC),
        )

    @property
    def dedupe_key(self) -> str:
        return (
            "report-artifact:"
            f"{self.user_id}:{self.report_schema_version}:{self.content_fingerprint}"
        )

    @property
    def catalog_values(self) -> dict[str, str]:
        details = [f"セクション {self.section_count}件"]
        if self.source_count:
            details.append(f"確認材料 {self.source_count}件")
        return {
            "subject": self.subject,
            "symbol": self.symbol or "",
            "detail": "、".join(details) + "を保存しました。",
        }


@dataclass(frozen=True, slots=True)
class ReportArtifactCompletionPublishResult:
    status: ResearchCompletionPublishStatus
    reason: str
    item: AppNotification | None = None


class ReportArtifactCompletionNotificationPublisher:
    """Publish a saved Assistant Report without changing archive success semantics."""

    def __init__(
        self,
        history: NotificationHistoryRepository,
        settings: NotificationSettingsRepository,
        *,
        client_factory: NotificationClientFactory | None = None,
    ) -> None:
        self._history = history
        self._settings = settings
        self._client_factory = client_factory or (
            lambda user_id: configured_notification_client(self._settings, user_id)
        )

    def publish(
        self, event: ReportArtifactCompletionEvent
    ) -> ReportArtifactCompletionPublishResult:
        if event.user_id == "default":
            return ReportArtifactCompletionPublishResult("skipped", "default_user")
        try:
            item = CatalogNotificationProducer(self._history, self._settings).produce(
                "smai_report_ready",
                user_id=event.user_id,
                values=event.catalog_values,
                dedupe_key=event.dedupe_key,
                client=self._client_factory(event.user_id),
                now=event.occurred_at,
                source="assistant_report_archive",
            )
        except NotificationSettingsError:
            return ReportArtifactCompletionPublishResult(
                "failed", "notification_storage_unavailable"
            )
        except Exception:
            return ReportArtifactCompletionPublishResult("failed", "notification_publish_failed")
        if item is None:
            return ReportArtifactCompletionPublishResult("skipped", "disabled_or_duplicate")
        return ReportArtifactCompletionPublishResult("created", "ok", item)


def _normalized_optional_symbol(value: object) -> str | None:
    symbol = str(value or "").strip().upper()
    return symbol or None


def _nonnegative_int(value: object) -> int:
    if not isinstance(value, (int, str)):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
