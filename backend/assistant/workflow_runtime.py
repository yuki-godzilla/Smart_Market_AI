from __future__ import annotations

from datetime import UTC, datetime

from backend.assistant.action_result import AssistantActionResult
from backend.assistant.guided_workflow import AssistantGuidedWorkflow
from backend.assistant.plan_validation import (
    safe_validation_warnings,
    validate_assistant_guided_workflow,
)
from backend.assistant.workflow_session import (
    AssistantWorkflowRuntimeStep,
    AssistantWorkflowSession,
    WorkflowRuntimeStepStatus,
    WorkflowSessionStatus,
    workflow_session_from_guided_workflow,
)

_TERMINAL_STEP_STATUSES = {"done", "failed", "skipped", "cancelled", "blocked"}
_SUCCESS_ACTION_STATUSES = {"success", "partial_success"}
_FAILED_ACTION_STATUSES = {"failed", "not_available", "validation_error"}


def start_session(workflow: AssistantGuidedWorkflow) -> AssistantWorkflowSession | None:
    """Create a runtime session only after the guided workflow passes the safety gate."""

    validation = validate_assistant_guided_workflow(workflow)
    if not validation.valid:
        return None
    return workflow_session_from_guided_workflow(
        workflow,
        warnings=safe_validation_warnings(validation.warnings),
    )


def set_waiting_confirmation(
    session: AssistantWorkflowSession,
    step_id: str,
) -> AssistantWorkflowSession:
    step = _step_by_id(session, step_id)
    if step is None:
        return _append_session_warning(session, "指定された手順が見つかりません。")
    if step.status in _TERMINAL_STEP_STATUSES or step.status == "running":
        return _append_session_warning(session, "この手順は確認待ちに戻せません。")
    if not step.requires_confirmation:
        return _append_session_warning(session, "この手順は実行前確認を必要としません。")
    return _replace_step(
        session,
        step.model_copy(update={"status": "waiting_confirmation"}),
        status="active",
        active_step_id=step.step_id,
    )


def mark_running(
    session: AssistantWorkflowSession,
    step_id: str,
    *,
    confirmed: bool = False,
) -> AssistantWorkflowSession:
    step = _step_by_id(session, step_id)
    if step is None:
        return _append_session_warning(session, "指定された手順が見つかりません。")
    if session.status in {"completed", "cancelled", "failed"}:
        return _append_session_warning(session, "終了済みのフローは実行できません。")
    if step.requires_confirmation and not confirmed:
        return _append_session_warning(session, "この手順は実行前確認が必要です。")
    if step.status == "running":
        return _append_session_warning(session, "この手順はすでに実行中です。")
    if step.status in _TERMINAL_STEP_STATUSES:
        return _append_session_warning(session, "完了済みまたは停止済みの手順は再実行しません。")
    return _replace_step(
        session,
        step.model_copy(
            update={
                "status": "running",
                "started_at": step.started_at or datetime.now(UTC),
            }
        ),
        status="active",
        active_step_id=step.step_id,
    )


def apply_action_result(
    session: AssistantWorkflowSession,
    step_id: str,
    result: AssistantActionResult,
) -> AssistantWorkflowSession:
    step = _step_by_id(session, step_id)
    if step is None:
        return _append_session_warning(session, "実行結果に対応する手順が見つかりません。")
    if step.status in {"done", "running"} and step.result_status == result.status:
        return _append_session_warning(session, "同じ手順の実行結果はすでに反映済みです。")
    if step.action_id and step.action_id != result.action_id:
        return _append_session_warning(session, "実行結果の操作IDが手順と一致しません。")

    runtime_status = _runtime_status_from_action_result(result)
    updated_step = step.model_copy(
        update={
            "status": runtime_status,
            "result_status": result.status,
            "result_summary": result.summary,
            "warnings": _safe_warnings([*step.warnings, *result.warnings]),
            "started_at": step.started_at or result.started_at,
            "completed_at": result.completed_at or datetime.now(UTC),
        }
    )
    updated = _replace_step(
        session,
        updated_step,
        last_result_summary=result.summary,
    )

    if result.action_id == "update_research" and runtime_status == "done":
        return _activate_followup_step(
            updated,
            action_id="create_decision_report",
            enabled="create_decision_report" in result.followup_actions,
        )
    if result.action_id == "create_decision_report" and runtime_status == "done":
        return _complete_session(updated)
    if runtime_status == "failed":
        return _fail_session(updated)
    return _refresh_session_progress(updated)


def skip_step(
    session: AssistantWorkflowSession,
    step_id: str,
    reason: str | None = None,
) -> AssistantWorkflowSession:
    step = _step_by_id(session, step_id)
    if step is None:
        return _append_session_warning(session, "指定された手順が見つかりません。")
    if step.status in _TERMINAL_STEP_STATUSES:
        return _append_session_warning(session, "終了済みの手順はスキップしません。")
    summary = reason.strip() if reason else "ユーザー操作により、この手順をスキップしました。"
    updated = _replace_step(
        session,
        step.model_copy(
            update={
                "status": "skipped",
                "result_summary": summary,
                "completed_at": datetime.now(UTC),
            }
        ),
    )
    return _refresh_session_progress(updated)


def cancel_session(
    session: AssistantWorkflowSession,
    reason: str | None = None,
) -> AssistantWorkflowSession:
    cancelled_steps = [
        (
            step.model_copy(
                update={
                    "status": "cancelled",
                    "completed_at": step.completed_at or datetime.now(UTC),
                }
            )
            if step.status not in _TERMINAL_STEP_STATUSES
            else step
        )
        for step in session.steps
    ]
    return session.model_copy(
        update={
            "status": "cancelled",
            "active_step_id": None,
            "steps": cancelled_steps,
            "cancelled_reason": reason.strip() if reason else "ユーザー操作により中止しました。",
            "updated_at": datetime.now(UTC),
            "completed_at": datetime.now(UTC),
        }
    )


def _runtime_status_from_action_result(
    result: AssistantActionResult,
) -> WorkflowRuntimeStepStatus:
    if result.status in _SUCCESS_ACTION_STATUSES:
        return "done"
    if result.status in _FAILED_ACTION_STATUSES:
        return "failed"
    if result.status == "cancelled":
        return "cancelled"
    return "skipped"


def _activate_followup_step(
    session: AssistantWorkflowSession,
    *,
    action_id: str,
    enabled: bool,
) -> AssistantWorkflowSession:
    if not enabled:
        return _refresh_session_progress(session)
    for step in session.steps:
        if step.action_id != action_id or step.status in _TERMINAL_STEP_STATUSES:
            continue
        updated = _replace_step(
            session,
            step.model_copy(update={"status": "waiting_confirmation"}),
            status="active",
            active_step_id=step.step_id,
        )
        return updated
    return _refresh_session_progress(session)


def _complete_session(session: AssistantWorkflowSession) -> AssistantWorkflowSession:
    return session.model_copy(
        update={
            "status": "completed",
            "active_step_id": None,
            "updated_at": datetime.now(UTC),
            "completed_at": datetime.now(UTC),
        }
    )


def _fail_session(session: AssistantWorkflowSession) -> AssistantWorkflowSession:
    return session.model_copy(
        update={
            "status": "failed",
            "active_step_id": None,
            "updated_at": datetime.now(UTC),
        }
    )


def _refresh_session_progress(session: AssistantWorkflowSession) -> AssistantWorkflowSession:
    active_step_id = _next_active_step_id(session.steps)
    if active_step_id:
        status: WorkflowSessionStatus = "active"
        completed_at = None
    elif any(step.status == "failed" for step in session.steps):
        status = "failed"
        completed_at = None
    else:
        status = "completed"
        completed_at = datetime.now(UTC)
    return session.model_copy(
        update={
            "status": status,
            "active_step_id": active_step_id,
            "updated_at": datetime.now(UTC),
            "completed_at": completed_at,
        }
    )


def _next_active_step_id(steps: list[AssistantWorkflowRuntimeStep]) -> str | None:
    for preferred_status in ("waiting_confirmation", "planned", "running"):
        for step in steps:
            if step.status == preferred_status:
                return step.step_id
    return None


def _replace_step(
    session: AssistantWorkflowSession,
    step: AssistantWorkflowRuntimeStep,
    **updates: object,
) -> AssistantWorkflowSession:
    steps = [step if item.step_id == step.step_id else item for item in session.steps]
    return session.model_copy(update={"steps": steps, "updated_at": datetime.now(UTC), **updates})


def _step_by_id(
    session: AssistantWorkflowSession,
    step_id: str,
) -> AssistantWorkflowRuntimeStep | None:
    return next((step for step in session.steps if step.step_id == step_id), None)


def _append_session_warning(
    session: AssistantWorkflowSession,
    warning: str,
) -> AssistantWorkflowSession:
    return session.model_copy(
        update={
            "warnings": _safe_warnings([*session.warnings, warning]),
            "updated_at": datetime.now(UTC),
        }
    )


def _safe_warnings(items: list[str]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()][:5]
