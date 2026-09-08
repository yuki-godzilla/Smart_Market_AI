from __future__ import annotations

from datetime import UTC, datetime

from backend.assistant.action_result import AssistantActionResult, safe_action_error_message
from backend.assistant.tool_registry import AssistantActionSpec


def validate_action_for_execution(
    *,
    action: AssistantActionSpec,
    confirmed: bool,
    started_at: datetime,
) -> AssistantActionResult | None:
    """Enforce the shared action safety boundary before any handler runs."""
    if action.is_destructive:
        return _result(
            action=action,
            status="not_available",
            title="この操作は実行できません",
            summary="安全境界を超える操作はSMAIアシスタントから実行できません。",
            error_code="destructive_action",
            started_at=started_at,
        )
    if not action.enabled:
        return _result(
            action=action,
            status="not_available",
            title="この操作は現在利用できません",
            summary=action.disabled_reason or "現在の画面では利用できない操作です。",
            error_code="disabled_action",
            started_at=started_at,
        )
    if action.requires_confirmation and not confirmed:
        return _confirmation_required_result(action=action, started_at=started_at)
    if action.is_external_fetch and not confirmed:
        return _result(
            action=action,
            status="skipped",
            title="外部取得の確認が必要です",
            summary="外部取得はユーザー確認後にだけ実行します。",
            error_code="confirmation_required",
            started_at=started_at,
            requires_followup=True,
        )
    return None


def _confirmation_required_result(
    *, action: AssistantActionSpec, started_at: datetime
) -> AssistantActionResult:
    return _result(
        action=action,
        status="skipped",
        title="実行前確認が必要です",
        summary="ユーザー確認がないため、操作は実行していません。",
        error_code="confirmation_required",
        started_at=started_at,
        requires_followup=True,
    )


def _result(
    *,
    action: AssistantActionSpec,
    status: str,
    title: str,
    summary: str,
    error_code: str,
    started_at: datetime,
    requires_followup: bool = False,
) -> AssistantActionResult:
    return AssistantActionResult(
        action_id=action.action_id,
        status=status,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        user_message=safe_action_error_message(error_code),
        error_code=error_code,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        requires_followup=requires_followup,
        followup_actions=["summarize_next_checks"] if requires_followup else [],
    )
