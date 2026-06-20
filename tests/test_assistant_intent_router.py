from backend.assistant import detect_assistant_intent


def test_detect_assistant_intent_report_request():
    decision = detect_assistant_intent("トヨタをニュースも含めてレポートにして")

    assert decision.intent == "report_creation"
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

    assert decision.intent == "news_lookup"


def test_detect_assistant_intent_rag_request():
    decision = detect_assistant_intent("RAGで根拠を探して")

    assert decision.intent == "rag_search"


def test_detect_assistant_intent_identity_request():
    decision = detect_assistant_intent("あなたの名前は？")

    assert decision.intent == "self_introduction"


def test_detect_assistant_intent_capability_request():
    decision = detect_assistant_intent("何ができるの？")

    assert decision.intent == "capability_help"


def test_detect_assistant_intent_greeting_is_smalltalk():
    decision = detect_assistant_intent("こんにちは")

    assert decision.intent == "smalltalk"


def test_detect_assistant_intent_concept_explanation():
    decision = detect_assistant_intent("セクターの意味わかりますか？")

    assert decision.intent == "concept_explanation"


def test_detect_assistant_intent_broad_discovery():
    decision = detect_assistant_intent("今後上がりそうな銘柄やセクターについて教えてほしいな")

    assert decision.intent == "theme_or_sector_discovery"


def test_detect_assistant_intent_explicit_candidate_search():
    decision = detect_assistant_intent("半導体関連の候補銘柄をランキングで比較したい")

    assert decision.intent == "stock_candidate_search"
