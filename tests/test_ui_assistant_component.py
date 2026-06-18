from __future__ import annotations

from backend.assistant import AssistantResponse
from ui.components import assistant as assistant_component
from ui.components.assistant import (
    ASSISTANT_QUERY_CONTEXT_KEY,
    SmaiAssistantContext,
    _assistant_trigger_label,
    _fallback_assistant_context,
    _query_targets_current_context,
    floating_assistant_html,
)


def test_floating_assistant_html_renders_contextual_question_chips():
    context = SmaiAssistantContext(
        context_id="cockpit_forecast",
        page_key="cockpit",
        page_label="銘柄コックピット",
        section_key="ai_forecast",
        section_label="AI予測インサイト",
        lead="中心予測とレンジを確認します。",
        suggested_questions=("AI予測インサイトをどう読む？", "中心予測とは？"),
    )

    markup = floating_assistant_html(context, open_panel=True)

    assert 'class="smai-floating-assistant"' in markup
    assert "<details" in markup
    assert "<summary" in markup
    assert 'class="smai-floating-assistant-toggle" type="checkbox"' in markup
    assert 'id="smai-assistant-cockpit-forecast-open" checked' in markup
    assert 'class="smai-floating-assistant-backdrop"' in markup
    assert 'for="smai-assistant-cockpit-forecast-open"' in markup
    assert "SMAIアシスタント" in markup
    assert "AI予測インサイト" in markup
    assert "予測の読み方を聞く" in markup
    assert "中心予測とレンジを確認します。" in markup
    assert "smai-floating-assistant-avatar--forecast" in markup
    assert "smai-assistant-holo-chart" in markup
    assert "smai-assistant-holo-range" in markup
    assert "smai-floating-assistant-localqa" in markup
    assert "smai-floating-assistant-qa-item" in markup
    assert "smai-floating-assistant-qa-item--1" in markup
    assert "smai-floating-assistant-chip--2" in markup
    assert "smai-floating-assistant-answer-panel--2" in markup
    assert 'type="radio"' not in markup
    assert (
        '<summary class="smai-floating-assistant-chip smai-floating-assistant-chip--1">' in markup
    )
    assert "<span>AI予測インサイトをどう読む？</span>" in markup
    assert '<a class="smai-floating-assistant-chip"' not in markup
    assert "smai_assistant_question=" not in markup
    assert 'target="_blank"' not in markup
    assert "data:image/webp;base64," in markup


def test_floating_assistant_html_keeps_panel_closed_by_default():
    context = SmaiAssistantContext(
        context_id="ranking_setup",
        page_key="ranking",
        page_label="銘柄ランキング",
        section_key="setup",
        section_label="ランキング作成前",
        lead="条件を確認します。",
    )

    markup = floating_assistant_html(context)

    assert 'id="smai-assistant-ranking-setup-open" checked' not in markup
    assert 'class="smai-floating-assistant-backdrop"' in markup
    assert 'for="smai-assistant-ranking-setup-open"' in markup


def test_floating_assistant_html_escapes_context_and_answer_copy():
    context = SmaiAssistantContext(
        context_id="ranking_results",
        page_key="ranking",
        page_label="銘柄<ランキング>",
        section_key="ranking",
        section_label="ランキング<結果>",
        lead="候補 <script> を確認します。",
    )
    response = AssistantResponse(
        intent="ranking",
        answer="順位 <候補> を確認します。",
        reasons=["総合 <Score>: 72"],
        cautions=["売買 <推奨> ではありません。"],
        next_checkpoints=["コックピット <確認>"],
    )

    markup = floating_assistant_html(
        context,
        response=response,
        selected_question="なぜ <上位> ？",
        open_panel=True,
    )

    assert "銘柄&lt;ランキング&gt;" in markup
    assert "ランキング&lt;結果&gt;" in markup
    assert "候補 &lt;script&gt; を確認します。" in markup
    assert "なぜ &lt;上位&gt; ？" in markup
    assert "順位 &lt;候補&gt; を確認します。" in markup
    assert "総合 &lt;Score&gt;: 72" in markup


def test_floating_assistant_html_lists_related_contexts():
    current = SmaiAssistantContext(
        context_id="ranking_results",
        page_key="ranking",
        page_label="銘柄ランキング",
        section_key="ranking",
        section_label="ランキング結果",
        lead="候補を確認します。",
    )
    sibling = SmaiAssistantContext(
        context_id="ranking_deep_dive",
        page_key="ranking",
        page_label="銘柄ランキング",
        section_key="deep_dive",
        section_label="深掘り候補",
        lead="選択候補を確認します。",
    )

    markup = floating_assistant_html(current, sibling_contexts=(current, sibling))

    assert "関連セクション" in markup
    assert "深掘り候補" in markup
    assert "smai_assistant_context=ranking_deep_dive" in markup
    assert 'target="_self"' in markup


def test_floating_assistant_html_uses_ranking_visual_for_ranking_context():
    context = SmaiAssistantContext(
        context_id="ranking_results",
        page_key="ranking",
        page_label="銘柄ランキング",
        section_key="ranking_results",
        section_label="ランキング結果",
        lead="候補を確認します。",
    )

    markup = floating_assistant_html(context)

    assert "smai-floating-assistant-avatar--ranking" in markup
    assert "smai-assistant-rank-bars" in markup


def test_assistant_legacy_query_open_only_targets_current_context(monkeypatch):
    context = SmaiAssistantContext(
        context_id="news_overview",
        page_key="news",
        page_label="投資レーダー",
        section_key="overview",
        section_label="ニュース確認",
        lead="ニュースを確認します。",
    )
    monkeypatch.setattr(
        assistant_component.st,
        "query_params",
        {ASSISTANT_QUERY_CONTEXT_KEY: "cockpit_setup"},
        raising=False,
    )

    assert not _query_targets_current_context(context)

    monkeypatch.setattr(
        assistant_component.st,
        "query_params",
        {ASSISTANT_QUERY_CONTEXT_KEY: "news_overview"},
        raising=False,
    )

    assert _query_targets_current_context(context)


def test_fallback_assistant_context_uses_page_specific_copy():
    news = _fallback_assistant_context(page_key="news", page_label="投資レーダー")
    rebalance = _fallback_assistant_context(page_key="rebalance", page_label="リバランス")
    settings = _fallback_assistant_context(page_key="settings", page_label="設定 / データ情報")

    assert news.section_label == "ニュース確認"
    assert "市場ニュース" in news.lead
    assert "関連銘柄はどう読む？" in news.suggested_questions
    assert rebalance.section_label == "配分見直し"
    assert "目標比率" in rebalance.lead
    assert settings.section_label == "データ設定"
    assert "キャッシュ状態" in settings.lead


def test_assistant_trigger_label_varies_by_context():
    cases = (
        ("cockpit_setup", "cockpit", "setup", "データ取得前", "取得前の確認を聞く"),
        (
            "cockpit_forecast",
            "cockpit",
            "ai_forecast_insight",
            "AI予測インサイト",
            "予測の読み方を聞く",
        ),
        (
            "cockpit_direction",
            "cockpit",
            "direction_signal",
            "上昇気配・下降警戒",
            "シグナルの理由を聞く",
        ),
        ("cockpit_report", "cockpit", "decision_report", "確認レポート", "残す確認点を聞く"),
        ("ranking_setup", "ranking", "setup", "ランキング作成前", "条件設定を確認する"),
        ("ranking_results", "ranking", "ranking_results", "ランキング結果", "上位理由を聞く"),
        ("ranking_deep_dive", "ranking", "deep_dive_candidate", "深掘り候補", "候補の比べ方を聞く"),
        ("news_overview", "news", "overview", "ニュース確認", "ニュースの見方を聞く"),
        ("rebalance_overview", "rebalance", "overview", "配分見直し", "配分見直しを聞く"),
        ("settings_overview", "settings", "overview", "データ設定", "データ設定を確認する"),
    )
    for context_id, page_key, section_key, section_label, expected in cases:
        context = SmaiAssistantContext(
            context_id=context_id,
            page_key=page_key,
            page_label="画面",
            section_key=section_key,
            section_label=section_label,
            lead="確認します。",
        )

        assert _assistant_trigger_label(context) == expected
        markup = floating_assistant_html(context)
        assert expected in markup
        assert f"SMAIアシスタント: {expected}" in markup


def test_assistant_trigger_label_has_future_context_fallbacks():
    cases = (
        ("news_overview", "news", "market_news", "ニュース", "ニュースの見方を聞く"),
        ("risk_overview", "cockpit", "risk", "リスク確認", "リスクの見方を聞く"),
        ("rebalance_overview", "rebalance", "allocation", "配分調整", "配分見直しを聞く"),
        ("unknown_overview", "unknown", "overview", "画面の見方", "この画面の見どころを聞く"),
    )
    for context_id, page_key, section_key, section_label, expected in cases:
        context = SmaiAssistantContext(
            context_id=context_id,
            page_key=page_key,
            page_label="画面",
            section_key=section_key,
            section_label=section_label,
            lead="確認します。",
        )

        assert _assistant_trigger_label(context) == expected
