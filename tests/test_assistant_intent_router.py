from backend.assistant import detect_assistant_intent


def test_detect_assistant_intent_report_request():
    decision = detect_assistant_intent("トヨタをニュースも含めてレポートにして")

    assert decision.intent == "decision_report_draft"
    assert decision.confidence in {"medium", "high"}


def test_detect_assistant_intent_file_export_request():
    decision = detect_assistant_intent("この内容をMarkdownで保存して")

    assert decision.intent == "file_export"


def test_detect_assistant_intent_chart_request():
    decision = detect_assistant_intent("株価チャートを見て")

    assert decision.intent == "chart_check"


def test_detect_assistant_intent_forecast_request():
    decision = detect_assistant_intent("AI予測を確認して")

    assert decision.intent == "forecast_check"


def test_detect_assistant_intent_news_request():
    decision = detect_assistant_intent("ニュースを調べて")

    assert decision.intent == "news_materials"


def test_detect_assistant_intent_rag_request():
    decision = detect_assistant_intent("RAGで根拠を探して")

    assert decision.intent == "rag_search"


def test_detect_assistant_intent_unknown_falls_back_to_free_chat():
    decision = detect_assistant_intent("こんにちは")

    assert decision.intent == "free_chat"
