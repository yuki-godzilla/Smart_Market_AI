from __future__ import annotations

import json

import httpx

from backend.assistant import (
    AssistantPlannerResponse,
    HttpAssistantGatewayClient,
    MockAssistantGatewayClient,
    build_assistant_context,
    build_assistant_planner_request,
    build_assistant_planner_states,
)


def test_planner_request_redacts_raw_material_state_and_lists_actions():
    context = build_assistant_context(
        current_page="cockpit",
        user_question="トヨタの根拠を確認したい",
        page_state={"active_symbol": "7203.T"},
        material_state={
            "research_status": "missing",
            "provider_raw_payload": '{"debug": true}',
            "forecast_status": "available",
        },
    )

    request = build_assistant_planner_request(context)

    assert request.task_type == "assistant_tool_plan"
    assert request.schema_version == "assistant_tool_planner_request.v1"
    assert request.prompt_version == "assistant_tool_planner_mvp.v1"
    assert request.current_page == "cockpit"
    assert "provider_raw_payload" not in request.material_state
    assert request.material_state["forecast_status"] == "available"
    assert "update_research" in {action.action_id for action in request.available_actions}
    assert "update_research" in request.constraints.allowed_action_ids


def test_valid_llm_tool_plan_is_adopted_after_validation():
    context = _context()
    response = AssistantPlannerResponse(
        plan_type="tool_plan",
        user_intent="根拠資料を確認する",
        overall_summary="価格と根拠資料を分けて確認します。",
        steps=[
            {
                "step_id": "step_open_research",
                "title": "根拠資料を見る",
                "summary": "取得済み資料と不足材料を確認します。",
                "action_id": "open_research_section",
                "reason": "資料の有無を先に分けるためです。",
                "requires_confirmation": False,
                "confidence": 0.72,
                "priority": "high",
            },
            {
                "step_id": "step_update_research",
                "title": "AI調査を更新",
                "summary": "必要なら最新の開示やニュース候補を確認します。",
                "action_id": "update_research",
                "reason": "根拠資料が不足しているためです。",
                "requires_confirmation": True,
                "confidence": 0.68,
                "priority": "medium",
            },
        ],
        provider="mock",
        model="mock-planner",
        profile="assistant_fast",
        gateway_status="ok",
    )
    client = MockAssistantGatewayClient(planner_response=response)

    states = build_assistant_planner_states(context, client=client, enabled=True)

    assert states.tool_plan.generated_by == "llm"
    assert states.tool_plan.provider == "mock"
    assert states.tool_plan.steps[0].action_id == "open_research_section"
    assert states.tool_plan.steps[0].requires_confirmation is False
    assert states.tool_plan.steps[1].action_id == "update_research"
    assert states.tool_plan.steps[1].requires_confirmation is True
    assert states.metadata.planner_source == "llm"
    assert states.metadata.used_plan_type == "tool_plan"
    assert len(client.planner_requests) == 1


def test_unknown_planner_action_falls_back_to_deterministic_plan():
    context = _context()
    client = MockAssistantGatewayClient(
        planner_response={
            "plan_type": "tool_plan",
            "user_intent": "未知操作を試す",
            "overall_summary": "未知操作を含みます。",
            "steps": [
                {
                    "step_id": "s1",
                    "title": "未知操作",
                    "summary": "未定義の操作です。",
                    "action_id": "unknown_action",
                    "reason": "検証用です。",
                    "requires_confirmation": False,
                    "confidence": 0.5,
                    "priority": "medium",
                }
            ],
            "safety_note": "確認手順の整理です。",
            "planner_source": "llm",
            "provider": "mock",
            "model": "mock-planner",
            "profile": "assistant_fast",
            "elapsed_ms": 1,
            "gateway_status": "ok",
        }
    )

    states = build_assistant_planner_states(context, client=client, enabled=True)

    assert states.metadata.planner_source == "fallback"
    assert states.metadata.fallback_reason == "planner_validation_failure"
    assert "unknown_action" in " ".join(states.metadata.errors)
    assert states.tool_plan.generated_by == "deterministic"


def test_external_fetch_without_confirmation_falls_back():
    context = _context()
    client = MockAssistantGatewayClient(
        planner_response=_planner_payload(
            action_id="update_research",
            requires_confirmation=False,
        )
    )

    states = build_assistant_planner_states(context, client=client, enabled=True)

    assert states.metadata.planner_source == "fallback"
    assert states.metadata.fallback_reason == "planner_validation_failure"
    assert "requires confirmation" in " ".join(states.metadata.errors)


def test_unsafe_planner_wording_falls_back():
    context = _context()
    client = MockAssistantGatewayClient(
        planner_response=_planner_payload(
            overall_summary="買うべき候補を確実に利益が出る順で整理します。",
            action_id="open_research_section",
            requires_confirmation=False,
        )
    )

    states = build_assistant_planner_states(context, client=client, enabled=True)

    assert states.metadata.planner_source == "fallback"
    assert states.metadata.fallback_reason == "planner_tool_plan_validation_failure"
    assert "investment-advice-like" in " ".join(states.metadata.errors)


def test_http_gateway_client_posts_tool_plan_request():
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        payload = json.loads(request.read().decode("utf-8"))
        observed["payload"] = payload
        return httpx.Response(
            200,
            json={
                "schema_version": "assistant_tool_planner_response.v1",
                "plan_type": "tool_plan",
                "user_intent": "確認順",
                "overall_summary": "安全な確認順です。",
                "steps": [],
                "safety_note": "確認手順の整理です。",
                "planner_source": "llm",
                "provider": "fake",
                "model": "qwen3:1.7b",
                "profile": "assistant_fast",
                "elapsed_ms": 3,
                "gateway_status": "ok",
                "request_id": payload["request_id"],
            },
            request=request,
        )

    context = _context()
    gateway_client = HttpAssistantGatewayClient(
        base_url="http://gateway.local",
        tool_plan_path="/api/v1/assistant/tool-plan",
        timeout_seconds=2.0,
        model="qwen3:1.7b",
        preferred_profile="assistant_fast",
        transport=httpx.MockTransport(handler),
    )

    response = gateway_client.tool_plan(build_assistant_planner_request(context))

    assert observed["url"] == "http://gateway.local/api/v1/assistant/tool-plan"
    assert response.provider == "fake"
    payload = observed["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "qwen3:1.7b"
    assert payload["preferred_profile"] == "assistant_fast"


def _planner_payload(
    *,
    action_id: str,
    requires_confirmation: bool,
    overall_summary: str = "確認順を整理します。",
) -> dict[str, object]:
    return {
        "plan_type": "tool_plan",
        "user_intent": "確認する",
        "overall_summary": overall_summary,
        "steps": [
            {
                "step_id": "s1",
                "title": "確認する",
                "summary": "材料を確認します。",
                "action_id": action_id,
                "reason": "検証用です。",
                "requires_confirmation": requires_confirmation,
                "confidence": 0.5,
                "priority": "medium",
            }
        ],
        "safety_note": "確認手順の整理です。",
        "planner_source": "llm",
        "provider": "mock",
        "model": "mock-planner",
        "profile": "assistant_fast",
        "elapsed_ms": 1,
        "gateway_status": "ok",
    }


def _context():
    return build_assistant_context(
        current_page="cockpit",
        user_question="この銘柄の根拠を確認したい",
        page_state={"active_symbol": "7203.T"},
        material_state={
            "price_data_status": "available",
            "forecast_status": "available",
            "research_status": "missing",
        },
    )
