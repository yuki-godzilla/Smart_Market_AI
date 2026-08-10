from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from .radar_overview_models import (
    RADAR_OVERVIEW_INTERPRETATION_PROMPT_VERSION,
    RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION,
    RadarOverviewDeepDiveHint,
    RadarOverviewInterpretationContext,
    RadarOverviewInterpretationFallbackReason,
    RadarOverviewInterpretationPoint,
    RadarOverviewInterpretationResult,
    RadarOverviewInterpretationStatus,
    RadarOverviewSectorNote,
    RadarOverviewThemeNote,
)


def build_deterministic_radar_overview_interpretation(
    context: RadarOverviewInterpretationContext,
    *,
    status: RadarOverviewInterpretationStatus,
    fallback_reason: RadarOverviewInterpretationFallbackReason,
    generated_at: datetime | None = None,
    prompt_version: str = RADAR_OVERVIEW_INTERPRETATION_PROMPT_VERSION,
    schema_version: str = RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION,
) -> RadarOverviewInterpretationResult:
    """Build a compact reading guide without generating market conclusions."""

    sections = {item.section_id: item for item in context.bundle.sections}
    scope = sections["radar_scope"].summary
    direct = scope.get("direct_mention_count", "0")
    inferred = scope.get("inferred_candidate_count", "0")
    macro = scope.get("macro_proxy_count", "0")
    movement = _movement_point(context, sections=sections)
    warnings = list(context.warnings)
    if fallback_reason == "disabled":
        warnings.append("投資レーダーのOverview AI解釈は設定で無効です。")
    else:
        warnings.append("live生成を採用せず、表示済みデータの確認手順を案内しています。")
    return RadarOverviewInterpretationResult(
        radar_context_id=context.radar_context_id,
        status=status,
        summary=RadarOverviewInterpretationPoint(
            summary=(
                f"本文言及{direct}件、テーマ推測{inferred}件、市場背景{macro}件を別々に確認します。"
                "これは確認候補の整理であり、投資順位や売買推奨ではありません。"
            ),
            evidence_ids=["radar_scope"],
        ),
        candidate_set_movement=movement,
        sector_notes=_sector_notes(context, sections=sections),
        theme_notes=_theme_notes(context, sections=sections),
        deep_dive_hints=_deep_dive_hints(context, sections=sections),
        unknowns=_unknown_points(context),
        next_checks=_next_checks(context),
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


def _movement_point(
    context: RadarOverviewInterpretationContext, *, sections: Mapping[str, object]
) -> RadarOverviewInterpretationPoint | None:
    if context.market_state not in {"fresh", "partial"}:
        return None
    section = sections["radar_market_breadth"]
    summary = getattr(section, "summary", {})
    if summary.get("direction_available") != "yes":
        return None
    measured = summary.get("measured_count", "0")
    unavailable = summary.get("unavailable_count", "0")
    return RadarOverviewInterpretationPoint(
        summary=(
            f"取得済み候補{measured}件の値動きを確認できます。未取得は{unavailable}件です。"
            "この範囲を市場全体の動きとして扱わないでください。"
        ),
        evidence_ids=["radar_market_breadth"],
    )


def _sector_notes(
    context: RadarOverviewInterpretationContext, *, sections: Mapping[str, object]
) -> list[RadarOverviewSectorNote]:
    if context.market_state not in {"fresh", "partial"}:
        return []
    section = sections["radar_sector_comparison"]
    rows = getattr(section, "rows", [])
    return [
        RadarOverviewSectorNote(
            sector_id=row["sector_id"],
            reading=RadarOverviewInterpretationPoint(
                summary=(
                    f'{row["sector_label"]}は測定候補{row["measured_count"]}件です。'
                    "候補集合内の比較として確認してください。"
                ),
                evidence_ids=["radar_sector_comparison"],
            ),
        )
        for row in rows
    ]


def _theme_notes(
    context: RadarOverviewInterpretationContext, *, sections: Mapping[str, object]
) -> list[RadarOverviewThemeNote]:
    notes: list[RadarOverviewThemeNote] = []
    for theme_id in context.allowed_theme_ids:
        section = sections[theme_id]
        summary = getattr(section, "summary", {})
        related = context.theme_candidate_ids.get(theme_id, [])
        notes.append(
            RadarOverviewThemeNote(
                theme_id=theme_id,
                related_candidate_ids=related,
                reading=RadarOverviewInterpretationPoint(
                    summary=(
                        f'{summary.get("theme_label", "未分類テーマ")}は、ニュース根拠の量と鮮度を'
                        "確認し、本文言及とテーマ推測を区別して読んでください。"
                    ),
                    evidence_ids=[theme_id],
                ),
            )
        )
    return notes


def _deep_dive_hints(
    context: RadarOverviewInterpretationContext, *, sections: Mapping[str, object]
) -> list[RadarOverviewDeepDiveHint]:
    hints: list[RadarOverviewDeepDiveHint] = []
    for candidate_id in context.deep_dive_candidate_ids:
        section = sections[candidate_id]
        summary = getattr(section, "summary", {})
        hints.append(
            RadarOverviewDeepDiveHint(
                candidate_id=candidate_id,
                reason=RadarOverviewInterpretationPoint(
                    summary=(
                        f'{summary.get("display_name", summary.get("symbol", candidate_id))}は、'
                        "候補詳細で根拠記事、鮮度、確認不足を順に確認できます。"
                    ),
                    evidence_ids=[candidate_id],
                ),
            )
        )
    return hints


def _unknown_points(
    context: RadarOverviewInterpretationContext,
) -> list[RadarOverviewInterpretationPoint]:
    if context.market_state == "missing":
        message = "候補価格が未取得のため、候補集合とセクターの値動きは未確認です。"
    elif context.market_state == "stale":
        message = "候補価格が古いため、現在の値動きとしては扱いません。"
    elif context.market_state == "partial":
        message = "価格未取得の候補があるため、表示中の比較には未確認範囲があります。"
    else:
        return []
    return [
        RadarOverviewInterpretationPoint(
            summary=message,
            evidence_ids=["radar_market_breadth"],
        )
    ]


def _next_checks(
    context: RadarOverviewInterpretationContext,
) -> list[RadarOverviewInterpretationPoint]:
    evidence_ids = context.deep_dive_candidate_ids or ["radar_scope"]
    return [
        RadarOverviewInterpretationPoint(
            summary=(
                "候補詳細を開き、本文言及かテーマ推測かを確認したうえで、必要な候補だけ根拠資料を確認してください。"
            ),
            evidence_ids=evidence_ids[:2],
        )
    ]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
