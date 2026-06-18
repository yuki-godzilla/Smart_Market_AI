from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from backend.assistant.action_result import AssistantActionResult, safe_action_error_message
from backend.assistant.context_builder import SMAIAssistantContext
from backend.assistant.tool_registry import AssistantActionSpec, get_assistant_action
from backend.assistant.tools import AssistantToolLayer, AssistantToolResult
from backend.reporting import DecisionReportContext, render_decision_report_markdown


class AssistantActionExecutor:
    """Execute user-confirmed Assistant actions through safe, bounded handlers."""

    def __init__(self, *, tool_layer: AssistantToolLayer | None = None) -> None:
        self._tool_layer = tool_layer or AssistantToolLayer()

    def execute(
        self,
        action_id: str,
        context: SMAIAssistantContext,
        *,
        payload: Mapping[str, Any] | None = None,
        confirmed: bool = False,
    ) -> AssistantActionResult:
        started_at = datetime.now(UTC)
        action = get_assistant_action(action_id)
        if action is None:
            return _result(
                action_id=action_id or "unknown",
                status="not_available",
                title="操作を確認できません",
                summary="指定された操作はSMAIアシスタントの許可リストにありません。",
                error_code="unknown_action",
                started_at=started_at,
            )
        validation = _validate_action_for_execution(
            action=action,
            confirmed=confirmed,
            started_at=started_at,
        )
        if validation is not None:
            return validation
        try:
            if action.action_id == "create_decision_report":
                return self._execute_create_decision_report(
                    action=action,
                    context=context,
                    payload=payload or {},
                    started_at=started_at,
                )
            return _result(
                action_id=action.action_id,
                status="not_available",
                title="この操作はまだ実行できません",
                summary=f"{action.label} はPhase 30-Cの後続接続として扱います。",
                error_code="not_implemented",
                started_at=started_at,
                warnings=["ユーザー確認なしの外部取得、ランキング作成、スコア変更は行いません。"],
                followup_actions=["summarize_next_checks"],
                requires_followup=True,
            )
        except Exception:
            return _result(
                action_id=action.action_id,
                status="failed",
                title="操作を完了できませんでした",
                summary="確認レポート作成中に問題が発生しました。",
                error_code="execution_error",
                started_at=started_at,
                requires_followup=True,
                followup_actions=["open_cockpit", "summarize_next_checks"],
            )

    def _execute_create_decision_report(
        self,
        *,
        action: AssistantActionSpec,
        context: SMAIAssistantContext,
        payload: Mapping[str, Any],
        started_at: datetime,
    ) -> AssistantActionResult:
        report_context = _report_context_from_payload(payload)
        symbol = _symbol_for_action(context=context, report_context=report_context, payload=payload)
        if not symbol:
            return _result(
                action_id=action.action_id,
                status="failed",
                title="確認レポートを作成できませんでした",
                summary="対象銘柄を特定できませんでした。",
                error_code="symbol_missing",
                started_at=started_at,
                requires_followup=True,
                followup_actions=["open_cockpit"],
            )
        if not _has_minimum_report_materials(context=context, report_context=report_context):
            return _result(
                action_id=action.action_id,
                status="failed",
                title="確認レポートを作成できませんでした",
                summary="価格やAI予測などの確認材料が不足しています。",
                error_code="insufficient_materials",
                started_at=started_at,
                details={"symbol": symbol},
                requires_followup=True,
                followup_actions=["fetch_symbol_data", "open_cockpit"],
            )

        current_context = self._tool_layer.get_current_context(
            report_context,
            analysis_mode="assistant_action:create_decision_report",
        )
        current_context = replace(current_context, symbol=symbol)
        tool_results = _report_tool_results(
            tool_layer=self._tool_layer,
            report_context=report_context,
            context=context,
            symbol=symbol,
            question=str(payload.get("user_question") or context.user_question or ""),
        )
        try:
            draft_context = self._tool_layer.build_decision_report(
                current_context,
                tool_results,
            )
            markdown = render_decision_report_markdown(draft_context)
        except Exception:
            return _result(
                action_id=action.action_id,
                status="failed",
                title="確認レポートを作成できませんでした",
                summary="確認レポート作成に必要な部品を利用できませんでした。",
                error_code="report_builder_unavailable",
                started_at=started_at,
                details={"symbol": symbol},
                requires_followup=True,
                followup_actions=["summarize_next_checks"],
            )

        company_name = _clean_text(payload.get("company_name") or context.page_state.get("company"))
        return _result(
            action_id=action.action_id,
            status="success",
            title="確認レポートを作成しました",
            summary=f"{symbol} の確認材料を、Decision Report下書きとして整理しました。",
            user_message=(
                f"{symbol}{' / ' + company_name if company_name else ''} の価格・予測・"
                "根拠資料をもとに、確認用レポートを生成しました。"
            ),
            started_at=started_at,
            details={
                "symbol": symbol,
                "company_name": company_name,
                "report_title": draft_context.title,
                "sections_count": len(draft_context.sections),
                "report_context_json": draft_context.model_dump_json(indent=2),
                "report_markdown": markdown,
            },
            warnings=[
                "このレポートは売買推奨ではありません。",
                "Ranking score、Forecast、Investment Score、AI総合は変更していません。",
                "外部取得とbroker連携は行っていません。",
            ],
            followup_actions=["download_decision_report", "open_research_section"],
        )


def _validate_action_for_execution(
    *,
    action: AssistantActionSpec,
    confirmed: bool,
    started_at: datetime,
) -> AssistantActionResult | None:
    if action.is_destructive:
        return _result(
            action_id=action.action_id,
            status="not_available",
            title="この操作は実行できません",
            summary="安全境界を超える操作はSMAIアシスタントから実行できません。",
            error_code="destructive_action",
            started_at=started_at,
        )
    if not action.enabled:
        return _result(
            action_id=action.action_id,
            status="not_available",
            title="この操作は現在利用できません",
            summary=action.disabled_reason or "現在の画面では利用できない操作です。",
            error_code="disabled_action",
            started_at=started_at,
        )
    if action.requires_confirmation and not confirmed:
        return _result(
            action_id=action.action_id,
            status="skipped",
            title="実行前確認が必要です",
            summary="ユーザー確認がないため、操作は実行していません。",
            error_code="confirmation_required",
            started_at=started_at,
            requires_followup=True,
            followup_actions=["summarize_next_checks"],
        )
    if action.is_external_fetch and not confirmed:
        return _result(
            action_id=action.action_id,
            status="skipped",
            title="外部取得の確認が必要です",
            summary="外部取得はユーザー確認後にだけ実行します。",
            error_code="confirmation_required",
            started_at=started_at,
            requires_followup=True,
            followup_actions=["summarize_next_checks"],
        )
    return None


def _report_tool_results(
    *,
    tool_layer: AssistantToolLayer,
    report_context: DecisionReportContext | None,
    context: SMAIAssistantContext,
    symbol: str,
    question: str,
) -> tuple[AssistantToolResult, ...]:
    results: list[AssistantToolResult] = [
        AssistantToolResult(
            name="resolve_symbol",
            status="ok",
            summary=f"銘柄を特定: {symbol}",
            details={"symbol": symbol},
        )
    ]
    results.append(
        _tool_result_or_context_fallback(
            tool_result=tool_layer.get_price_summary(report_context, symbol),
            name="get_price_summary",
            context=context,
            material_key="price_data_status",
            available_summary="価格データを確認しました。",
            missing_summary="価格データは現在の文脈にありません。",
            symbol=symbol,
        )
    )
    results.append(
        _tool_result_or_context_fallback(
            tool_result=tool_layer.get_forecast_summary(report_context, symbol),
            name="get_forecast_summary",
            context=context,
            material_key="forecast_status",
            available_summary="AI予測インサイトを確認しました。",
            missing_summary="AI予測インサイトは現在の文脈にありません。",
            symbol=symbol,
        )
    )
    news = tool_layer.search_news_materials(report_context, question)
    if news.status == "ok" or _material_available(context.material_state.get("news_status")):
        results.append(
            news
            if news.status == "ok"
            else AssistantToolResult(
                name="search_news_materials",
                status="ok",
                summary="ニュース材料を確認しました。",
                details={"symbol": symbol},
            )
        )
    research = tool_layer.search_rag_materials(report_context, question)
    if research.status == "ok" or _material_available(
        context.material_state.get("research_status")
    ):
        results.append(
            research
            if research.status == "ok"
            else AssistantToolResult(
                name="search_rag_materials",
                status="ok",
                summary="Research Evidenceを確認しました。",
                details={"symbol": symbol},
            )
        )
    return tuple(results)


def _tool_result_or_context_fallback(
    *,
    tool_result: AssistantToolResult,
    name: str,
    context: SMAIAssistantContext,
    material_key: str,
    available_summary: str,
    missing_summary: str,
    symbol: str,
) -> AssistantToolResult:
    if tool_result.status == "ok":
        return tool_result
    if _material_available(context.material_state.get(material_key)):
        return AssistantToolResult(
            name=name,
            status="ok",
            summary=available_summary,
            details={"symbol": symbol},
        )
    return AssistantToolResult(
        name=name,
        status="missing",
        summary=missing_summary,
        details={"symbol": symbol},
    )


def _has_minimum_report_materials(
    *,
    context: SMAIAssistantContext,
    report_context: DecisionReportContext | None,
) -> bool:
    current = AssistantToolLayer().get_current_context(report_context)
    has_price = current.has_price or _material_available(
        context.material_state.get("price_data_status")
    )
    has_forecast = current.has_forecast or _material_available(
        context.material_state.get("forecast_status")
    )
    return bool(has_price and has_forecast)


def _report_context_from_payload(payload: Mapping[str, Any]) -> DecisionReportContext | None:
    value = payload.get("report_context")
    if isinstance(value, DecisionReportContext):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return DecisionReportContext.model_validate_json(value)
        except ValueError:
            return None
    return None


def _symbol_for_action(
    *,
    context: SMAIAssistantContext,
    report_context: DecisionReportContext | None,
    payload: Mapping[str, Any],
) -> str:
    candidates = [
        payload.get("symbol"),
        context.page_state.get("selected_symbol"),
        context.page_state.get("active_symbol"),
        context.page_state.get("symbol"),
        context.metadata.get("symbol"),
    ]
    if report_context is not None:
        candidates.extend(section.source.symbol for section in report_context.sections)
    for candidate in candidates:
        symbol = _normalize_symbol(candidate)
        if symbol:
            return symbol
    return ""


def _normalize_symbol(value: Any) -> str:
    text = _clean_text(value).upper()
    if not text:
        return ""
    for token in (
        text.replace("（", " ").replace("）", " ").replace("(", " ").replace(")", " ").split()
    ):
        clean = token.strip(" ,;:/")
        if clean.endswith(".T") and clean[:-2].isdigit():
            return clean
        if clean.isascii() and clean.replace(".", "").isalnum() and 1 <= len(clean) <= 8:
            return clean
    return ""


def _material_available(value: Any) -> bool:
    text = _clean_text(value).lower()
    return text in {"available", "ok", "true", "1", "あり", "有り", "取得済み", "下書き可"}


def _result(
    *,
    action_id: str,
    status: str,
    title: str,
    summary: str,
    started_at: datetime,
    user_message: str | None = None,
    details: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    requires_followup: bool = False,
    followup_actions: list[str] | None = None,
) -> AssistantActionResult:
    return AssistantActionResult(
        action_id=action_id,
        status=status,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        user_message=user_message or safe_action_error_message(error_code),
        details=details or {},
        warnings=warnings or [],
        error_code=error_code,
        error_message=error_message,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        requires_followup=requires_followup,
        followup_actions=followup_actions or [],
    )


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
