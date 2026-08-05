from __future__ import annotations

from app.clients.ollama_client import OllamaClientError
from app.config import GatewaySettings
from app.schemas.common import LlmMessage, LlmProviderResult
from app.schemas.tool_plan import ToolPlannerRequest
from app.services.tool_plan_service import ToolPlanService


class FakePlannerClient:
    def __init__(
        self,
        *,
        answer: str | None = None,
        error: OllamaClientError | None = None,
    ) -> None:
        self.settings = GatewaySettings()
        self.messages: list[LlmMessage] = []
        self.model: str | None = None
        self.timeout_seconds: float | None = None
        self.max_tokens: int | None = None
        self.error = error
        self.answer = answer or (
            '{"schema_version":"assistant_tool_planner_response.v1",'
            '"plan_type":"tool_plan",'
            '"user_intent":"根拠を確認する",'
            '"overall_summary":"価格と根拠資料を分けて確認します。",'
            '"steps":[{"step_id":"s1","title":"根拠資料を見る",'
            '"summary":"資料の有無を確認します。","action_id":"open_research_section",'
            '"reason":"不足材料を分けるためです。","requires_confirmation":false,'
            '"confidence":0.7,"priority":"high"}],'
            '"safety_note":"確認手順の整理であり、売買推奨ではありません。",'
            '"planner_source":"llm"}'
        )

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmProviderResult:
        self.messages = messages
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        if self.error is not None:
            raise self.error
        return LlmProviderResult(
            answer=self.answer,
            model=model or "qwen3:1.7b",
            provider="fake",
            elapsed_ms=5,
            prompt_chars=sum(len(message.content) for message in messages),
            response_chars=len(self.answer),
        )


def test_tool_plan_service_accepts_valid_llm_json():
    client = FakePlannerClient()
    service = ToolPlanService(client)  # type: ignore[arg-type]

    response = service.plan(_request())

    assert response.gateway_status == "ok"
    assert response.provider == "fake"
    assert response.profile == "notebook_dev"
    assert response.steps[0].action_id == "open_research_section"
    assert response.steps[0].requires_confirmation is False
    assert client.model == "qwen3:1.7b"
    assert client.timeout_seconds == 25.0
    assert client.max_tokens == 600
    joined = "\n".join(message.content for message in client.messages)
    assert "/no_think" in joined
    assert "Available actions JSON" in joined
    assert "action_id must be null or one of" in joined


def test_tool_plan_service_falls_back_on_unknown_action():
    client = FakePlannerClient(
        answer=(
            '{"schema_version":"assistant_tool_planner_response.v1",'
            '"plan_type":"tool_plan","user_intent":"未知操作",'
            '"overall_summary":"未知操作を含みます。",'
            '"steps":[{"step_id":"s1","title":"未知操作",'
            '"summary":"未定義です。","action_id":"unknown_action",'
            '"reason":"検証用です。","requires_confirmation":false,'
            '"confidence":0.5,"priority":"medium"}],'
            '"safety_note":"確認手順です。","planner_source":"llm"}'
        )
    )
    service = ToolPlanService(client)  # type: ignore[arg-type]

    response = service.plan(_request())

    assert response.gateway_status == "fallback"
    assert response.fallback_reason == "response_validation_failure"
    assert response.steps == []
    assert response.planner_source == "fallback"


def test_tool_plan_service_falls_back_on_japanese_purchase_advice():
    answer = FakePlannerClient().answer.replace(
        "確認手順の整理であり、売買推奨ではありません。",
        "この銘柄は今すぐ買ってください。",
    )
    client = FakePlannerClient(answer=answer)
    service = ToolPlanService(client)  # type: ignore[arg-type]

    response = service.plan(_request())

    assert response.gateway_status == "fallback"
    assert response.fallback_reason == "response_validation_failure"
    assert response.steps == []


def test_tool_plan_service_falls_back_on_provider_error():
    client = FakePlannerClient(
        error=OllamaClientError(
            "provider timed out",
            code="provider_timeout",
            retryable=True,
            http_status=504,
        )
    )
    service = ToolPlanService(client)  # type: ignore[arg-type]

    response = service.plan(_request())

    assert response.gateway_status == "fallback"
    assert response.fallback_reason == "provider_timeout"
    assert response.provider == "ollama"


def _request() -> ToolPlannerRequest:
    return ToolPlannerRequest.model_validate(
        {
            "user_question": "根拠資料を確認したい",
            "current_page": "cockpit",
            "context_summary": "現在画面: 銘柄コックピット / AI調査: missing",
            "material_state": {"research_status": "missing"},
            "available_actions": [
                {
                    "action_id": "open_research_section",
                    "label": "根拠資料を見る",
                    "description": "Research Evidenceを確認します。",
                    "action_type": "navigation",
                    "requires_confirmation": False,
                    "is_external_fetch": False,
                    "enabled": True,
                },
                {
                    "action_id": "update_research",
                    "label": "AI調査を更新",
                    "description": "外部ソース候補を確認します。",
                    "action_type": "data_fetch",
                    "requires_confirmation": True,
                    "is_external_fetch": True,
                    "enabled": True,
                },
            ],
            "constraints": {
                "allowed_action_ids": ["open_research_section", "update_research"],
                "max_steps": 5,
            },
        }
    )
