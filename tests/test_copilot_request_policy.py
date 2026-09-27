from ui.copilot_request_policy import news_update_guidance, route_news_safe_conversation


def test_news_update_guidance_separates_questions_negation_and_compound_requests():
    question = news_update_guidance("ニュースは更新できますか？")
    negation = news_update_guidance("ニュースを更新してほしくない")
    compound = news_update_guidance("ニュースを更新して、ランキングも作り直して")
    quoted = news_update_guidance("「ニュースを更新して」と入力したらどうなる？")

    assert question is not None and "実行前に内容を確認" in question
    assert negation is not None and "更新しません" in negation
    assert compound is not None and "まとめて実行しません" in compound
    assert quoted is not None and "実行前に内容を確認" in quoted
    assert "まとめて実行しません" in news_update_guidance("ニュースを更新して、レーダーを開いて")
    assert "実行していません" in news_update_guidance("ニュース更新の状態を確認したい")
    assert news_update_guidance("ニュースを更新して") is None
    assert news_update_guidance("トヨタのニュースを見たい") is None
    assert (
        route_news_safe_conversation("ニュースを更新して、レーダーを開いて").conversation_mode
        == "normal_chat"
    )
