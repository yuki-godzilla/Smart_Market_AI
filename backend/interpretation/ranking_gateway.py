from __future__ import annotations

from typing import Mapping

from pydantic import ValidationError

from backend.assistant import (
    AssistantGatewayClient,
    AssistantGatewayResponse,
    build_assistant_gateway_request,
)

from .ranking_models import (
    RANKING_INTERPRETATION_PROMPT_VERSION,
    RANKING_INTERPRETATION_SCHEMA_VERSION,
    RankingInterpretationContext,
)
from .ranking_validation import RankingInterpretationValidationError

RANKING_INTERPRETATION_QUESTION = (
    "intent: ranking_interpretation\n"
    "現在のRanking結果について、指定された根拠IDだけを使い、共通する強み・注意点、"
    "効いている指標、今回の候補集合内のセクター傾向、上位候補ごとの読み方と次の確認事項を"
    "整理してください。順位・スコア・Forecastを変更または再計算せず、売買推奨もしないでください。"
)


class RankingInterpretationGatewayAdapter:
    def __init__(
        self,
        client: AssistantGatewayClient,
        *,
        execution_mode: str = "auto",
        environment_profile: str = "desktop",
        preferred_profile: str | None = None,
    ) -> None:
        self.client = client
        self.execution_mode = execution_mode
        self.environment_profile = environment_profile
        self.preferred_profile = preferred_profile

    def generate(self, context: RankingInterpretationContext) -> AssistantGatewayResponse:
        request = build_assistant_gateway_request(
            question=RANKING_INTERPRETATION_QUESTION,
            context=context.bundle,
            task="explain",
            language="ja",
            active_context_id="ranking_interpretation",
            referenced_context_ids=context.allowed_evidence_ids[:8],
            response_schema=RANKING_INTERPRETATION_SCHEMA_VERSION,
            task_type="ranking_interpretation",
            execution_mode=self.execution_mode,  # type: ignore[arg-type]
            environment_profile=self.environment_profile,  # type: ignore[arg-type]
            preferred_profile=self.preferred_profile,  # type: ignore[arg-type]
        )
        return _coerce_gateway_response(self.client.answer(request))


def ranking_interpretation_contract_metadata() -> dict[str, str]:
    return {
        "task_type": "ranking_interpretation",
        "prompt_version": RANKING_INTERPRETATION_PROMPT_VERSION,
        "schema_version": RANKING_INTERPRETATION_SCHEMA_VERSION,
        "response_schema": RANKING_INTERPRETATION_SCHEMA_VERSION,
    }


def _coerce_gateway_response(
    response: AssistantGatewayResponse | Mapping[str, object],
) -> AssistantGatewayResponse:
    if isinstance(response, AssistantGatewayResponse):
        return response
    try:
        return AssistantGatewayResponse.model_validate(response)
    except ValidationError as exc:
        raise RankingInterpretationValidationError("malformed_json") from exc
