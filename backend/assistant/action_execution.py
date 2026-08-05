from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

from backend.assistant.action_result import AssistantActionResult, safe_action_error_message
from backend.assistant.context_builder import SMAIAssistantContext
from backend.assistant.tool_registry import AssistantActionSpec, get_assistant_action
from backend.assistant.tools import AssistantToolLayer, AssistantToolResult
from backend.reporting import DecisionReportContext, render_decision_report_markdown


class AssistantActionExecutor:
    """Execute user-confirmed Assistant actions through safe, bounded handlers."""

    def __init__(
        self,
        *,
        tool_layer: AssistantToolLayer | None = None,
        research_fetcher: Callable[..., Any] | None = None,
    ) -> None:
        self._tool_layer = tool_layer or AssistantToolLayer()
        self._research_fetcher = research_fetcher

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
            if action.action_id == "update_research":
                return self._execute_update_research(
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
                summary="確認済み操作の実行中に問題が発生しました。",
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
        symbol, target_error = _symbol_for_action(
            context=context,
            report_context=report_context,
            payload=payload,
        )
        if target_error:
            return _result(
                action_id=action.action_id,
                status="validation_error",
                title="確認レポートを作成できませんでした",
                summary="確認した対象と現在の材料が一致しません。",
                error_code=target_error,
                started_at=started_at,
                requires_followup=True,
                followup_actions=["open_cockpit", "summarize_next_checks"],
            )
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

    def _execute_update_research(
        self,
        *,
        action: AssistantActionSpec,
        context: SMAIAssistantContext,
        payload: Mapping[str, Any],
        started_at: datetime,
    ) -> AssistantActionResult:
        symbol, target_error = _symbol_for_action(
            context=context,
            report_context=None,
            payload=payload,
        )
        if target_error:
            return _result(
                action_id=action.action_id,
                status="validation_error",
                title="AI調査を更新できませんでした",
                summary="確認した対象と現在の材料が一致しません。",
                error_code=target_error,
                started_at=started_at,
                requires_followup=True,
                followup_actions=["open_cockpit", "summarize_next_checks"],
            )
        if not symbol:
            return _result(
                action_id=action.action_id,
                status="failed",
                title="AI調査を更新できませんでした",
                summary="対象銘柄を特定できませんでした。",
                error_code="symbol_missing",
                started_at=started_at,
                requires_followup=True,
                followup_actions=["open_cockpit"],
            )
        if self._research_fetcher is None:
            return _result(
                action_id=action.action_id,
                status="not_available",
                title="AI調査を更新できませんでした",
                summary="AI調査を更新する準備ができていません。",
                error_code="research_fetcher_unavailable",
                started_at=started_at,
                details={"symbol": symbol},
                requires_followup=True,
                followup_actions=["answer_with_existing_materials", "open_cockpit"],
            )

        company_name = _clean_text(
            payload.get("company_name")
            or payload.get("symbol_name")
            or context.page_state.get("company")
        )
        related_keywords = _research_related_keywords(
            context=context,
            payload=payload,
            symbol=symbol,
            company_name=company_name,
        )
        try:
            fetch_result = self._research_fetcher(
                symbol=symbol,
                company_name=company_name or None,
                related_keywords=related_keywords,
                allow_network=True,
                context={
                    "current_page": context.current_page,
                    "user_question": context.user_question,
                    "action_id": action.action_id,
                },
            )
        except TimeoutError:
            return _result(
                action_id=action.action_id,
                status="failed",
                title="AI調査を更新できませんでした",
                summary="外部取得元の応答が時間切れになりました。",
                error_code="provider_timeout",
                started_at=started_at,
                details={"symbol": symbol, "company_name": company_name},
                warnings=["外部取得は完了していません。取得済み材料で確認してください。"],
                requires_followup=True,
                followup_actions=[
                    "answer_with_existing_materials",
                    "open_cockpit",
                    "retry_update_research",
                ],
            )
        except Exception:
            return _result(
                action_id=action.action_id,
                status="failed",
                title="AI調査を更新できませんでした",
                summary="最新情報を確認できませんでした。",
                error_code="external_fetch_failed",
                started_at=started_at,
                details={"symbol": symbol, "company_name": company_name},
                warnings=["取得元の詳細エラーは通常表示していません。"],
                requires_followup=True,
                followup_actions=[
                    "answer_with_existing_materials",
                    "open_cockpit",
                    "retry_update_research",
                ],
            )

        return _research_fetch_result_to_action_result(
            action=action,
            fetch_result=fetch_result,
            symbol=symbol,
            company_name=company_name,
            started_at=started_at,
        )


def _research_fetch_result_to_action_result(
    *,
    action: AssistantActionSpec,
    fetch_result: Any,
    symbol: str,
    company_name: str,
    started_at: datetime,
) -> AssistantActionResult:
    entries = _as_sequence(_result_field(fetch_result, "entries", []))
    explicit_count = _safe_int(_result_field(fetch_result, "entry_count", None))
    entry_count = max(len(entries), explicit_count or 0)
    source_counts = _research_source_counts(fetch_result=fetch_result, entries=entries)
    failed_sources = _provider_sources_by_status(fetch_result, {"failed"})
    timeout_sources = _provider_sources_by_status(fetch_result, {"timeout"})
    no_result_sources = _provider_sources_by_status(fetch_result, {"no_result"})
    warnings = _research_fetch_warnings(
        fetch_result=fetch_result,
        failed_sources=failed_sources,
        timeout_sources=timeout_sources,
        no_result_sources=no_result_sources,
    )
    fetched_at = _iso_timestamp(_result_field(fetch_result, "fetched_at", None))
    details = {
        "symbol": symbol,
        "company_name": company_name,
        "fetched_at": fetched_at,
        "entry_count": entry_count,
        "source_counts": source_counts,
        "warning_count": len(warnings),
        "failed_sources": failed_sources,
        "timeout_sources": timeout_sources,
        "no_result_sources": no_result_sources,
        "retention_policy": _clean_text(_result_field(fetch_result, "retention_policy", "")),
    }
    status_hint = _clean_text(_result_field(fetch_result, "status", "")).lower()
    has_provider_gap = bool(failed_sources or timeout_sources or no_result_sources)
    if status_hint == "failed" or entry_count <= 0:
        return _result(
            action_id=action.action_id,
            status="failed",
            title="AI調査を更新できませんでした",
            summary=f"{symbol} の新しい根拠資料は見つかりませんでした。",
            user_message="取得済み材料を使って確認できます。必要に応じて条件を変えて再確認してください。",
            error_code=_clean_text(_result_field(fetch_result, "error_code", ""))
            or "no_external_research_found",
            started_at=started_at,
            details=details,
            warnings=warnings,
            requires_followup=True,
            followup_actions=[
                "answer_with_existing_materials",
                "open_cockpit",
                "retry_update_research",
            ],
        )

    if status_hint == "partial_success" or warnings or has_provider_gap:
        return _result(
            action_id=action.action_id,
            status="partial_success",
            title="AI調査を一部更新しました",
            summary=f"{symbol} の根拠資料を{entry_count}件反映しました。",
            user_message=(
                "取得できた材料をAI調査に反映しました。"
                "未取得の資料があるため、必要に応じて再確認してください。"
            ),
            started_at=started_at,
            details=details,
            warnings=warnings,
            followup_actions=[
                "open_research_section",
                "create_decision_report",
                "retry_update_research",
            ],
        )

    return _result(
        action_id=action.action_id,
        status="success",
        title="AI調査を更新しました",
        summary=f"{symbol} の根拠資料を{entry_count}件反映しました。",
        user_message=(
            f"{symbol}{' / ' + company_name if company_name else ''} のIR、開示、"
            "ニュースなどの確認材料をAI調査に反映しました。"
        ),
        started_at=started_at,
        details=details,
        warnings=[],
        followup_actions=[
            "open_research_section",
            "create_decision_report",
            "summarize_next_checks",
        ],
    )


def _research_fetch_warnings(
    *,
    fetch_result: Any,
    failed_sources: list[str],
    timeout_sources: list[str],
    no_result_sources: list[str],
) -> list[str]:
    warnings = _clean_strings(_result_field(fetch_result, "warnings", []), limit=5)
    if failed_sources:
        warnings.append(f"一部の取得元を確認できませんでした: {', '.join(failed_sources)}")
    if timeout_sources:
        warnings.append(f"一部の取得元が時間切れになりました: {', '.join(timeout_sources)}")
    if no_result_sources:
        warnings.append(f"一部の取得元は該当情報なしでした: {', '.join(no_result_sources)}")
    return _dedupe_strings(warnings)[:8]


def _research_source_counts(*, fetch_result: Any, entries: Sequence[Any]) -> dict[str, int]:
    explicit = _result_field(fetch_result, "source_counts", None)
    if isinstance(explicit, Mapping):
        counts: dict[str, int] = {}
        for key, value in explicit.items():
            source = _clean_text(key)
            count = _safe_int(value)
            if source and count is not None:
                counts[source] = count
        return counts
    counter: Counter[str] = Counter()
    for entry in entries:
        source = _clean_text(_result_field(entry, "source_type", ""))
        if source:
            counter[source] += 1
    return dict(counter)


def _provider_sources_by_status(fetch_result: Any, statuses: set[str]) -> list[str]:
    explicit_key = {
        "failed": "failed_sources",
        "timeout": "timeout_sources",
        "no_result": "no_result_sources",
    }
    for status in statuses:
        explicit = _clean_strings(_result_field(fetch_result, explicit_key.get(status, ""), []))
        if explicit:
            return explicit
    sources: list[str] = []
    for item in _as_sequence(_result_field(fetch_result, "provider_statuses", [])):
        status = _clean_text(_result_field(item, "status", "")).lower()
        if status not in statuses:
            continue
        source = _clean_text(_result_field(item, "source", "")) or _clean_text(
            _result_field(item, "provider", "")
        )
        if source:
            sources.append(source)
    return _dedupe_strings(sources)


def _research_related_keywords(
    *,
    context: SMAIAssistantContext,
    payload: Mapping[str, Any],
    symbol: str,
    company_name: str,
) -> list[str]:
    explicit = _clean_strings(payload.get("related_keywords", []), limit=4)
    if explicit:
        return explicit
    candidates = [
        company_name,
        _clean_text(payload.get("subject", "")),
        _clean_text(payload.get("user_question", "")),
        context.user_question,
        symbol,
    ]
    return _dedupe_strings([item for item in candidates if item])[:4]


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
) -> tuple[str, str | None]:
    payload_symbol = _normalize_symbol(payload.get("symbol"))
    context_symbols = _normalized_symbols(
        (
            context.page_state.get("selected_symbol"),
            context.page_state.get("active_symbol"),
            context.page_state.get("symbol"),
            context.metadata.get("symbol"),
        )
    )
    report_symbols: set[str] = set()
    if report_context is not None:
        report_symbols = _normalized_symbols(
            section.source.symbol for section in report_context.sections
        )

    known_symbols = context_symbols | report_symbols
    if len(known_symbols) > 1:
        return "", "target_mismatch"
    if payload_symbol and known_symbols and payload_symbol not in known_symbols:
        return "", "target_mismatch"
    known_symbol = next(iter(known_symbols), "")
    return payload_symbol or known_symbol, None


def _normalized_symbols(candidates: Iterable[Any]) -> set[str]:
    return {symbol for candidate in candidates if (symbol := _normalize_symbol(candidate))}


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


def _result_field(value: Any, name: str, default: Any = None) -> Any:
    if not name:
        return default
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence):
        return list(value)
    return [value]


def _clean_strings(value: Any, *, limit: int | None = None) -> list[str]:
    items = [_clean_text(item) for item in _as_sequence(value)]
    cleaned = [item for item in items if item]
    if limit is None:
        return cleaned
    return cleaned[: max(0, limit)]


def _dedupe_strings(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        clean = _clean_text(value)
        if clean and clean not in deduped:
            deduped.append(clean)
    return deduped


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _clean_text(value)
    return text if text else datetime.now(UTC).isoformat()
