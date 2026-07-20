from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from backend.news import (
    RadarCandidate,
    build_radar_evidence_bundle,
    build_radar_research_context,
)
from backend.research import ResearchEvidence, ResearchRetrievalQuality, ResearchSearchRequest


class _FakeRetriever:
    def __init__(self, evidence: list[ResearchEvidence]) -> None:
        self.evidence = evidence
        self.requests: list[ResearchSearchRequest] = []
        self.last_search_quality = ResearchRetrievalQuality(
            backend="hybrid",
            query="candidate query",
            candidate_count=len(evidence),
            evidence_count=len(evidence),
            keyword_candidate_count=len(evidence),
            vector_candidate_count=0,
            document_count=len({item.document_id for item in evidence}),
            latency_ms=3,
        )

    def search(self, request: ResearchSearchRequest) -> list[ResearchEvidence]:
        self.requests.append(request)
        return self.evidence


def _candidate() -> RadarCandidate:
    return RadarCandidate(
        candidate_id="radar:direct_mention:7203.T",
        symbol="7203.T",
        display_name="Toyota Motor",
        provenance="direct_mention",
        categories=["自動車", "決算・業績修正"],
        evidence_ids=["radar-news-1"],
        directness=1.0,
        confirmation_priority=74,
    )


def _evidence(
    *,
    chunk_id: str,
    document_id: str | None = None,
    symbol: str = "7203.T",
    published_at: date | None = date(2026, 7, 10),
    relevance: str = "0.80",
) -> ResearchEvidence:
    return ResearchEvidence(
        symbol=symbol,
        document_id=document_id or f"doc-{chunk_id}",
        chunk_id=chunk_id,
        title=f"資料 {chunk_id}",
        source_type="company_ir",
        published_at=published_at,
        excerpt="会社計画と投資方針を確認するための根拠資料です。",
        relevance_score=Decimal(relevance),
        reliability=Decimal("0.80"),
    )


def test_radar_evidence_bundle_uses_only_candidate_symbol_timely_relevant_local_evidence():
    candidate = _candidate()
    context = build_radar_research_context(candidate, as_of=date(2026, 7, 13))
    retriever = _FakeRetriever(
        [
            _evidence(chunk_id="accepted"),
            _evidence(chunk_id="future", published_at=date(2026, 7, 14)),
            _evidence(chunk_id="low", relevance="0.09"),
            _evidence(chunk_id="other", symbol="AAPL"),
        ]
    )

    bundle = build_radar_evidence_bundle(
        candidate,
        context=context,
        retriever=retriever,
        now=datetime(2026, 7, 13, 9, 0, tzinfo=UTC),
    )

    assert retriever.requests[0].symbol == "7203.T"
    assert retriever.requests[0].top_k == 12
    assert "7203.T" in context.query
    assert bundle.status == "available"
    assert [citation.research_evidence_id for citation in bundle.citations] == ["accepted"]
    assert bundle.citations[0].citation_id == "radar-rag:doc-accepted:accepted"
    assert bundle.citations[0].directness == 1.0
    assert bundle.retrieval_quality is not None
    assert bundle.retrieval_quality.backend == "hybrid"
    assert any("後の資料" in gap for gap in bundle.confirmation_gaps)
    assert any("関連度が低い" in gap for gap in bundle.confirmation_gaps)
    assert any("別銘柄" in gap for gap in bundle.confirmation_gaps)


def test_radar_evidence_bundle_keeps_missing_material_as_confirmation_gap():
    candidate = _candidate()
    context = build_radar_research_context(candidate, as_of=date(2026, 7, 13))
    bundle = build_radar_evidence_bundle(
        candidate,
        context=context,
        retriever=_FakeRetriever([]),
        now=datetime(2026, 7, 13, 9, 0, tzinfo=UTC),
    )

    assert bundle.status == "confirmation_gap"
    assert bundle.citations == []
    assert any("確認できません" in gap for gap in bundle.confirmation_gaps)


def test_radar_evidence_bundle_prefers_distinct_documents_from_the_local_rag_pool():
    candidate = _candidate()
    context = build_radar_research_context(candidate, as_of=date(2026, 7, 13))
    retriever = _FakeRetriever(
        [
            _evidence(chunk_id="first", document_id="doc-a"),
            _evidence(chunk_id="nearby", document_id="doc-a"),
            _evidence(chunk_id="second", document_id="doc-b"),
        ]
    )

    bundle = build_radar_evidence_bundle(
        candidate,
        context=context,
        retriever=retriever,
        now=datetime(2026, 7, 13, 9, 0, tzinfo=UTC),
    )

    assert retriever.requests[0].top_k == 12
    assert [citation.research_evidence_id for citation in bundle.citations] == ["first", "second"]
    assert any("同一資料の近接断片" in gap for gap in bundle.confirmation_gaps)
