from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field

from backend.assistant.guided_workflow import AssistantGuidedWorkflow, AssistantWorkflowStep
from backend.core.data_contracts import StrictBaseModel

ASSISTANT_WORKFLOW_SESSION_SCHEMA_VERSION = "assistant-workflow-session-v1"

WorkflowSessionStatus = Literal[
    "planned",
    "active",
    "paused",
    "completed",
    "cancelled",
    "failed",
]
WorkflowRuntimeStepStatus = Literal[
    "planned",
    "waiting_confirmation",
    "running",
    "done",
    "failed",
    "skipped",
    "cancelled",
    "blocked",
]


class AssistantWorkflowRuntimeStep(StrictBaseModel):
    step_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    action_id: str | None = Field(default=None, min_length=1)
    target_page: str | None = Field(default=None, min_length=1)
    symbol: str | None = Field(default=None, min_length=1)
    requires_confirmation: bool = False
    status: WorkflowRuntimeStepStatus = "planned"
    disabled_reason: str | None = Field(default=None, min_length=1)
    result_summary: str | None = Field(default=None, min_length=1)
    result_status: str | None = Field(default=None, min_length=1)
    followup_hint: str | None = Field(default=None, min_length=1)
    warnings: list[str] = Field(default_factory=list, max_length=5)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AssistantWorkflowSession(StrictBaseModel):
    session_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    workflow_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    user_intent: str = Field(min_length=1)
    current_page: str = Field(min_length=1)
    target_symbol: str | None = Field(default=None, min_length=1)
    generated_by: str = Field(min_length=1)
    status: WorkflowSessionStatus = "planned"
    active_step_id: str | None = Field(default=None, min_length=1)
    steps: list[AssistantWorkflowRuntimeStep] = Field(default_factory=list, max_length=6)
    safety_note: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list, max_length=5)
    last_result_summary: str | None = Field(default=None, min_length=1)
    cancelled_reason: str | None = Field(default=None, min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    schema_version: str = ASSISTANT_WORKFLOW_SESSION_SCHEMA_VERSION


def workflow_session_from_guided_workflow(
    workflow: AssistantGuidedWorkflow,
    *,
    session_id: str | None = None,
    warnings: list[str] | None = None,
) -> AssistantWorkflowSession:
    steps = [runtime_step_from_workflow_step(step) for step in workflow.steps]
    active_step_id = _first_active_step_id(steps)
    status: WorkflowSessionStatus = "active" if active_step_id else "completed"
    return AssistantWorkflowSession(
        session_id=session_id or uuid4().hex,
        workflow_id=workflow.workflow_id,
        title=workflow.title,
        summary=workflow.summary,
        user_intent=workflow.user_intent,
        current_page=workflow.current_page,
        target_symbol=workflow.target_symbol,
        generated_by=workflow.generated_by,
        status=status,
        active_step_id=active_step_id,
        steps=steps,
        safety_note=workflow.safety_note,
        warnings=_safe_warnings(warnings or []),
        completed_at=datetime.now(UTC) if status == "completed" else None,
    )


def runtime_step_from_workflow_step(
    step: AssistantWorkflowStep,
) -> AssistantWorkflowRuntimeStep:
    return AssistantWorkflowRuntimeStep(
        step_id=step.step_id,
        title=step.title,
        summary=step.summary,
        kind=step.kind,
        action_id=step.action_id,
        target_page=step.target_page,
        symbol=step.symbol,
        requires_confirmation=step.requires_confirmation,
        status=_runtime_status_from_workflow_step(step),
        disabled_reason=step.disabled_reason,
        result_summary=step.result_summary,
        followup_hint=step.followup_hint,
    )


def _runtime_status_from_workflow_step(
    step: AssistantWorkflowStep,
) -> WorkflowRuntimeStepStatus:
    if step.disabled_reason or step.kind == "not_available" or step.status == "blocked":
        return "blocked"
    if step.status == "done":
        return "done"
    if step.status == "skipped":
        return "skipped"
    if step.status == "failed":
        return "failed"
    if step.requires_confirmation:
        return "waiting_confirmation"
    return "planned"


def _first_active_step_id(steps: list[AssistantWorkflowRuntimeStep]) -> str | None:
    for status in ("waiting_confirmation", "planned", "running"):
        for step in steps:
            if step.status == status:
                return step.step_id
    return None


def _safe_warnings(items: list[str]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()][:5]
