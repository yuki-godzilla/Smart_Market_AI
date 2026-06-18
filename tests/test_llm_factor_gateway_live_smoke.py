from __future__ import annotations

import os
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from backend.core.config import Settings
from backend.llm_factor import EvidenceSource, build_llm_factor_reference_result_from_settings

pytestmark = pytest.mark.skipif(
    os.getenv("SMAI_LLM_FACTOR_GATEWAY_LIVE_SMOKE") != "1",
    reason="Set SMAI_LLM_FACTOR_GATEWAY_LIVE_SMOKE=1 to run the live Gateway/Ollama smoke.",
)


def test_llm_factor_gateway_live_smoke(tmp_path) -> None:
    base_url = os.getenv("SMAI_LLM_FACTOR_GATEWAY_BASE_URL", "http://127.0.0.1:8088")
    model = os.getenv("SMAI_LLM_FACTOR_GATEWAY_MODEL")
    profile = os.getenv("SMAI_LLM_FACTOR_GATEWAY_PROFILE", "desktop_analysis")
    live_config: dict[str, object] = {
        "enabled": True,
        "base_url": base_url,
        "timeout_seconds": float(os.getenv("SMAI_LLM_FACTOR_GATEWAY_TIMEOUT", "90")),
        "preferred_profile": profile,
        "cache_enabled": False,
    }
    if model:
        live_config["model"] = model
    settings = Settings.model_validate({"llm_factor": {"live": live_config}})

    result = build_llm_factor_reference_result_from_settings(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[
            EvidenceSource(
                title="増配と自社株買いを発表",
                source_type="company_ir",
                source_url="https://example.com/ir/7203",
                source_date=date(2026, 6, 12),
                fetched_at=datetime(2026, 6, 12, 9, 0, tzinfo=UTC),
                provider="fixture",
                summary="トヨタが増配と自社株買いを発表し、株主還元姿勢を示しました。",
                reliability_score=Decimal("82"),
            )
        ],
        settings=settings,
        cache_dir=tmp_path,
        now=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )

    assert result.result.gateway_status == "ok"
    assert result.result.fallback_reason is None
    assert result.result.provider not in {None, "deterministic"}
    assert result.result.model_name
    assert result.result.gateway_profile == profile
    assert result.result.evidence_sources
