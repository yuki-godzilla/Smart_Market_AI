from __future__ import annotations

from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

from backend.assistant import AssistantMessage, AssistantResponse
from backend.core.config import Settings
from ui.views.copilot import (
    COPILOT_CHAT_HISTORY_STATE_KEY,
    CopilotGatewayRuntimeConfig,
    _chat_header_html,
    _context_for_llm,
    _gateway_question,
    _intent_from_message,
    _probe_copilot_gateway_runtime,
    _stream_chunks,
    _turn_from_response,
    copilot_answer_detail_html,
    copilot_context_label,
    copilot_context_options,
    copilot_conversation_presets,
    copilot_history_messages,
    copilot_settings_from_gateway_runtime,
    copilot_turn_html,
    copilot_turn_markdown,
    copilot_turn_plain_text,
)


def _click_button_label(app: AppTest, label: str) -> None:
    for button in app.button:
        if str(getattr(button, "label", "")) == label:
            button.click().run()
            return
    raise AssertionError(f"button not found: {label}")


def _reset_copilot_session(app: AppTest) -> None:
    app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = []
    app.session_state["smai_copilot_pending_request"] = None
    app.session_state["smai_copilot_pending_stream_turn_id"] = ""
    app.session_state["smai_copilot_suppress_next_submit"] = False


def test_copilot_layout_uses_shared_wide_lane():
    css = Path("ui/styles.py").read_text(encoding="utf-8")

    lane_gutter = "calc(100% - var(--smai-content-gutter))"
    shared_lane = f"width: min(var(--smai-content-max-width), {lane_gutter});"
    chat_lane = f"width: min(var(--smai-chat-main-width), {lane_gutter});"
    assert "--smai-content-max-width: 1320px;" in css
    assert "--smai-chat-main-width: 1180px;" in css
    assert css.count(shared_lane) >= 5
    assert chat_lane in css
    assert ".smai-copilot-chat-topbar" in css
    assert "grid-template-columns: auto minmax(0, 1fr) auto;" in css
    assert ".smai-copilot-material-status" in css
    assert ".smai-copilot-thread" in css
    assert ".smai-copilot-composer-toolbar" in css
    assert ".smai-copilot-response-meta summary" in css
    assert "border-left: 3px solid var(--smai-teal);" in css
    assert "width: min(54rem, calc(100% - 1.5rem));" not in css


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


def test_copilot_llm_micro_intents_use_minimal_context_and_prompt():
    context = copilot_context_options()[0]

    free_chat_context = _context_for_llm(
        intent="free_chat",
        context=context,
        question="こんにちは",
    )
    app_help_context = _context_for_llm(
        intent="app_help",
        context=context,
        question="SMAIの使い方を教えて",
    )
    stock_context = _context_for_llm(
        intent="stock_summary",
        context=context,
        question="この銘柄を整理したい",
    )

    assert free_chat_context.context_id == "copilot_free_chat_minimal"
    assert app_help_context.context_id == "copilot_app_help_minimal"
    assert app_help_context.summary == {
        "assistant_name": "SMAIナビ",
        "screen": "SMAIアシスタント",
        "role": "Smart Market AIの投資判断アシスタント",
        "message": "SMAIの使い方を教えて",
    }
    assert stock_context is context
    assert (
        _gateway_question(
            question="SMAIの使い方を教えて",
            intent="app_help",
            prompt_instruction="toolを使わない",
            tool_summaries=["現在文脈を確認"],
        )
        == "SMAIの使い方を教えて"
    )


def test_copilot_identity_and_capability_route_to_llm_micro_intents():
    assert _intent_from_message("あなたの名前は？", fallback="free_chat") == "identity"
    assert _intent_from_message("何ができるの？", fallback="free_chat") == "capability_help"

    identity_context = _context_for_llm(
        intent="identity",
        context=copilot_context_options()[0],
        question="あなたの名前は？",
    )
    capability_context = _context_for_llm(
        intent="capability_help",
        context=copilot_context_options()[0],
        question="何ができるの？",
    )

    assert identity_context.context_id == "copilot_identity_minimal"
    assert capability_context.context_id == "copilot_capability_help_minimal"
    assert identity_context.summary["message"] == "あなたの名前は？"
    assert capability_context.summary["message"] == "何ができるの？"


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
        timeout_seconds=5.0,
        context_answer_path="/api/v1/context-answer",
        execution_mode="light",
        environment_profile="notebook",
    )

    settings = copilot_settings_from_gateway_runtime(runtime_config, base_settings)

    assert settings.assistant.gateway.enabled
    assert settings.assistant.gateway.base_url == "http://gateway.local"
    assert settings.assistant.gateway.model == "qwen3:1.7b"
    assert settings.assistant.gateway.timeout_seconds == 5.0
    assert settings.assistant.gateway.execution_mode == "light"
    assert settings.assistant.gateway.environment_profile == "notebook"
    assert settings.assistant.gateway.preferred_profile == "notebook_dev"
    assert not base_settings.assistant.gateway.enabled


def test_copilot_gateway_probe_reports_model_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "default_profile": "notebook_dev",
                "default_model": "qwen3:1.7b",
                "installed_models": [],
                "configured_model_installed": False,
                "install_hint": "Please run: ollama pull qwen3:1.7b",
            },
            request=request,
        )

    runtime = _probe_copilot_gateway_runtime(
        CopilotGatewayRuntimeConfig(
            enabled=True,
            base_url="http://gateway.local",
            timeout_seconds=5.0,
            context_answer_path="/api/v1/context-answer",
            execution_mode="auto",
            environment_profile="notebook",
        ),
        transport=httpx.MockTransport(handler),
    )

    assert runtime.readiness_status == "model_missing"
    assert runtime.readiness_label == "モデル未取得"
    assert runtime.provider_error_type == "model_not_found"
    assert runtime.ollama_base_url == "http://localhost:11434"


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
            "executed_checks": "現在文脈 <確認>",
            "response_meta": "qwen3:8b / live / assistant_standard / ollama / forecast_risk_compare",
        }
    )

    assert markup.index("予測側の見方") < markup.index("実行した確認")
    assert "材料 &lt;1&gt;" in markup
    assert "注意 &lt;2&gt;" in markup
    assert "次 &lt;3&gt;" in markup
    assert "温度差 &lt;4&gt;" in markup
    assert "現在文脈 &lt;確認&gt;" in markup
    assert "qwen3:8b / live / assistant_standard / ollama / forecast_risk_compare" in markup
    assert "予測側の見方" in markup
    assert "リスク側の見方" in markup
    assert "<script>" not in markup
    assert "smai-copilot-answer-grid" in markup


def test_copilot_answer_detail_html_includes_gateway_diagnostics():
    markup = copilot_answer_detail_html(
        {
            "intent": "free_chat",
            "answer": "こんにちは。SMAIナビです。",
            "response_source": "deterministic_fallback",
            "fallback_reason": "gateway_unavailable",
            "gateway_error_type": "connection_refused",
            "gateway_error_message": "Failed to connect",
            "gateway_url": "http://127.0.0.1:8088/api/v1/context-answer",
            "http_status": "",
            "provider_error_type": "",
            "provider_error_message": "",
            "response_meta": "SMAI通常回答 / fallback: gateway_unavailable / free_chat",
        }
    )

    assert "gateway_error" in markup
    assert "connection_refused" in markup
    assert "gateway_url" in markup
    assert "http://127.0.0.1:8088/api/v1/context-answer" in markup


def test_copilot_answer_detail_html_uses_intent_specific_formats():
    app_help = copilot_answer_detail_html(
        {
            "intent": "app_help",
            "reasons": "銘柄コックピット",
            "cautions": "売買推奨ではありません",
            "next_checkpoints": "銘柄を入力します",
            "response_meta": "SMAI通常回答 / deterministic / app_help",
        }
    )
    forecast = copilot_answer_detail_html(
        {
            "intent": "forecast_risk_compare",
            "reasons": "中心予測",
            "cautions": "下振れ警戒",
            "next_checkpoints": "モデル合意度",
            "memo_points": "温度差",
        }
    )
    news = copilot_answer_detail_html(
        {
            "intent": "news_materials",
            "reasons": "強気ニュース",
            "cautions": "弱気ニュース",
            "next_checkpoints": "出典URL",
            "memo_points": "未確認材料",
        }
    )
    report = copilot_answer_detail_html(
        {
            "intent": "decision_report_draft",
            "reasons": "確認した材料",
            "cautions": "未確認事項",
            "next_checkpoints": "次回確認",
            "memo_points": "メモ",
        }
    )
    free_chat = copilot_answer_detail_html(
        {
            "intent": "free_chat",
            "reasons": "固定カードにしない",
            "cautions": "注意",
            "next_checkpoints": "次",
            "response_meta": "SMAI通常回答 / deterministic / free_chat",
        }
    )

    assert "目的別の使い方" not in app_help
    assert "smai-copilot-inline-sections" not in app_help
    assert "smai-copilot-answer-grid" not in app_help
    assert "見る材料" not in app_help
    assert "Markdownで保存" not in app_help
    assert "予測側の見方" in forecast
    assert "リスク側の見方" in forecast
    assert "強気材料" in news
    assert "未確認材料" in news
    assert "確認した材料" in report
    assert "次回確認" in report
    assert "smai-copilot-answer-grid" not in free_chat
    assert "固定カードにしない" not in free_chat
    assert "SMAI通常回答 / deterministic / free_chat" in free_chat


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
            "response_meta": "SMAI通常回答 / fallback: gateway_timeout / stock_summary",
        }
    )

    assert "smai-copilot-message-row--user" in markup
    assert "smai-copilot-message-row--assistant" in markup
    assert markup.count("smai-copilot-thread") == 1
    assert "あなたの確認" in markup
    assert "SMAIナビ" in markup
    assert "smai-copilot-natural-lead" in markup
    assert "SMAI通常回答 / fallback: gateway_timeout / stock_summary" in markup
    assert "smai-copilot-assistant-avatar" in markup
    assert "smai-copilot-assistant-avatar-image--reply" in markup
    assert "技術情報を表示" in markup
    assert "data:image/webp;base64," in markup
    assert "この銘柄の確認点は？" in markup
    assert "価格と材料を分けて確認します。" in markup


def test_copilot_pending_turn_renders_as_smai_bubble_without_runtime_meta():
    markup = copilot_turn_html(
        {
            "status": "pending",
            "context_label": "SMAI assistant",
            "question": "hello",
            "answer": "SMAIナビが考えています...",
            "intent": "free_chat",
            "response_meta": "qwen3:1.7b / live / provider_timeout",
        }
    )

    assert "smai-copilot-thread" in markup
    assert "smai-copilot-message-row--assistant" in markup
    assert "smai-copilot-message-card--pending" in markup
    assert "smai-copilot-pending-dots" in markup
    assert "SMAIナビが考えています..." in markup
    assert "provider_timeout" not in markup


def test_copilot_turn_from_response_adds_natural_lead_and_meta():
    context = copilot_context_options()[0]

    turn = _turn_from_response(
        context,
        "SMAIの使い方を教えて",
        AssistantResponse(
            intent="overview",
            answer="銘柄コックピットから確認できます。",
            reasons=["銘柄を深掘りしたい -> 銘柄コックピット"],
            next_checkpoints=["気になる銘柄を入力します。"],
            response_source="llm",
            model="qwen3:8b",
            provider="ollama",
            profile="assistant_fast",
            latency_ms=4230,
            gateway_status="ok",
            request_id="request-1",
        ),
        intent="app_help",
        executed_checks=["現在文脈を確認"],
    )

    assert turn["answer"].startswith("はい。SMAIは目的別に画面を使い分ける")
    assert turn["response_meta"] == "qwen3:8b / live / assistant_fast / ollama / app_help / 4230ms"
    assert turn["latency_ms"] == "4230"
    assert turn["gateway_status"] == "ok"
    assert turn["request_id"] == "request-1"


def test_copilot_turn_from_response_hides_internal_prompt_text():
    context = copilot_context_options()[1]

    turn = _turn_from_response(
        context,
        "AI予測インサイトと下振れ警戒をどう比べればいい？",
        AssistantResponse(
            intent="forecast",
            answer="SMAI Assistant intent: forecast_risk_compare\nBoundary: no advice",
            response_source="deterministic_fallback",
            fallback_reason="gateway_timeout",
        ),
        intent="forecast_risk_compare",
    )

    assert turn["answer"].startswith("AI予測とリスクを分けて確認します。")
    assert "SMAI Assistant intent" not in turn["answer"]
    assert (
        turn["response_meta"] == "SMAI通常回答 / fallback: gateway_timeout / forecast_risk_compare"
    )


def test_copilot_free_chat_identity_answer_stays_on_identity():
    context = copilot_context_options()[0]

    turn = _turn_from_response(
        context,
        "あなたの名前は？",
        AssistantResponse(
            intent="unknown",
            answer="分かる範囲で短く整理します。",
            response_source="deterministic_fallback",
            fallback_reason="local_conversation_fallback",
        ),
        intent="free_chat",
    )

    assert "SMAIナビ" in turn["answer"]
    assert "Smart Market AI" in turn["answer"]
    assert "SMAIで確認する観点" not in turn["answer"]


def test_copilot_identity_and_capability_plain_text_do_not_require_section_cards():
    base_turn = {
        "intent_label": "SMAIアシスタント / SMAIの使い方",
        "context_label": "SMAIアシスタント",
        "question": "あなたの名前は何ですか？",
        "answer": "私はSMAIナビです。",
        "executed_checks": "",
        "reasons": "",
        "cautions": "",
        "next_checkpoints": "",
        "memo_points": "",
    }

    identity_text = copilot_turn_plain_text({**base_turn, "intent": "identity"})
    capability_text = copilot_turn_plain_text(
        {**base_turn, "intent": "capability_help", "question": "何ができるの？"}
    )

    assert "私はSMAIナビです。" in identity_text
    assert "何ができるの？" in capability_text


def test_copilot_actions_and_exports_are_sanitized_by_intent():
    micro_turn = {
        "intent": "identity",
        "intent_label": "SMAIアシスタント / SMAIの使い方",
        "context_label": "SMAIアシスタント",
        "question": "あなたの名前は？",
        "answer": "私はSMAIナビです。 Provider raw fields were excluded.",
        "executed_checks": "debug logs omitted",
        "reasons": "Provider raw fields",
        "cautions": "privacy_notes",
        "next_checkpoints": "score or ranking recomputation",
        "memo_points": "",
    }
    stock_turn = {
        **micro_turn,
        "intent": "stock_summary",
        "answer": "価格とニュースを分けて確認します。",
        "reasons": "価格トレンド\ndebug logs omitted",
        "cautions": "AI予測だけで判断しないでください。\nprovider raw fields",
    }

    micro_actions = copilot_answer_detail_html(micro_turn)
    plain_text = copilot_turn_plain_text(micro_turn)
    markdown = copilot_turn_markdown(stock_turn)

    assert "コピー" in micro_actions
    assert "Markdownで保存" not in micro_actions
    assert "Decision Reportに追加" not in micro_actions
    assert "Provider raw fields" not in plain_text
    assert "debug logs" not in plain_text
    assert "provider raw fields" not in markdown.lower()
    assert "debug logs" not in markdown.lower()
    assert "価格トレンド" in markdown


def test_stream_chunks_progressively_build_answer_text():
    chunks = _stream_chunks("SMAIナビが少しずつ回答を表示します。")

    assert len(chunks) >= 2
    assert chunks[-1] == "SMAIナビが少しずつ回答を表示します。"
    assert all(chunks[index] != chunks[index + 1] for index in range(len(chunks) - 1))


def test_copilot_header_uses_smai_navi_chat_icon():
    markup = _chat_header_html(history_count=0)

    assert "smai-copilot-header-icon" in markup
    assert "data:image/png;base64," in markup
    assert "SMAIアシスタント" in markup
    assert "SMAIナビ" in markup


def test_copilot_header_shows_gateway_readiness_status():
    markup = _chat_header_html(
        history_count=0,
        runtime_config=CopilotGatewayRuntimeConfig(
            enabled=True,
            base_url="http://gateway.local",
            timeout_seconds=5.0,
            context_answer_path="/api/v1/context-answer",
            execution_mode="auto",
            environment_profile="notebook",
            readiness_status="provider_unavailable",
            readiness_message="Ollama APIに接続できません",
        ),
    )

    assert "Ollama未接続" in markup
    assert "Ollama APIに接続できません" in markup


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
    app = AppTest.from_file("ui/app.py", default_timeout=40)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)

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
    text_input_placeholders = [
        str(getattr(element, "placeholder", "")) for element in app.text_input
    ]

    assert "SMAIナビ" in page_text
    assert "LLM接続" not in page_text
    assert "LLM Gateway" not in page_text
    assert "こんにちは。SMAIナビです。" not in page_text
    assert "smai-copilot-chat-topbar" in page_text
    assert "SMAIアシスタント" in button_labels
    assert (
        "価格・予測・ニュース・根拠資料について確認したいことを入力..." in text_input_placeholders
    )
    assert "送信" in button_labels
    assert "新しい会話" in button_labels
    assert "SMAIの使い方を聞きたい" in button_labels
    assert "この銘柄を整理したい" in button_labels
    assert "予測とリスクを比べたい" in button_labels
    assert "ニュース材料を見たい" in button_labels
    assert "Decision Reportを作りたい" in button_labels
    assert "自由に会話する" in button_labels
    assert "参照中の材料" in page_text


def test_copilot_page_does_not_use_streamlit_spinner_for_generation():
    source = Path("ui/views/copilot.py").read_text(encoding="utf-8")

    assert "st.spinner" not in source
    assert "LLMで回答を生成中" not in source


def test_copilot_page_chat_input_appends_chat_turn(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=40)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)
    app.run()

    app.text_input[0].set_value("確認点を整理して")
    _click_button_label(app, "送信")

    assert not app.exception
    assert len(app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]) >= 1
    assert app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY][-1]["question"] == "確認点を整理して"
    button_labels = [str(getattr(element, "label", "")) for element in app.button]
    page_text = "\n".join(
        str(element.value)
        for element in app.markdown
        if getattr(element, "value", None) is not None
    )
    assert "SMAIの使い方を聞きたい" not in button_labels
    assert "自由に会話する" not in button_labels
    assert "予測だけ確認" not in button_labels
    assert "ニュースだけ再確認" not in button_labels
    assert "Decision Report下書きへ" not in button_labels
    assert "smai-copilot-actions-row--inside" in page_text


def test_copilot_page_free_chat_does_not_render_fixed_cards(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=40)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)
    app.run()

    app.text_input[0].set_value("こんにちは")
    _click_button_label(app, "送信")

    assert not app.exception
    history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    assert history[-1]["intent"] == "free_chat"
    latest_markup = copilot_turn_html(history[-1])
    assert "SMAI通常回答" in latest_markup
    assert "見る材料" not in latest_markup
    assert "注意点" not in latest_markup
    assert "次に確認" not in latest_markup
    assert "実行した確認" not in latest_markup
    assert "売買推奨" not in history[-1]["answer"]
    assert history[-1]["answer"].startswith("こんにちは。SMAIナビです。")
    assert len(history[-1]["answer"]) >= 40
