from __future__ import annotations

from typing import Sequence

from pydantic import Field

from backend.assistant.tool_plan import AssistantToolPlan
from backend.assistant.tool_registry import assistant_action_registry
from backend.core.data_contracts import StrictBaseModel

_BANNED_ADVICE_TERMS = (
    "買うべき",
    "売るべき",
    "必ず上がる",
    "必ず下がる",
    "買い推奨",
    "売り推奨",
    "strong buy",
    "strong sell",
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
            *(step.title for step in plan.steps),
            *(step.summary for step in plan.steps),
            *(step.reason for step in plan.steps),
        ]
    ).lower()
    if any(term.lower() in text_blob for term in _BANNED_ADVICE_TERMS):
        errors.append("plan contains investment-advice-like wording")

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

    return AssistantPlanValidationResult(valid=not errors, errors=errors, warnings=warnings)


def safe_validation_warnings(items: Sequence[str]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()][:5]
