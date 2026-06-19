from __future__ import annotations

import json
import re
from collections.abc import Sequence
from time import perf_counter

from pydantic import Field, ValidationError

from app.clients.ollama_client import OllamaClient, OllamaClientError
from app.schemas.common import GatewayBaseModel
from app.schemas.tool_plan import (
    TOOL_PLANNER_RESPONSE_SCHEMA_VERSION,
    PlannerAvailableAction,
    ToolPlannerRequest,
    ToolPlannerResponse,
    ToolPlannerStep,
)
from app.services.model_router import resolve_model_route
from app.services.prompt_service import PromptService

_UNSUPPORTED_LLM_ACTION_IDS = {"create_ranking", "refresh_news"}
_BANNED_TERMS = (
    "買うべき",
    "売るべき",
    "保有すべき",
    "必ず上がる",
    "必ず下がる",
    "確実に利益",
    "買い推奨",
    "売り推奨",
    "strong buy",
    "strong sell",
    "buy this",
    "sell this",
    "hold this",
    "guaranteed profit",
    "broker",
    "order sending",
    "execution",
    "place order",
    "trade placement",
    "注文",
    "発注",
    "約定",
    "自動売買",
)


class LlmToolPlannerPayload(GatewayBaseModel):
    schema_version: str = TOOL_PLANNER_RESPONSE_SCHEMA_VERSION
    plan_type: str = Field(pattern="^(tool_plan|guided_workflow)$")
    user_intent: str = Field(min_length=1)
    overall_summary: str = Field(min_length=1, max_length=320)
    steps: list[ToolPlannerStep] = Field(default_factory=list, max_length=6)
    safety_note: str = Field(
        default="この提案は確認手順の整理であり、売買推奨ではありません。",
        min_length=1,
    )
    planner_source: str = Field(pattern="^llm$")


class ToolPlanService:
    """Generate a schema-validated tool-plan proposal without executing actions."""

    def __init__(
        self,
        client: OllamaClient,
        *,
        prompt_service: PromptService | None = None,
    ) -> None:
        self.client = client
        self.prompt_service = prompt_service or PromptService()

    def plan(self, request: ToolPlannerRequest) -> ToolPlannerResponse:
        started = perf_counter()
        route = resolve_model_route(
            settings=self.client.settings,
            task_type=request.task_type,
            execution_mode=request.execution_mode,
            environment_profile=request.environment_profile,
            preferred_profile=request.profile or request.preferred_profile,
            requested_model=request.model,
        )
        messages = self.prompt_service.build_tool_plan_messages(request)
        prompt_chars = sum(len(message.content) for message in messages)
        if route.fallback:
            return _fallback_response(
                request,
                provider=route.provider,
                model=route.model,
                profile=route.profile,
                timeout_sec=route.timeout_seconds,
                prompt_chars=prompt_chars,
                started=started,
                reason=route.reason,
            )
        try:
            result = self.client.chat(
                messages,
                model=route.model,
                timeout_seconds=route.timeout_seconds,
                max_tokens=route.max_tokens,
            )
        except OllamaClientError as exc:
            return _fallback_response(
                request,
                provider=exc.provider,
                model=route.model,
                profile=route.profile,
                timeout_sec=route.timeout_seconds,
                prompt_chars=prompt_chars,
                started=started,
                reason=exc.code,
            )

        payload = _parse_llm_tool_plan(result.answer)
        validation_errors = _validate_payload(payload, request=request)
        if payload is None or validation_errors:
            return _fallback_response(
                request,
                provider=result.provider,
                model=result.model,
                profile=route.profile,
                timeout_sec=route.timeout_seconds,
                prompt_chars=prompt_chars,
                started=started,
                reason="response_validation_failure",
                response_chars=result.response_chars,
                llm_generation_ms=result.elapsed_ms,
            )

        total_elapsed_ms = _elapsed_ms(started)
        return ToolPlannerResponse(
            plan_type=payload.plan_type,  # type: ignore[arg-type]
            user_intent=payload.user_intent,
            overall_summary=payload.overall_summary,
            steps=payload.steps[: request.constraints.max_steps],
            safety_note=payload.safety_note,
            planner_source="llm",
            provider=result.provider,
            model=result.model,
            profile=route.profile,
            elapsed_ms=result.elapsed_ms,
            gateway_status="ok",
            fallback_reason=None,
            request_id=request.request_id,
            timeout_sec=route.timeout_seconds,
            prompt_chars=prompt_chars,
            response_chars=result.response_chars,
            llm_generation_ms=result.elapsed_ms,
            total_elapsed_ms=total_elapsed_ms,
        )


def _fallback_response(
    request: ToolPlannerRequest,
    *,
    provider: str,
    model: str,
    profile: str,
    timeout_sec: float | None,
    prompt_chars: int,
    started: float,
    reason: str,
    response_chars: int | None = None,
    llm_generation_ms: int | None = None,
) -> ToolPlannerResponse:
    elapsed = _elapsed_ms(started)
    return ToolPlannerResponse(
        plan_type="tool_plan",
        user_intent=request.user_question,
        overall_summary="LLM Planner案は採用せず、親アプリ側の安全な確認順に戻します。",
        steps=[],
        safety_note="この提案は確認手順の整理であり、売買推奨ではありません。",
        planner_source="fallback",
        provider=provider,
        model=model,
        profile=profile,  # type: ignore[arg-type]
        elapsed_ms=elapsed,
        gateway_status="fallback",
        fallback_reason=reason,
        request_id=request.request_id,
        timeout_sec=timeout_sec,
        prompt_chars=prompt_chars,
        response_chars=response_chars or 0,
        llm_generation_ms=llm_generation_ms or 0,
        total_elapsed_ms=elapsed,
    )


def _parse_llm_tool_plan(raw_answer: str) -> LlmToolPlannerPayload | None:
    text = _strip_thinking_blocks(raw_answer).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        return LlmToolPlannerPayload.model_validate(data)
    except ValidationError:
        return None


def _validate_payload(
    payload: LlmToolPlannerPayload | None,
    *,
    request: ToolPlannerRequest,
) -> list[str]:
    if payload is None:
        return ["payload is not valid JSON for tool planner"]
    errors: list[str] = []
    if len(payload.steps) > request.constraints.max_steps:
        errors.append(f"step count exceeds max_steps={request.constraints.max_steps}")
    text_blob = " ".join(
        [
            payload.user_intent,
            payload.overall_summary,
            payload.safety_note,
            *(step.title for step in payload.steps),
            *(step.summary for step in payload.steps),
            *(step.reason for step in payload.steps),
        ]
    ).lower()
    if any(term.lower() in text_blob for term in _BANNED_TERMS):
        errors.append("payload contains unsafe wording")

    actions = _enabled_action_map(request.available_actions)
    allowed_ids = set(request.constraints.allowed_action_ids) or set(actions)
    for step in payload.steps:
        if not step.action_id:
            continue
        action = actions.get(step.action_id)
        if action is None or step.action_id not in allowed_ids:
            errors.append(f"unknown action_id: {step.action_id}")
            continue
        if step.action_id in _UNSUPPORTED_LLM_ACTION_IDS:
            errors.append(f"unsupported planner action_id: {step.action_id}")
        if action.is_external_fetch and not step.requires_confirmation:
            errors.append(f"external fetch requires confirmation: {step.action_id}")
        if action.requires_confirmation and not step.requires_confirmation:
            errors.append(f"action requires confirmation: {step.action_id}")
    return errors


def _enabled_action_map(
    actions: Sequence[PlannerAvailableAction],
) -> dict[str, PlannerAvailableAction]:
    return {action.action_id: action for action in actions if action.enabled}


def _strip_thinking_blocks(value: str) -> str:
    return re.sub(r"<think>.*?</think>", "", value, flags=re.IGNORECASE | re.DOTALL)


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)
