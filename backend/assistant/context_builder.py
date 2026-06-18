from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import Field

from backend.assistant.tool_registry import AssistantActionSpec, assistant_actions_for_page
from backend.core.data_contracts import StrictBaseModel
from backend.reporting import DecisionReportContext

AssistantPageName = Literal[
    "ranking",
    "cockpit",
    "news",
    "rebalance",
    "settings",
    "assistant",
    "unknown",
]


class SMAIAssistantContext(StrictBaseModel):
    """Compact current-page context for proposing safe next actions."""

    current_page: AssistantPageName = "unknown"
    user_question: str | None = Field(default=None, min_length=1)
    summary: str = ""
    page_state: dict[str, Any] = Field(default_factory=dict)
    material_state: dict[str, Any] = Field(default_factory=dict)
    available_actions: list[AssistantActionSpec] = Field(default_factory=list)
    missing_materials: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_assistant_context(
    *,
    current_page: str | None = None,
    user_question: str | None = None,
    page_state: Mapping[str, Any] | None = None,
    material_state: Mapping[str, Any] | None = None,
    report_context: DecisionReportContext | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> SMAIAssistantContext:
    page = _normalize_page(current_page or _page_from_report_context(report_context))
    clean_page_state = _compact_mapping(page_state or {})
    clean_material_state = _compact_mapping(material_state or {})
    report_material_state = _material_state_from_report_context(report_context)
    merged_material_state = {**report_material_state, **clean_material_state}
    missing_materials = _missing_materials_for_page(page, merged_material_state)
    warnings = _warnings_for_context(
        page=page,
        page_state=clean_page_state,
        material_state=merged_material_state,
        report_context=report_context,
    )
    return SMAIAssistantContext(
        current_page=page,
        user_question=_clean_text(user_question) or None,
        summary=_summary_for_context(
            page=page,
            page_state=clean_page_state,
            material_state=merged_material_state,
            missing_materials=missing_materials,
        ),
        page_state=clean_page_state,
        material_state=merged_material_state,
        available_actions=list(assistant_actions_for_page(page)),
        missing_materials=missing_materials,
        warnings=warnings,
        metadata=_compact_mapping(metadata or {}),
    )


def _normalize_page(value: str | None) -> AssistantPageName:
    text = str(value or "").strip().lower()
    aliases = {
        "銘柄ランキング": "ranking",
        "ranking": "ranking",
        "rank": "ranking",
        "銘柄コックピット": "cockpit",
        "symbol cockpit": "cockpit",
        "cockpit": "cockpit",
        "投資レーダー": "news",
        "news": "news",
        "radar": "news",
        "investment radar": "news",
        "リバランス": "rebalance",
        "rebalance": "rebalance",
        "settings": "settings",
        "設定": "settings",
        "assistant": "assistant",
        "smaiアシスタント": "assistant",
        "smai assistant": "assistant",
    }
    return aliases.get(text, "unknown")  # type: ignore[return-value]


def _page_from_report_context(report_context: DecisionReportContext | None) -> str:
    if report_context is None:
        return "unknown"
    haystack = " ".join(
        [
            report_context.title,
            *(tag for tag in report_context.tags),
            *(section.title for section in report_context.sections),
            *(section.source.kind for section in report_context.sections),
            *(
                str(value)
                for section in report_context.sections
                for value in section.summary.values()
            ),
        ]
    ).lower()
    if any(term in haystack for term in ("ranking", "ランキング")):
        return "ranking"
    if any(term in haystack for term in ("cockpit", "コックピット")):
        return "cockpit"
    if any(term in haystack for term in ("news", "ニュース", "投資レーダー")):
        return "news"
    if any(term in haystack for term in ("rebalance", "リバランス")):
        return "rebalance"
    if any(term in haystack for term in ("settings", "設定")):
        return "settings"
    if any(term in haystack for term in ("assistant", "アシスタント")):
        return "assistant"
    return "unknown"


def _material_state_from_report_context(
    report_context: DecisionReportContext | None,
) -> dict[str, Any]:
    if report_context is None:
        return {}
    joined = " ".join(
        [
            report_context.title,
            *(section.title for section in report_context.sections),
            *(
                str(value)
                for section in report_context.sections
                for value in section.summary.values()
            ),
            *(note for section in report_context.sections for note in section.notes),
        ]
    ).lower()
    return {
        "price_data_status": (
            "available"
            if any(term in joined for term in ("価格", "price", "chart", "cockpit"))
            else "missing"
        ),
        "forecast_status": (
            "available"
            if any(term in joined for term in ("予測", "forecast", "上昇気配", "下降警戒"))
            else "missing"
        ),
        "research_status": (
            "available"
            if any(term in joined for term in ("research", "rag", "根拠", "evidence"))
            else "missing"
        ),
        "news_status": (
            "available"
            if any(term in joined for term in ("news", "ニュース", "開示", "tdnet"))
            else "missing"
        ),
        "decision_report_status": "available" if report_context.sections else "missing",
    }


def _missing_materials_for_page(
    page: AssistantPageName,
    material_state: Mapping[str, Any],
) -> list[str]:
    missing: list[str] = []

    def is_missing(key: str) -> bool:
        return _status_missing(material_state.get(key))

    if page == "cockpit":
        if is_missing("price_data_status"):
            missing.append("価格データ")
        if is_missing("forecast_status"):
            missing.append("AI予測インサイト")
        if is_missing("research_status"):
            missing.append("AI調査 / Research Evidence")
    elif page == "ranking":
        if is_missing("ranking_result_status"):
            missing.append("ランキング結果")
        if is_missing("top_symbols_available"):
            missing.append("上位候補")
    elif page == "news":
        if is_missing("news_status"):
            missing.append("投資レーダーのニュース")
    return missing


def _warnings_for_context(
    *,
    page: AssistantPageName,
    page_state: Mapping[str, Any],
    material_state: Mapping[str, Any],
    report_context: DecisionReportContext | None,
) -> list[str]:
    warnings: list[str] = []
    if report_context is None and page != "assistant":
        warnings.append("現在画面の詳細材料が少ないため、一般的な確認順として提案します。")
    if page == "cockpit" and _status_missing(material_state.get("research_status")):
        warnings.append("根拠資料が未取得の場合は、AI調査を更新してから材料を確認します。")
    if page == "ranking" and _status_missing(page_state.get("candidate_count")):
        warnings.append("候補数が未確認のため、条件とランキング作成状態を先に確認します。")
    return warnings


def _summary_for_context(
    *,
    page: AssistantPageName,
    page_state: Mapping[str, Any],
    material_state: Mapping[str, Any],
    missing_materials: Sequence[str],
) -> str:
    page_label = {
        "ranking": "銘柄ランキング",
        "cockpit": "銘柄コックピット",
        "news": "投資レーダー",
        "rebalance": "リバランス",
        "settings": "設定",
        "assistant": "SMAIアシスタント",
        "unknown": "不明な画面",
    }[page]
    details: list[str] = [f"現在画面: {page_label}"]
    active_symbol = _clean_text(
        page_state.get("active_symbol") or page_state.get("selected_symbol")
    )
    if active_symbol:
        details.append(f"選択銘柄: {active_symbol}")
    ranking_policy = _clean_text(page_state.get("ranking_policy"))
    if ranking_policy:
        details.append(f"評価方針: {ranking_policy}")
    candidate_count = _clean_text(page_state.get("candidate_count"))
    if candidate_count:
        details.append(f"候補数: {candidate_count}")
    research_status = _clean_text(material_state.get("research_status"))
    if research_status:
        details.append(f"AI調査: {research_status}")
    if missing_materials:
        details.append("未確認材料: " + " / ".join(missing_materials[:4]))
    return " / ".join(details)


def _compact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        clean_key = _clean_text(key)
        if not clean_key:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[clean_key] = value
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            result[clean_key] = [_clean_text(item) for item in value[:8]]
        else:
            result[clean_key] = _clean_text(value)[:240]
    return result


def _status_missing(value: Any) -> bool:
    text = _clean_text(value).lower()
    return not text or text in {"missing", "none", "false", "0", "未取得", "なし", "unknown"}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
