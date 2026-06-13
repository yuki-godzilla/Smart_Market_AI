from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from backend.reporting import (
    DecisionReportContext,
    build_decision_report_context,
    build_report_section,
)

AssistantToolStatus = Literal["ok", "missing", "failed"]


@dataclass(frozen=True)
class AssistantCurrentContext:
    screen: str
    symbol: str | None
    company_name: str | None
    analysis_mode: str
    has_price: bool
    has_forecast: bool
    has_news: bool
    has_research: bool
    has_decision_report: bool


@dataclass(frozen=True)
class AssistantToolResult:
    name: str
    status: AssistantToolStatus
    summary: str
    details: dict[str, str] = field(default_factory=dict)
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssistantToolPlanResult:
    intent: str
    current_context: AssistantCurrentContext
    executed: tuple[AssistantToolResult, ...]
    report_context: DecisionReportContext | None = None


class AssistantToolLayer:
    """Read-only tool layer for Assistant agent planning over safe SMAI context."""

    def get_current_context(
        self,
        report_context: DecisionReportContext | None,
        *,
        analysis_mode: str = "SMAIアシスタント",
    ) -> AssistantCurrentContext:
        sections = tuple(report_context.sections) if report_context else ()
        joined = " ".join(
            [
                *(section.title for section in sections),
                *(str(value) for section in sections for value in section.summary.values()),
            ]
        ).lower()
        symbol = next(
            (section.source.symbol for section in sections if section.source.symbol),
            None,
        )
        return AssistantCurrentContext(
            screen=report_context.title if report_context else "SMAIアシスタント",
            symbol=symbol,
            company_name=None,
            analysis_mode=analysis_mode,
            has_price=any(term in joined for term in ("価格", "price", "chart", "cockpit")),
            has_forecast=any(term in joined for term in ("予測", "forecast", "upside", "downside")),
            has_news=any(term in joined for term in ("news", "ニュース", "開示", "tdnet")),
            has_research=any(term in joined for term in ("research", "rag", "根拠", "evidence")),
            has_decision_report=report_context is not None,
        )

    def resolve_symbol(
        self,
        query: str,
        report_context: DecisionReportContext | None = None,
    ) -> AssistantToolResult:
        context_symbol = None
        if report_context is not None:
            context_symbol = next(
                (
                    section.source.symbol
                    for section in report_context.sections
                    if section.source.symbol
                ),
                None,
            )
        symbol = _symbol_from_query(query) or context_symbol
        if symbol:
            return AssistantToolResult(
                name="resolve_symbol",
                status="ok",
                summary=f"銘柄を特定: {symbol}",
                details={"symbol": symbol},
            )
        return AssistantToolResult(
            name="resolve_symbol",
            status="missing",
            summary="銘柄を特定できませんでした。",
        )

    def get_price_summary(
        self,
        report_context: DecisionReportContext | None,
        symbol: str | None,
    ) -> AssistantToolResult:
        section = _find_section(report_context, ("価格", "price", "chart", "cockpit"))
        if section is None:
            return AssistantToolResult(
                name="get_price_summary",
                status="missing",
                summary="価格データは現在の文脈にありません。",
                details={"symbol": symbol or ""},
            )
        return AssistantToolResult(
            name="get_price_summary",
            status="ok",
            summary=f"価格・チャート文脈を確認: {section.title}",
            details=_stringify_mapping(section.summary),
            sources=(section.title,),
        )

    def get_forecast_summary(
        self,
        report_context: DecisionReportContext | None,
        symbol: str | None,
    ) -> AssistantToolResult:
        section = _find_section(report_context, ("予測", "forecast", "upside", "downside"))
        if section is None:
            return AssistantToolResult(
                name="get_forecast_summary",
                status="missing",
                summary="AI予測インサイトは現在の文脈にありません。",
                details={"symbol": symbol or ""},
            )
        return AssistantToolResult(
            name="get_forecast_summary",
            status="ok",
            summary=f"AI予測インサイトを確認: {section.title}",
            details=_stringify_mapping(section.summary),
            sources=(section.title,),
        )

    def search_news_materials(
        self,
        report_context: DecisionReportContext | None,
        query: str,
    ) -> AssistantToolResult:
        section = _find_section(report_context, ("news", "ニュース", "開示", "tdnet"))
        if section is None:
            return AssistantToolResult(
                name="search_news_materials",
                status="missing",
                summary="ニュース材料は現在の文脈にありません。",
                details={"query": query},
            )
        return AssistantToolResult(
            name="search_news_materials",
            status="ok",
            summary=f"ニュース・開示材料を確認: {section.title}",
            details=_stringify_mapping(section.summary),
            sources=(section.title,),
        )

    def search_rag_materials(
        self,
        report_context: DecisionReportContext | None,
        query: str,
    ) -> AssistantToolResult:
        section = _find_section(report_context, ("research", "rag", "根拠", "evidence"))
        if section is None:
            return AssistantToolResult(
                name="search_rag_materials",
                status="missing",
                summary="Research Evidenceは現在の文脈にありません。",
                details={"query": query},
            )
        return AssistantToolResult(
            name="search_rag_materials",
            status="ok",
            summary=f"Research Evidenceを確認: {section.title}",
            details=_stringify_mapping(section.summary),
            sources=(section.title,),
        )

    def build_decision_report(
        self,
        current_context: AssistantCurrentContext,
        tool_results: tuple[AssistantToolResult, ...],
    ) -> DecisionReportContext:
        section = build_report_section(
            title="SMAIアシスタント / Tool結果",
            source_kind="manual",
            symbol=current_context.symbol,
            summary={
                "画面": current_context.screen,
                "分析モード": current_context.analysis_mode,
                "実行した確認": ", ".join(
                    result.summary for result in tool_results if result.status == "ok"
                )
                or "取得済み材料なし",
            },
            rows=[
                {
                    "tool": result.name,
                    "status": result.status,
                    "summary": result.summary,
                }
                for result in tool_results
            ],
            warnings=[
                result.summary for result in tool_results if result.status in {"missing", "failed"}
            ],
            notes=["Assistant Tool Layerはread-onlyで、スコアや予測値は変更しません。"],
        )
        return build_decision_report_context(
            title="SMAIアシスタント Decision Report下書き",
            sections=[section],
        )

    def export_markdown_report(
        self,
        report_markdown: str,
        output_dir: Path,
        *,
        symbol: str | None = None,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        prefix = f"{_safe_filename_part(symbol)}_decision_memo" if symbol else "smai_assistant_memo"
        path = output_dir / f"{prefix}_{timestamp}.md"
        suffix = 1
        while path.exists():
            path = output_dir / f"{prefix}_{timestamp}_{suffix}.md"
            suffix += 1
        path.write_text(report_markdown, encoding="utf-8")
        return path


def execute_assistant_tool_plan(
    *,
    intent: str,
    message: str,
    report_context: DecisionReportContext | None,
    tool_layer: AssistantToolLayer | None = None,
) -> AssistantToolPlanResult:
    tools = tool_layer or AssistantToolLayer()
    current_context = tools.get_current_context(report_context, analysis_mode=intent)
    symbol_result = tools.resolve_symbol(message, report_context)
    symbol = symbol_result.details.get("symbol") or current_context.symbol
    executed: list[AssistantToolResult] = [symbol_result]

    if intent in {
        "stock_summary",
        "chart_check",
        "forecast_check",
        "forecast_risk_compare",
        "decision_report_draft",
    }:
        executed.append(tools.get_price_summary(report_context, symbol))
    if intent in {
        "stock_summary",
        "forecast_check",
        "forecast_risk_compare",
        "decision_report_draft",
    }:
        executed.append(tools.get_forecast_summary(report_context, symbol))
    if intent in {"stock_summary", "news_materials", "decision_report_draft"}:
        executed.append(tools.search_news_materials(report_context, message))
    if intent in {"stock_summary", "rag_search", "decision_report_draft"}:
        executed.append(tools.search_rag_materials(report_context, message))

    report = (
        tools.build_decision_report(current_context, tuple(executed))
        if intent in {"decision_report_draft", "file_export"}
        else None
    )
    return AssistantToolPlanResult(
        intent=intent,
        current_context=current_context,
        executed=tuple(executed),
        report_context=report,
    )


def _find_section(report_context: DecisionReportContext | None, terms: tuple[str, ...]):
    if report_context is None:
        return None
    for section in report_context.sections:
        text = " ".join(
            [
                section.title,
                section.source.kind,
                *(str(value) for value in section.summary.values()),
                *(section.notes),
            ]
        ).lower()
        if any(term.lower() in text for term in terms):
            return section
    return None


def _symbol_from_query(query: str) -> str | None:
    lowered = query.lower()
    aliases = {
        "トヨタ": "7203.T",
        "toyota": "7203.T",
        "大阪ガス": "9532.T",
        "microsoft": "MSFT",
        "マイクロソフト": "MSFT",
    }
    for name, symbol in aliases.items():
        if name.lower() in lowered:
            return symbol
    tokens = query.replace("。", " ").replace(",", " ").split()
    for token in tokens:
        cleaned = token.strip().upper()
        if cleaned.endswith(".T") and cleaned[:-2].isdigit():
            return cleaned
        if cleaned.isascii() and cleaned.isalnum() and 1 <= len(cleaned) <= 5:
            return cleaned
    return None


def _stringify_mapping(values: dict[str, object]) -> dict[str, str]:
    return {str(key): str(value) for key, value in values.items() if str(value).strip()}


def _safe_filename_part(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value if ch.isascii() and (ch.isalnum() or ch in "-_")).strip("_-")
