from __future__ import annotations

from datetime import UTC, datetime

from backend.interpretation import CockpitInterpretationResult, InterpretationBullet
from ui.app import _cockpit_interpretation_panel_html


def test_cockpit_interpretation_panel_html_shows_disabled_state() -> None:
    result = _result(status="disabled", fallback_reason="disabled")

    html = _cockpit_interpretation_panel_html(result)

    assert "AI解釈メモ" in html
    assert "LLM接続: disabled" in html
    assert "設定で無効 (disabled)" in html
    assert "Ranking・予測・Investment Scoreには反映していません" in html
    assert "売買推奨ではなく" in html


def test_cockpit_interpretation_panel_html_shows_live_metadata() -> None:
    result = _result(status="live", fallback_reason=None)

    html = _cockpit_interpretation_panel_html(result)

    assert "LLM接続: live" in html
    assert "provider: ollama / model: qwen3:8b / profile: desktop_fast" in html
    assert "強材料" in html
    assert "次に確認すべき材料" in html


def test_cockpit_interpretation_panel_html_shows_validation_error_reason() -> None:
    result = _result(status="validation_error", fallback_reason="policy_violation")

    html = _cockpit_interpretation_panel_html(result)

    assert "LLM接続: validation error" in html
    assert "売買推奨などの禁止表現 (policy_violation)" in html


def _result(
    *,
    status: str,
    fallback_reason: str | None,
) -> CockpitInterpretationResult:
    return CockpitInterpretationResult(
        symbol="7203.T",
        company_name="Toyota Motor",
        status=status,  # type: ignore[arg-type]
        overall_reading="価格、予測、根拠資料を分けて確認する参考メモです。",
        positive_points=[
            InterpretationBullet(
                title="品質項目",
                summary="Investment Scoreの品質項目は確認材料です。",
                evidence_ids=["investment_score"],
                confidence=0.55,
            )
        ],
        caution_points=[
            InterpretationBullet(
                title="予測の不確実性",
                summary="予測は短期の目安として確認します。",
                evidence_ids=["forecast_summary"],
                confidence=0.45,
            )
        ],
        next_checks=[
            InterpretationBullet(
                title="最新ニュース",
                summary="最新ニュースと適時開示を確認してください。",
                evidence_ids=["research_evidence"],
                confidence=0.55,
            )
        ],
        warnings=["不足項目を確認してください。"],
        provider="ollama" if status == "live" else "deterministic",
        model="qwen3:8b" if status == "live" else "fallback",
        gateway_profile="desktop_fast" if status == "live" else "fallback",
        generated_at=datetime(2026, 6, 18, 10, 0, tzinfo=UTC),
        context_hash="abc123",
        fallback_reason=fallback_reason,  # type: ignore[arg-type]
        is_fallback=status != "live",
    )
