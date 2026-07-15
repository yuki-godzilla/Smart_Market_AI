"""Explicit local-RAG evidence bundles for Investment Radar candidates."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Protocol

from backend.news.contracts import (
    NewsFreshnessStatus,
    RadarCandidate,
    RadarEvidenceBundle,
    RadarEvidenceCitation,
    RadarResearchContext,
    RadarRetrievalQuality,
)
from backend.research import ResearchEvidence, ResearchRetrievalQuality, ResearchSearchRequest

_MIN_RELEVANCE = 0.10
_MAX_CITATIONS = 5
_MAX_RETRIEVAL_CANDIDATES = 12
_MAX_QUERY_CHARS = 360
_MAX_EXCERPT_CHARS = 320


class RadarResearchRetriever(Protocol):
    """Narrow retrieval boundary; it has no external-fetch capability."""

    last_search_quality: ResearchRetrievalQuality | None

    def search(self, request: ResearchSearchRequest) -> list[ResearchEvidence]: ...


def build_radar_research_context(
    candidate: RadarCandidate,
    *,
    as_of: date,
) -> RadarResearchContext:
    """Build a compact candidate query without forwarding raw news/provider payloads."""

    query_parts = [candidate.symbol, *candidate.categories]
    query_parts.extend(evidence.headline_title for evidence in candidate.evidence[:3])
    query = _clip(" ".join(part for part in query_parts if part), _MAX_QUERY_CHARS)
    return RadarResearchContext(
        candidate_id=candidate.candidate_id,
        symbol=candidate.symbol,
        query=query or candidate.symbol,
        as_of=as_of,
        news_evidence_ids=candidate.evidence_ids,
    )


def build_radar_evidence_bundle(
    candidate: RadarCandidate,
    *,
    context: RadarResearchContext,
    retriever: RadarResearchRetriever,
    now: datetime | None = None,
) -> RadarEvidenceBundle:
    """Retrieve only existing local evidence and retain gaps instead of scoring them."""

    generated_at = _ensure_utc(now or datetime.now(UTC))
    retrieved = retriever.search(
        ResearchSearchRequest(
            symbol=context.symbol,
            query=context.query,
            # Ask the local retriever for a wider, bounded pool before choosing
            # citations.  This avoids filling the evidence panel with adjacent
            # chunks from one document when different source documents exist.
            top_k=_MAX_RETRIEVAL_CANDIDATES,
            as_of=context.as_of,
        )
    )
    citations: list[RadarEvidenceCitation] = []
    gaps: list[str] = []
    seen_chunks: set[tuple[str, str]] = set()
    seen_documents: set[str] = set()
    future_filtered = False
    low_relevance_filtered = False
    wrong_symbol_filtered = False
    duplicate_document_filtered = False
    for evidence in retrieved:
        if evidence.symbol.strip().upper() != context.symbol.strip().upper():
            wrong_symbol_filtered = True
            continue
        if evidence.published_at is not None and evidence.published_at > context.as_of:
            future_filtered = True
            continue
        if float(evidence.relevance_score) < _MIN_RELEVANCE:
            low_relevance_filtered = True
            continue
        identity = (evidence.document_id, evidence.chunk_id)
        if identity in seen_chunks:
            continue
        seen_chunks.add(identity)
        if evidence.document_id in seen_documents:
            duplicate_document_filtered = True
            continue
        seen_documents.add(evidence.document_id)
        citations.append(
            RadarEvidenceCitation(
                citation_id=f"radar-rag:{evidence.document_id}:{evidence.chunk_id}",
                research_evidence_id=evidence.chunk_id,
                title=evidence.title,
                source_type=evidence.source_type,
                published_at=evidence.published_at,
                retrieved_at=generated_at,
                freshness_status=_freshness_status(evidence.published_at, as_of=context.as_of),
                directness=candidate.directness,
                excerpt=_clip(evidence.excerpt, _MAX_EXCERPT_CHARS),
            )
        )
        if len(citations) >= _MAX_CITATIONS:
            break

    if future_filtered:
        gaps.append("ニュース時点より後の資料は根拠に含めませんでした。")
    if low_relevance_filtered:
        gaps.append("関連度が低い資料は根拠に採用していません。")
    if wrong_symbol_filtered:
        gaps.append("別銘柄の資料は根拠に採用していません。")
    if duplicate_document_filtered:
        gaps.append("同一資料の近接断片はまとめ、異なる資料を優先して表示しています。")
    quality = _radar_retrieval_quality(getattr(retriever, "last_search_quality", None))
    if not citations:
        gaps.append("候補に対応するローカルRAG根拠は確認できませんでした。")
    return RadarEvidenceBundle(
        candidate_id=candidate.candidate_id,
        context=context,
        citations=citations,
        retrieval_quality=quality,
        status="available" if citations else "confirmation_gap",
        confirmation_gaps=_dedupe(gaps),
        generated_at=generated_at,
    )


def _radar_retrieval_quality(
    quality: ResearchRetrievalQuality | None,
) -> RadarRetrievalQuality | None:
    if quality is None:
        return None
    return RadarRetrievalQuality(
        backend=quality.backend,
        candidate_count=quality.candidate_count,
        evidence_count=quality.evidence_count,
        keyword_candidate_count=quality.keyword_candidate_count,
        vector_candidate_count=quality.vector_candidate_count,
        document_count=quality.document_count,
        latency_ms=quality.latency_ms,
        warnings=quality.warnings,
    )


def _freshness_status(published_at: date | None, *, as_of: date) -> NewsFreshnessStatus:
    if published_at is None:
        return "unknown"
    age_days = (as_of - published_at).days
    if age_days <= 1:
        return "latest"
    if age_days <= 7:
        return "recent"
    return "stale"


def _clip(value: str, max_chars: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}…"


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
