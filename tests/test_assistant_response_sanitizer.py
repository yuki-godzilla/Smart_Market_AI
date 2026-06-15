from __future__ import annotations

from backend.assistant.response_sanitizer import (
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
