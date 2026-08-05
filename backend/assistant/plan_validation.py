from __future__ import annotations

from typing import Sequence

from pydantic import Field

from backend.assistant.guided_workflow import AssistantGuidedWorkflow
from backend.assistant.tool_plan import AssistantToolPlan
from backend.assistant.tool_registry import assistant_action_registry
from backend.core.data_contracts import StrictBaseModel

_BANNED_ADVICE_TERMS = (
    "買うべき",
    "売るべき",
    "保有すべき",
    "必ず上がる",
    "必ず下がる",
    "確実に利益",
    "利益が出ます",
    "買い推奨",
    "売り推奨",
    "strong buy",
    "strong sell",
    "buy this",
    "sell this",
    "hold this",
    "guaranteed profit",
    "guaranteed return",
    "購入推奨",
    "保有推奨",
    "買ってください",
    "売ってください",
    "今すぐ買",
    "今すぐ売",
    "買い時です",
    "売り時です",
)
_BANNED_EXECUTION_TERMS = (
    "broker",
    "order sending",
    "execution",
    "place order",
    "execute trade",
    "trade placement",
    "注文",
    "発注",
    "約定",
    "自動売買",
)


class AssistantPlanValidationResult(StrictBaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def validate_assistant_tool_plan(
    plan: AssistantToolPlan,
    *,
    max_steps: int = 5,
) -> AssistantPlanValidationResult:
    registry = assistant_action_registry()
    errors: list[str] = []
    warnings: list[str] = []

    if len(plan.steps) > max_steps:
        errors.append(f"step count exceeds max_steps={max_steps}")

    text_blob = " ".join(
        [
            plan.user_intent,
            plan.overall_summary,
            plan.safety_note,
            *plan.missing_materials,
            *plan.warnings,
            *(step.title for step in plan.steps),
            *(step.summary for step in plan.steps),
            *(step.reason for step in plan.steps),
            *(step.disabled_reason or "" for step in plan.steps),
        ]
    ).lower()
    if any(term.lower() in text_blob for term in _BANNED_ADVICE_TERMS):
        errors.append("plan contains investment-advice-like wording")
    if any(term.lower() in text_blob for term in _BANNED_EXECUTION_TERMS):
        errors.append("plan contains execution-like wording")

    for step in plan.steps:
        if not step.action_id:
            continue
        action = registry.get(step.action_id)
        if action is None:
            errors.append(f"unknown action_id: {step.action_id}")
            continue
        if action.is_destructive:
            errors.append(f"destructive action is not allowed: {step.action_id}")
        if action.is_external_fetch and not step.requires_confirmation:
            errors.append(f"external fetch requires confirmation: {step.action_id}")
        if action.requires_confirmation and not step.requires_confirmation:
            errors.append(f"action requires confirmation: {step.action_id}")
        if not action.enabled and step.status == "ready":
            errors.append(f"disabled action cannot be ready: {step.action_id}")
        if not action.enabled and not step.disabled_reason:
            warnings.append(f"disabled action has no disabled_reason: {step.action_id}")
        if step.action_id in {"create_ranking", "refresh_news"} and step.status == "ready":
            errors.append(f"{step.action_id} is not connected for ready execution")

    return AssistantPlanValidationResult(valid=not errors, errors=errors, warnings=warnings)


def validate_assistant_guided_workflow(
    workflow: AssistantGuidedWorkflow,
    *,
    max_steps: int = 6,
) -> AssistantPlanValidationResult:
    registry = assistant_action_registry()
    errors: list[str] = []
    warnings: list[str] = []

    if len(workflow.steps) > max_steps:
        errors.append(f"workflow step count exceeds max_steps={max_steps}")

    text_blob = " ".join(
        [
            workflow.title,
            workflow.summary,
            workflow.user_intent,
            workflow.safety_note,
            *(step.title for step in workflow.steps),
            *(step.summary for step in workflow.steps),
            *(step.followup_hint or "" for step in workflow.steps),
            *(step.disabled_reason or "" for step in workflow.steps),
            *(step.result_summary or "" for step in workflow.steps),
        ]
    ).lower()
    if any(term.lower() in text_blob for term in _BANNED_ADVICE_TERMS):
        errors.append("workflow contains investment-advice-like wording")
    if any(term.lower() in text_blob for term in _BANNED_EXECUTION_TERMS):
        errors.append("workflow contains execution-like wording")

    for step in workflow.steps:
        if step.kind == "confirmable_action" and not step.requires_confirmation:
            errors.append(f"confirmable workflow step requires confirmation: {step.step_id}")
        if not step.action_id:
            continue
        action = registry.get(step.action_id)
        if action is None:
            errors.append(f"unknown workflow action_id: {step.action_id}")
            continue
        if action.is_destructive:
            errors.append(f"destructive workflow action is not allowed: {step.action_id}")
        if action.is_external_fetch and not step.requires_confirmation:
            errors.append(f"workflow external fetch requires confirmation: {step.action_id}")
        if action.requires_confirmation and not step.requires_confirmation:
            errors.append(f"workflow action requires confirmation: {step.action_id}")
        if step.action_id == "create_ranking" and step.status in {
            "ready",
            "waiting_confirmation",
        }:
            errors.append("create_ranking is not connected for guided workflow")
        if step.action_id == "refresh_news" and step.status in {
            "ready",
            "waiting_confirmation",
        }:
            errors.append("refresh_news is not connected for guided workflow")
        if not action.enabled and step.status == "ready":
            errors.append(f"disabled workflow action cannot be ready: {step.action_id}")
        if not action.enabled and not step.disabled_reason:
            warnings.append(f"disabled workflow action has no disabled_reason: {step.action_id}")

    return AssistantPlanValidationResult(valid=not errors, errors=errors, warnings=warnings)


def safe_validation_warnings(items: Sequence[str]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()][:5]
