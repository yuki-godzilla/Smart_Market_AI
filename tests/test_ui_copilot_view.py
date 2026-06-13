from __future__ import annotations

from streamlit.testing.v1 import AppTest

from backend.assistant import AssistantMessage
from backend.core.config import Settings
from ui.views.copilot import (
    COPILOT_CHAT_HISTORY_STATE_KEY,
    CopilotGatewayRuntimeConfig,
    _chat_header_html,
    copilot_answer_detail_html,
    copilot_context_label,
    copilot_context_options,
    copilot_conversation_presets,
    copilot_history_messages,
    copilot_settings_from_gateway_runtime,
    copilot_turn_html,
    copilot_turn_markdown,
)


def test_copilot_context_options_cover_core_workflows():
    options = copilot_context_options()
    labels = [copilot_context_label(context) for context in options]

    assert "SMAIアシスタント / SMAIの使い方" in labels
    assert "銘柄コックピット / 価格・予測・材料確認" in labels
    assert "銘柄ランキング / 候補比較" in labels
    assert "投資レーダー / ニュース材料確認" in labels
    assert "銘柄コックピット / AI材料分析" in labels
    assert "リバランス / 配分見直し" in labels
    assert all(context.suggested_questions for context in options)


def test_copilot_conversation_presets_define_six_entry_intents():
    presets = copilot_conversation_presets()

    assert [preset.intent for preset in presets] == [
        "app_help",
        "stock_summary",
        "forecast_risk_compare",
        "news_materials",
        "decision_report_draft",
        "free_chat",
    ]
    assert [preset.label for preset in presets] == [
        "SMAIの使い方を聞きたい",
        "この銘柄を整理したい",
        "予測とリスクを比べたい",
        "ニュース材料を見たい",
        "Decision Reportを作りたい",
        "自由に会話する",
    ]


def test_copilot_history_messages_keeps_recent_chat_pairs():
    turns = [{"question": f"質問{i}", "answer": f"回答{i}"} for i in range(1, 7)]

    messages = copilot_history_messages(turns, max_turns=2)

    assert messages == [
        AssistantMessage(role="user", content="質問5"),
        AssistantMessage(role="assistant", content="回答5"),
        AssistantMessage(role="user", content="質問6"),
        AssistantMessage(role="assistant", content="回答6"),
    ]


def test_copilot_settings_from_gateway_runtime_enables_session_gateway():
    base_settings = Settings()
    runtime_config = CopilotGatewayRuntimeConfig(
        enabled=True,
        base_url="http://gateway.local",
        model="qwen3:8b",
        timeout_seconds=5.0,
        context_answer_path="/api/v1/context-answer",
    )

    settings = copilot_settings_from_gateway_runtime(runtime_config, base_settings)

    assert settings.assistant.gateway.enabled
    assert settings.assistant.gateway.base_url == "http://gateway.local"
    assert settings.assistant.gateway.model == "qwen3:8b"
    assert settings.assistant.gateway.timeout_seconds == 5.0
    assert not base_settings.assistant.gateway.enabled


def test_copilot_answer_detail_html_escapes_detail_lists():
    markup = copilot_answer_detail_html(
        {
            "context_label": "銘柄<コックピット>",
            "question": "確認<script>",
            "answer": "回答<b>",
            "intent": "forecast_risk_compare",
            "reasons": "材料 <1>",
            "cautions": "注意 <2>",
            "next_checkpoints": "次 <3>",
            "memo_points": "温度差 <4>",
        }
    )

    assert "材料 &lt;1&gt;" in markup
    assert "注意 &lt;2&gt;" in markup
    assert "次 &lt;3&gt;" in markup
    assert "温度差 &lt;4&gt;" in markup
    assert "予測側の見方" in markup
    assert "リスク側の見方" in markup
    assert "<script>" not in markup
    assert "smai-copilot-answer-grid" in markup


def test_copilot_turn_html_separates_user_and_smai_messages():
    markup = copilot_turn_html(
        {
            "context_label": "銘柄コックピット / 価格・予測",
            "question": "この銘柄の確認点は？",
            "answer": "価格と材料を分けて確認します。",
            "intent": "stock_summary",
            "reasons": "価格トレンド",
            "cautions": "売買推奨ではありません",
            "next_checkpoints": "ニュースを見る",
        }
    )

    assert "smai-copilot-message-row--user" in markup
    assert "smai-copilot-message-row--assistant" in markup
    assert "あなたの確認" in markup
    assert "SMAIナビの整理" in markup
    assert "smai-copilot-assistant-avatar" in markup
    assert "smai-copilot-assistant-avatar-image--reply" in markup
    assert "data:image/webp;base64," in markup
    assert "この銘柄の確認点は？" in markup
    assert "価格と材料を分けて確認します。" in markup


def test_copilot_header_uses_smai_navi_chat_icon():
    markup = _chat_header_html(history_count=0)

    assert "smai-copilot-header-icon" in markup
    assert "data:image/png;base64," in markup
    assert "SMAIアシスタント" in markup
    assert "SMAIナビ" in markup


def test_copilot_turn_markdown_uses_decision_memo_template():
    markdown = copilot_turn_markdown(
        {
            "context_label": "銘柄コックピット / 価格・予測",
            "intent_label": "Decision Reportを作りたい",
            "created_at": "2026-06-14 06:10",
            "answer": "材料を整理します。",
            "reasons": "価格\nAI予測",
            "cautions": "未確認ニュース",
            "next_checkpoints": "根拠資料を見る",
            "memo_points": "判断メモ",
        }
    )

    assert markdown.startswith("# SMAIアシスタント メモ")
    assert "## 対象" in markdown
    assert "- 画面: 銘柄コックピット / 価格・予測" in markdown
    assert "- 分析モード: Decision Reportを作りたい" in markdown
    assert "本レポートは投資判断を補助するための整理メモ" in markdown


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
    chat_input_placeholders = [
        str(getattr(element, "placeholder", "")) for element in app.chat_input
    ]

    assert "SMAIナビ" in page_text
    assert "LLM接続" not in page_text
    assert "LLM Gateway" not in page_text
    assert "こんにちは。SMAIナビです。" in page_text
    assert "smai-copilot-chat-topbar" in page_text
    assert "SMAIアシスタント" in button_labels
    assert (
        "価格・予測・ニュース・根拠資料について確認したいことを入力..." in chat_input_placeholders
    )
    assert "新しい会話" in button_labels
    assert "SMAIの使い方を聞きたい" in button_labels
    assert "この銘柄を整理したい" in button_labels
    assert "予測とリスクを比べたい" in button_labels
    assert "ニュース材料を見たい" in button_labels
    assert "Decision Reportを作りたい" in button_labels
    assert "自由に会話する" in button_labels
    assert "参照中の材料" in page_text


def test_copilot_page_chat_input_appends_chat_turn(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=20)
    app.session_state["sidemenu_page"] = "copilot"
    app.run()

    app.chat_input[0].set_value("確認点を整理して").run()

    assert not app.exception
    assert len(app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]) == 1
    button_labels = [str(getattr(element, "label", "")) for element in app.button]
    assert "SMAIの使い方を聞きたい" not in button_labels
    assert "自由に会話する" not in button_labels
    assert "予測だけ確認" in button_labels
    assert "ニュースだけ再確認" in button_labels
    assert "Decision Report下書きへ" in button_labels
