from __future__ import annotations

from collections.abc import Mapping, Sequence
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
AssistantResearchChoice = Literal["approve", "cached_only", "normal"]
AssistantResearchMaterialStatus = Literal["confirmed", "missing", "failed"]


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


@dataclass(frozen=True)
class AssistantResearchMaterial:
    key: str
    label: str
    status: AssistantResearchMaterialStatus
    summary: str
    external: bool = False
    required: bool = False
    details: dict[str, str] = field(default_factory=dict)
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssistantResearchContextBundle:
    subject: str
    choice: AssistantResearchChoice
    confirmed_materials: tuple[AssistantResearchMaterial, ...]
    missing_materials: tuple[AssistantResearchMaterial, ...]
    caution_materials: tuple[str, ...]
    next_checkpoints: tuple[str, ...]
    report_context: DecisionReportContext | None = None

    def llm_context_lines(self) -> tuple[str, ...]:
        """Structured, compact material context for LLM answer generation."""

        lines = [
            f"対象: {self.subject}",
            f"回答方針: {_research_choice_label(self.choice)}",
            "確認できた材料:",
        ]
        lines.extend(
            f"- {material.label}: {material.summary}" for material in self.confirmed_materials
        )
        if not self.confirmed_materials:
            lines.append("- なし")
        lines.append("未確認材料:")
        lines.extend(
            f"- {material.label}: {material.summary}" for material in self.missing_materials
        )
        if not self.missing_materials:
            lines.append("- なし")
        lines.append("注意材料:")
        lines.extend(f"- {item}" for item in self.caution_materials)
        if not self.caution_materials:
            lines.append("- 売買判断ではなく、確認材料の整理として扱います。")
        lines.append("次に確認:")
        lines.extend(f"- {item}" for item in self.next_checkpoints)
        if not self.next_checkpoints:
            lines.append("- 前提が変わっていないか、価格・予測・ニュースを再確認します。")
        return tuple(lines)

    def executed_check_lines(self) -> tuple[str, ...]:
        lines = [f"✓ {material.label}: {material.summary}" for material in self.confirmed_materials]
        lines.extend(
            f"… {material.label}: 取得できませんでした" for material in self.missing_materials
        )
        return tuple(lines)

    def missing_labels(self) -> tuple[str, ...]:
        return tuple(material.label for material in self.missing_materials)


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


def build_assistant_research_context_bundle(
    *,
    subject: str,
    choice: AssistantResearchChoice,
    tool_plan: AssistantToolPlanResult | None,
    planned_tools: Sequence[Mapping[str, object]] = (),
) -> AssistantResearchContextBundle:
    """Aggregate read-only Assistant Tool results into LLM-ready research context."""

    clean_subject = subject.strip() or "この相談"
    results_by_name = {result.name: result for result in (tool_plan.executed if tool_plan else ())}
    planned = tuple(planned_tools) or tuple(
        _planned_tool_from_result(result) for result in (tool_plan.executed if tool_plan else ())
    )
    confirmed: list[AssistantResearchMaterial] = []
    missing: list[AssistantResearchMaterial] = []

    for item in planned:
        tool_name = str(item.get("name", "")).strip()
        result_name = _tool_result_name_for_plan_tool(tool_name)
        result = results_by_name.get(result_name)
        label = str(item.get("label", "")).strip() or _tool_label_for_result_name(result_name)
        external = bool(item.get("external"))
        required = bool(item.get("required"))
        material = _research_material_from_tool_result(
            key=tool_name or result_name,
            label=label,
            external=external,
            required=required,
            result=result,
            force_missing=choice == "cached_only" and external,
        )
        if material.status == "confirmed":
            confirmed.append(material)
        else:
            missing.append(material)

    cautions = _research_cautions(choice=choice, missing_materials=tuple(missing))
    next_checkpoints = _research_next_checkpoints(
        missing_materials=tuple(missing),
        has_confirmed=bool(confirmed),
    )
    return AssistantResearchContextBundle(
        subject=clean_subject,
        choice=choice,
        confirmed_materials=tuple(confirmed),
        missing_materials=tuple(missing),
        caution_materials=cautions,
        next_checkpoints=next_checkpoints,
        report_context=tool_plan.report_context if tool_plan else None,
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


def _planned_tool_from_result(result: AssistantToolResult) -> dict[str, object]:
    return {
        "name": _plan_tool_name_for_result(result.name),
        "label": _tool_label_for_result_name(result.name),
        "external": False,
        "required": result.name in {"resolve_symbol", "get_price_summary", "get_forecast_summary"},
    }


def _research_material_from_tool_result(
    *,
    key: str,
    label: str,
    external: bool,
    required: bool,
    result: AssistantToolResult | None,
    force_missing: bool,
) -> AssistantResearchMaterial:
    if force_missing:
        return AssistantResearchMaterial(
            key=key,
            label=label,
            status="missing",
            summary="外部取得を行わないため、最新材料としては未確認です。",
            external=external,
            required=required,
        )
    if result is None:
        return AssistantResearchMaterial(
            key=key,
            label=label,
            status="missing",
            summary="この確認はまだ実行されていません。",
            external=external,
            required=required,
        )
    if result.status == "ok":
        return AssistantResearchMaterial(
            key=key,
            label=label,
            status="confirmed",
            summary=_clean_material_summary(label, result.summary),
            external=external,
            required=required,
            details=dict(result.details),
            sources=result.sources,
        )
    return AssistantResearchMaterial(
        key=key,
        label=label,
        status="failed" if result.status == "failed" else "missing",
        summary=_clean_material_summary(label, result.summary),
        external=external,
        required=required,
        details=dict(result.details),
        sources=result.sources,
    )


def _clean_material_summary(label: str, summary: str) -> str:
    clean_label = str(label or "").strip()
    clean_summary = str(summary or "").strip()
    for separator in (":", "："):
        prefix = f"{clean_label}{separator}"
        if clean_label and clean_summary.startswith(prefix):
            return clean_summary[len(prefix) :].strip()
    return clean_summary


def _research_cautions(
    *,
    choice: AssistantResearchChoice,
    missing_materials: tuple[AssistantResearchMaterial, ...],
) -> tuple[str, ...]:
    cautions: list[str] = []
    if choice == "cached_only":
        cautions.append(
            "外部取得は行っていないため、最新ニュースや根拠資料は未確認の可能性があります。"
        )
    cautions.extend(
        f"{material.label}は未確認です。取得済み材料だけで判断しないよう注意します。"
        for material in missing_materials[:3]
    )
    cautions.append("売買を断定せず、上昇方向を見る材料と注意材料を分けて確認します。")
    return _dedupe_tuple(cautions)


def _research_next_checkpoints(
    *,
    missing_materials: tuple[AssistantResearchMaterial, ...],
    has_confirmed: bool,
) -> tuple[str, ...]:
    checkpoints = [f"{material.label}を確認します。" for material in missing_materials[:4]]
    if not checkpoints and has_confirmed:
        checkpoints.append("確認済み材料の前提が変わっていないか、必要に応じて更新します。")
    if not checkpoints:
        checkpoints.append("銘柄、価格、予測、ニュース、根拠資料の順に確認します。")
    return _dedupe_tuple(checkpoints)


def _research_choice_label(choice: AssistantResearchChoice) -> str:
    if choice == "cached_only":
        return "取得済み情報だけで回答する"
    if choice == "approve":
        return "取得できた材料を整理し、未取得材料は未確認として明示する"
    return "SMAIの取得済み材料を整理する"


def _tool_result_name_for_plan_tool(name: str) -> str:
    return {
        "symbol_resolve": "resolve_symbol",
        "price_fetch": "get_price_summary",
        "forecast_fetch": "get_forecast_summary",
        "news_fetch": "search_news_materials",
        "research_fetch": "search_rag_materials",
        "decision_report_draft": "build_decision_report",
    }.get(name, name)


def _plan_tool_name_for_result(name: str) -> str:
    return {
        "resolve_symbol": "symbol_resolve",
        "get_price_summary": "price_fetch",
        "get_forecast_summary": "forecast_fetch",
        "search_news_materials": "news_fetch",
        "search_rag_materials": "research_fetch",
        "build_decision_report": "decision_report_draft",
    }.get(name, name)


def _tool_label_for_result_name(name: str) -> str:
    return {
        "resolve_symbol": "銘柄を特定",
        "get_price_summary": "価格の動き",
        "get_forecast_summary": "AI予測・下振れ警戒",
        "search_news_materials": "最新ニュース",
        "search_rag_materials": "根拠資料 / Research Evidence",
        "build_decision_report": "Decision Report下書き",
    }.get(name, name)


def _dedupe_tuple(items: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = str(item).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return tuple(deduped)


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
