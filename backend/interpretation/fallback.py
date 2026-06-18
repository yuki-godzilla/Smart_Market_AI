from __future__ import annotations

from datetime import UTC, datetime
from typing import Mapping

from backend.assistant import AssistantContextSection

from .models import (
    COCKPIT_INTERPRETATION_PROMPT_VERSION,
    COCKPIT_INTERPRETATION_SCHEMA_VERSION,
    CockpitInterpretationContext,
    CockpitInterpretationFallbackReason,
    CockpitInterpretationResult,
    CockpitInterpretationStatus,
    InterpretationBullet,
)


def build_deterministic_cockpit_interpretation(
    context: CockpitInterpretationContext,
    *,
    status: CockpitInterpretationStatus,
    fallback_reason: CockpitInterpretationFallbackReason | None,
    generated_at: datetime | None = None,
) -> CockpitInterpretationResult:
    sections = {section.section_id: section for section in context.bundle.sections}
    warnings = [*context.warnings]
    if fallback_reason == "disabled":
        warnings.append("AI解釈メモのlive生成は設定で無効です。")
    elif fallback_reason:
        warnings.append(
            "AI解釈メモのlive生成に失敗したため、既存ルールの簡易メモを表示しています。"
        )
    if context.missing_fields:
        warnings.append(f"不足項目: {', '.join(context.missing_fields)}")

    return CockpitInterpretationResult(
        symbol=context.symbol,
        company_name=context.company_name,
        status=status,
        overall_reading=_overall_reading(context, fallback_reason=fallback_reason),
        positive_points=_positive_points(sections),
        caution_points=_caution_points(sections, context=context),
        contradictions=_contradictions(sections),
        uncertainties=_uncertainties(context),
        next_checks=_next_checks(sections),
        missing_fields=context.missing_fields,
        warnings=_dedupe(warnings),
        provider="deterministic",
        model="fallback",
        gateway_profile="fallback",
        generated_at=_ensure_utc(generated_at or datetime.now(UTC)),
        prompt_version=COCKPIT_INTERPRETATION_PROMPT_VERSION,
        schema_version=COCKPIT_INTERPRETATION_SCHEMA_VERSION,
        context_hash=context.context_hash,
        fallback_reason=fallback_reason,
        is_fallback=status != "live",
    )


def _overall_reading(
    context: CockpitInterpretationContext,
    *,
    fallback_reason: str | None,
) -> str:
    label = context.company_name or context.symbol
    if fallback_reason == "disabled":
        return (
            f"{label} のAI解釈メモはlive生成を使わず、表示済みの価格・予測・根拠資料・AI材料分析から"
            "簡易的に読み方を整理しています。"
        )
    if fallback_reason:
        return (
            f"{label} のAI解釈メモはlive生成できなかったため、既存データにもとづく簡易メモです。"
            "価格、予測、根拠資料、AI材料分析を分けて確認してください。"
        )
    return f"{label} の表示済み材料を、価格・予測・根拠資料・AI材料分析の順に読み解くための参考メモです。"


def _positive_points(sections: Mapping[str, AssistantContextSection]) -> list[InterpretationBullet]:
    bullets: list[InterpretationBullet] = []
    score = getattr(sections.get("investment_score"), "summary", {})
    if isinstance(score, dict) and score:
        bullets.append(
            InterpretationBullet(
                title="Score内訳の確認",
                summary="Investment Scoreは総合点だけでなく、どの内訳が支えているかを見ると強材料を整理しやすくなります。",
                evidence_ids=["investment_score"],
                confidence=0.5,
            )
        )
    llm_factor = getattr(sections.get("llm_factor"), "summary", {})
    if isinstance(llm_factor, dict) and llm_factor.get("overall_summary"):
        bullets.append(
            InterpretationBullet(
                title="AI材料分析の要約",
                summary=str(llm_factor["overall_summary"]),
                evidence_ids=["llm_factor"],
                confidence=0.5,
            )
        )
    return bullets[:4]


def _caution_points(
    sections: Mapping[str, AssistantContextSection],
    *,
    context: CockpitInterpretationContext,
) -> list[InterpretationBullet]:
    bullets: list[InterpretationBullet] = []
    forecast = getattr(sections.get("forecast_summary"), "summary", {})
    if isinstance(forecast, dict) and forecast:
        bullets.append(
            InterpretationBullet(
                title="予測の不確実性",
                summary="AI予測は短期の目安です。方向、レンジ、モデル合意度、不確実性を分けて確認してください。",
                evidence_ids=["forecast_summary"],
                confidence=0.45,
            )
        )
    if "research_evidence" in sections:
        bullets.append(
            InterpretationBullet(
                title="根拠資料の鮮度",
                summary="Research Evidenceは件数だけでなく、公開日、出典種別、未確認材料を確認してください。",
                evidence_ids=["research_evidence"],
                confidence=0.45,
            )
        )
    if context.missing_fields:
        bullets.append(
            InterpretationBullet(
                title="不足データ",
                summary=f"不足している材料があります: {', '.join(context.missing_fields)}。",
                evidence_ids=[],
                confidence=0.35,
            )
        )
    return bullets[:4]


def _contradictions(sections: Mapping[str, AssistantContextSection]) -> list[InterpretationBullet]:
    if "forecast_summary" in sections and "llm_factor" in sections:
        return [
            InterpretationBullet(
                title="予測と材料の方向差",
                summary="予測とAI材料分析の方向が違う場合は、短期の価格要因と中長期の材料を分けて確認してください。",
                evidence_ids=["forecast_summary", "llm_factor"],
                confidence=0.4,
            )
        ]
    return []


def _uncertainties(context: CockpitInterpretationContext) -> list[InterpretationBullet]:
    return [
        InterpretationBullet(
            title="未確認材料",
            summary=warning,
            evidence_ids=[],
            confidence=0.35,
        )
        for warning in context.warnings[:3]
    ]


def _next_checks(sections: Mapping[str, AssistantContextSection]) -> list[InterpretationBullet]:
    checks = [
        InterpretationBullet(
            title="最新ニュースと開示",
            summary="直近のニュース、適時開示、企業IRで材料の鮮度を確認してください。",
            evidence_ids=["research_evidence"] if "research_evidence" in sections else [],
            confidence=0.55,
        ),
        InterpretationBullet(
            title="予測モデルの一致度",
            summary="予測方向、レンジ、下振れ警戒、モデル合意度を確認してください。",
            evidence_ids=["forecast_summary"] if "forecast_summary" in sections else [],
            confidence=0.55,
        ),
    ]
    return checks


def _dedupe(values: list[str]) -> list[str]:
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
