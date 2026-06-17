from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
from streamlit.testing.v1 import AppTest

from backend.assistant import (
    AssistantMessage,
    AssistantResponse,
    build_assistant_research_tool_plan,
    execute_assistant_tool_plan,
)
from backend.core.config import Settings
from backend.research import ExternalResearchFetchManifestEntry, ExternalResearchFetchResult
from ui.views.copilot import (
    COPILOT_CHAT_HISTORY_STATE_KEY,
    COPILOT_LLM_MODEL_OPTIONS,
    COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY,
    COPILOT_RUNTIME_STATUS_STATE_KEY,
    AssistantStatusEvent,
    CopilotGatewayRuntimeConfig,
    _assistant_runtime_status_for_header,
    _chat_header_html,
    _context_for_llm,
    _fallback_free_chat_answer,
    _gateway_question,
    _intent_from_message,
    _pending_detail_html,
    _pending_steps_for_intent,
    _probe_copilot_gateway_runtime,
    _stream_chunks,
    _tool_plan_answer,
    _tool_plan_tools_state,
    _tool_plan_with_approved_external_fetch,
    _turn_from_response,
    _with_cached_gateway_diagnostic,
    copilot_answer_detail_html,
    copilot_context_label,
    copilot_context_options,
    copilot_conversation_presets,
    copilot_history_messages,
    copilot_settings_from_gateway_runtime,
    copilot_turn_html,
    copilot_turn_markdown,
    copilot_turn_plain_text,
    derive_assistant_runtime_status,
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
    app.session_state[COPILOT_RUNTIME_STATUS_STATE_KEY] = None


def _fake_external_research_result(symbol: str = "7203.T") -> ExternalResearchFetchResult:
    fetched_at = datetime(2026, 6, 17, 6, 0, tzinfo=UTC)
    return ExternalResearchFetchResult(
        symbol=symbol,
        provider="fake_external",
        fetched_at=fetched_at,
        entries=[
            ExternalResearchFetchManifestEntry(
                title="Toyota raises guidance",
                symbol=symbol,
                source_type="news",
                source_url="https://example.com/toyota-guidance",
                provider="fake_news",
                published_at=date(2026, 6, 16),
                fetched_at=fetched_at,
                freshness_status="latest",
                document_id="doc-news",
                content_summary="Toyota raised guidance after stronger demand.",
            ),
            ExternalResearchFetchManifestEntry(
                title="Toyota IR",
                symbol=symbol,
                source_type="company_ir",
                source_url="https://example.com/toyota-ir",
                provider="fake_ir",
                published_at=None,
                fetched_at=fetched_at,
                freshness_status="unknown",
                document_id="doc-ir",
                content_summary="Official IR page was checked.",
            ),
        ],
        warnings=["ニュースの鮮度は取得時点に依存します。"],
    )


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
    assert ".smai-copilot-chat-actions-anchor" in css
    assert 'div[data-testid="stHorizontalBlock"]' in css
    assert ".smai-copilot-material-status" in css
    assert ".smai-copilot-thread" in css
    assert ".smai-copilot-composer-toolbar" in css
    assert ".smai-copilot-statusbar--warning" in css
    assert ".smai-copilot-statusbar--error" in css
    copilot_source = Path("ui/views/copilot.py").read_text(encoding="utf-8")
    assert "data-status-state" in copilot_source
    assert '.smai-copilot-composer-toolbar div[data-testid="stTextInput"] input:focus' in css
    assert 'input[aria-invalid="true"]' in css
    assert ".smai-copilot-response-meta summary" in css
    assert "border-left: 3px solid var(--smai-teal);" in css
    assert "min-height: 6.5rem;" in css
    assert "min-height: 8.5rem;" in css
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


def test_copilot_llm_model_options_include_notebook_standard_qwen4b():
    models = [model for _, model, _ in COPILOT_LLM_MODEL_OPTIONS]

    assert models == ["qwen3:1.7b", "qwen3:4b", "qwen3:8b", "qwen3:14b", "qwen3:30b"]


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
            "intent": "stock_summary",
            "answer": "確認材料を整理します。",
            "response_source": "deterministic_fallback",
            "fallback_reason": "gateway_unavailable",
            "gateway_error_type": "connection_refused",
            "gateway_error_message": "Failed to connect",
            "gateway_url": "http://127.0.0.1:8088/api/v1/context-answer",
            "http_status": "",
            "provider_error_type": "",
            "provider_error_message": "",
            "response_meta": "SMAI通常回答 / fallback: gateway_unavailable / stock_summary",
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
    assert "SMAI通常回答 / deterministic / free_chat" not in free_chat
    assert "技術情報を表示" not in free_chat
    assert "コピー" in free_chat


def test_fallback_free_chat_answer_handles_wellbeing_greeting():
    answer = _fallback_free_chat_answer("こんにちは、元気ですか？", greeting=True)

    assert answer.startswith("こんにちは。元気です。")
    assert "fallback" not in answer.lower()


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
    assert "smai-copilot-pending-steps" in markup
    assert "smai-copilot-pending-current" in markup
    assert "現在の処理" in markup
    assert "質問の意図を確認中" in markup
    assert "LLMへ短い回答を依頼中" not in markup
    assert "SMAIナビが考えています..." in markup
    assert "provider_timeout" not in markup


def test_copilot_pending_turn_renders_only_selected_current_step():
    markup = copilot_turn_html(
        {
            "status": "pending",
            "context_label": "SMAI assistant",
            "question": "この銘柄を整理したい",
            "answer": "SMAIナビが銘柄・価格・材料を確認しています...",
            "intent": "stock_summary",
            "pending_steps": "\n".join(_pending_steps_for_intent("stock_summary")),
            "pending_step_index": "2",
        }
    )

    assert "ニュース材料を整理中" in markup
    assert "銘柄を確認中" not in markup
    assert "価格・予測材料を確認中" not in markup
    assert "LLMへ回答作成を依頼中" not in markup


def test_copilot_pending_steps_are_intent_specific():
    stock_steps = _pending_steps_for_intent("stock_summary")
    offline_stock_steps = _pending_steps_for_intent("stock_summary", uses_llm=False)
    report_steps = _pending_steps_for_intent("decision_report_draft")

    assert stock_steps == (
        "銘柄を確認中",
        "価格・予測材料を確認中",
        "ニュース材料を整理中",
        "LLMへ回答作成を依頼中",
    )
    assert offline_stock_steps[-1] == "回答を作成中"
    assert "Decision Reportの見出しを準備中" in report_steps


def test_copilot_tool_plan_turn_renders_research_plan_card():
    plan = build_assistant_research_tool_plan("トヨタはこれから上がるかな？")
    assert plan is not None

    markup = copilot_turn_html(
        {
            "status": "tool_plan",
            "context_label": "銘柄コックピット / 価格・予測・材料確認",
            "question": plan.user_question,
            "answer": "7203.Tについて、確認する材料の計画を作りました。",
            "intent": "stock_summary",
            "conversation_reason": "特定銘柄と将来見通しの質問です。",
            "approval_reason": plan.approval_reason,
            "symbol_query": plan.symbol_query or "",
            "symbol": plan.symbol or "",
            "company_name": plan.company_name or "",
            "tool_plan_tools": _tool_plan_tools_state(plan),
        }
    )

    assert "調査計画" in markup
    assert "トヨタ自動車（7203.T）" in markup
    assert "価格の動き" in markup
    assert "AI予測・下振れ警戒" in markup
    assert "最新ニュース" in markup
    assert "根拠資料 / Research Evidence" in markup
    assert "外部取得あり" in markup
    assert "実行した確認" not in markup


def test_copilot_tool_plan_answer_handles_legacy_plan_without_company_name():
    plan = SimpleNamespace(
        symbol="7203.T",
        symbol_query="トヨタ",
        has_external_tools=True,
    )

    answer = _tool_plan_answer(plan)  # type: ignore[arg-type]

    assert "トヨタ自動車（7203.T）について、確認する材料を整理しました。" in answer
    assert "外部情報の取得を含むため、実行前に確認します。" in answer


def test_copilot_tool_plan_tools_state_normalizes_legacy_labels():
    plan = SimpleNamespace(
        tools=(
            SimpleNamespace(
                name="symbol_resolve",
                label="銘柄特定",
                reason="トヨタを銘柄コードに変換します。",
                external=False,
                required=True,
            ),
            SimpleNamespace(
                name="price_fetch",
                label="価格データ",
                reason="直近の価格推移と変動を確認します。",
                external=True,
                required=True,
            ),
        )
    )

    state = _tool_plan_tools_state(plan)  # type: ignore[arg-type]

    assert "銘柄を特定" in state
    assert "入力された銘柄名から、対象銘柄を確認します。" in state
    assert "価格の動き" in state
    assert "価格データ" not in state


def test_copilot_tool_plan_pending_progress_uses_current_tool_status():
    plan = build_assistant_research_tool_plan("トヨタはこれから上がるかな？")
    assert plan is not None

    markup = _pending_detail_html(
        {
            "status": "pending",
            "tool_plan_choice": "approve",
            "tool_plan_subject": "トヨタ自動車（7203.T）",
            "tool_plan_tools": _tool_plan_tools_state(plan),
            "pending_step_index": "3",
        }
    )

    assert "SMAIナビが材料を確認しています" in markup
    assert "✓" in markup
    assert "銘柄を特定: トヨタ自動車（7203.T）" in markup
    assert "価格の動きを確認" in markup
    assert "AI予測・下振れ警戒を確認" in markup
    assert "最新ニュースを確認中" in markup


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


def test_stream_chunks_prefer_sentence_boundaries():
    chunks = _stream_chunks("銘柄を確認しました。価格材料を整理します。ニュースも見ます。")

    assert chunks == [
        "銘柄を確認しました。",
        "銘柄を確認しました。価格材料を整理します。",
        "銘柄を確認しました。価格材料を整理します。ニュースも見ます。",
    ]


def test_copilot_header_uses_smai_navi_chat_icon():
    markup = _chat_header_html(history_count=0)

    assert "smai-copilot-header-icon" in markup
    assert "data:image/png;base64," in markup
    assert "SMAIアシスタント" in markup
    assert "SMAIナビ" in markup


def test_copilot_header_uses_neutral_initial_gateway_state():
    runtime_config = CopilotGatewayRuntimeConfig(
        enabled=True,
        base_url="http://gateway.local",
        timeout_seconds=5.0,
        context_answer_path="/api/v1/context-answer",
        execution_mode="auto",
        environment_profile="notebook",
        readiness_status="unchecked",
    )
    status = _assistant_runtime_status_for_header(
        history=[],
        runtime_config=runtime_config,
    )
    markup = _chat_header_html(
        history_count=0,
        runtime_config=runtime_config,
        runtime_status=status,
    )

    assert status.state == "checking"
    assert status.label == "LLM待機中"
    assert status.message == "送信時にGateway接続を確認します。"
    assert "LLM接続エラー" not in markup
    assert "smai-copilot-statusbar--error" not in markup
    assert 'data-status-state="checking"' in markup


def test_copilot_gateway_diagnostic_does_not_probe_by_default(monkeypatch):
    def fail_probe(runtime_config: CopilotGatewayRuntimeConfig) -> CopilotGatewayRuntimeConfig:
        raise AssertionError("initial render should not probe Gateway readiness")

    monkeypatch.setattr("ui.views.copilot._probe_copilot_gateway_runtime", fail_probe)
    runtime_config = CopilotGatewayRuntimeConfig(
        enabled=True,
        base_url="http://gateway.local",
        timeout_seconds=5.0,
        context_answer_path="/api/v1/context-answer",
        execution_mode="auto",
        environment_profile="notebook",
        readiness_status="unchecked",
    )

    runtime = _with_cached_gateway_diagnostic(runtime_config)

    assert runtime.readiness_status == "unchecked"
    assert runtime.readiness_label == "LLM待機中"
    assert runtime.readiness_detail == "送信時にGateway接続を確認します。"


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
    assert "Ollamaまたは選択モデルに接続できません。" in markup
    assert "smai-copilot-statusbar--error" in markup
    assert 'data-status-state="provider_unavailable"' in markup


def test_copilot_header_marks_gateway_timeout_as_warning():
    markup = _chat_header_html(
        history_count=0,
        runtime_config=CopilotGatewayRuntimeConfig(
            enabled=True,
            base_url="http://gateway.local",
            timeout_seconds=5.0,
            context_answer_path="/api/v1/context-answer",
            execution_mode="auto",
            environment_profile="notebook",
            readiness_status="gateway_timeout",
            readiness_message=(
                "smai-ai-gateway の状態確認がタイムアウトしました。"
                "回答時はGateway接続を再試行します。"
            ),
        ),
    )

    assert "LLM接続エラー" in markup
    assert "Gatewayに接続できません。簡易モードで回答します。" in markup
    assert "smai-copilot-statusbar--error" in markup
    assert 'data-status-state="gateway_unavailable"' in markup


def test_copilot_header_shows_pending_generation_state():
    markup = _chat_header_html(
        history_count=1,
        has_pending=True,
        runtime_config=CopilotGatewayRuntimeConfig(
            enabled=True,
            base_url="http://gateway.local",
            timeout_seconds=5.0,
            context_answer_path="/api/v1/context-answer",
            execution_mode="auto",
            environment_profile="notebook",
            readiness_status="ready",
            readiness_message="qwen3:1.7b 利用可能",
        ),
    )

    assert "回答生成中" in markup
    assert "SMAIナビが回答を整理しています。" in markup
    assert "smai-copilot-statusbar--checking" in markup


def test_copilot_runtime_config_reflects_latest_gateway_success():
    status = derive_assistant_runtime_status(
        AssistantStatusEvent(
            name="response_completed",
            runtime_config=CopilotGatewayRuntimeConfig(
                enabled=True,
                base_url="http://gateway.local",
                timeout_seconds=5.0,
                context_answer_path="/api/v1/context-answer",
                execution_mode="auto",
                environment_profile="notebook",
                readiness_status="gateway_timeout",
                readiness_message="状態確認がタイムアウト",
            ),
            response=AssistantResponse(
                intent="unknown",
                answer="回答しました。",
                response_source="llm",
                gateway_status="ok",
                provider="ollama",
                model="qwen3:1.7b",
                profile="notebook_dev",
                latency_ms=1234,
            ),
        )
    )

    assert status.state == "ready"
    assert status.label == "準備完了"
    assert status.message == "SMAIナビは通常回答できます。"
    markup = _chat_header_html(
        history_count=1,
        runtime_config=CopilotGatewayRuntimeConfig(
            enabled=True,
            base_url="http://gateway.local",
            timeout_seconds=5.0,
            context_answer_path="/api/v1/context-answer",
            execution_mode="auto",
            environment_profile="notebook",
        ),
        runtime_status=status,
    )
    assert "準備完了" in markup
    assert "SMAIナビは通常回答できます。" in markup
    assert 'data-status-state="ready"' in markup


def test_copilot_runtime_config_reflects_latest_gateway_fallback():
    status = derive_assistant_runtime_status(
        AssistantStatusEvent(
            name="response_completed",
            runtime_config=CopilotGatewayRuntimeConfig(
                enabled=True,
                base_url="http://gateway.local",
                timeout_seconds=5.0,
                context_answer_path="/api/v1/context-answer",
                execution_mode="auto",
                environment_profile="notebook",
                readiness_status="ready",
            ),
            response=AssistantResponse(
                intent="unknown",
                answer="取得済み材料で回答しました。",
                response_source="deterministic_fallback",
                fallback_reason="response_validation_failure",
                provider="ollama",
                model="qwen3:1.7b",
                profile="notebook_dev",
            ),
        )
    )

    assert status.state == "degraded"
    assert status.label == "簡易モードで回答中"
    assert "LLM応答が不安定" in status.message


def test_copilot_runtime_status_reflects_research_plan_and_running():
    runtime_config = CopilotGatewayRuntimeConfig(
        enabled=True,
        base_url="http://gateway.local",
        timeout_seconds=5.0,
        context_answer_path="/api/v1/context-answer",
        execution_mode="auto",
        environment_profile="notebook",
        readiness_status="ready",
    )
    planned = _assistant_runtime_status_for_header(
        history=[{"status": "tool_plan"}],
        runtime_config=runtime_config,
    )
    running = _assistant_runtime_status_for_header(
        history=[{"status": "pending", "tool_plan_choice": "approve"}],
        runtime_config=runtime_config,
    )

    assert planned.state == "research_planned"
    assert planned.label == "調査計画あり"
    assert running.state == "research_running"
    assert running.label == "材料確認中"


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
    assert "smai-copilot-chat-actions-anchor" in page_text
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


def test_copilot_submit_uses_inline_chat_placeholder_flow():
    source = Path("ui/views/copilot.py").read_text(encoding="utf-8")

    assert "header_placeholder = st.empty()" in source
    assert "_refresh_copilot_header(" in source
    assert "chat_placeholder = st.empty()" in source
    assert "_process_queued_copilot_request_inline(" in source
    assert "_render_pending_step_progression(chat_placeholder=chat_placeholder)" in source
    assert "_render_chat_thread(_copilot_history(), placeholder=chat_placeholder)" in source
    assert "suggestions_placeholder.empty()" in source


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


def test_copilot_page_new_conversation_clears_stale_runtime_status(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=40)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)
    app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = [
        {
            "turn_id": "old",
            "status": "complete",
            "context_label": "SMAIアシスタント / SMAIの使い方",
            "question": "こんにちは",
            "answer": "こんにちは。",
            "intent": "free_chat",
            "fallback_reason": "provider_timeout",
        }
    ]
    app.session_state[COPILOT_RUNTIME_STATUS_STATE_KEY] = {
        "state": "degraded",
        "label": "簡易モードで回答中",
        "message": "LLM応答が不安定です。",
        "severity": "warning",
        "provider": "ollama",
        "model": "qwen3:1.7b",
        "profile": "notebook_dev",
        "last_updated_at": "2026-06-16 10:00:00",
        "fallback_reason": "provider_timeout",
    }
    app.run()

    _click_button_label(app, "新しい会話")

    assert not app.exception
    assert app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] == []
    assert COPILOT_RUNTIME_STATUS_STATE_KEY not in app.session_state


def test_copilot_page_second_chat_input_appends_next_turn(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=40)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)
    app.run()

    app.text_input[0].set_value("こんにちは")
    _click_button_label(app, "送信")
    first_history = list(app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY])

    app.text_input[0].set_value("あなたの名前は何ですか")
    _click_button_label(app, "送信")
    second_history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]

    assert not app.exception
    assert len(first_history) == 1
    assert len(second_history) == 2
    assert second_history[-1]["question"] == "あなたの名前は何ですか"


def test_copilot_page_research_question_shows_tool_plan_before_execution(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=40)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)
    app.run()

    app.text_input[0].set_value("トヨタはこれから上がるかな？")
    _click_button_label(app, "送信")

    assert not app.exception
    history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    assert history[-1]["status"] == "tool_plan"
    assert history[-1]["research_intent"] == "stock_forward_view"
    assert app.session_state["smai_copilot_pending_request"] is None
    page_text = "\n".join(
        str(element.value)
        for element in app.markdown
        if getattr(element, "value", None) is not None
    )
    button_labels = [str(getattr(element, "label", "")) for element in app.button]
    assert "調査計画あり" in page_text
    assert "調査計画" in page_text
    assert "トヨタ自動車（7203.T）" in page_text
    assert "価格の動き" in page_text
    assert "外部取得あり" in page_text
    assert "取得して分析する" in button_labels
    assert "取得済み情報だけで回答" in button_labels
    assert "キャンセル" in button_labels


def test_copilot_page_tool_plan_approve_returns_material_summary(monkeypatch, tmp_path):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    monkeypatch.setattr(
        "ui.views.copilot._assistant_decision_report_archive_dir",
        lambda: tmp_path,
    )
    fetch_calls: list[dict[str, object]] = []

    def fake_fetch(symbol: str, **kwargs: object) -> ExternalResearchFetchResult:
        fetch_calls.append({"symbol": symbol, **kwargs})
        return _fake_external_research_result(symbol)

    monkeypatch.setattr("ui.views.copilot.fetch_external_research_for_symbol", fake_fetch)

    app = AppTest.from_file("ui/app.py", default_timeout=40)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)
    app.run()

    app.text_input[0].set_value("トヨタこれから上がるかな")
    _click_button_label(app, "送信")
    _click_button_label(app, "取得して分析する")

    assert not app.exception
    history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    assert history[-1]["status"] == "complete"
    assert history[-1]["conversation_mode"] == "research_answer"
    assert "トヨタ自動車（7203.T）について、取得できた材料を整理しました。" in history[-1]["answer"]
    assert "買い/売りを断定するのではなく" in history[-1]["answer"]
    assert "確認できた材料:" in history[-1]["answer"]
    assert "注意すべき材料:" in history[-1]["answer"]
    assert "次に確認:" in history[-1]["answer"]
    assert fetch_calls == [
        {
            "symbol": "7203.T",
            "company_name": "トヨタ自動車",
            "related_keywords": [
                "トヨタ自動車",
                "トヨタ自動車（7203.T）",
                "トヨタこれから上がるかな",
            ],
            "allow_network": True,
        }
    ]
    assert "銘柄を特定: 銘柄を特定" not in history[-1]["answer"]
    assert "まず、この銘柄で確認する材料を短く整理します。" not in history[-1]["answer"]
    assert "\n\n取得できた材料を整理しました。" not in history[-1]["answer"]
    assert "見る材料\n銘柄を特定" not in history[-1]["answer"]
    assert history[-1]["hide_answer_grid"] == "true"
    assert "最新ニュース" in history[-1]["executed_checks"]
    assert "根拠資料 / Research Evidence" in history[-1]["executed_checks"]
    assert "価格の動き" in history[-1]["executed_checks"]
    assert history[-1]["can_add_to_decision_report"] == "true"
    assert history[-1]["report_draft_status"] == "draft_ready"
    assert "Decision Report Draft: トヨタ自動車" in history[-1]["decision_report_markdown"]
    assert "https://example.com/toyota-guidance" in history[-1]["decision_report_markdown"]
    assert "https://example.com/toyota-ir" in history[-1]["decision_report_markdown"]
    assert "provider raw" not in history[-1]["decision_report_markdown"].lower()
    assert "Decision Reportに追加" in [str(getattr(element, "label", "")) for element in app.button]

    _click_button_label(app, "Decision Reportに追加")

    draft = app.session_state[COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY]
    assert draft["source"] == "assistant_research_mode"
    assert draft["symbol"] == "7203.T"
    assert "Decision Report Draft: トヨタ自動車" in draft["markdown"]
    assert draft["context"]
    updated_history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    assert updated_history[-1]["report_draft_status"] == "pending_draft_created"

    app.run()
    assert "下書きを保存" in [str(getattr(element, "label", "")) for element in app.button]
    _click_button_label(app, "下書きを保存")

    archived = app.session_state[COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY]
    archive_path = Path(str(archived["archive_markdown_path"]))
    zip_path = Path(str(archived["archive_zip_path"]))
    manifest_path = tmp_path / "assistant_decision_report_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert archived["status"] == "archived"
    assert archived["manifest_status"] == "updated"
    assert archive_path.exists()
    assert zip_path.exists()
    assert "https://example.com/toyota-guidance" in archive_path.read_text(encoding="utf-8")
    assert manifest["reports"][0]["symbol"] == "7203.T"
    assert manifest["reports"][0]["cached_only"] is False
    assert manifest["reports"][0]["tool_status"]["news_fetch"] == "success"
    updated_history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    assert updated_history[-1]["report_draft_status"] == "archived"


def test_copilot_page_tool_plan_cached_only_mentions_missing_materials(monkeypatch, tmp_path):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    monkeypatch.setattr(
        "ui.views.copilot._assistant_decision_report_archive_dir",
        lambda: tmp_path,
    )

    def fail_if_called(*_args: object, **_kwargs: object) -> ExternalResearchFetchResult:
        raise AssertionError("cached-only must not call external fetch")

    monkeypatch.setattr("ui.views.copilot.fetch_external_research_for_symbol", fail_if_called)

    app = AppTest.from_file("ui/app.py", default_timeout=40)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)
    app.run()

    app.text_input[0].set_value("トヨタこれから上がるかな")
    _click_button_label(app, "送信")
    _click_button_label(app, "取得済み情報だけで回答")

    assert not app.exception
    history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    assert history[-1]["status"] == "complete"
    assert history[-1]["conversation_mode"] == "research_answer"
    assert history[-1]["answer"].startswith("取得済み情報だけで整理します。")
    assert "未確認材料:" in history[-1]["answer"]
    assert "外部取得は行っていない" in history[-1]["answer"]
    assert "最新ニュース" in history[-1]["answer"]
    assert "根拠資料 / Research Evidence" in history[-1]["answer"]
    assert history[-1]["can_add_to_decision_report"] == "true"
    assert "## 未確認材料" in history[-1]["decision_report_markdown"]

    _click_button_label(app, "Decision Reportに追加")
    app.run()
    _click_button_label(app, "下書きを保存")

    archived = app.session_state[COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY]
    archive_path = Path(str(archived["archive_markdown_path"]))
    manifest = json.loads(
        (tmp_path / "assistant_decision_report_manifest.json").read_text(encoding="utf-8")
    )

    assert archived["status"] == "archived"
    assert "今回は取得済み情報のみで整理しています。" in archive_path.read_text(encoding="utf-8")
    assert manifest["reports"][0]["cached_only"] is True
    assert manifest["reports"][0]["tool_status"]["news_fetch"] == "skipped"
    assert manifest["reports"][0]["tool_status"]["research_fetch"] == "skipped"


def test_approved_external_fetch_failure_becomes_failed_tool_results(monkeypatch):
    def failing_fetch(*_args: object, **_kwargs: object) -> ExternalResearchFetchResult:
        raise RuntimeError("provider raw request_id=abc")

    monkeypatch.setattr("ui.views.copilot.fetch_external_research_for_symbol", failing_fetch)
    plan = execute_assistant_tool_plan(
        intent="stock_summary",
        message="トヨタこれから上がるかな",
        report_context=None,
    )
    tool_plan_tools = "\n".join(
        [
            "news_fetch\t最新ニュース\t直近ニュースや開示材料を確認します。\t1\t0",
            "research_fetch\t根拠資料 / Research Evidence\t根拠資料を確認します。\t1\t0",
        ]
    )

    updated = _tool_plan_with_approved_external_fetch(
        tool_plan=plan,
        choice="approve",
        subject="トヨタ自動車（7203.T）",
        question="トヨタこれから上がるかな",
        tool_plan_tools=tool_plan_tools,
    )
    result_by_name = {result.name: result for result in updated.executed}

    assert result_by_name["search_news_materials"].status == "failed"
    assert result_by_name["search_rag_materials"].status == "failed"
    assert "取得結果を確認できません" in result_by_name["search_news_materials"].summary
    assert "request_id" not in result_by_name["search_news_materials"].summary


def test_copilot_page_decision_report_request_reuses_recent_research_draft(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    fetch_calls: list[str] = []

    def fake_fetch(symbol: str, **_kwargs: object) -> ExternalResearchFetchResult:
        fetch_calls.append(symbol)
        return _fake_external_research_result(symbol)

    monkeypatch.setattr("ui.views.copilot.fetch_external_research_for_symbol", fake_fetch)

    app = AppTest.from_file("ui/app.py", default_timeout=60)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)
    app.run()

    app.text_input[0].set_value("トヨタこれから上がるかな")
    _click_button_label(app, "送信")
    _click_button_label(app, "取得して分析する")
    first_draft = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY][-1]["decision_report_markdown"]

    app.text_input[0].set_value("この内容をDecision Reportにして")
    _click_button_label(app, "送信")
    assert app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY][-1]["status"] == "tool_plan"
    _click_button_label(app, "取得して分析する")

    history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    assert not app.exception
    assert history[-1]["intent"] == "decision_report_draft"
    assert history[-1]["can_add_to_decision_report"] == "true"
    assert history[-1]["report_draft_status"] == "draft_ready_from_recent_research"
    assert history[-1]["decision_report_markdown"] == first_draft
    assert "直近の調査結果" in history[-1]["answer"]
    assert fetch_calls == ["7203.T"]


def test_copilot_page_normal_chat_does_not_show_report_add(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=40)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)
    app.run()

    app.text_input[0].set_value("あなたの名前は何ですか")
    _click_button_label(app, "送信")

    labels = [str(getattr(element, "label", "")) for element in app.button]
    history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    assert not app.exception
    assert history[-1]["can_add_to_decision_report"] == ""
    assert "Decision Reportに追加" not in labels


def test_copilot_page_tool_plan_cancel_is_natural(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")

    def fail_if_called(*_args: object, **_kwargs: object) -> ExternalResearchFetchResult:
        raise AssertionError("cancel must not call external fetch")

    monkeypatch.setattr("ui.views.copilot.fetch_external_research_for_symbol", fail_if_called)

    app = AppTest.from_file("ui/app.py", default_timeout=40)
    app.session_state["sidemenu_page"] = "copilot"
    _reset_copilot_session(app)
    app.run()

    app.text_input[0].set_value("トヨタこれから上がるかな")
    _click_button_label(app, "送信")
    _click_button_label(app, "キャンセル")

    assert not app.exception
    history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    assert history[-1]["status"] == "complete"
    assert "了解しました。外部情報の取得は行いません。" in history[-1]["answer"]
    assert history[-1]["fallback_reason"] == "research_cancelled"


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
    assert history[-1]["conversation_mode"] == "normal_chat"
    latest_markup = copilot_turn_html(history[-1])
    assert "SMAI通常回答" not in latest_markup
    assert "技術情報を表示" not in latest_markup
    assert "見る材料" not in latest_markup
    assert "注意点" not in latest_markup
    assert "次に確認" not in latest_markup
    assert "実行した確認" not in latest_markup
    assert "売買推奨" not in history[-1]["answer"]
    assert history[-1]["answer"].startswith("こんにちは。SMAIナビです。")
    assert len(history[-1]["answer"]) >= 40
