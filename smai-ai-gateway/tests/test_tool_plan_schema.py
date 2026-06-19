from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.tool_plan import ToolPlannerRequest, ToolPlannerResponse


def test_tool_planner_request_accepts_available_actions():
    request = ToolPlannerRequest.model_validate(
        {
            "user_question": "確認順を教えて",
            "current_page": "cockpit",
            "context_summary": "現在画面: 銘柄コックピット",
            "available_actions": [
                {
                    "action_id": "open_cockpit",
                    "label": "銘柄コックピットを開く",
                    "description": "価格や予測を確認します。",
                    "action_type": "navigation",
                    "requires_confirmation": False,
                    "is_external_fetch": False,
                    "enabled": True,
                }
            ],
        }
    )

    assert request.schema_version == "assistant_tool_planner_request.v1"
    assert request.task_type == "assistant_tool_plan"
    assert request.available_actions[0].action_id == "open_cockpit"


def test_tool_planner_response_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        ToolPlannerResponse.model_validate(
            {
                "plan_type": "tool_plan",
                "user_intent": "確認する",
                "overall_summary": "確認順です。",
                "steps": [
                    {
                        "step_id": "s1",
                        "title": "確認",
                        "summary": "確認します。",
                        "action_id": "open_cockpit",
                        "reason": "検証用です。",
                        "requires_confirmation": False,
                        "confidence": 1.5,
                        "priority": "medium",
                    }
                ],
                "safety_note": "確認手順です。",
                "planner_source": "llm",
                "provider": "fake",
                "model": "qwen3:1.7b",
                "profile": "assistant_fast",
                "elapsed_ms": 1,
                "gateway_status": "ok",
            }
        )
