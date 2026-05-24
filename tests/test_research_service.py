from datetime import date
from decimal import Decimal

import pytest

from backend.research import (
    CompanyResearchRequest,
    ResearchAnalysisService,
    ResearchDocumentError,
    ResearchDocumentRegisterRequest,
    ResearchIndexService,
    ResearchIngestionService,
    ResearchInMemoryStore,
    ResearchRetrievalService,
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
