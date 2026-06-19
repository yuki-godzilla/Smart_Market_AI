from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import Field

from app.schemas.common import GatewayBaseModel
from app.services.model_router import (
    LlmEnvironmentProfile,
    LlmExecutionMode,
    LlmProfileName,
)

TOOL_PLANNER_REQUEST_SCHEMA_VERSION = "assistant_tool_planner_request.v1"
TOOL_PLANNER_RESPONSE_SCHEMA_VERSION = "assistant_tool_planner_response.v1"
TOOL_PLANNER_PROMPT_VERSION = "assistant_tool_planner_mvp.v1"

PlannerActionType = Literal["navigation", "state_change", "data_fetch", "report", "explain"]
ToolPlannerGatewayStatus = Literal["ok", "fallback"]


class PlannerAvailableAction(GatewayBaseModel):
    action_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    action_type: PlannerActionType
    requires_confirmation: bool = True
    is_external_fetch: bool = False
    enabled: bool = True
    disabled_reason: str | None = Field(default=None, min_length=1)


class ToolPlannerConstraints(GatewayBaseModel):
    no_investment_advice: bool = True
    no_auto_execution: bool = True
    do_not_change_scores: bool = True
    do_not_rank_symbols: bool = True
    require_confirmation_for_external_fetch: bool = True
    max_steps: int = Field(default=5, gt=0, le=6)
    allowed_action_ids: list[str] = Field(default_factory=list)


class ToolPlannerRequest(GatewayBaseModel):
    schema_version: str = TOOL_PLANNER_REQUEST_SCHEMA_VERSION
    prompt_version: str = TOOL_PLANNER_PROMPT_VERSION
    task_type: Literal["assistant_tool_plan"] = "assistant_tool_plan"
    language: Literal["ja", "en"] = "ja"
    user_question: str = Field(min_length=1)
    current_page: str = Field(min_length=1)
    context_summary: str = Field(min_length=1)
    material_state: dict[str, str] = Field(default_factory=dict)
    available_actions: list[PlannerAvailableAction] = Field(default_factory=list)
    constraints: ToolPlannerConstraints = Field(default_factory=ToolPlannerConstraints)
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    profile: LlmProfileName | None = None
    execution_mode: LlmExecutionMode = "auto"
    environment_profile: LlmEnvironmentProfile = "notebook"
    preferred_profile: LlmProfileName | None = None


class ToolPlannerStep(GatewayBaseModel):
    step_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=240)
    action_id: str | None = Field(default=None, min_length=1)
    reason: str = Field(min_length=1, max_length=240)
    requires_confirmation: bool = True
    confidence: float = Field(default=0.5, ge=0, le=1)
    priority: Literal["high", "medium", "low"] = "medium"


class ToolPlannerResponse(GatewayBaseModel):
    schema_version: str = TOOL_PLANNER_RESPONSE_SCHEMA_VERSION
    plan_type: Literal["tool_plan", "guided_workflow"] = "tool_plan"
    user_intent: str = Field(min_length=1)
    overall_summary: str = Field(min_length=1, max_length=320)
    steps: list[ToolPlannerStep] = Field(default_factory=list, max_length=6)
    safety_note: str = Field(
        default="この提案は確認手順の整理であり、売買推奨ではありません。",
        min_length=1,
    )
    planner_source: Literal["llm", "fallback"] = "llm"
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    profile: LlmProfileName = "fallback"
    elapsed_ms: int = Field(ge=0)
    gateway_status: ToolPlannerGatewayStatus = "ok"
    fallback_reason: str | None = Field(default=None, min_length=1)
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    timeout_sec: float | None = Field(default=None, ge=0)
    prompt_chars: int | None = Field(default=None, ge=0)
    response_chars: int | None = Field(default=None, ge=0)
    llm_generation_ms: int | None = Field(default=None, ge=0)
    total_elapsed_ms: int | None = Field(default=None, ge=0)
