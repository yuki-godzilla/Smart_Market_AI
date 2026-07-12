from __future__ import annotations

from backend.assistant.response_sanitizer import (
    contains_investment_advice,
    sanitize_presentation_items,
    sanitize_presentation_text,
)


def test_sanitize_presentation_text_removes_internal_sentences():
    text = (
        "SMAIナビでは銘柄の見方を整理できます。 "
        "Provider raw fields were excluded from the bundle. "
        "気になる銘柄名を入れて聞いてください。"
    )

    sanitized = sanitize_presentation_text(text)

    assert "SMAIナビでは銘柄の見方を整理できます。" in sanitized
    assert "Provider raw fields" not in sanitized
    assert "気になる銘柄名を入れて聞いてください。" in sanitized


def test_sanitize_presentation_items_drops_debug_and_recompute_notes():
    sanitized = sanitize_presentation_items(
        [
            "ニュース材料を確認してください。",
            "debug logs are omitted.",
            "score or ranking recomputation is not performed.",
            "AI予測だけで判断しないでください。",
        ]
    )

    assert sanitized == [
        "ニュース材料を確認してください。",
        "AI予測だけで判断しないでください。",
    ]


def test_investment_advice_detector_distinguishes_prescription_from_boundary_copy():
    assert contains_investment_advice("価格変動リスクが高いため、購入は慎重に検討してください。")
    assert contains_investment_advice("今は買い時です。")
    assert contains_investment_advice("この株を買った方がいいです。")
    assert contains_investment_advice("保有を続けるのがおすすめです。")
    assert contains_investment_advice("This is a strong buy recommendation.")
    assert contains_investment_advice("You should buy this stock.")
    assert contains_investment_advice("We recommend holding the stock.")
    assert not contains_investment_advice("買うべきかどうかは、画面の材料だけでは判断できません。")
    assert not contains_investment_advice(
        "今が買い時かどうかは、画面の材料だけでは判断できません。"
    )
    assert not contains_investment_advice("投資目的（保有・売却）を明確にしてください。")
