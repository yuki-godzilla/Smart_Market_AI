from __future__ import annotations

from streamlit.testing.v1 import AppTest

from backend.assistant import AssistantMessage
from ui.views.copilot import (
    COPILOT_CHAT_HISTORY_STATE_KEY,
    _chat_header_html,
    copilot_answer_detail_html,
    copilot_context_label,
    copilot_context_options,
    copilot_history_messages,
    copilot_turn_html,
)


def test_copilot_context_options_cover_core_workflows():
    options = copilot_context_options()
    labels = [copilot_context_label(context) for context in options]

    assert "銘柄コックピット / 価格・予測・材料確認" in labels
    assert "銘柄ランキング / 候補比較" in labels
    assert "投資レーダー / ニュース材料確認" in labels
    assert "銘柄コックピット / AI材料分析" in labels
    assert "リバランス / 配分見直し" in labels
    assert all(context.suggested_questions for context in options)


def test_copilot_history_messages_keeps_recent_chat_pairs():
    turns = [{"question": f"質問{i}", "answer": f"回答{i}"} for i in range(1, 7)]

    messages = copilot_history_messages(turns, max_turns=2)

    assert messages == [
        AssistantMessage(role="user", content="質問5"),
        AssistantMessage(role="assistant", content="回答5"),
        AssistantMessage(role="user", content="質問6"),
        AssistantMessage(role="assistant", content="回答6"),
    ]


def test_copilot_answer_detail_html_escapes_detail_lists():
    markup = copilot_answer_detail_html(
        {
            "context_label": "銘柄<コックピット>",
            "question": "確認<script>",
            "answer": "回答<b>",
            "reasons": "材料 <1>",
            "cautions": "注意 <2>",
            "next_checkpoints": "次 <3>",
        }
    )

    assert "材料 &lt;1&gt;" in markup
    assert "注意 &lt;2&gt;" in markup
    assert "次 &lt;3&gt;" in markup
    assert "<script>" not in markup
    assert "smai-copilot-answer-grid" in markup


def test_copilot_turn_html_separates_user_and_smai_messages():
    markup = copilot_turn_html(
        {
            "context_label": "銘柄コックピット / 価格・予測",
            "question": "この銘柄の確認点は？",
            "answer": "価格と材料を分けて確認します。",
            "reasons": "価格トレンド",
            "cautions": "売買推奨ではありません",
            "next_checkpoints": "ニュースを見る",
        }
    )

    assert "smai-copilot-message-row--user" in markup
    assert "smai-copilot-message-row--assistant" in markup
    assert "あなたの確認" in markup
    assert "SMAIの整理" in markup
    assert "smai-copilot-assistant-avatar" in markup
    assert "smai-copilot-assistant-avatar-image--reply" in markup
    assert "data:image/webp;base64," in markup
    assert "この銘柄の確認点は？" in markup
    assert "価格と材料を分けて確認します。" in markup


def test_copilot_header_uses_smai_navi_chat_icon():
    markup = _chat_header_html(history_count=0)

    assert "smai-copilot-header-icon" in markup
    assert "data:image/png;base64," in markup
    assert "投資判断アシスタント" in markup


def test_copilot_page_renders_with_streamlit_app(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=20)
    app.session_state["sidemenu_page"] = "copilot"

    app.run()

    assert not app.exception
    page_text = "\n".join(
        str(element.value)
        for group in (
            app.caption,
            app.markdown,
        )
        for element in group
        if getattr(element, "value", None) is not None
    )
    button_labels = [str(getattr(element, "label", "")) for element in app.button]
    selectbox_labels = [str(getattr(element, "label", "")) for element in app.selectbox]
    chat_input_placeholders = [
        str(getattr(element, "placeholder", "")) for element in app.chat_input
    ]

    assert "SMAI Copilot" in page_text
    assert "投資判断アシスタント" in page_text
    assert "smai-copilot-chat-topbar" in page_text
    assert "SMAIアシスタント" in button_labels
    assert "分析モード" in selectbox_labels
    assert (
        "価格・予測・ニュース・根拠資料について確認したいことを入力..." in chat_input_placeholders
    )
    assert "新しい分析" in button_labels
    assert "この観点で聞く" in button_labels
    assert "現在の分析テーマ" in page_text


def test_copilot_page_chat_input_appends_chat_turn(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=20)
    app.session_state["sidemenu_page"] = "copilot"
    app.run()

    app.chat_input[0].set_value("確認点を整理して").run()

    assert not app.exception
    assert len(app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]) == 1
