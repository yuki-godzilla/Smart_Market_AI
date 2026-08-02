"""Deterministic evidence freshness, source, dedupe, and reranking policy."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.research.contracts import ResearchEvidence
from backend.research.external_contracts import ResearchSourceType


def freshness_factor(published_at: date | None, *, as_of: date) -> Decimal:
    if published_at is None:
        return Decimal("0.85")
    age_days = (as_of - published_at).days
    if age_days < 0:
        return Decimal("1")
    if age_days <= 365:
        return Decimal("1")
    if age_days <= 730:
        return Decimal("0.90")
    if age_days <= 1095:
        return Decimal("0.75")
    return Decimal("0.60")


def source_type_priority(source_type: ResearchSourceType) -> float:
    priorities: dict[ResearchSourceType, float] = {
        "annual_report": 1.0,
        "earnings_report": 0.95,
        "earnings_presentation": 0.95,
        "medium_term_plan": 0.95,
        "integrated_report": 0.95,
        "company_ir": 0.88,
        "tdnet": 0.90,
        "provider_profile": 0.65,
        "user_note": 0.70,
        "news": 0.60,
    }
    return priorities[source_type]


def dedupe_evidence(evidence: list[ResearchEvidence]) -> list[ResearchEvidence]:
    deduped: dict[str, ResearchEvidence] = {}
    for row in evidence:
        existing = deduped.get(row.chunk_id)
        if existing is None or row.relevance_score > existing.relevance_score:
            deduped[row.chunk_id] = row
    return sorted(
        deduped.values(),
        key=lambda row: (
            -row.relevance_score,
            -(row.published_at or date.min).toordinal(),
            row.document_id,
            row.chunk_id,
        ),
    )


def evidence_rerank_score(row: ResearchEvidence, *, as_of: date) -> Decimal:
    score = (
        (row.relevance_score * Decimal("0.55"))
        + (row.reliability * Decimal("0.25"))
        + (freshness_factor(row.published_at, as_of=as_of) * Decimal("0.10"))
        + (Decimal(str(source_type_priority(row.source_type))) * Decimal("0.10"))
    )
    return score.quantize(Decimal("0.0001"))


class ResearchEvidenceReranker:
    """Deterministically rerank evidence while preserving ResearchEvidence output."""

    def rerank(
        self,
        evidence: list[ResearchEvidence],
        *,
        as_of: date | None = None,
    ) -> list[ResearchEvidence]:
        effective_as_of = as_of or date.today()
        deduped = dedupe_evidence(evidence)
        return sorted(
            deduped,
            key=lambda row: (
                -evidence_rerank_score(row, as_of=effective_as_of),
                -row.relevance_score,
                -row.reliability,
                -source_type_priority(row.source_type),
                -(row.published_at or date.min).toordinal(),
                row.document_id,
                row.chunk_id,
            ),
        )
