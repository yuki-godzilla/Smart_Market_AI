"""Pure assembly for the company quantitative Research summary."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from backend.research.contracts import QuantitativeSummary, ResearchEvidenceLevel


@dataclass(frozen=True)
class QuantitativeFieldValue:
    """One already-resolved quantitative value and its user-facing label."""

    key: str
    label: str
    value: str | None


def build_quantitative_summary(
    fields: Sequence[QuantitativeFieldValue],
    *,
    source_titles: Sequence[str],
    source_types: Sequence[str],
    evidence_level_from_source_types: Callable[[Sequence[str]], ResearchEvidenceLevel],
    unique_text: Callable[[Sequence[str]], list[str]],
) -> QuantitativeSummary:
    """Build the established deterministic summary from already-selected metric values."""

    values = {field.key: field.value for field in fields}
    missing_items = [field.label for field in fields if not field.value]
    found_items = [f"{field.label} {field.value}" for field in fields if field.value]
    if found_items:
        summary = f"確認できた主要指標は{'、'.join(found_items[:5])}です。"
        if missing_items:
            summary += f"{'、'.join(missing_items[:5])}は追加確認が必要です。"
    else:
        summary = "主要な財務指標が未取得のため、業績トレンドや規模感の把握には追加確認が必要です。"
    return QuantitativeSummary(
        revenue=values["revenue"],
        operating_profit=values["operating_profit"],
        net_income=values["net_income"],
        eps=values["eps"],
        per=values["per"],
        pbr=values["pbr"],
        roe=values["roe"],
        dividend_yield=values["dividend_yield"],
        market_cap=values["market_cap"],
        enterprise_value=values["enterprise_value"],
        employee_count=values["employee_count"],
        summary=summary,
        missing_items=missing_items,
        item_statuses={field.key: "found" if field.value else "missing" for field in fields},
        information_status="found" if found_items else "missing",
        evidence_level=evidence_level_from_source_types(source_types),
        source_titles=unique_text(source_titles)[:5],
    )
