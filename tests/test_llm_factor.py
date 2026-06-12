from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.llm_factor import (
    LLM_FACTOR_FAKE_MODEL_NAME,
    LLM_FACTOR_PROMPT_VERSION,
    BullishFactor,
    EvidenceSource,
    FakeLLMFactorService,
    LLMFactorResult,
    source_hash_for_evidence,
)


def _evidence_source(
    *,
    title: str = "増配と自社株買いを発表",
    source_url: str = "https://example.com/ir/7203",
    source_date: date = date(2026, 6, 12),
    summary: str = "好決算、増配、自社株買い、AI関連需要の成長が確認できます。",
) -> EvidenceSource:
    return EvidenceSource(
        title=title,
        source_type="company_ir",
        source_url=source_url,
        source_date=source_date,
        fetched_at=datetime(2026, 6, 12, 9, 0, tzinfo=UTC),
        provider="fixture",
        summary=summary,
        reliability_score=Decimal("82"),
    )


def test_fake_llm_factor_service_builds_source_backed_reference_result() -> None:
    source = _evidence_source()
    result = FakeLLMFactorService().build_reference_result(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        evidence_sources=[source],
        generated_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )

    assert result.ticker == "7203.T"
    assert result.model_name == LLM_FACTOR_FAKE_MODEL_NAME
    assert result.prompt_version == LLM_FACTOR_PROMPT_VERSION
    assert result.source_hash == source_hash_for_evidence([source])
    assert result.llm_bullish_score > Decimal("50")
    assert result.llm_confidence_score >= Decimal("70")
    assert result.bullish_factors
    assert result.bullish_factors[0].source_url == source.source_url
    assert result.bullish_factors[0].source_date == source.source_date
    assert "売買推奨ではありません" in result.disclaimer
    assert any("LLM実行はまだ接続していない" in warning for warning in result.warnings)


def test_fake_llm_factor_service_uses_low_confidence_fallback_without_sources() -> None:
    result = FakeLLMFactorService().build_reference_result(
        ticker="9532.T",
        as_of=date(2026, 6, 12),
        generated_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )

    assert result.evidence_sources[0].source_url == "smai://llm-factor/reference/9532.T"
    assert result.llm_confidence_score < Decimal("50")
    assert not result.bullish_factors
    assert any("出典付き" in warning for warning in result.warnings)


def test_llm_factor_contract_rejects_missing_url_and_out_of_range_scores() -> None:
    with pytest.raises(ValidationError):
        EvidenceSource(
            title="URLなし",
            source_type="news",
            source_url="",
            source_date=date(2026, 6, 12),
        )

    with pytest.raises(ValidationError):
        BullishFactor(
            title="上方修正",
            score=Decimal("101"),
            reason="スコア範囲外です。",
            source_url="https://example.com/ir",
            source_date=date(2026, 6, 12),
            source_type="company_ir",
        )


def test_parse_provider_json_validates_json_and_falls_back_conservatively() -> None:
    source = _evidence_source()
    service = FakeLLMFactorService()
    fallback = service.parse_provider_json(
        '{"ticker": "7203.T", "llm_bullish_score": 200}',
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        fallback_sources=[source],
        generated_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )

    assert isinstance(fallback, LLMFactorResult)
    assert fallback.llm_confidence_score <= Decimal("20")
    assert fallback.evidence_sources == [source]
    assert any("LLM応答を検証できなかった" in warning for warning in fallback.warnings)
