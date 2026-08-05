from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Iterable, cast

from backend.llm_factor import (
    LLM_FACTOR_FAKE_MODEL_NAME,
    LLM_FACTOR_PROMPT_VERSION,
    EvidenceSource,
    FakeLLMFactorService,
    LLMFactorRankingReference,
    LLMFactorResult,
    attach_llm_factor_references_to_ranking_items,
    build_llm_factor_references_for_ranking_items,
    llm_factor_ranking_candidate_key,
    normalized_evidence_sources_for_factor,
    source_hash_for_evidence,
)
from backend.llm_factor.cache import (
    build_llm_factor_cache_entry,
    llm_factor_cache_key,
    save_llm_factor_cache_entry,
)


class CountingFakeLLMFactorService(FakeLLMFactorService):
    def __init__(self, *, fail_tickers: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.fail_tickers = fail_tickers or set()

    def build_reference_result(
        self,
        *,
        ticker: str,
        as_of: date,
        evidence_sources: Iterable[EvidenceSource] = (),
        company_name: str | None = None,
        generated_at: datetime | None = None,
    ) -> LLMFactorResult:
        self.calls.append(ticker)
        if ticker in self.fail_tickers:
            raise RuntimeError("fixture failure")
        return super().build_reference_result(
            ticker=ticker,
            as_of=as_of,
            evidence_sources=evidence_sources,
            company_name=company_name,
            generated_at=generated_at,
        )


def test_attach_llm_reference_preserves_ranking_order() -> None:
    rows = [
        {"rank": "1", "symbol": "AAA", "total_score": "90"},
        {"rank": "2", "symbol": "BBB", "total_score": "10"},
    ]

    enriched = attach_llm_factor_references_to_ranking_items(
        rows,
        as_of_date=date(2026, 6, 12),
    )

    assert [row["symbol"] for row in enriched] == ["AAA", "BBB"]
    assert [row["rank"] for row in enriched] == ["1", "2"]
    assert [row["rank"] for row in rows] == ["1", "2"]


def test_attach_llm_reference_does_not_change_existing_scores() -> None:
    rows = [
        {
            "rank": "1",
            "symbol": "AAA",
            "ranking_score": "88.1",
            "total_score": "88.1",
            "forecast": {"return_pct": "1.2"},
            "investment_score": "88.1",
        }
    ]

    enriched = attach_llm_factor_references_to_ranking_items(
        rows,
        as_of_date=date(2026, 6, 12),
    )

    for key in ("rank", "ranking_score", "total_score", "forecast", "investment_score"):
        assert enriched[0][key] == rows[0][key]


def test_attach_llm_reference_uses_cache_when_available(tmp_path) -> None:
    as_of = date(2026, 6, 12)
    ticker = "7203.T"
    result = FakeLLMFactorService().build_reference_result(
        ticker=ticker,
        as_of=as_of,
        generated_at=datetime(2026, 6, 12, 9, 0, tzinfo=UTC),
    )
    cache_key = _cache_key_for_ticker(ticker, as_of)
    save_llm_factor_cache_entry(
        build_llm_factor_cache_entry(
            result,
            cache_key=cache_key,
            expires_at=datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
        ),
        cache_dir=tmp_path,
    )
    fake = CountingFakeLLMFactorService()

    references = build_llm_factor_references_for_ranking_items(
        [{"symbol": ticker}],
        as_of_date=as_of,
        cache_dir=tmp_path,
        fake_service=fake,
        now=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )

    reference = references[ticker]
    assert reference.source_type == "cache"
    assert reference.bullish_score == result.llm_bullish_score
    assert fake.calls == []


def test_attach_llm_reference_uses_deterministic_fake_on_cache_miss(tmp_path) -> None:
    rows = [{"symbol": "9532.T"}]

    first = build_llm_factor_references_for_ranking_items(
        rows,
        as_of_date=date(2026, 6, 12),
        cache_dir=tmp_path,
    )
    second = build_llm_factor_references_for_ranking_items(
        rows,
        as_of_date=date(2026, 6, 12),
        cache_dir=tmp_path,
    )

    assert first["9532.T"].source_type == "deterministic_fake"
    assert first["9532.T"].bullish_score == second["9532.T"].bullish_score
    assert first["9532.T"].confidence_score == second["9532.T"].confidence_score


def test_attach_llm_reference_only_for_displayed_or_selected_candidates(tmp_path) -> None:
    universe_rows = [{"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": "CCC"}]
    displayed_rows = universe_rows[:2]
    fake = CountingFakeLLMFactorService()

    references = build_llm_factor_references_for_ranking_items(
        displayed_rows,
        as_of_date=date(2026, 6, 12),
        cache_dir=tmp_path,
        fake_service=fake,
    )

    assert list(references) == ["AAA", "BBB"]
    assert fake.calls == ["AAA", "BBB"]
    assert "CCC" not in references


def test_attach_llm_reference_handles_unavailable_without_breaking_ranking(tmp_path) -> None:
    rows = [
        {"rank": "1", "symbol": "OK", "total_score": "80"},
        {"rank": "2", "symbol": "FAIL", "total_score": "70"},
    ]
    fake = CountingFakeLLMFactorService(fail_tickers={"FAIL"})

    enriched = attach_llm_factor_references_to_ranking_items(
        rows,
        as_of_date=date(2026, 6, 12),
        cache_dir=tmp_path,
        fake_service=fake,
    )

    assert [row["symbol"] for row in enriched] == ["OK", "FAIL"]
    assert [row["total_score"] for row in enriched] == ["80", "70"]
    ok_reference = cast(LLMFactorRankingReference, enriched[0]["llm_factor_reference"])
    fail_reference = cast(LLMFactorRankingReference, enriched[1]["llm_factor_reference"])
    assert ok_reference.source_type == "deterministic_fake"
    assert fail_reference.source_type == "unavailable"


def test_llm_factor_ranking_reference_dto_is_optional() -> None:
    rows = [{"rank": "1", "symbol": "AAPL", "total_score": "90"}]

    assert "llm_factor_reference" not in rows[0]
    enriched = attach_llm_factor_references_to_ranking_items(
        rows,
        as_of_date=date(2026, 6, 12),
        max_candidates=0,
    )

    assert "llm_factor_reference" not in enriched[0]
    assert enriched[0]["rank"] == "1"
    assert enriched[0]["total_score"] == "90"


def test_duplicate_symbol_uses_existing_candidate_key_policy() -> None:
    first = {"symbol": "ABC", "market": "TSE"}
    second = {"symbol": "ABC", "market": "NASDAQ"}

    assert llm_factor_ranking_candidate_key(first) == "ABC|TSE"
    assert llm_factor_ranking_candidate_key(second) == "ABC|NASDAQ"
    assert llm_factor_ranking_candidate_key(first) != llm_factor_ranking_candidate_key(second)


def _cache_key_for_ticker(ticker: str, as_of: date) -> str:
    sources = normalized_evidence_sources_for_factor(
        ticker=ticker,
        as_of=as_of,
        evidence_sources=[],
    )
    return llm_factor_cache_key(
        ticker=ticker,
        as_of=as_of,
        source_hash=source_hash_for_evidence(sources),
        model_name=LLM_FACTOR_FAKE_MODEL_NAME,
        prompt_version=LLM_FACTOR_PROMPT_VERSION,
    )
