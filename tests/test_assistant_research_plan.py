from backend.assistant import (
    build_assistant_research_tool_plan,
    route_assistant_conversation_mode,
)


def test_research_tool_plan_is_not_built_for_normal_chat():
    decision = route_assistant_conversation_mode("ありがとう")

    assert build_assistant_research_tool_plan("ありがとう", decision) is None


def test_research_tool_plan_is_not_built_for_soft_suggestion():
    decision = route_assistant_conversation_mode("トヨタってどう？")

    assert build_assistant_research_tool_plan("トヨタってどう？", decision) is None


def test_stock_forward_view_tool_plan_requires_approval_before_external_fetch():
    decision = route_assistant_conversation_mode("トヨタはこれから上がるかな？")
    plan = build_assistant_research_tool_plan("トヨタはこれから上がるかな？", decision)

    assert plan is not None
    assert plan.intent == "stock_forward_view"
    assert plan.symbol_query == "トヨタ"
    assert plan.symbol == "7203.T"
    assert plan.requires_approval
    assert plan.has_external_tools
    assert [tool.name for tool in plan.tools] == [
        "symbol_resolve",
        "price_fetch",
        "forecast_fetch",
        "news_fetch",
        "research_fetch",
    ]
    assert any(tool.external for tool in plan.tools)
    assert any(not tool.external for tool in plan.tools)


def test_news_research_tool_plan_focuses_on_news_and_research():
    plan = build_assistant_research_tool_plan("最新ニュースで投資判断に影響しそうなものを教えて")

    assert plan is not None
    assert plan.intent == "news_research"
    assert [tool.name for tool in plan.tools] == [
        "news_fetch",
        "research_fetch",
        "symbol_resolve",
    ]
    assert plan.tools[0].external
    assert plan.requires_approval


def test_decision_report_tool_plan_does_not_require_external_tool():
    plan = build_assistant_research_tool_plan("この内容をDecision Reportにして")

    assert plan is not None
    assert plan.intent == "decision_report_request"
    assert [tool.name for tool in plan.tools] == ["decision_report_draft"]
    assert not plan.has_external_tools
    assert "下書き" in plan.approval_reason
