from __future__ import annotations

from typing import Mapping

from pydantic import ValidationError

from backend.assistant import (
    AssistantGatewayClient,
    AssistantGatewayResponse,
    build_assistant_gateway_request,
)

from .radar_overview_models import (
    RADAR_OVERVIEW_INTERPRETATION_PROMPT_VERSION,
    RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION,
    RadarOverviewInterpretationContext,
)
from .radar_overview_validation import RadarOverviewInterpretationValidationError

RADAR_OVERVIEW_INTERPRETATION_QUESTION = (
    "intent: radar_overview_interpretation\n"
    "現在の投資レーダーについて、指定された根拠IDだけを使い、今日の見方、取得済み候補集合の"
    "値動き、セクター別確認、ニューステーマと関連候補、次に詳しく確認する候補、未確認事項を"
    "整理してください。本文言及・テーマ推測・市場背景を混同せず、市場全体へ一般化しないでください。"
    "候補順、価格、Ranking、Forecast、各Scoreを変更または再計算せず、売買推奨もしないでください。"
)


class RadarOverviewInterpretationGatewayAdapter:
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

    def generate(self, context: RadarOverviewInterpretationContext) -> AssistantGatewayResponse:
        request = build_assistant_gateway_request(
            question=RADAR_OVERVIEW_INTERPRETATION_QUESTION,
            context=context.bundle,
            task="explain",
            language="ja",
            active_context_id="radar_overview_interpretation",
            referenced_context_ids=context.allowed_evidence_ids,
            response_schema=RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION,
            task_type="radar_overview_interpretation",
            execution_mode=self.execution_mode,  # type: ignore[arg-type]
            environment_profile=self.environment_profile,  # type: ignore[arg-type]
            preferred_profile=self.preferred_profile,  # type: ignore[arg-type]
        )
        return _coerce_gateway_response(self.client.answer(request))


def radar_overview_interpretation_contract_metadata() -> dict[str, str]:
    return {
        "task_type": "radar_overview_interpretation",
        "prompt_version": RADAR_OVERVIEW_INTERPRETATION_PROMPT_VERSION,
        "schema_version": RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION,
        "response_schema": RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION,
    }


def _coerce_gateway_response(
    response: AssistantGatewayResponse | Mapping[str, object],
) -> AssistantGatewayResponse:
    if isinstance(response, AssistantGatewayResponse):
        return response
    try:
        return AssistantGatewayResponse.model_validate(response)
    except ValidationError as exc:
        raise RadarOverviewInterpretationValidationError("malformed_json") from exc
