from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
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

_ASSISTANT_NEWS_SOURCE_TYPES = {"news", "tdnet"}


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


_REPORT_TECHNICAL_MARKERS = (
    "provider raw",
    "debug logs",
    "request_id",
    "latency",
    "gateway",
    "http_status",
    "privacy_notes",
    "safety_notes",
)


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

    report = None
    if intent in {"decision_report_draft", "file_export"}:
        report = tools.build_decision_report(current_context, tuple(executed))
        executed.append(
            AssistantToolResult(
                name="build_decision_report",
                status="ok",
                summary="Decision Report下書きを作成しました。",
                details={"title": report.title},
            )
        )
    return AssistantToolPlanResult(
        intent=intent,
        current_context=current_context,
        executed=tuple(executed),
        report_context=report,
    )


def assistant_research_bundle_to_decision_report_context(
    bundle: AssistantResearchContextBundle,
    *,
    user_question: str,
    assistant_answer: str | None = None,
    intent: str | None = None,
    created_at: datetime | None = None,
) -> DecisionReportContext:
    """Build a reusable Decision Report draft from a Research Mode material bundle."""

    symbol = _symbol_from_research_bundle(bundle)
    company_name = _company_name_from_research_subject(bundle.subject, symbol=symbol)
    clean_question = _report_safe_text(user_question) or "未入力"
    clean_answer = _report_safe_text(assistant_answer or "")
    clean_intent = _report_safe_text(intent or "research_answer")
    confirmed_labels = (
        ", ".join(material.label for material in bundle.confirmed_materials) or "なし"
    )
    missing_labels = ", ".join(material.label for material in bundle.missing_materials) or "なし"
    title_subject = company_name or symbol or bundle.subject

    overview = build_report_section(
        title="SMAIアシスタント 調査概要",
        source_kind="manual",
        provider="assistant_research_mode",
        symbol=symbol,
        summary={
            "source": "assistant_research_mode",
            "intent": clean_intent,
            "fetch_mode": bundle.choice,
            "cached_only": "true" if bundle.choice == "cached_only" else "false",
            "user_question": clean_question,
            "subject": _report_safe_text(bundle.subject),
            "company_name": company_name,
            "available_materials": confirmed_labels,
            "missing_materials": missing_labels,
            "assistant_answer": clean_answer,
        },
        notes=[
            "SMAIアシスタント Research Mode の会話結果を、判断材料メモとして整理した下書きです。",
            "売買推奨ではなく、上昇方向を見る材料、注意材料、未確認材料、次の確認を分けて保存します。",
        ],
        metadata={
            "source": "assistant_research_mode",
            "intent": clean_intent,
            "fetch_mode": bundle.choice,
        },
    )
    available_materials = build_report_section(
        title="確認できた材料",
        source_kind="manual",
        provider="assistant_research_mode",
        symbol=symbol,
        rows=[
            _material_report_row(material, row_type="available_material")
            for material in bundle.confirmed_materials
        ]
        or [
            {
                "row_type": "available_material",
                "label": "確認できた材料",
                "status": "missing",
                "summary": "この会話では、Report化できる確認済み材料がまだありません。",
            }
        ],
        notes=["確認済み材料も、スコア・ランキング・予測値を変更するものではありません。"],
        metadata={"source": "assistant_research_mode", "intent": clean_intent},
    )
    cautions_and_unknowns = build_report_section(
        title="注意材料と未確認事項",
        source_kind="manual",
        provider="assistant_research_mode",
        symbol=symbol,
        rows=[
            _material_report_row(material, row_type="missing_material")
            for material in bundle.missing_materials
        ]
        + [
            {
                "row_type": "caution",
                "label": "注意材料",
                "status": "caution",
                "summary": _report_safe_text(caution),
            }
            for caution in bundle.caution_materials
        ],
        warnings=[_report_safe_text(item) for item in bundle.caution_materials],
        notes=["未確認材料は、確認不足の整理であり、銘柄評価そのものではありません。"],
        metadata={"source": "assistant_research_mode", "intent": clean_intent},
    )
    next_checks = build_report_section(
        title="次に確認すること",
        source_kind="manual",
        provider="assistant_research_mode",
        symbol=symbol,
        rows=[
            {
                "row_type": "next_check",
                "label": f"確認{index}",
                "status": "planned",
                "summary": _report_safe_text(checkpoint),
            }
            for index, checkpoint in enumerate(bundle.next_checkpoints, start=1)
        ],
        notes=["次の確認は、投資判断を補助するための作業メモです。"],
        metadata={"source": "assistant_research_mode", "intent": clean_intent},
    )
    source_rows = _source_report_rows(bundle)
    sources_section = (
        build_report_section(
            title="出典",
            source_kind="manual",
            provider="assistant_research_mode",
            symbol=symbol,
            rows=source_rows,
            notes=[
                "外部取得本文ではなく、確認用のsource URL / provider / 公開日などの短い出典情報だけを保存します。"
            ],
            metadata={"source": "assistant_research_mode", "intent": clean_intent},
        )
        if source_rows
        else None
    )
    sections = [overview, available_materials, cautions_and_unknowns, next_checks]
    if sources_section is not None:
        sections.append(sources_section)
    return build_decision_report_context(
        title=f"SMAIアシスタント Decision Report下書き: {title_subject}",
        sections=sections,
        created_at=created_at or datetime.now(UTC),
        tags=["assistant", "research-mode", "decision-report-draft"],
    )


def render_research_bundle_markdown_memo(context: DecisionReportContext) -> str:
    """Render a compact human-facing Markdown memo for an Assistant report draft."""

    overview = _section_by_title(context, "SMAIアシスタント 調査概要")
    available = _section_by_title(context, "確認できた材料")
    cautions = _section_by_title(context, "注意材料と未確認事項")
    next_checks = _section_by_title(context, "次に確認すること")
    sources = _section_by_title(context, "出典")
    summary = overview.summary if overview else {}
    subject = _report_safe_text(
        summary.get("company_name") or summary.get("subject") or context.title
    )
    question = _report_safe_text(summary.get("user_question") or "未入力")
    assistant_answer = _report_safe_text(summary.get("assistant_answer") or "")
    available_lines = _row_summaries(available, row_types=("available_material",))
    missing_lines = _row_summaries(cautions, row_types=("missing_material",))
    caution_lines = _row_summaries(cautions, row_types=("caution",))
    next_lines = _row_summaries(next_checks, row_types=("next_check",))
    source_lines = _row_summaries(sources, row_types=("source",))
    fetch_condition_lines = _fetch_condition_lines(summary)
    tool_status_lines = _tool_status_lines(available, cautions)
    if not available_lines:
        available_lines = ("確認済み材料はまだありません。",)
    if not caution_lines:
        caution_lines = ("確認済み材料だけで判断を固定しないよう注意します。",)
    if not missing_lines:
        missing_lines = ("未確認材料はありません。必要に応じて前提の更新を確認します。",)
    if not next_lines:
        next_lines = ("価格・予測・ニュース・根拠資料の前提を必要に応じて再確認します。",)
    overview_text = (
        assistant_answer or f"{subject}について、取得済み材料をもとに確認ポイントを整理しました。"
    )
    fetch_condition_block = (
        f"## 取得条件\n{_markdown_list(fetch_condition_lines)}\n\n" if fetch_condition_lines else ""
    )
    sources_block = f"## 出典\n{_markdown_list(source_lines)}\n\n" if source_lines else ""
    tool_status_block = (
        f"## Tool Status\n{_markdown_list(tool_status_lines)}\n\n" if tool_status_lines else ""
    )
    return (
        f"# Decision Report Draft: {subject}\n\n"
        "## 作成元\n"
        "SMAIアシスタント / Research Mode\n\n"
        "## ユーザー質問\n"
        f"{question}\n\n"
        "## 概要\n"
        f"{overview_text}\n\n"
        f"{fetch_condition_block}"
        "## 上昇方向を見る材料\n"
        f"{_markdown_list(available_lines)}\n\n"
        "## 注意すべき材料\n"
        f"{_markdown_list(caution_lines)}\n\n"
        "## 未確認材料\n"
        f"{_markdown_list(missing_lines)}\n\n"
        f"{sources_block}"
        f"{tool_status_block}"
        "## 次に確認すること\n"
        f"{_markdown_list(next_lines)}\n\n"
        "---\n\n"
        "この下書きは投資判断を補助するための整理メモであり、"
        "買い/売りを推奨するものではありません。\n"
    )


def assistant_tool_results_from_external_research_fetch(
    fetch_result: object,
    *,
    include_news: bool = True,
    include_research: bool = True,
) -> tuple[AssistantToolResult, ...]:
    """Compress an approved external research fetch manifest into Assistant tool results."""

    entries = tuple(getattr(fetch_result, "entries", ()) or ())
    warnings = tuple(str(item).strip() for item in getattr(fetch_result, "warnings", ()) if item)
    results: list[AssistantToolResult] = []
    if include_news:
        news_entries = tuple(
            entry
            for entry in entries
            if _external_entry_source_type(entry) in _ASSISTANT_NEWS_SOURCE_TYPES
        )
        results.append(
            _external_entries_tool_result(
                name="search_news_materials",
                label="最新ニュース",
                entries=news_entries,
                warnings=warnings,
                empty_summary="最新ニュースや適時開示は取得結果に含まれていませんでした。",
            )
        )
    if include_research:
        results.append(
            _external_entries_tool_result(
                name="search_rag_materials",
                label="根拠資料 / Research Evidence",
                entries=entries,
                warnings=warnings,
                empty_summary="外部参照ソースは取得結果に含まれていませんでした。",
            )
        )
    return tuple(results)


def assistant_tool_results_from_external_research_failure(
    *,
    message: str,
    include_news: bool = True,
    include_research: bool = True,
) -> tuple[AssistantToolResult, ...]:
    """Build failed Assistant tool results without exposing provider/debug details."""

    clean_message = _report_safe_text(message) or "外部情報を取得できませんでした。"
    results: list[AssistantToolResult] = []
    if include_news:
        results.append(
            AssistantToolResult(
                name="search_news_materials",
                status="failed",
                summary=f"最新ニュースは取得できませんでした。{clean_message}",
                details={"error_message": clean_message},
            )
        )
    if include_research:
        results.append(
            AssistantToolResult(
                name="search_rag_materials",
                status="failed",
                summary=f"Research Evidenceは取得できませんでした。{clean_message}",
                details={"error_message": clean_message},
            )
        )
    return tuple(results)


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

    cautions = _dedupe_tuple(
        [
            *_research_material_warnings(tuple(confirmed)),
            *_research_material_warnings(tuple(missing)),
            *_research_cautions(choice=choice, missing_materials=tuple(missing)),
        ]
    )
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


def _external_entries_tool_result(
    *,
    name: str,
    label: str,
    entries: Sequence[object],
    warnings: Sequence[str],
    empty_summary: str,
) -> AssistantToolResult:
    clean_entries = tuple(entries)
    if not clean_entries:
        details = {"warning": _first_warning(warnings)}
        return AssistantToolResult(
            name=name,
            status="missing",
            summary=empty_summary,
            details={key: value for key, value in details.items() if value},
        )

    count = len(clean_entries)
    source_lines = tuple(_external_entry_source_line(entry) for entry in clean_entries)
    summary = _external_entries_summary(label=label, entries=clean_entries)
    freshness_warning = _external_entries_freshness_warning(clean_entries, warnings)
    details = {
        "entry_count": str(count),
        "freshness_warning": freshness_warning,
        "warning": _first_warning(warnings),
    }
    return AssistantToolResult(
        name=name,
        status="ok",
        summary=summary,
        details={key: value for key, value in details.items() if value},
        sources=tuple(line for line in source_lines if line),
    )


def _external_entries_summary(*, label: str, entries: Sequence[object]) -> str:
    titles = [
        _report_safe_text(getattr(entry, "title", ""))
        for entry in entries[:3]
        if _report_safe_text(getattr(entry, "title", ""))
    ]
    if not titles:
        return f"{label}を{len(entries)}件確認しました。"
    return f"{label}を{len(entries)}件確認しました: {' / '.join(titles)}"


def _external_entry_source_line(entry: object) -> str:
    title = _report_safe_text(getattr(entry, "title", ""))
    provider = _report_safe_text(getattr(entry, "provider", ""))
    source_type = _report_safe_text(getattr(entry, "source_type", ""))
    published_at = getattr(entry, "published_at", None)
    published = ""
    if published_at is not None and hasattr(published_at, "isoformat"):
        published = str(published_at.isoformat())
    freshness = _report_safe_text(getattr(entry, "freshness_status", ""))
    source_url = _report_safe_text(getattr(entry, "source_url", ""))
    parts = [
        part for part in (title, provider, source_type, published, freshness, source_url) if part
    ]
    return " | ".join(parts)


def _external_entry_source_type(entry: object) -> str:
    return str(getattr(entry, "source_type", "") or "").strip()


def _external_entries_freshness_warning(
    entries: Sequence[object],
    warnings: Sequence[str],
) -> str:
    if any(str(getattr(entry, "freshness_status", "")) == "stale" for entry in entries):
        return "取得できた外部情報に古い可能性がある材料が含まれます。"
    return _first_warning(warnings)


def _first_warning(warnings: Sequence[str]) -> str:
    return next(
        (_report_safe_text(warning) for warning in warnings if _report_safe_text(warning)), ""
    )


def _material_report_row(
    material: AssistantResearchMaterial,
    *,
    row_type: str,
) -> dict[str, str]:
    return {
        "row_type": row_type,
        "key": material.key,
        "label": material.label,
        "status": material.status,
        "external": "true" if material.external else "false",
        "required": "true" if material.required else "false",
        "summary": _report_safe_text(material.summary),
        "sources": ", ".join(_report_safe_text(source) for source in material.sources),
    }


def _source_report_rows(bundle: AssistantResearchContextBundle) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for material in (*bundle.confirmed_materials, *bundle.missing_materials):
        for source in material.sources:
            clean_source = _report_safe_text(source)
            if not clean_source or clean_source in seen:
                continue
            seen.add(clean_source)
            rows.append(
                {
                    "row_type": "source",
                    "label": material.label,
                    "status": material.status,
                    "summary": clean_source,
                }
            )
    return rows


def _symbol_from_research_bundle(bundle: AssistantResearchContextBundle) -> str | None:
    for material in bundle.confirmed_materials:
        symbol = material.details.get("symbol")
        if symbol:
            return symbol
    return _symbol_from_query(bundle.subject)


def _company_name_from_research_subject(subject: str, *, symbol: str | None) -> str | None:
    clean = str(subject or "").strip()
    if "（" in clean and "）" in clean:
        before = clean.split("（", 1)[0].strip()
        if before:
            return before
    if "(" in clean and ")" in clean:
        before = clean.split("(", 1)[0].strip()
        if before and before != symbol:
            return before
    if symbol and clean and clean != symbol:
        return clean
    return None


def _section_by_title(
    context: DecisionReportContext,
    title: str,
):
    return next((section for section in context.sections if section.title == title), None)


def _row_summaries(
    section,
    *,
    row_types: tuple[str, ...],
) -> tuple[str, ...]:
    if section is None:
        return ()
    rows: list[str] = []
    for row in section.rows:
        if str(row.get("row_type", "")).strip() not in row_types:
            continue
        label = _report_safe_text(row.get("label", ""))
        summary = _report_safe_text(row.get("summary", ""))
        if not summary:
            continue
        rows.append(f"{label}: {summary}" if label and label not in summary else summary)
    return _dedupe_tuple(rows)


def _fetch_condition_lines(summary: Mapping[str, str]) -> tuple[str, ...]:
    fetch_mode = _report_safe_text(summary.get("fetch_mode", ""))
    if fetch_mode == "cached_only" or summary.get("cached_only") == "true":
        return (
            "今回は取得済み情報のみで整理しています。",
            "最新ニュースやResearch Evidenceは未確認材料として残します。",
        )
    if fetch_mode == "approve":
        return (
            "ユーザー承認後に、計画された外部ニュース / Research Evidence の取得結果を反映しています。",
            "取得できなかった材料は未確認材料として残します。",
        )
    return ("取得済み材料を中心に整理しています。",)


def _tool_status_lines(
    available_section,
    caution_section,
) -> tuple[str, ...]:
    rows = []
    for section in (available_section, caution_section):
        if section is not None:
            rows.extend(section.rows)
    lines: list[str] = []
    for row in rows:
        key = _report_safe_text(row.get("key", ""))
        if not key:
            continue
        label = _report_safe_text(row.get("label", "")) or key
        status = _report_safe_text(row.get("status", "")) or "unknown"
        lines.append(f"{key}: {status} ({label})")
    return _dedupe_tuple(lines)


def _markdown_list(items: Sequence[str]) -> str:
    lines = [_report_safe_text(item) for item in items if _report_safe_text(item)]
    return "\n".join(f"- {line}" for line in lines) or "- なし"


def _report_safe_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        clean = line.strip()
        lowered = clean.lower()
        if not clean:
            continue
        if any(marker in lowered for marker in _REPORT_TECHNICAL_MARKERS):
            continue
        lines.append(clean)
    return "\n".join(lines)


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


def _research_material_warnings(
    materials: tuple[AssistantResearchMaterial, ...],
) -> tuple[str, ...]:
    warnings: list[str] = []
    for material in materials:
        for key in ("freshness_warning", "warning", "error_message"):
            value = _report_safe_text(material.details.get(key, ""))
            if value:
                warnings.append(f"{material.label}: {value}")
    return _dedupe_tuple(warnings)


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
