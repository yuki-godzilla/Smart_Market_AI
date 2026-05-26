from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from backend.research import (
    CompanyResearchRequest,
    HybridResearchRetrievalService,
    ResearchAnalysisService,
    ResearchDisabledVectorStore,
    ResearchDocumentError,
    ResearchDocumentRegisterRequest,
    ResearchEmbedding,
    ResearchEvidence,
    ResearchEvidenceReranker,
    ResearchHybridScorer,
    ResearchIndexService,
    ResearchIngestionService,
    ResearchInMemoryStore,
    ResearchInMemoryVectorStore,
    ResearchQueryExpansionService,
    ResearchRetrievalCandidate,
    ResearchRetrievalQuality,
    ResearchRetrievalService,
    ResearchSearchError,
    ResearchSearchRequest,
)


def test_research_local_document_flow_registers_chunks_searches_and_summarizes(tmp_path):
    document_path = tmp_path / "7203_research.md"
    document_path.write_text(
        """# 7203 Research Note

## Growth

The company explains growth strategy through hybrid demand, software revenue, and
market expansion outside Japan.

## Shareholder Return

Dividend policy and shareholder return remain part of the capital allocation plan.

## Risk

Business risk includes competition, supply constraints, and foreign exchange demand.
""",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    document = ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="7203 Research Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
            reliability=Decimal("0.80"),
        )
    )
    summary = index.rebuild_index(symbol="7203.T")
    evidence = retrieval.search(
        ResearchSearchRequest(symbol="7203.T", query="growth strategy market", top_k=2)
    )
    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="7203.T", as_of=date(2026, 5, 24))
    )

    assert document.symbol == "7203.T"
    assert summary.document_count == 1
    assert summary.chunk_count >= 3
    assert evidence
    assert evidence[0].title == "7203 Research Note"
    assert evidence[0].reliability == Decimal("0.80")
    assert report.data_quality.status == "OK"
    assert report.data_quality.document_count == 1
    assert any(point.category == "growth" and point.evidence for point in report.points)
    growth_claim = next(claim for claim in report.extracted_claims if claim.category == "growth")
    assert growth_claim.supporting_evidence
    assert growth_claim.confidence > Decimal("0")
    assert "売買推奨ではありません" in (growth_claim.caution_note or "")
    assert report.grounded_answer is not None
    assert report.grounded_answer.provider == "template"
    assert report.grounded_answer.referenced_evidence
    assert "売買推奨ではなく" in report.grounded_answer.answer
    assert report.retrieval_quality is not None
    assert report.retrieval_quality.backend == "keyword"
    assert report.retrieval_quality.candidate_count >= report.retrieval_quality.evidence_count
    assert report.retrieval_quality.evidence_count == len(report.evidence)
    assert "growth" in report.retrieval_quality.query
    assert "strategy" in report.retrieval_quality.expanded_terms


def test_research_ingestion_deduplicates_by_document_hash(tmp_path):
    document_path = tmp_path / "note.md"
    document_path.write_text("Growth strategy and dividend policy.", encoding="utf-8")
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    request = ResearchDocumentRegisterRequest(
        symbol="AAPL",
        title="Apple Note",
        local_path=str(document_path),
        published_at=date(2026, 5, 1),
    )

    first = ingestion.register_document(request)
    second = ingestion.register_document(request)

    assert first.document_id == second.document_id
    assert len(ingestion.list_documents("AAPL")) == 1


def test_research_search_applies_freshness_and_source_type_filters(tmp_path):
    old_path = tmp_path / "old_report.md"
    old_path.write_text(
        "Growth strategy includes market expansion in the legacy plan.",
        encoding="utf-8",
    )
    new_path = tmp_path / "new_report.md"
    new_path.write_text(
        "Growth strategy includes market expansion in the current plan.",
        encoding="utf-8",
    )
    note_path = tmp_path / "user_note.md"
    note_path.write_text(
        "Growth strategy includes market expansion in the analyst note.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Old Annual Report",
            local_path=str(old_path),
            source_type="annual_report",
            published_at=date(2023, 1, 1),
        )
    )
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="New Annual Report",
            local_path=str(new_path),
            source_type="annual_report",
            published_at=date(2026, 5, 1),
        )
    )
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="User Note",
            local_path=str(note_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
        )
    )
    index.rebuild_index(symbol="7203.T")

    evidence = retrieval.search(
        ResearchSearchRequest(
            symbol="7203.T",
            query="growth strategy market expansion",
            top_k=3,
            as_of=date(2026, 5, 25),
        )
    )
    filtered = retrieval.search(
        ResearchSearchRequest(
            symbol="7203.T",
            query="growth strategy market expansion",
            top_k=3,
            source_types=["user_note"],
            as_of=date(2026, 5, 25),
        )
    )

    assert evidence[-1].title == "Old Annual Report"
    old = next(row for row in evidence if row.title == "Old Annual Report")
    new = next(row for row in evidence if row.title == "New Annual Report")
    assert old.relevance_score < new.relevance_score
    assert [row.source_type for row in filtered] == ["user_note"]


def test_research_query_expansion_loads_config_and_expands_terms():
    expansion = ResearchQueryExpansionService.from_yaml(Path("config/research_query_terms.yml"))

    result = expansion.expand_query("growth", category="growth")

    assert result.category == "growth"
    assert "growth" in result.expanded_terms
    assert "strategy" in result.expanded_terms
    assert "overseas" in result.expanded_terms


def test_research_search_uses_category_query_expansion(tmp_path):
    document_path = tmp_path / "growth_note.md"
    document_path.write_text(
        "The medium-term plan explains overseas expansion and revenue expansion.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Research Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
        )
    )
    index.rebuild_index(symbol="7203.T")

    without_expansion = retrieval.search(
        ResearchSearchRequest(symbol="7203.T", query="growth strategy")
    )
    with_expansion = retrieval.search(
        ResearchSearchRequest(
            symbol="7203.T",
            query="growth strategy",
            query_category="growth",
        )
    )

    assert not without_expansion
    assert with_expansion
    assert with_expansion[0].title == "Research Note"


def test_research_analysis_uses_query_expansion_for_topic_evidence(tmp_path):
    document_path = tmp_path / "growth_note.md"
    document_path.write_text(
        "The medium-term plan explains overseas expansion and revenue expansion.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Research Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
        )
    )
    index.rebuild_index(symbol="7203.T")

    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="7203.T", as_of=date(2026, 5, 25))
    )

    assert any(point.category == "growth" and point.evidence for point in report.points)
    assert any(
        claim.category == "growth" and claim.supporting_evidence
        for claim in report.extracted_claims
    )


def test_research_analysis_adds_confirmation_gap_claim_for_missing_topic_evidence(tmp_path):
    document_path = tmp_path / "shareholder_note.md"
    document_path.write_text(
        "Dividend policy and shareholder return remain part of capital allocation.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Shareholder Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
        )
    )
    index.rebuild_index(symbol="7203.T")

    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="7203.T", as_of=date(2026, 5, 25))
    )

    gap_claims = [
        claim for claim in report.extracted_claims if claim.category == "confirmation_gap"
    ]
    assert gap_claims
    assert any("成長材料" in claim.claim for claim in gap_claims)
    assert all(not claim.supporting_evidence for claim in gap_claims)
    assert all(claim.confidence == Decimal("0") for claim in gap_claims)
    assert report.grounded_answer is not None
    assert "追加確認が必要" in report.grounded_answer.answer


def test_research_grounded_answer_uses_template_without_unsupported_claims():
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store)
    retrieval = ResearchRetrievalService(store)

    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="MSFT", as_of=date(2026, 5, 24))
    )

    assert report.grounded_answer is not None
    assert report.grounded_answer.provider == "template"
    assert report.grounded_answer.evidence_count == 0
    assert not report.grounded_answer.referenced_evidence
    assert "十分な根拠はまだ確認できません" in report.grounded_answer.answer
    assert "売買推奨ではなく" in report.grounded_answer.answer
    assert report.retrieval_quality is not None
    assert report.retrieval_quality.evidence_count == 0
    assert "検索で根拠候補が見つかりませんでした。" in report.retrieval_quality.warnings


def test_research_evidence_reranker_prefers_official_sources_when_scores_are_close():
    reranker = ResearchEvidenceReranker()
    user_note = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-user",
        chunk_id="chunk-user",
        title="User Note",
        source_type="user_note",
        published_at=date(2026, 5, 1),
        excerpt="Growth strategy and overseas expansion.",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.80"),
    )
    annual_report = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-annual",
        chunk_id="chunk-annual",
        title="Annual Report",
        source_type="annual_report",
        published_at=date(2025, 12, 1),
        excerpt="Growth strategy and overseas expansion.",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.80"),
    )

    reranked = reranker.rerank([user_note, annual_report], as_of=date(2026, 5, 25))

    assert [row.title for row in reranked] == ["Annual Report", "User Note"]


def test_research_evidence_reranker_prefers_reliability_and_suppresses_duplicates():
    reranker = ResearchEvidenceReranker()
    duplicate_low = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-a",
        chunk_id="same-chunk",
        title="Low Duplicate",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        excerpt="Dividend policy.",
        relevance_score=Decimal("0.50"),
        reliability=Decimal("0.90"),
    )
    duplicate_high = duplicate_low.model_copy(
        update={
            "title": "High Duplicate",
            "relevance_score": Decimal("0.70"),
            "reliability": Decimal("0.90"),
        }
    )
    low_reliability = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-b",
        chunk_id="chunk-b",
        title="Low Reliability",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        excerpt="Dividend policy.",
        relevance_score=Decimal("0.70"),
        reliability=Decimal("0.30"),
    )

    reranked = reranker.rerank(
        [low_reliability, duplicate_low, duplicate_high],
        as_of=date(2026, 5, 25),
    )

    assert [row.title for row in reranked] == ["High Duplicate", "Low Reliability"]
    assert len(reranked) == 2


def test_research_analysis_warns_when_evidence_reliability_is_low(tmp_path):
    document_path = tmp_path / "low_reliability_note.md"
    document_path.write_text(
        "Growth strategy includes market expansion and shareholder return.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Low Reliability Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
            reliability=Decimal("0.40"),
        )
    )
    index.rebuild_index(symbol="7203.T")

    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="7203.T", as_of=date(2026, 5, 25))
    )

    assert report.data_quality.status == "WARN"
    assert report.data_quality.evidence_count > 0
    assert "信頼度が低い" in " ".join(report.data_quality.warnings)


def test_research_ingestion_rejects_path_outside_document_dirs(tmp_path):
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    outside_path = tmp_path / "outside.md"
    outside_path.write_text("Growth strategy.", encoding="utf-8")
    ingestion = ResearchIngestionService(ResearchInMemoryStore(), document_dirs=[allowed_dir])

    with pytest.raises(ResearchDocumentError) as exc_info:
        ingestion.register_document(
            ResearchDocumentRegisterRequest(
                symbol="AAPL",
                title="Outside",
                local_path=str(outside_path),
            )
        )

    assert "outside configured document directories" in exc_info.value.message


def test_research_analysis_marks_missing_evidence_as_warning():
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store)
    retrieval = ResearchRetrievalService(store)
    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="MSFT", as_of=date(2026, 5, 24))
    )

    assert report.data_quality.status == "WARN"
    assert report.data_quality.document_count == 0
    assert report.data_quality.evidence_count == 0
    assert any(point.category == "confirmation_gap" for point in report.points)


def test_research_disabled_vector_store_returns_empty_candidates_and_quality_warning():
    vector_store = ResearchDisabledVectorStore()
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth strategy",
        expanded_terms=["growth", "strategy"],
    )

    candidates = vector_store.search(request)
    quality = vector_store.retrieval_quality(request)

    assert candidates == []
    assert quality.backend == "vector"
    assert quality.candidate_count == 0
    assert quality.evidence_count == 0
    assert quality.expanded_terms == ["growth", "strategy"]
    assert "Vector retrieval is disabled" in quality.warnings[0]


def test_research_hybrid_scorer_combines_keyword_vector_freshness_and_reliability():
    candidate = ResearchRetrievalCandidate(
        symbol="7203.T",
        document_id="doc-1",
        chunk_id="chunk-1",
        title="Annual Report",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        section_title="Growth",
        excerpt="Growth strategy and overseas expansion.",
        keyword_score=Decimal("0.80"),
        vector_score=Decimal("0.60"),
        reliability=Decimal("0.90"),
    )

    scored = ResearchHybridScorer().score(candidate, as_of=date(2026, 5, 25))

    assert scored.retrieval_backend == "hybrid"
    assert scored.freshness_score == Decimal("1")
    assert scored.final_relevance_score == Decimal("0.7700")


def test_research_embedding_contract_carries_cache_key_fields():
    embedding = ResearchEmbedding(
        chunk_id="chunk-1",
        symbol="7203.T",
        embedding_model="local-test",
        vector=[0.1, 0.2, 0.3],
        created_at=datetime(2026, 5, 25, tzinfo=UTC),
        text_hash="abc123",
    )

    assert embedding.chunk_id == "chunk-1"
    assert embedding.embedding_model == "local-test"
    assert embedding.text_hash == "abc123"


def test_hybrid_retrieval_falls_back_to_keyword_when_vector_store_is_disabled(tmp_path):
    document_path = tmp_path / "growth_note.md"
    document_path.write_text(
        "Growth strategy includes market expansion and overseas revenue.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    ResearchIndexService(store, max_chars=240).rebuild_index(symbol="7203.T")
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Growth Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
        )
    )
    ResearchIndexService(store, max_chars=240).rebuild_index(symbol="7203.T")
    keyword = ResearchRetrievalService(store)
    hybrid = HybridResearchRetrievalService(keyword)
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth strategy market",
        top_k=2,
        as_of=date(2026, 5, 25),
    )

    evidence = hybrid.search(request)
    quality = hybrid.retrieval_quality(request)

    assert evidence
    assert evidence[0].title == "Growth Note"
    assert quality.backend == "hybrid"
    assert quality.candidate_count == len(evidence)
    assert "Hybrid retrieval fell back to keyword retrieval." in quality.warnings


def test_hybrid_retrieval_scores_vector_candidates_when_available():
    class FakeVectorStore:
        def search(self, request: ResearchSearchRequest) -> list[ResearchRetrievalCandidate]:
            return [
                ResearchRetrievalCandidate(
                    symbol=request.symbol,
                    document_id="doc-vector",
                    chunk_id="chunk-vector",
                    title="Vector Report",
                    source_type="annual_report",
                    published_at=date(2026, 5, 1),
                    section_title="Growth",
                    excerpt="Growth strategy and overseas expansion.",
                    keyword_score=Decimal("0.50"),
                    vector_score=Decimal("0.90"),
                    reliability=Decimal("0.80"),
                )
            ]

        def retrieval_quality(
            self,
            request: ResearchSearchRequest,
            *,
            expanded_terms: list[str] | None = None,
        ) -> ResearchRetrievalQuality:
            return ResearchRetrievalQuality(
                backend="vector",
                query=request.query,
                expanded_terms=expanded_terms or request.expanded_terms,
                candidate_count=1,
                evidence_count=1,
                warnings=[],
            )

    hybrid = HybridResearchRetrievalService(
        ResearchRetrievalService(ResearchInMemoryStore()),
        vector_store=FakeVectorStore(),
    )
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth strategy",
        top_k=1,
        as_of=date(2026, 5, 25),
    )

    evidence = hybrid.search(request)
    quality = hybrid.retrieval_quality(request)

    assert evidence[0].title == "Vector Report"
    assert evidence[0].relevance_score == Decimal("0.7450")
    assert quality.backend == "hybrid"
    assert quality.candidate_count == 1


def test_in_memory_vector_store_searches_by_query_vector_and_filters_symbol():
    store = ResearchInMemoryVectorStore()
    toyota_candidate = ResearchRetrievalCandidate(
        symbol="7203.T",
        document_id="doc-toyota",
        chunk_id="chunk-toyota",
        title="Toyota Vector Note",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        section_title="Growth",
        excerpt="Growth strategy and overseas expansion.",
        keyword_score=Decimal("0.40"),
        reliability=Decimal("0.90"),
    )
    unrelated_candidate = toyota_candidate.model_copy(
        update={
            "symbol": "6758.T",
            "document_id": "doc-sony",
            "chunk_id": "chunk-sony",
            "title": "Sony Vector Note",
        }
    )
    store.upsert(
        toyota_candidate,
        ResearchEmbedding(
            chunk_id="chunk-toyota",
            symbol="7203.T",
            embedding_model="local-test",
            vector=[1.0, 0.0],
            created_at=datetime(2026, 5, 25, tzinfo=UTC),
            text_hash="hash-toyota",
        ),
    )
    store.upsert(
        unrelated_candidate,
        ResearchEmbedding(
            chunk_id="chunk-sony",
            symbol="6758.T",
            embedding_model="local-test",
            vector=[1.0, 0.0],
            created_at=datetime(2026, 5, 25, tzinfo=UTC),
            text_hash="hash-sony",
        ),
    )
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth",
        query_vector=[1.0, 0.0],
    )

    candidates = store.search(request)
    quality = store.retrieval_quality(request)

    assert [candidate.title for candidate in candidates] == ["Toyota Vector Note"]
    assert candidates[0].vector_score == Decimal("1.0000")
    assert quality.backend == "vector"
    assert quality.candidate_count == 1
    assert not quality.warnings


def test_in_memory_vector_store_empty_query_reports_warning():
    store = ResearchInMemoryVectorStore()
    request = ResearchSearchRequest(symbol="7203.T", query="growth")

    assert store.search(request) == []
    quality = store.retrieval_quality(request)

    assert quality.backend == "vector"
    assert quality.candidate_count == 0
    assert "Vector query is empty" in quality.warnings[0]


def test_in_memory_vector_store_rejects_mismatched_embedding_chunk_id():
    store = ResearchInMemoryVectorStore()
    candidate = ResearchRetrievalCandidate(
        symbol="7203.T",
        document_id="doc-1",
        chunk_id="chunk-candidate",
        title="Vector Note",
        source_type="annual_report",
        excerpt="Growth strategy.",
        reliability=Decimal("0.90"),
    )

    with pytest.raises(ResearchSearchError):
        store.upsert(
            candidate,
            ResearchEmbedding(
                chunk_id="chunk-embedding",
                symbol="7203.T",
                embedding_model="local-test",
                vector=[1.0, 0.0],
                created_at=datetime(2026, 5, 25, tzinfo=UTC),
                text_hash="hash",
            ),
        )
