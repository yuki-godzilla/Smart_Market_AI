from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from backend.assistant import AssistantContextBundle, AssistantContextSection
from backend.llm_factor import LLMFactorResult

from .models import CockpitInterpretationContext

_MAX_TEXT_CHARS = 260


def build_cockpit_interpretation_context(
    *,
    symbol: str,
    as_of: date,
    company_name: str | None = None,
    price_summary: Mapping[str, object] | None = None,
    forecast_summary: Mapping[str, object] | None = None,
    investment_score: Mapping[str, object] | None = None,
    research_evidence: Sequence[Mapping[str, object]] | None = None,
    llm_factor: LLMFactorResult | None = None,
    warnings: list[str] | None = None,
    max_research_evidence: int = 6,
    max_text_chars: int = _MAX_TEXT_CHARS,
    now: datetime | None = None,
) -> CockpitInterpretationContext:
    """Compress visible Cockpit information into a Gateway-safe context bundle."""

    created_at = _ensure_utc(now or datetime.now(UTC))
    warning_items = _clean_strings(warnings or [], max_chars=max_text_chars)
    missing_fields: list[str] = []
    sections: list[AssistantContextSection] = []

    if price_summary:
        sections.append(
            _section(
                section_id="price_summary",
                title="価格サマリー",
                source_kind="cockpit_price",
                summary=_safe_mapping(price_summary, max_chars=max_text_chars),
                warnings=[],
                notes=["価格は短期の動きとデータ鮮度を分けて確認してください。"],
                symbol=symbol,
            )
        )
    else:
        missing_fields.append("price_summary")

    if forecast_summary:
        sections.append(
            _section(
                section_id="forecast_summary",
                title="AI予測サマリー",
                source_kind="cockpit_forecast",
                summary=_safe_mapping(forecast_summary, max_chars=max_text_chars),
                warnings=[],
                notes=["予測値は不確実性とモデル合意度を合わせて確認してください。"],
                symbol=symbol,
            )
        )
    else:
        missing_fields.append("forecast_summary")

    if investment_score:
        sections.append(
            _section(
                section_id="investment_score",
                title="Investment Score",
                source_kind="cockpit_score",
                summary=_safe_mapping(investment_score, max_chars=max_text_chars),
                warnings=[],
                notes=["Investment Scoreは再計算せず、内訳の偏りだけ確認材料にします。"],
                symbol=symbol,
            )
        )
    else:
        missing_fields.append("investment_score")

    evidence_rows = _research_evidence_rows(
        research_evidence or [],
        max_items=max_research_evidence,
        max_chars=max_text_chars,
    )
    if evidence_rows:
        sections.append(
            _section(
                section_id="research_evidence",
                title="Research Evidence",
                source_kind="cockpit_research",
                summary={"件数": str(len(evidence_rows))},
                rows=evidence_rows,
                warnings=[],
                notes=["出典の新しさ、種別、未確認材料を分けて確認してください。"],
                symbol=symbol,
            )
        )
    else:
        missing_fields.append("research_evidence")

    if llm_factor is not None:
        sections.append(
            _section(
                section_id="llm_factor",
                title="AI材料分析",
                source_kind="cockpit_llm_factor",
                summary=_llm_factor_summary(llm_factor, max_chars=max_text_chars),
                rows=_llm_factor_rows(llm_factor, max_chars=max_text_chars),
                warnings=_clean_strings(llm_factor.warnings, max_chars=max_text_chars),
                notes=["AI材料分析は参考表示であり、スコアや予測値には反映していません。"],
                symbol=symbol,
            )
        )
    else:
        missing_fields.append("llm_factor")

    if not sections:
        sections.append(
            _section(
                section_id="empty_context",
                title="Cockpit 表示材料",
                source_kind="cockpit_empty",
                summary={"状態": "表示中の材料が不足しています。"},
                warnings=warning_items,
                notes=["価格、予測、Research Evidence、AI材料分析を順に確認してください。"],
                symbol=symbol,
            )
        )

    bundle = AssistantContextBundle(
        bundle_id=f"cockpit-interpretation-{symbol}-{as_of.isoformat()}",
        title=f"Cockpit Interpretation - {symbol}",
        source="streamlit_context",
        created_at=created_at,
        active_context_id="cockpit_interpretation",
        sections=sections,
        tags=["cockpit", "interpretation", symbol],
        privacy_notes=[
            "Provider raw fields, debug logs, and full external source bodies are excluded.",
            "The bundle is for interpretation support, not score or forecast recomputation.",
        ],
    )
    context_hash = cockpit_interpretation_context_hash(bundle)
    allowed_ids = sorted(
        {section.section_id for section in sections}
        | {
            str(row.get("evidence_id") or "").strip()
            for section in sections
            for row in section.rows
            if str(row.get("evidence_id") or "").strip()
        }
    )
    return CockpitInterpretationContext(
        symbol=symbol,
        company_name=company_name,
        as_of=as_of,
        bundle=bundle,
        context_hash=context_hash,
        allowed_evidence_ids=allowed_ids,
        warnings=warning_items,
        missing_fields=missing_fields,
    )


def cockpit_interpretation_context_hash(bundle: AssistantContextBundle) -> str:
    payload = bundle.model_dump(mode="json")
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _section(
    *,
    section_id: str,
    title: str,
    source_kind: str,
    summary: Mapping[str, str],
    rows: list[dict[str, str]] | None = None,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
    symbol: str,
) -> AssistantContextSection:
    return AssistantContextSection(
        section_id=section_id,
        title=title,
        source_kind=source_kind,
        symbol=symbol,
        summary=dict(summary),
        rows=rows or [],
        warnings=warnings or [],
        notes=notes or [],
        included_fields=sorted(summary.keys()),
    )


def _research_evidence_rows(
    values: Sequence[Mapping[str, object]],
    *,
    max_items: int,
    max_chars: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, item in enumerate(values[:max_items], start=1):
        row = _safe_mapping(item, max_chars=max_chars)
        row.setdefault("evidence_id", f"research_{index:03d}")
        rows.append(row)
    return rows


def _llm_factor_summary(result: LLMFactorResult, *, max_chars: int) -> dict[str, str]:
    return {
        "overall_summary": _trim(result.summary, max_chars),
        "sentiment_label": _trim(result.sentiment_label or "unknown", max_chars),
        "confidence_score": _decimal_text(result.llm_confidence_score),
        "bullish_score": _decimal_text(result.llm_bullish_score),
        "bearish_score": _decimal_text(result.llm_bearish_score),
        "gateway_status": _trim(result.gateway_status, max_chars),
        "fallback_reason": _trim(result.fallback_reason or "", max_chars),
    }


def _llm_factor_rows(result: LLMFactorResult, *, max_chars: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, factor in enumerate(result.bullish_factors[:3], start=1):
        rows.append(
            {
                "evidence_id": f"llm_factor_positive_{index:03d}",
                "kind": "positive",
                "title": _trim(factor.title, max_chars),
                "summary": _trim(factor.reason, max_chars),
                "score": _decimal_text(factor.score),
                "source_date": factor.source_date.isoformat(),
            }
        )
    for index, bearish_factor in enumerate(result.bearish_factors[:3], start=1):
        rows.append(
            {
                "evidence_id": f"llm_factor_caution_{index:03d}",
                "kind": "caution",
                "title": _trim(bearish_factor.title, max_chars),
                "summary": _trim(bearish_factor.reason, max_chars),
                "score": _decimal_text(bearish_factor.score),
                "source_date": bearish_factor.source_date.isoformat(),
            }
        )
    return rows


def _safe_mapping(values: Mapping[str, object], *, max_chars: int) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in values.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        if _should_redact(normalized_key):
            continue
        normalized_value = _trim(_value_text(value), max_chars)
        if normalized_value:
            result[normalized_key] = normalized_value
    return result


def _clean_strings(values: list[str], *, max_chars: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _trim(value, max_chars)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _value_text(value: object) -> str:
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _decimal_text(value: Decimal) -> str:
    return f"{value.normalize():f}".rstrip("0").rstrip(".")


def _trim(value: object, max_chars: int) -> str:
    text = str(value).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _should_redact(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(
        marker in normalized
        for marker in (
            "raw",
            "payload",
            "debug",
            "traceback",
            "html",
            "source_text",
            "body",
        )
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
