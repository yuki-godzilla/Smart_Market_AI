from __future__ import annotations

from backend.assistant import (
    AssistantRequest,
    build_assistant_context_bundle,
    build_assistant_gateway_request,
)
from backend.reporting import build_decision_report_context, build_report_section


def test_parent_gateway_request_carries_task_type_without_model_choice():
    context = build_assistant_context_bundle(_report_context())

    request = build_assistant_gateway_request(
        question="AI予測とリスクを比較してください",
        context=context,
        task_type="forecast_risk_compare",
        execution_mode="auto",
        environment_profile="notebook",
    )

    assert request.task_type == "forecast_risk_compare"
    assert request.execution_mode == "auto"
    assert request.environment_profile == "notebook"
    assert "model" not in request.model_dump(mode="json")


def test_assistant_request_defaults_to_free_chat_task_type():
    request = AssistantRequest(question="こんにちは")

    assert request.gateway_task_type == "free_chat"


def _report_context():
    return build_decision_report_context(
        title="SMAI Assistant",
        sections=[
            build_report_section(
                title="AI予測インサイト",
                source_kind="cockpit",
                summary={"中心予測": "+1.2%"},
            )
        ],
    )
