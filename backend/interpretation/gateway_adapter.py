from __future__ import annotations

from typing import Mapping

from pydantic import ValidationError

from backend.assistant import (
    AssistantGatewayClient,
    AssistantGatewayResponse,
    build_assistant_gateway_request,
)

from .models import (
    COCKPIT_INTERPRETATION_PROMPT_VERSION,
    COCKPIT_INTERPRETATION_SCHEMA_VERSION,
    CockpitInterpretationContext,
)

COCKPIT_INTERPRETATION_QUESTION = (
    "intent: cockpit_interpretation\n"
    "この銘柄コックピットの価格、予測、Investment Score、Research Evidence、AI材料分析を、"
    "投資判断前にどう読めばよいか整理してください。売買推奨はせず、"
    "スコアや予測値も変更しないでください。"
)


class CockpitInterpretationGatewayAdapter:
    def __init__(
        self,
        client: AssistantGatewayClient,
        *,
        execution_mode: str = "auto",
        environment_profile: str = "notebook",
        preferred_profile: str | None = None,
    ) -> None:
        self.client = client
        self.execution_mode = execution_mode
        self.environment_profile = environment_profile
        self.preferred_profile = preferred_profile

    def generate(self, context: CockpitInterpretationContext) -> AssistantGatewayResponse:
        request = build_assistant_gateway_request(
            question=COCKPIT_INTERPRETATION_QUESTION,
            context=context.bundle,
            task="explain",
            language="ja",
            active_context_id="cockpit_interpretation",
            referenced_context_ids=context.allowed_evidence_ids[:8],
            task_type="cockpit_interpretation",  # type: ignore[arg-type]
            execution_mode=self.execution_mode,  # type: ignore[arg-type]
            environment_profile=self.environment_profile,  # type: ignore[arg-type]
            preferred_profile=self.preferred_profile,  # type: ignore[arg-type]
        )
        raw_response = self.client.answer(request)
        return _coerce_gateway_response(raw_response)


def _coerce_gateway_response(
    response: AssistantGatewayResponse | Mapping[str, object],
) -> AssistantGatewayResponse:
    if isinstance(response, AssistantGatewayResponse):
        return response
    try:
        return AssistantGatewayResponse.model_validate(response)
    except ValidationError as exc:
        raise ValueError("cockpit_interpretation_gateway_response_invalid") from exc


def cockpit_interpretation_contract_metadata() -> dict[str, str]:
    return {
        "task_type": "cockpit_interpretation",
        "prompt_version": COCKPIT_INTERPRETATION_PROMPT_VERSION,
        "schema_version": COCKPIT_INTERPRETATION_SCHEMA_VERSION,
    }
