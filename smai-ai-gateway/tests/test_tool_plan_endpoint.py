from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_module
from app.config import GatewaySettings
from app.main import app
from app.schemas.common import LlmMessage, LlmProviderResult


class FakePlannerOllamaClient:
    def __init__(self, settings: GatewaySettings) -> None:
        self.settings = settings

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmProviderResult:
        answer = (
            '{"schema_version":"assistant_tool_planner_response.v1",'
            '"plan_type":"tool_plan","user_intent":"確認する",'
            '"overall_summary":"確認順を整理します。",'
            '"steps":[{"step_id":"s1","title":"画面を見る",'
            '"summary":"現在画面を確認します。","action_id":"explain_current_page",'
            '"reason":"最初の確認点です。","requires_confirmation":false,'
            '"confidence":0.8,"priority":"medium"}],'
            '"safety_note":"確認手順の整理です。","planner_source":"llm"}'
        )
        return LlmProviderResult(
            answer=answer,
            model=model or "qwen3:1.7b",
            provider="fake",
            elapsed_ms=4,
            prompt_chars=sum(len(message.content) for message in messages),
            response_chars=len(answer),
        )


def test_assistant_tool_plan_endpoint(monkeypatch):
    monkeypatch.setattr(main_module, "OllamaClient", FakePlannerOllamaClient)
    client = TestClient(app)

    response = client.post(
        "/api/v1/assistant/tool-plan",
        json={
            "user_question": "次に何を見る？",
            "current_page": "assistant",
            "context_summary": "現在画面: SMAIアシスタント",
            "available_actions": [
                {
                    "action_id": "explain_current_page",
                    "label": "この画面の見方",
                    "description": "現在画面の見方を整理します。",
                    "action_type": "explain",
                    "requires_confirmation": False,
                    "is_external_fetch": False,
                    "enabled": True,
                }
            ],
            "constraints": {
                "allowed_action_ids": ["explain_current_page"],
                "max_steps": 5,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "assistant_tool_planner_response.v1"
    assert payload["gateway_status"] == "ok"
    assert payload["provider"] == "fake"
    assert payload["steps"][0]["action_id"] == "explain_current_page"
