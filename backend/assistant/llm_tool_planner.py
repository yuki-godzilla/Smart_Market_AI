from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import Field, ValidationError

from backend.assistant.context_builder import SMAIAssistantContext
from backend.assistant.gateway_client import (
    AssistantGatewayError,
    AssistantGatewayTimeoutError,
    AssistantPlannerGatewayClient,
    create_assistant_planner_gateway_client_from_settings,
)
from backend.assistant.gateway_contracts import (
    ASSISTANT_PLANNER_PROMPT_VERSION,
    AssistantPlannerConstraints,
    AssistantPlannerRequest,
    AssistantPlannerResponse,
    PlannerAvailableAction,
)
from backend.assistant.guided_workflow import (
    ASSISTANT_GUIDED_WORKFLOW_SAFETY_NOTE,
    AssistantGuidedWorkflow,
    AssistantWorkflowStep,
)
from backend.assistant.plan_validation import (
    AssistantPlanValidationResult,
    safe_validation_warnings,
    validate_assistant_guided_workflow,
    validate_assistant_tool_plan,
)
from backend.assistant.tool_plan import (
    ASSISTANT_TOOL_PLAN_SAFETY_NOTE,
    AssistantToolPlan,
    AssistantToolPlanStep,
    build_deterministic_assistant_tool_plan,
)
from backend.assistant.tool_registry import (
    AssistantActionSpec,
    assistant_action_catalog,
)
from backend.core.config import Settings, get_settings
from backend.core.data_contracts import StrictBaseModel

PlannerSource = Literal["disabled", "llm", "fallback"]
_UNSUPPORTED_LLM_ACTION_IDS = {"create_ranking", "refresh_news"}
_REDACTED_MATERIAL_KEYS = (
    "provider_raw",
    "raw_payload",
    "raw_text",
    "full_text",
    "source_text",
    "body_html",
    "html",
    "payload",
    "debug",
    "traceback",
    "log",
)


class AssistantPlannerMetadata(StrictBaseModel):
    """Technical planner metadata kept out of normal user-facing wording."""

    planner_source: PlannerSource = "fallback"
    used_plan_type: str | None = Field(default=None, min_length=1)
    fallback_reason: str | None = Field(default=None, min_length=1)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    profile: str | None = Field(default=None, min_length=1)
    gateway_status: str | None = Field(default=None, min_length=1)
    request_id: str | None = Field(default=None, min_length=1)
    show_source_details: bool = False


class AssistantPlannerStates(StrictBaseModel):
    """UI-ready planner states after validation and deterministic fallback."""

    tool_plan: AssistantToolPlan
    guided_workflow: AssistantGuidedWorkflow | None = None
    metadata: AssistantPlannerMetadata = Field(default_factory=AssistantPlannerMetadata)


def build_assistant_planner_request(
    context: SMAIAssistantContext,
    *,
    max_steps: int = 5,
    available_actions: Sequence[AssistantActionSpec] | None = None,
) -> AssistantPlannerRequest:
    """Build a compact, redacted request for the optional Gateway planner."""

    actions = tuple(available_actions or assistant_action_catalog())
    allowed_action_ids = [action.action_id for action in actions if action.enabled]
    return AssistantPlannerRequest(
        user_question=str(context.user_question or "次に確認することを整理して").strip(),
        current_page=context.current_page,
        context_summary=context.summary or "現在の画面と取得済み材料をもとに確認順を整理します。",
        material_state=_safe_material_state(context.material_state),
        available_actions=[_planner_action_from_spec(action) for action in actions],
        constraints=AssistantPlannerConstraints(
            max_steps=max_steps,
            allowed_action_ids=allowed_action_ids,
        ),
    )


def build_assistant_planner_states(
    context: SMAIAssistantContext,
    *,
    settings: Settings | None = None,
    client: AssistantPlannerGatewayClient | None = None,
    enabled: bool | None = None,
    max_steps: int | None = None,
) -> AssistantPlannerStates:
    """Try the optional LLM planner, then fall back to deterministic safe states."""

    resolved_settings = settings or get_settings()
    planner_config = resolved_settings.assistant.llm_planner
    planner_enabled = planner_config.enabled if enabled is None else enabled
    resolved_max_steps = max_steps or planner_config.max_steps
    fallback_states = _deterministic_states(context, max_steps=resolved_max_steps)
    if not planner_enabled:
        return fallback_states.model_copy(
            update={
                "metadata": AssistantPlannerMetadata(
                    planner_source="disabled",
                    fallback_reason="planner_disabled",
                    show_source_details=planner_config.show_source_details,
                )
            }
        )

    planner_client = client or create_assistant_planner_gateway_client_from_settings(
        resolved_settings
    )
    if planner_client is None:
        return _with_fallback_metadata(
            fallback_states,
            reason="planner_client_unavailable",
            show_source_details=planner_config.show_source_details,
        )

    request = build_assistant_planner_request(context, max_steps=resolved_max_steps)
    try:
        raw_response = planner_client.tool_plan(request)
        planner_response = _coerce_planner_response(raw_response)
    except AssistantGatewayTimeoutError as exc:
        return _with_fallback_metadata(
            fallback_states,
            reason="gateway_timeout",
            errors=[str(exc)],
            request_id=request.request_id,
            show_source_details=planner_config.show_source_details,
        )
    except AssistantGatewayError as exc:
        return _with_fallback_metadata(
            fallback_states,
            reason=exc.gateway_error_type,
            errors=[exc.gateway_error_message],
            request_id=request.request_id,
            show_source_details=planner_config.show_source_details,
        )
    except (TimeoutError, ValidationError, ValueError) as exc:
        return _with_fallback_metadata(
            fallback_states,
            reason="planner_response_invalid",
            errors=[str(exc)],
            request_id=request.request_id,
            show_source_details=planner_config.show_source_details,
        )

    response_validation = _validate_planner_response(
        planner_response,
        request=request,
        max_steps=resolved_max_steps,
    )
    if planner_response.gateway_status != "ok" or not response_validation.valid:
        reason = planner_response.fallback_reason or "planner_validation_failure"
        return _with_fallback_metadata(
            fallback_states,
            reason=reason,
            errors=response_validation.errors,
            warnings=response_validation.warnings,
            provider=planner_response.provider,
            model=planner_response.model,
            profile=planner_response.profile,
            gateway_status=planner_response.gateway_status,
            request_id=planner_response.request_id or request.request_id,
            show_source_details=planner_config.show_source_details,
        )

    if planner_response.plan_type == "guided_workflow":
        workflow = _guided_workflow_from_planner_response(
            planner_response,
            context=context,
            request=request,
            max_steps=resolved_max_steps,
        )
        validation = validate_assistant_guided_workflow(workflow)
        if not validation.valid:
            return _with_fallback_metadata(
                fallback_states,
                reason="planner_workflow_validation_failure",
                errors=validation.errors,
                warnings=validation.warnings,
                provider=planner_response.provider,
                model=planner_response.model,
                profile=planner_response.profile,
                gateway_status=planner_response.gateway_status,
                request_id=planner_response.request_id or request.request_id,
                show_source_details=planner_config.show_source_details,
            )
        return AssistantPlannerStates(
            tool_plan=fallback_states.tool_plan,
            guided_workflow=workflow,
            metadata=_llm_metadata(
                planner_response,
                used_plan_type="guided_workflow",
                request_id=request.request_id,
                warnings=validation.warnings,
                show_source_details=planner_config.show_source_details,
            ),
        )

    plan = _tool_plan_from_planner_response(
        planner_response,
        context=context,
        request=request,
        max_steps=resolved_max_steps,
    )
    validation = validate_assistant_tool_plan(plan)
    if not validation.valid:
        return _with_fallback_metadata(
            fallback_states,
            reason="planner_tool_plan_validation_failure",
            errors=validation.errors,
            warnings=validation.warnings,
            provider=planner_response.provider,
            model=planner_response.model,
            profile=planner_response.profile,
            gateway_status=planner_response.gateway_status,
            request_id=planner_response.request_id or request.request_id,
            show_source_details=planner_config.show_source_details,
        )
    if validation.warnings:
        plan = plan.model_copy(update={"warnings": [*plan.warnings, *validation.warnings]})
    return AssistantPlannerStates(
        tool_plan=plan,
        guided_workflow=fallback_states.guided_workflow,
        metadata=_llm_metadata(
            planner_response,
            used_plan_type="tool_plan",
            request_id=request.request_id,
            warnings=validation.warnings,
            show_source_details=planner_config.show_source_details,
        ),
    )


def _deterministic_states(
    context: SMAIAssistantContext,
    *,
    max_steps: int,
) -> AssistantPlannerStates:
    plan = build_deterministic_assistant_tool_plan(context, max_steps=min(max_steps, 5))
    plan_validation = validate_assistant_tool_plan(plan)
    if not plan_validation.valid:
        plan = plan.model_copy(
            update={
                "generated_by": "fallback",
                "warnings": [
                    *plan.warnings,
                    *safe_validation_warnings(plan_validation.errors),
                    "Tool Planを安全側に検証しました。表示できない操作は実行しません。",
                ],
            }
        )
    elif plan_validation.warnings:
        plan = plan.model_copy(update={"warnings": [*plan.warnings, *plan_validation.warnings]})
    from backend.assistant.guided_workflow import build_deterministic_guided_workflow

    workflow = build_deterministic_guided_workflow(context, max_steps=6)
    if workflow is not None:
        workflow_validation = validate_assistant_guided_workflow(workflow)
        if not workflow_validation.valid:
            workflow = None
    return AssistantPlannerStates(tool_plan=plan, guided_workflow=workflow)


def _tool_plan_from_planner_response(
    response: AssistantPlannerResponse,
    *,
    context: SMAIAssistantContext,
    request: AssistantPlannerRequest,
    max_steps: int,
) -> AssistantToolPlan:
    actions = _action_map(request.available_actions)
    steps: list[AssistantToolPlanStep] = []
    for index, planner_step in enumerate(response.steps[: min(max_steps, 5)], start=1):
        action = actions.get(planner_step.action_id or "")
        confirmation = bool(
            planner_step.requires_confirmation
            or (action and action.requires_confirmation)
            or (action and action.is_external_fetch)
        )
        enabled = True if action is None else action.enabled
        steps.append(
            AssistantToolPlanStep(
                step_id=_safe_step_id(planner_step.step_id, index=index),
                title=planner_step.title,
                summary=planner_step.summary,
                action_id=planner_step.action_id,
                reason=planner_step.reason,
                requires_confirmation=confirmation,
                priority=planner_step.priority,
                status="suggested" if enabled else "blocked",
                disabled_reason=None if enabled else action.disabled_reason,
            )
        )
    return AssistantToolPlan(
        user_intent=response.user_intent,
        current_page=context.current_page,
        overall_summary=response.overall_summary,
        steps=steps,
        missing_materials=context.missing_materials[:5],
        warnings=context.warnings[:5],
        safety_note=response.safety_note or ASSISTANT_TOOL_PLAN_SAFETY_NOTE,
        generated_by="llm",
        provider=response.provider,
        model=response.model,
        prompt_version=ASSISTANT_PLANNER_PROMPT_VERSION,
    )


def _guided_workflow_from_planner_response(
    response: AssistantPlannerResponse,
    *,
    context: SMAIAssistantContext,
    request: AssistantPlannerRequest,
    max_steps: int,
) -> AssistantGuidedWorkflow:
    actions = _action_map(request.available_actions)
    target_symbol = _target_symbol(context)
    steps: list[AssistantWorkflowStep] = []
    for index, planner_step in enumerate(response.steps[:max_steps], start=1):
        action = actions.get(planner_step.action_id or "")
        requires_confirmation = bool(
            planner_step.requires_confirmation
            or (action and action.requires_confirmation)
            or (action and action.is_external_fetch)
        )
        enabled = True if action is None else action.enabled
        kind = _workflow_kind_for_action(action, requires_confirmation=requires_confirmation)
        steps.append(
            AssistantWorkflowStep(
                step_id=_safe_step_id(planner_step.step_id, index=index),
                title=planner_step.title,
                summary=planner_step.summary,
                kind=kind if enabled else "not_available",
                action_id=planner_step.action_id,
                target_page=_target_page_for_action(planner_step.action_id),
                symbol=target_symbol,
                requires_confirmation=requires_confirmation,
                status=_workflow_status_for_step(kind, enabled=enabled),
                disabled_reason=None if enabled else action.disabled_reason,
                followup_hint=planner_step.reason,
            )
        )
    return AssistantGuidedWorkflow(
        title="AI提案の確認フロー",
        summary=response.overall_summary,
        user_intent=response.user_intent,
        current_page=context.current_page,
        target_symbol=target_symbol,
        steps=steps,
        safety_note=response.safety_note or ASSISTANT_GUIDED_WORKFLOW_SAFETY_NOTE,
        generated_by="llm",
    )


def _validate_planner_response(
    response: AssistantPlannerResponse,
    *,
    request: AssistantPlannerRequest,
    max_steps: int,
) -> AssistantPlanValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    allowed = _action_map(request.available_actions)
    if len(response.steps) > max_steps:
        errors.append(f"planner step count exceeds max_steps={max_steps}")
    if response.planner_source != "llm":
        errors.append(f"unsupported planner_source: {response.planner_source}")
    for step in response.steps:
        if not step.action_id:
            continue
        action = allowed.get(step.action_id)
        if action is None:
            errors.append(f"planner referenced unavailable action_id: {step.action_id}")
            continue
        if not action.enabled:
            errors.append(f"planner referenced disabled action_id: {step.action_id}")
        if action.is_external_fetch and not step.requires_confirmation:
            errors.append(f"planner external fetch requires confirmation: {step.action_id}")
        if action.requires_confirmation and not step.requires_confirmation:
            errors.append(f"planner action requires confirmation: {step.action_id}")
        if step.action_id in _UNSUPPORTED_LLM_ACTION_IDS:
            errors.append(f"planner action is not connected for LLM planning: {step.action_id}")
    return AssistantPlanValidationResult(valid=not errors, errors=errors, warnings=warnings)


def _planner_action_from_spec(action: AssistantActionSpec) -> PlannerAvailableAction:
    return PlannerAvailableAction(
        action_id=action.action_id,
        label=action.label,
        description=action.description,
        action_type=action.action_type,
        requires_confirmation=action.requires_confirmation,
        is_external_fetch=action.is_external_fetch,
        enabled=action.enabled,
        disabled_reason=action.disabled_reason,
    )


def _coerce_planner_response(
    response: AssistantPlannerResponse | Mapping[str, object],
) -> AssistantPlannerResponse:
    if isinstance(response, AssistantPlannerResponse):
        return response
    return AssistantPlannerResponse.model_validate(response)


def _action_map(
    actions: Sequence[PlannerAvailableAction],
) -> dict[str, PlannerAvailableAction]:
    return {action.action_id: action for action in actions}


def _workflow_kind_for_action(
    action: PlannerAvailableAction | None,
    *,
    requires_confirmation: bool,
) -> Literal["navigation", "confirmable_action", "review", "manual_check", "not_available"]:
    if action is None:
        return "review"
    if requires_confirmation or action.action_type in {"data_fetch", "report", "state_change"}:
        return "confirmable_action"
    if action.action_type == "navigation":
        return "navigation"
    return "review"


def _workflow_status_for_step(
    kind: str,
    *,
    enabled: bool,
) -> Literal["suggested", "ready", "waiting_confirmation", "blocked"]:
    if not enabled:
        return "blocked"
    if kind == "confirmable_action":
        return "waiting_confirmation"
    if kind == "navigation":
        return "ready"
    return "suggested"


def _target_page_for_action(action_id: str | None) -> str | None:
    return {
        "open_ranking": "ranking",
        "open_cockpit": "cockpit",
        "open_symbol_from_ranking": "cockpit",
        "open_news_radar": "news",
        "open_macro_news": "news",
        "open_symbol_related_news": "news",
        "open_forecast_section": "cockpit",
        "open_research_section": "cockpit",
        "open_ai_interpretation": "cockpit",
    }.get(str(action_id or ""))


def _target_symbol(context: SMAIAssistantContext) -> str | None:
    for value in (
        context.page_state.get("active_symbol"),
        context.page_state.get("selected_symbol"),
        context.page_state.get("symbol"),
        context.material_state.get("symbol"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    return None


def _safe_material_state(values: Mapping[str, object]) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in values.items():
        clean_key = str(key or "").strip()
        if not clean_key or _should_redact_key(clean_key):
            continue
        text = str(value or "").strip()
        if text:
            safe[clean_key] = text[:180]
    return safe


def _should_redact_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(term in normalized for term in _REDACTED_MATERIAL_KEYS)


def _safe_step_id(step_id: str, *, index: int) -> str:
    normalized = str(step_id or "").strip().replace(" ", "_")
    if normalized:
        return normalized[:80]
    return f"planner_step_{index}"


def _with_fallback_metadata(
    states: AssistantPlannerStates,
    *,
    reason: str,
    errors: Sequence[str] = (),
    warnings: Sequence[str] = (),
    provider: str | None = None,
    model: str | None = None,
    profile: str | None = None,
    gateway_status: str | None = None,
    request_id: str | None = None,
    show_source_details: bool = False,
) -> AssistantPlannerStates:
    return states.model_copy(
        update={
            "metadata": AssistantPlannerMetadata(
                planner_source="fallback",
                fallback_reason=reason,
                errors=safe_validation_warnings(errors),
                warnings=safe_validation_warnings(warnings),
                provider=provider,
                model=model,
                profile=profile,
                gateway_status=gateway_status,
                request_id=request_id,
                show_source_details=show_source_details,
            )
        }
    )


def _llm_metadata(
    response: AssistantPlannerResponse,
    *,
    used_plan_type: str,
    request_id: str,
    warnings: Sequence[str],
    show_source_details: bool,
) -> AssistantPlannerMetadata:
    return AssistantPlannerMetadata(
        planner_source="llm",
        used_plan_type=used_plan_type,
        warnings=safe_validation_warnings(warnings),
        provider=response.provider,
        model=response.model,
        profile=response.profile,
        gateway_status=response.gateway_status,
        request_id=response.request_id or request_id,
        show_source_details=show_source_details,
    )
