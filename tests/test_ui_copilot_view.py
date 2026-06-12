from __future__ import annotations

from streamlit.testing.v1 import AppTest

from backend.assistant import AssistantMessage
from ui.views.copilot import (
    COPILOT_CHAT_HISTORY_STATE_KEY,
    copilot_context_label,
    copilot_context_options,
    copilot_history_messages,
    copilot_turn_html,
    copilot_welcome_html,
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


def test_copilot_turn_html_escapes_question_and_answer():
    markup = copilot_turn_html(
        {
            "context_label": "銘柄<コックピット>",
            "question": "確認 <script>",
            "answer": "回答 <b>",
            "reasons": "材料 <1>",
            "cautions": "注意 <2>",
            "next_checkpoints": "次 <3>",
        }
    )

    assert "銘柄&lt;コックピット&gt;" in markup
    assert "確認 &lt;script&gt;" in markup
    assert "回答 &lt;b&gt;" in markup
    assert "材料 &lt;1&gt;" in markup
    assert "注意 &lt;2&gt;" in markup
    assert "次 &lt;3&gt;" in markup
    assert "<script>" not in markup
    assert "smai-copilot-bubble-row--user" in markup
    assert "smai-copilot-bubble-row--assistant" in markup


def test_copilot_welcome_html_uses_chat_bubble_markup():
    context = copilot_context_options()[0]

    markup = copilot_welcome_html(context)

    assert "smai-copilot-turn--welcome" in markup
    assert "smai-copilot-avatar" in markup
    assert copilot_context_label(context) in markup
    assert "質問例" in markup


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
    text_area_labels = [str(getattr(element, "label", "")) for element in app.text_area]

    assert "SMAI Copilot" in page_text
    assert "smai-copilot-chat-topbar" in page_text
    assert "文脈" in selectbox_labels
    assert "クイック質問" in selectbox_labels
    assert "メッセージ" in text_area_labels
    assert {"送信", "クリア"}.issubset(set(button_labels))


def test_copilot_page_send_button_appends_chat_turn(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=20)
    app.session_state["sidemenu_page"] = "copilot"
    app.run()

    app.text_area[0].set_value("確認点を整理して")
    app.button[0].click().run()

    assert not app.exception
    assert len(app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]) == 1
