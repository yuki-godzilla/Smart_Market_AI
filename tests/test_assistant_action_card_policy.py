from backend.assistant import decide_assistant_action_cards, detect_assistant_intent


def _decision(message: str):
    intent = detect_assistant_intent(message).intent
    return decide_assistant_action_cards(message, intent)


def test_smalltalk_and_concept_explanation_have_no_action_cards():
    assert _decision("こんにちは").level == 0
    assert _decision("セクターって何？").level == 0


def test_broad_discovery_uses_light_suggestion_only():
    decision = _decision("今後上がりそうな銘柄やセクターについて教えてほしいな")

    assert decision.level == 1
    assert not decision.show_cards


def test_explicit_navigation_and_report_requests_show_cards():
    assert _decision("半導体関連の候補銘柄をランキングで比較したい").level == 2
    assert _decision("トヨタをコックピットで詳しく見たい").level == 2
    assert _decision("この材料で確認レポートを作って").level == 2
