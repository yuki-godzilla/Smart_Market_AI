from backend.assistant import route_assistant_conversation_mode


def test_conversation_mode_keeps_greeting_as_normal_chat():
    decision = route_assistant_conversation_mode("こんにちは")

    assert decision.conversation_mode == "normal_chat"
    assert not decision.tool_plan_enabled
    assert not decision.requires_approval


def test_conversation_mode_keeps_app_help_as_normal_chat():
    decision = route_assistant_conversation_mode("SMAIの使い方を教えて")

    assert decision.conversation_mode == "normal_chat"
    assert decision.intent == "none"


def test_conversation_mode_keeps_term_explanation_as_normal_chat():
    decision = route_assistant_conversation_mode("AI予測と下振れ警戒の違いは？")

    assert decision.conversation_mode == "normal_chat"
    assert not decision.requires_research


def test_conversation_mode_ambiguous_symbol_question_is_soft_suggestion():
    decision = route_assistant_conversation_mode("トヨタってどう？")

    assert decision.conversation_mode == "soft_research_suggestion"
    assert decision.intent == "stock_forward_view"
    assert decision.symbol_query == "トヨタ"
    assert not decision.tool_plan_enabled
    assert not decision.requires_approval


def test_conversation_mode_clear_forward_view_gets_research_plan():
    decision = route_assistant_conversation_mode("トヨタはこれから上がるかな？")

    assert decision.conversation_mode == "research_plan"
    assert decision.intent == "stock_forward_view"
    assert decision.symbol_query == "トヨタ"
    assert decision.tool_plan_enabled
    assert decision.requires_approval


def test_conversation_mode_news_request_gets_research_plan():
    decision = route_assistant_conversation_mode("最新ニュースで投資判断に影響しそうなものを教えて")

    assert decision.conversation_mode == "research_plan"
    assert decision.intent == "news_research"
    assert decision.requires_approval


def test_conversation_mode_theme_discovery_gets_research_plan():
    decision = route_assistant_conversation_mode("半導体の分野で安定しているのはどれ？")

    assert decision.conversation_mode == "research_plan"
    assert decision.intent == "theme_stock_discovery"
    assert decision.symbol_query == "半導体"
