from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any

from backend.assistant.action_result import AssistantActionResult, safe_action_error_message
from backend.assistant.context_builder import SMAIAssistantContext
from backend.assistant.tool_registry import AssistantActionSpec


def execute_news_refresh(
    *,
    action: AssistantActionSpec,
    context: SMAIAssistantContext,
    news_refresher: Callable[..., Any] | None,
    started_at: datetime,
) -> AssistantActionResult:
    """Refresh News Radar through the injected UI boundary and return a safe summary."""
    if news_refresher is None:
        return _result(
            action_id=action.action_id,
            status="not_available",
            title="ニュースを更新できませんでした",
            summary="ニュース更新の準備ができていません。",
            error_code="news_refresher_unavailable",
            started_at=started_at,
            requires_followup=True,
            followup_actions=["open_news_radar", "retry_refresh_news"],
        )
    try:
        refresh_result = news_refresher(
            allow_network=True,
            force=True,
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
            title="ニュースを更新できませんでした",
            summary="ニュース取得が時間切れになりました。",
            error_code="provider_timeout",
            started_at=started_at,
            warnings=["保存済みニュースは変更していません。"],
            requires_followup=True,
            followup_actions=["open_news_radar", "retry_refresh_news"],
        )
    except Exception:
        return _result(
            action_id=action.action_id,
            status="failed",
            title="ニュースを更新できませんでした",
            summary="最新ニュースを取得できませんでした。",
            error_code="news_refresh_failed",
            started_at=started_at,
            warnings=["取得元の詳細エラーは通常表示していません。"],
            requires_followup=True,
            followup_actions=["open_news_radar", "retry_refresh_news"],
        )

    return _news_refresh_result_to_action_result(
        action=action,
        refresh_result=refresh_result,
        started_at=started_at,
    )


def _news_refresh_result_to_action_result(
    *,
    action: AssistantActionSpec,
    refresh_result: Any,
    started_at: datetime,
) -> AssistantActionResult:
    snapshot = _result_field(refresh_result, "snapshot", None)
    refreshed = bool(_result_field(refresh_result, "refreshed", False))
    skipped = bool(_result_field(refresh_result, "skipped", False))
    used_fallback = bool(_result_field(refresh_result, "used_fallback_cache", False))
    details = _news_snapshot_details(snapshot)
    item_count = _safe_int(details.get("item_count")) or 0

    if refreshed and snapshot is not None:
        return _result(
            action_id=action.action_id,
            status="success",
            title="ニュースを更新しました",
            summary=f"投資レーダーへニュースを{item_count}件反映しました。",
            user_message="投資レーダーで確認できます。ランキング・スコアは変更していません。",
            started_at=started_at,
            details=details,
            followup_actions=["open_news_radar", "summarize_next_checks"],
        )

    if skipped and snapshot is not None:
        return _result(
            action_id=action.action_id,
            status="skipped",
            title="ニュースは更新済みです",
            summary=f"保存済みニュース{item_count}件は最新のため、再取得しませんでした。",
            user_message="投資レーダーで現在のニュースを確認できます。",
            started_at=started_at,
            details=details,
            followup_actions=["open_news_radar"],
        )

    if used_fallback and snapshot is not None:
        return _result(
            action_id=action.action_id,
            status="partial_success",
            title="前回のニュースを表示します",
            summary="最新ニュースを取得できなかったため、前回保存データを利用します。",
            user_message=f"投資レーダーで保存済みニュース{item_count}件を確認できます。",
            started_at=started_at,
            details={**details, "used_fallback_cache": True},
            warnings=["表示内容は最新でない可能性があります。"],
            requires_followup=True,
            followup_actions=["open_news_radar", "retry_refresh_news"],
        )

    return _result(
        action_id=action.action_id,
        status="failed",
        title="ニュースを更新できませんでした",
        summary="最新ニュースを取得できず、表示できる前回データもありません。",
        error_code="news_refresh_failed",
        started_at=started_at,
        requires_followup=True,
        followup_actions=["retry_refresh_news"],
    )


def _news_snapshot_details(snapshot: Any) -> dict[str, Any]:
    if snapshot is None:
        return {}
    stream_headlines = _as_sequence(_result_field(snapshot, "stream_headlines", []))
    category_lanes = _as_sequence(_result_field(snapshot, "category_lanes", []))
    category_headline_count = sum(
        len(_as_sequence(_result_field(lane, "headlines", []))) for lane in category_lanes
    )
    heatmap_cells = _as_sequence(_result_field(snapshot, "heatmap_cells", []))
    return {
        "item_count": len(stream_headlines) + category_headline_count,
        "category_count": len(category_lanes),
        "heatmap_count": len(heatmap_cells),
        "generated_at": _optional_iso_timestamp(_result_field(snapshot, "generated_at", None)),
        "fetched_at": _optional_iso_timestamp(_result_field(snapshot, "fetched_at", None)),
    }


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
        started_at=started_at,
        completed_at=datetime.now(UTC),
        requires_followup=requires_followup,
        followup_actions=followup_actions or [],
    )


def _result_field(value: Any, name: str, default: Any = None) -> Any:
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


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_iso_timestamp(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).strip()
