from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from .news_interpretation_models import (
    NEWS_INTERPRETATION_PROMPT_VERSION,
    NEWS_INTERPRETATION_SCHEMA_VERSION,
    NewsHandoffHint,
    NewsInterpretationContext,
    NewsInterpretationFallbackReason,
    NewsInterpretationPoint,
    NewsInterpretationResult,
    NewsInterpretationStatus,
    NewsMaterialNote,
    NewsSectorNote,
)


def build_deterministic_news_interpretation(
    context: NewsInterpretationContext,
    *,
    status: NewsInterpretationStatus,
    fallback_reason: NewsInterpretationFallbackReason,
    generated_at: datetime | None = None,
    prompt_version: str = NEWS_INTERPRETATION_PROMPT_VERSION,
    schema_version: str = NEWS_INTERPRETATION_SCHEMA_VERSION,
) -> NewsInterpretationResult:
    sections = {item.section_id: item for item in context.bundle.sections}
    quality = sections["news_source_quality"].summary
    warnings = list(context.warnings)
    warnings.append(
        "ニュースAI読み解きは設定で無効です。"
        if fallback_reason == "disabled"
        else "live生成を採用せず、保存済みニュースの確認手順を表示しています。"
    )
    material_notes = _material_notes(context, sections)
    sector_notes = _sector_notes(sections)
    handoffs = _handoff_hints(sections)
    noise = NewsInterpretationPoint(
        summary=(
            f'重複{quality.get("duplicate_count", "0")}件、stale{quality.get("stale_count", "0")}件、'
            f'鮮度不明{quality.get("unknown_freshness_count", "0")}件、入力上限外'
            f'{quality.get("capacity_excluded_count", "0")}件を区別しています。'
        ),
        evidence_ids=["news_source_quality"],
    )
    return NewsInterpretationResult(
        news_context_id=context.news_context_id,
        status=status,
        summary=NewsInterpretationPoint(
            summary=f'保存済みニュース{quality.get("headline_count", "0")}件を、主要材料、背景、ノイズに分けて確認します。これは投資順位や売買推奨ではありません。',
            evidence_ids=["news_scope", "news_source_quality"],
        ),
        material_notes=material_notes,
        sector_notes=sector_notes,
        noise_notes=[noise],
        handoff_hints=handoffs,
        unknowns=[
            NewsInterpretationPoint(
                summary="影響方向と時間軸は追加の開示、決算、政策情報で確認が必要です。",
                evidence_ids=["news_source_quality"],
            )
        ],
        next_checks=[
            NewsInterpretationPoint(
                summary="出典、公開日時、本文言及か推測かを確認してから、必要な候補だけコックピットで確認してください。",
                evidence_ids=["news_scope"],
            )
        ],
        referenced_evidence_ids=context.allowed_evidence_ids,
        warnings=list(dict.fromkeys(warnings)),
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


def _material_notes(
    context: NewsInterpretationContext, sections: Mapping[str, object]
) -> list[NewsMaterialNote]:
    notes: list[NewsMaterialNote] = []
    for material_id in context.allowed_material_ids:
        section = sections[material_id]
        title = str(getattr(section, "title", material_id))
        notes.append(
            NewsMaterialNote(
                material_id=material_id,
                business_impact_direction="unclear",
                impact_horizon="unclear",
                related_sector_ids=context.material_sector_ids.get(material_id, []),
                reading=NewsInterpretationPoint(
                    summary=f"{title}は出典と鮮度を確認し、事業・業績への影響方向は未確認として扱います。",
                    evidence_ids=[material_id],
                ),
                uncertainty=NewsInterpretationPoint(
                    summary="現在のニュースだけでは株価方向や確定的な業績影響を判断できません。",
                    evidence_ids=[material_id],
                ),
            )
        )
    return notes


def _sector_notes(sections: Mapping[str, object]) -> list[NewsSectorNote]:
    sector_section = sections.get("news_sector_relations")
    rows = getattr(sector_section, "rows", []) if sector_section is not None else []
    return [
        NewsSectorNote(
            sector_id=row["sector_id"],
            reading=NewsInterpretationPoint(
                summary=f'{row["sector_label"]}はカテゴリからの確認候補であり、影響方向の断定ではありません。',
                evidence_ids=["news_sector_relations"],
            ),
        )
        for row in rows
    ]


def _handoff_hints(sections: Mapping[str, object]) -> list[NewsHandoffHint]:
    handoff_section = sections.get("news_cockpit_handoffs")
    rows = getattr(handoff_section, "rows", []) if handoff_section is not None else []
    return [
        NewsHandoffHint(
            candidate_id=row["candidate_id"],
            reason=NewsInterpretationPoint(
                summary=f'{row["display_name"]}は{row["provenance"]}の確認候補として、コックピットで根拠を確認できます。',
                evidence_ids=["news_cockpit_handoffs"],
            ),
        )
        for row in rows
    ]


def _ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
