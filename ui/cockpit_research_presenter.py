"""Streamlit-independent presentation models for the Cockpit Research section."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from backend.research import (
    CompanyResearchReport,
    ExternalResearchFetchResult,
    ResearchBriefBuilder,
    StockNewsReport,
)
from ui.content.research_texts import RESEARCH_FETCH_BUTTON_LABEL
from ui.styles import truncate_text


@dataclass(frozen=True)
class CockpitResearchMaterialGroup:
    """One labeled group of research materials for the refresh operation card."""

    label: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class CockpitResearchOperationCard:
    """All display values for the Cockpit Research refresh operation."""

    title: str
    summary: str
    status_chips: tuple[tuple[str, str], ...]
    material_groups: tuple[CockpitResearchMaterialGroup, ...]
    action_label: str


def build_cockpit_research_operation_card(
    report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
    external_result: ExternalResearchFetchResult | None = None,
) -> CockpitResearchOperationCard:
    """Build the refresh-card model without touching Streamlit state or rendering HTML."""

    status_chips = research_operation_status_chips(report, news_report, external_result)
    if report is None:
        return CockpitResearchOperationCard(
            title="AI調査はまだ未取得です",
            summary="ニュース、IR、開示、保存済み資料を確認し、注目材料と注意材料を整理します。",
            status_chips=status_chips,
            material_groups=(),
            action_label=RESEARCH_FETCH_BUTTON_LABEL,
        )

    brief = ResearchBriefBuilder().build(report, news_report=news_report)
    status = dict(status_chips)
    if external_result is not None:
        summary = (
            f"重複なしの根拠候補{status['根拠候補']}（公式{status['公式']} / "
            f"ニュース{status['ニュース']} / 外部プロファイル{status['外部プロファイル']}）を確認"
        )
    else:
        summary = (
            f"ニュース{status['ニュース']} / IR・開示{status['IR/開示']} / "
            f"外部データ{status['外部データ']}を確認"
        )
    positive = tuple(
        research_brief_ui_text(item.summary, max_chars=88) for item in brief.positive_materials[:3]
    ) or tuple(research_brief_ui_text(item, max_chars=88) for item in brief.positive_candidates[:3])
    caution = tuple(
        research_brief_ui_text(item.summary, max_chars=88) for item in brief.caution_materials[:3]
    ) or tuple(research_brief_ui_text(item, max_chars=88) for item in brief.caution_candidates[:3])
    material_groups = tuple(
        CockpitResearchMaterialGroup(label=label, items=items)
        for label, items in (("注目材料", positive), ("注意材料", caution))
        if items
    )
    return CockpitResearchOperationCard(
        title="AI調査結果",
        summary=summary,
        status_chips=status_chips,
        material_groups=material_groups,
        action_label="AI調査を更新",
    )


def research_operation_status_chips(
    report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
    external_result: ExternalResearchFetchResult | None = None,
) -> tuple[tuple[str, str], ...]:
    """Return source-state labels without assigning investment meaning to data availability."""

    if external_result is not None:
        official_source_types = {
            "annual_report",
            "earnings_report",
            "earnings_presentation",
            "medium_term_plan",
            "integrated_report",
            "company_ir",
            "tdnet",
        }
        official_count = sum(
            1 for entry in external_result.entries if entry.source_type in official_source_types
        )
        news_count = sum(1 for entry in external_result.entries if entry.source_type == "news")
        profile_count = sum(
            1 for entry in external_result.entries if entry.source_type == "provider_profile"
        )
        return (
            ("レポート", "作成済み" if report is not None else "未取得"),
            ("根拠候補", f"{len(external_result.entries)}件"),
            ("公式", f"{official_count}件"),
            ("ニュース", f"{news_count}件"),
            ("外部プロファイル", f"{profile_count}件"),
            ("最終取得", _datetime_display_text(external_result.fetched_at)),
        )
    source_types = {
        evidence.source_type.strip().lower()
        for evidence in (report.evidence if report is not None else [])
    }
    ir_source_types = {
        "annual_report",
        "earnings_report",
        "financial_results",
        "tdnet",
        "company_ir",
    }
    ir_count = sum(
        1
        for evidence in (report.evidence if report is not None else [])
        if evidence.source_type.strip().lower() in ir_source_types
    )
    external_data_count = sum(
        1
        for evidence in (report.evidence if report is not None else [])
        if evidence.source_type.strip().lower() == "provider_profile"
    )
    return (
        ("レポート", "作成済み" if report is not None else "未取得"),
        ("ニュース", f"{len(news_report.news) if news_report is not None else 0}件"),
        ("IR/開示", f"{ir_count}件" if source_types & ir_source_types else "未確認"),
        ("外部データ", f"{external_data_count}件" if external_data_count else "未確認"),
    )


def research_brief_ui_text(text: str, *, max_chars: int) -> str:
    """Normalize provider-profile boilerplate before rendering a short research material."""

    cleaned = " ".join(text.split())
    if cleaned.lower() in {"nan", "none", "null", "raw"}:
        return ""
    cleaned = re.sub(r"\bCompany Name:\s*", "", cleaned, flags=re.IGNORECASE)
    for label in ("Provider Symbol", "Quote Type", "Exchange", "Currency"):
        cleaned = re.sub(rf"\b{label}:\s*\S+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\bSector:\s*[^:]+?(?=\s+(?:Industry|Business Summary|Summary):|$)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\bIndustry:\s*[^:]+?(?=\s+(?:Business Summary|Summary):|$)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.strip().lower() in {"nan", "none", "null", "raw"}:
        return ""
    return truncate_text(cleaned.strip(), max_chars=max_chars)


def _datetime_display_text(value: datetime) -> str:
    return value.isoformat(timespec="minutes")
