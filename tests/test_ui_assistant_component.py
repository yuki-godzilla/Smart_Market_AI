from __future__ import annotations

from backend.assistant import AssistantResponse
from ui.components.assistant import (
    SmaiAssistantContext,
    _assistant_trigger_label,
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
    assert "SMAI Copilot" in markup
    assert "AI予測インサイト" in markup
    assert "予測の読み方を聞く" in markup
    assert "中心予測とレンジを確認します。" in markup
    assert "smai-floating-assistant-avatar--forecast" in markup
    assert "smai-assistant-holo-chart" in markup
    assert "smai-assistant-holo-range" in markup
    assert "smai_assistant_context=cockpit_forecast" in markup
    assert "AI%E4%BA%88%E6%B8%AC" in markup
    assert 'target="_self"' in markup
    assert 'target="_blank"' not in markup
    assert "data:image/webp;base64," in markup


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
        ("cockpit_report", "cockpit", "decision_report", "投資判断レポート", "残す確認点を聞く"),
        ("ranking_setup", "ranking", "setup", "ランキング作成前", "条件設定を確認する"),
        ("ranking_results", "ranking", "ranking_results", "ランキング結果", "上位理由を聞く"),
        ("ranking_deep_dive", "ranking", "deep_dive_candidate", "深掘り候補", "候補の比べ方を聞く"),
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
        assert f"SMAI Copilot: {expected}" in markup


def test_assistant_trigger_label_has_future_context_fallbacks():
    cases = (
        ("news_overview", "news", "market_news", "ニュース", "根拠の見方を聞く"),
        ("risk_overview", "cockpit", "risk", "リスク確認", "リスクの見方を聞く"),
        ("rebalance_overview", "rebalance", "allocation", "配分調整", "調整ポイントを聞く"),
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
