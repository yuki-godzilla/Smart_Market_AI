from backend.assistant import AssistantResponse
from ui.copilot_runtime import (
    AssistantStatusEvent,
    CopilotGatewayRuntimeConfig,
    derive_assistant_runtime_status,
)
from ui.views.copilot import (
    AssistantStatusEvent as LegacyAssistantStatusEvent,
)
from ui.views.copilot import (
    CopilotGatewayRuntimeConfig as LegacyCopilotGatewayRuntimeConfig,
)
from ui.views.copilot import (
    derive_assistant_runtime_status as legacy_derive_assistant_runtime_status,
)


def _runtime() -> CopilotGatewayRuntimeConfig:
    return CopilotGatewayRuntimeConfig(
        enabled=True,
        base_url="http://127.0.0.1:8088",
        timeout_seconds=30.0,
        context_answer_path="/api/v1/context-answer",
        execution_mode="auto",
        environment_profile="notebook",
        readiness_status="ready",
    )


def test_copilot_view_keeps_runtime_contract_compatibility() -> None:
    assert LegacyAssistantStatusEvent is AssistantStatusEvent
    assert LegacyCopilotGatewayRuntimeConfig is CopilotGatewayRuntimeConfig
    assert legacy_derive_assistant_runtime_status is derive_assistant_runtime_status


def test_runtime_transition_remains_deterministic() -> None:
    response = AssistantResponse(intent="overview", answer="確認しました。", gateway_status="ok")
    status = derive_assistant_runtime_status(
        AssistantStatusEvent(
            name="response_completed", runtime_config=_runtime(), response=response
        )
    )

    assert status.state == "ready"
    assert status.severity == "ready"
