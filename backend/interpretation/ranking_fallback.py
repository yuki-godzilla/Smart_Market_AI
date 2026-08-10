from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from .ranking_models import (
    RANKING_INTERPRETATION_PROMPT_VERSION,
    RANKING_INTERPRETATION_SCHEMA_VERSION,
    RankingCandidateInterpretationNote,
    RankingInterpretationContext,
    RankingInterpretationFallbackReason,
    RankingInterpretationPoint,
    RankingInterpretationResult,
    RankingInterpretationStatus,
)


def build_deterministic_ranking_interpretation(
    context: RankingInterpretationContext,
    *,
    status: RankingInterpretationStatus,
    fallback_reason: RankingInterpretationFallbackReason,
    generated_at: datetime | None = None,
    prompt_version: str = RANKING_INTERPRETATION_PROMPT_VERSION,
    schema_version: str = RANKING_INTERPRETATION_SCHEMA_VERSION,
) -> RankingInterpretationResult:
    """Explain how to inspect the frozen ranking without inventing conclusions."""

    by_id = {section.section_id: section for section in context.bundle.sections}
    candidate_notes = _fallback_candidate_notes(context, sections=by_id)
    warnings = list(context.warnings)
    if fallback_reason == "disabled":
        warnings.append("Ranking AI解釈のlive生成は設定で無効です。")
    else:
        warnings.append("live生成に失敗したため、表示済みデータの読み方だけを案内しています。")
    return RankingInterpretationResult(
        ranking_context_id=context.ranking_context_id,
        status=status,
        overall_reading=(
            "このメモは現在の順位とスコアを変更せず、上位候補の比較観点を整理する参考情報です。"
            "順位、主要指標、下振れ警戒、データ品質を別々に確認してください。"
        ),
        common_strengths=[
            RankingInterpretationPoint(
                summary="上位候補で共通する材料は、主要指標とスコア内訳の両方で確認してください。",
                evidence_ids=["ranking_metrics"],
            )
        ],
        common_cautions=[
            RankingInterpretationPoint(
                summary="ランキングは候補の比較結果であり、売買推奨や将来の利益保証ではありません。",
                evidence_ids=["ranking_scope"],
            )
        ],
        sector_notes=[
            RankingInterpretationPoint(
                summary="セクター比較は今回の候補集合内だけの傾向として確認してください。",
                evidence_ids=["ranking_sectors"],
            )
        ],
        candidate_notes=candidate_notes,
        next_checks=[
            RankingInterpretationPoint(
                summary="候補ごとの根拠資料、予測の不確実性、データ取得時刻を確認してください。",
                evidence_ids=context.candidate_ids[:5],
            )
        ],
        referenced_evidence_ids=context.allowed_evidence_ids,
        warnings=_dedupe(warnings),
        provider="deterministic",
        model="fallback",
        gateway_profile="fallback",
        generated_at=_ensure_utc(generated_at or datetime.now(UTC)),
        prompt_version=prompt_version,
        schema_version=schema_version,
        context_hash=context.context_hash,
        fallback_reason=fallback_reason,
        is_fallback=True,
    )


def _fallback_candidate_notes(
    context: RankingInterpretationContext,
    *,
    sections: Mapping[str, object],
) -> list[RankingCandidateInterpretationNote]:
    notes: list[RankingCandidateInterpretationNote] = []
    for candidate_id in context.candidate_ids:
        section = sections[candidate_id]
        summary = getattr(section, "summary", {})
        rank = summary.get("rank", "-")
        symbol = summary.get("symbol", candidate_id)
        metric = summary.get("primary_metric_label", "主要指標")
        notes.append(
            RankingCandidateInterpretationNote(
                candidate_id=candidate_id,
                reading=RankingInterpretationPoint(
                    summary=f"{rank}位 {symbol} は、表示中の{metric}と総合スコア内訳を確認してください。",
                    evidence_ids=[candidate_id, "ranking_metrics"],
                ),
                caution=RankingInterpretationPoint(
                    summary="順位だけで結論づけず、下振れ警戒・データ品質・根拠資料を分けて確認してください。",
                    evidence_ids=[candidate_id],
                ),
                next_check=RankingInterpretationPoint(
                    summary="候補カードから銘柄コックピットを開き、最新の根拠と更新日時を確認してください。",
                    evidence_ids=[candidate_id],
                ),
            )
        )
    return notes


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
