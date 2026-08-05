from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from backend.research.errors import ResearchDocumentError
from backend.research.external_contracts import (
    ExternalResearchFetchManifestEntry,
    ExternalResearchFetchRequest,
    ExternalResearchFetchResult,
    ExternalResearchSourceAdapter,
    ExternalResearchSourcePayload,
)
from backend.research.external_registration import (
    external_fetch_manifest_entry,
    find_registered_external_document,
    stale_external_source_warning,
    write_external_fetch_manifest,
    write_external_payload_archive,
)
from backend.research.external_registration import (
    external_payload_markdown as _external_payload_markdown,
)
from backend.research.external_registration import (
    external_source_freshness as _stock_news_freshness,
)
from backend.research.normalization import normalize_symbol
from backend.research.service import (
    ResearchDocumentRegisterRequest,
    ResearchIndexService,
    ResearchIngestionService,
)
from backend.research.source_trace import ResearchSourceTrace


class ExternalResearchFetchService:
    """Fetch external sources into the session-local Research RAG store."""

    def __init__(
        self,
        adapter: ExternalResearchSourceAdapter,
        ingestion: ResearchIngestionService,
        index: ResearchIndexService,
        *,
        cache_dir: Path | None = None,
        persist_payloads: bool = False,
    ) -> None:
        self.adapter = adapter
        self.ingestion = ingestion
        self.index = index
        self.cache_dir = cache_dir
        self.persist_payloads = persist_payloads

    def fetch_register_sources(
        self,
        request: ExternalResearchFetchRequest,
    ) -> ExternalResearchFetchResult:
        if self.adapter.requires_network and not request.allow_network:
            raise ResearchDocumentError(
                "External research fetch requires explicit network opt-in.",
                details={"provider": self.adapter.provider, "symbol": request.symbol},
            )

        fetched_at = datetime.now(UTC)
        as_of = request.as_of or fetched_at.date()
        payloads = self.adapter.fetch_sources(request)
        provider_statuses = _external_fetch_provider_statuses(self.adapter)
        entries: list[ExternalResearchFetchManifestEntry] = []
        warnings: list[str] = []
        if self.persist_payloads:
            if self.cache_dir is None:
                raise ResearchDocumentError(
                    "External research archive requires a cache directory.",
                    details={
                        "provider": self.adapter.provider,
                        "symbol": request.symbol,
                    },
                )
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        for payload in payloads:
            if not payload.source_url.strip():
                warnings.append(f"{payload.title}: source URL is missing; skipped.")
                continue
            markdown = _external_payload_markdown(payload)
            path: Path | None = None
            existing_document = (
                None
                if self.persist_payloads
                else find_registered_external_document(
                    self.ingestion.list_documents(payload.symbol),
                    self.ingestion.store.raw_text_by_document_id,
                    payload,
                )
            )
            if existing_document is not None:
                document = existing_document
            elif self.persist_payloads:
                path = self._write_payload(payload)
                document = self.ingestion.register_document(
                    ResearchDocumentRegisterRequest(
                        symbol=payload.symbol,
                        title=payload.title,
                        local_path=str(path),
                        source_type=payload.source_type,
                        company_name=payload.company_name,
                        published_at=payload.published_at,
                        reliability=payload.reliability,
                    )
                )
            else:
                document = self.ingestion.register_text_document(
                    symbol=payload.symbol,
                    title=payload.title,
                    text=markdown,
                    source_type=payload.source_type,
                    source_url=payload.source_url,
                    provider=payload.provider,
                    company_name=payload.company_name,
                    published_at=payload.published_at,
                    reliability=payload.reliability,
                )
            if document.document_id not in self.index.store.chunks_by_document_id:
                self.index.build_chunks(document.document_id)
            freshness_status = _stock_news_freshness(document.published_at, as_of=as_of)
            if freshness_status == "stale":
                warnings.append(stale_external_source_warning(document.title))
            entries.append(
                external_fetch_manifest_entry(
                    payload=payload,
                    document=document,
                    as_of=as_of,
                    retention_policy="archive" if self.persist_payloads else "session",
                    local_path=path,
                    document_hash=(document.document_hash if self.persist_payloads else None),
                )
            )

        if not entries:
            warnings.append("External fetch returned no registerable URL-backed sources.")
        warnings.extend(
            _external_fetch_provider_status_warnings(
                entries=entries,
                provider_statuses=provider_statuses,
            )
        )
        manifest_path: Path | None = None
        if self.persist_payloads:
            manifest_path = self._write_manifest(
                request=request,
                fetched_at=fetched_at,
                entries=entries,
                warnings=warnings,
            )
        return ExternalResearchFetchResult(
            symbol=normalize_symbol(request.symbol),
            provider=self.adapter.provider,
            fetched_at=fetched_at,
            entries=entries,
            retention_policy="archive" if self.persist_payloads else "session",
            manifest_path=str(manifest_path) if manifest_path is not None else None,
            warnings=warnings,
            provider_statuses=provider_statuses,
        )

    def _write_payload(self, payload: ExternalResearchSourcePayload) -> Path:
        if self.cache_dir is None:
            raise ResearchDocumentError(
                "External research archive requires a cache directory.",
                details={"provider": self.adapter.provider, "symbol": payload.symbol},
            )
        return write_external_payload_archive(self.cache_dir, payload)

    def _write_manifest(
        self,
        *,
        request: ExternalResearchFetchRequest,
        fetched_at: datetime,
        entries: list[ExternalResearchFetchManifestEntry],
        warnings: list[str],
    ) -> Path:
        if self.cache_dir is None:
            raise ResearchDocumentError(
                "External research archive requires a cache directory.",
                details={"provider": self.adapter.provider, "symbol": request.symbol},
            )
        return write_external_fetch_manifest(
            self.cache_dir,
            request=request,
            provider=self.adapter.provider,
            fetched_at=fetched_at,
            entries=entries,
            warnings=warnings,
        )


def _external_fetch_provider_statuses(
    adapter: ExternalResearchSourceAdapter,
) -> list[ResearchSourceTrace]:
    traces = getattr(adapter, "last_source_traces", None)
    if not isinstance(traces, list):
        return []
    return [trace for trace in traces if isinstance(trace, ResearchSourceTrace)]


def _external_fetch_provider_status_warnings(
    *,
    entries: list[ExternalResearchFetchManifestEntry],
    provider_statuses: list[ResearchSourceTrace],
) -> list[str]:
    if not provider_statuses:
        return []
    warnings: list[str] = []
    timeout_count = sum(1 for status in provider_statuses if status.status == "timeout")
    failed_count = sum(1 for status in provider_statuses if status.status == "failed")
    if timeout_count:
        if entries:
            warnings.append(
                "一部の取得元は時間切れになりました。取得済みの情報のみ表示しています。"
            )
        else:
            warnings.append("外部取得元が時間切れになりました。時間をおいて再実行してください。")
    if failed_count and entries:
        warnings.append(
            "一部の取得元で取得できませんでした。取得済みの情報のみAI調査に反映しています。"
        )
    return warnings
