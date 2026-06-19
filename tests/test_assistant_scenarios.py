from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.assistant import (
    build_assistant_research_tool_plan,
    detect_assistant_intent,
    route_assistant_conversation_mode,
)

SCENARIOS = json.loads(Path("tests/fixtures/assistant_scenarios.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: item["id"])
def test_assistant_scenario_routing(scenario: dict[str, object]):
    message = str(scenario["input"])
    intent = detect_assistant_intent(message)
    decision = route_assistant_conversation_mode(message)

    assert intent.intent == scenario["legacy_intent"]
    assert decision.conversation_mode == scenario["conversation_mode"]
    if decision.conversation_mode == "research_plan":
        plan = build_assistant_research_tool_plan(message, decision)
        assert plan is not None
        if scenario.get("symbol"):
            assert plan.symbol == scenario["symbol"]
    else:
        assert build_assistant_research_tool_plan(message, decision) is None
