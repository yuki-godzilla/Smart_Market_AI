from __future__ import annotations

from ui.styles import (
    CHART_COLORS,
    RANKING_GRID_CUSTOM_CSS,
    SMAI_GLOBAL_CSS,
    THEME_COLORS,
    badge_html,
    compact_display_value,
    metric_card_html,
)


def test_compact_display_value_formats_numeric_text_without_new_logic():
    assert compact_display_value("84.6900") == "84.7"
    assert compact_display_value("100.00") == "100"
    assert compact_display_value("12.340%") == "12.3%"
    assert compact_display_value("") == "-"
    assert compact_display_value("Review") == "Review"


def test_badge_html_escapes_label_and_limits_tone():
    assert badge_html("<Check>", "caution") == (
        '<span class="smai-badge caution">&lt;Check&gt;</span>'
    )
    assert badge_html("Unknown", "unexpected") == (
        '<span class="smai-badge neutral">Unknown</span>'
    )


def test_metric_card_html_uses_shared_card_classes_and_escapes_text():
    markup = metric_card_html(
        "Investment <Score>",
        "72.00",
        caption="確認 <材料>",
        help_text="指標 <説明>",
        badges=(badge_html("Review", "info"),),
    )

    assert 'class="smai-metric-card"' in markup
    assert "Investment &lt;Score&gt;" in markup
    assert "72" in markup
    assert "確認 &lt;材料&gt;" in markup
    assert 'class="smai-card-help"' in markup
    assert "指標 &lt;説明&gt;" in markup
    assert 'class="smai-badge info"' in markup


def test_global_css_defines_copilot_presence_and_insight_motion():
    assert "--smai-muted-readable" in SMAI_GLOBAL_CSS
    assert '[data-testid="stCaptionContainer"]' in SMAI_GLOBAL_CSS
    assert "font-size: 0.9rem" in SMAI_GLOBAL_CSS
    assert ".smai-page-title--copilot" in SMAI_GLOBAL_CSS
    assert ".smai-page-title-accessory" in SMAI_GLOBAL_CSS
    assert ".smai-copilot-panel" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-trigger" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-toggle" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-backdrop" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-toggle:checked ~ .smai-floating-assistant-backdrop" in (
        SMAI_GLOBAL_CSS
    )
    assert ".smai-floating-assistant-toggle:checked ~ .smai-floating-assistant-body" in (
        SMAI_GLOBAL_CSS
    )
    assert ".smai-floating-assistant-localqa" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-qa-item" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-chip > span" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-qa-item[open] > .smai-floating-assistant-chip" in (
        SMAI_GLOBAL_CSS
    )
    assert ".smai-floating-assistant-answer-panel--2" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-localqa:has(.smai-floating-assistant-qa-item--2[open])" in (
        SMAI_GLOBAL_CSS
    )
    assert ".smai-floating-assistant-answer-panel" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-chip" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-avatar img" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-stage" in SMAI_GLOBAL_CSS
    assert ".smai-floating-assistant-avatar::after" in SMAI_GLOBAL_CSS
    assert ".smai-copilot-chat-topbar" in SMAI_GLOBAL_CSS
    assert ".smai-copilot-header-icon" in SMAI_GLOBAL_CSS
    assert ".smai-copilot-header-icon img" in SMAI_GLOBAL_CSS
    assert ".smai-copilot-suggestions-title" in SMAI_GLOBAL_CSS
    assert 'div[data-testid="stChatMessage"]' in SMAI_GLOBAL_CSS
    assert 'div[data-testid="stChatInput"]' in SMAI_GLOBAL_CSS
    assert ".smai-copilot-answer-grid" in SMAI_GLOBAL_CSS
    assert (
        "@media (max-width: 767px) {\n" "    .smai-workflow-loading--blocking"
    ) in SMAI_GLOBAL_CSS
    assert "--smai-chat-main-width: 1180px;" in SMAI_GLOBAL_CSS
    assert ".smai-copilot-inline-sections" in SMAI_GLOBAL_CSS
    assert ".smai-copilot-natural-lead" in SMAI_GLOBAL_CSS
    assert ".smai-copilot-action-link" in SMAI_GLOBAL_CSS
    assert ".smai-assistant-holo-chart" in SMAI_GLOBAL_CSS
    assert ".smai-assistant-rank-bars" in SMAI_GLOBAL_CSS
    assert "@keyframes smai-buddy-curious" in SMAI_GLOBAL_CSS
    assert "@keyframes smai-buddy-notice" in SMAI_GLOBAL_CSS
    assert "@keyframes smai-holo-peek" in SMAI_GLOBAL_CSS
    assert ".investment-news-freshness-badge" in SMAI_GLOBAL_CSS
    assert ".investment-news-freshness-time" in SMAI_GLOBAL_CSS
    assert ".investment-news-ticker-title" in SMAI_GLOBAL_CSS
    assert ".investment-news-card.compact" in SMAI_GLOBAL_CSS
    assert "height: auto;" in SMAI_GLOBAL_CSS
    assert ".investment-news-board-page" in SMAI_GLOBAL_CSS
    assert ".investment-stock-heatmap-board" in SMAI_GLOBAL_CSS
    assert "@container (min-width: 78rem)" in SMAI_GLOBAL_CSS
    assert (
        ".investment-market-heatmap-groups {\n"
        "        grid-template-columns: repeat(3, minmax(0, 1fr));"
    ) in SMAI_GLOBAL_CSS
    assert "container-type: inline-size;" in SMAI_GLOBAL_CSS
    assert "@container (min-width: 78rem)" in SMAI_GLOBAL_CSS
    assert "@container (max-height: 3.6rem)" in SMAI_GLOBAL_CSS
    tablet_media = "@media (min-width: 768px) and (max-width: 1200px) {"
    assert tablet_media in SMAI_GLOBAL_CSS
    assert (
        ".investment-stock-heatmap-board {\n"
        "        grid-template-columns: repeat(2, minmax(0, 1fr));"
    ) in SMAI_GLOBAL_CSS
    assert (
        ".investment-market-heatmap-groups {\n" "        grid-template-columns: 1fr;"
    ) in SMAI_GLOBAL_CSS
    assert (
        ".investment-market-heatmap-group.medium .investment-market-heatmap-canvas"
        in SMAI_GLOBAL_CSS
    )
    assert (
        ".investment-market-heatmap-group.dense .investment-market-heatmap-canvas"
        in SMAI_GLOBAL_CSS
    )
    assert ".investment-market-news-context" in SMAI_GLOBAL_CSS
    assert ".investment-market-news-context.is-link:focus-visible" in SMAI_GLOBAL_CSS
    assert ".investment-radar-candidate-footer-list" in SMAI_GLOBAL_CSS
    assert ".investment-radar-candidate-footer-item:focus-visible" in SMAI_GLOBAL_CSS
    assert "min-height: 44px;" in SMAI_GLOBAL_CSS
    assert ".investment-market-heatmap-group-header span" in SMAI_GLOBAL_CSS
    assert "overflow-wrap: anywhere;" in SMAI_GLOBAL_CSS
    assert "animation-duration: var(--investment-news-board-duration)" in SMAI_GLOBAL_CSS
    assert ".investment-news-ticker-flow" in SMAI_GLOBAL_CSS
    assert "@keyframes investment-news-flow-pulse" in SMAI_GLOBAL_CSS
    assert "@keyframes investment-news-ticker-spotlight" in SMAI_GLOBAL_CSS
    assert "min-height: 15.4rem;" in SMAI_GLOBAL_CSS
    assert "grid-template-rows: repeat(2, minmax(4.9rem, auto));" in SMAI_GLOBAL_CSS
    assert "container-type: inline-size;" in SMAI_GLOBAL_CSS
    assert "@container (max-width: 36rem)" in SMAI_GLOBAL_CSS
    assert "grid-template-rows: repeat(3, minmax(6.1rem, auto));" in SMAI_GLOBAL_CSS
    assert "-webkit-line-clamp: 3;" in SMAI_GLOBAL_CSS
    assert "font-size: clamp(1rem, 1.18vw, 1.25rem);" in SMAI_GLOBAL_CSS
    assert "font-size: clamp(1rem, 1.2vw, 1.28rem);" in SMAI_GLOBAL_CSS
    assert ".investment-market-heatmap-tile.micro" in SMAI_GLOBAL_CSS
    assert "font-size: clamp(1.06rem, 1.26vw, 1.34rem);" in SMAI_GLOBAL_CSS
    assert ".investment-market-heatmap-group.singleton .investment-market-heatmap-canvas" in (
        SMAI_GLOBAL_CSS
    )
    assert ".smai-insight" in SMAI_GLOBAL_CSS
    assert ".smai-insight-hero" in SMAI_GLOBAL_CSS
    assert ".smai-insight-center-forecast" in SMAI_GLOBAL_CSS
    assert ".smai-insight-price-row" in SMAI_GLOBAL_CSS
    assert ".smai-insight-range" in SMAI_GLOBAL_CSS
    assert ".smai-insight-mini-grid" in SMAI_GLOBAL_CSS
    assert ".smai-insight-mini-field" in SMAI_GLOBAL_CSS
    assert "justify-content: space-between;" in SMAI_GLOBAL_CSS
    assert '.smai-insight-range > div[data-case="downside"]' in SMAI_GLOBAL_CSS
    assert '.smai-insight-range > div[data-case="upside"]' in SMAI_GLOBAL_CSS
    assert ".vega-embed" in SMAI_GLOBAL_CSS
    assert ".vega-embed {\n    width: 100%;" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-condition-card" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-weight-grid" in SMAI_GLOBAL_CSS
    assert (
        'div[data-testid="stDialog"] {\n    position: fixed !important;\n    inset: 0 !important;'
        in SMAI_GLOBAL_CSS
    )
    assert "place-items: center !important;" in SMAI_GLOBAL_CSS
    assert 'div[data-testid="stDialog"] div[role="dialog"] {' in SMAI_GLOBAL_CSS
    assert "dialog[open]" in SMAI_GLOBAL_CSS
    assert 'dialog,\n[role="dialog"],\n[data-testid="stDialog"]' not in SMAI_GLOBAL_CSS
    assert "@media print" in SMAI_GLOBAL_CSS
    assert "break-inside: avoid;" in SMAI_GLOBAL_CSS
    assert "@keyframes smai-copilot-float" in SMAI_GLOBAL_CSS
    assert "translateY(-2px) scale(1.008)" in SMAI_GLOBAL_CSS
    assert "max-height: min(66vh, 34rem);" in SMAI_GLOBAL_CSS
    assert "cursor: default;" in SMAI_GLOBAL_CSS
    assert "right: 0;" in SMAI_GLOBAL_CSS
    assert "bottom: 0;" in SMAI_GLOBAL_CSS
    assert ".smai-app-logo" in SMAI_GLOBAL_CSS
    assert "justify-items: center;" in SMAI_GLOBAL_CSS
    assert "width: min(43rem, 72vw);" in SMAI_GLOBAL_CSS
    assert "object-position: center center;" in SMAI_GLOBAL_CSS
    assert "object-fit: contain;" in SMAI_GLOBAL_CSS
    assert ".element-container:has(.smai-favorite-button-anchor)" in SMAI_GLOBAL_CSS
    assert '[data-testid="column"]:has(.smai-cockpit-favorite-action-anchor)' in SMAI_GLOBAL_CSS
    assert "@media (prefers-reduced-motion: reduce)" in SMAI_GLOBAL_CSS
    assert "Responsive baseline for LAN clients." in SMAI_GLOBAL_CSS
    assert ".smai-responsive-grid" in SMAI_GLOBAL_CSS
    assert ".smai-card-grid-responsive" in SMAI_GLOBAL_CSS
    assert "@media (min-width: 768px) and (max-width: 1024px)" in SMAI_GLOBAL_CSS
    assert ":has(.smai-copilot-composer-toolbar):has(" in SMAI_GLOBAL_CSS
    assert "flex: 0 1 30% !important;" in SMAI_GLOBAL_CSS
    assert "flex: 1 1 82% !important;" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-radar-grid" in SMAI_GLOBAL_CSS
    assert (
        "@media (min-width: 768px) and (max-width: 1024px) {\n"
        "    .smai-watchlist-radar-grid {\n"
        "        grid-template-columns: repeat(2, minmax(0, 1fr));"
    ) in SMAI_GLOBAL_CSS
    assert (
        "@media (max-width: 767px) {\n"
        "    .smai-watchlist-radar-grid {\n"
        "        grid-template-columns: 1fr;"
    ) in SMAI_GLOBAL_CSS
    assert '[data-testid="stDataFrame"]' in SMAI_GLOBAL_CSS
    assert '[data-testid="stDataEditor"]' in SMAI_GLOBAL_CSS
    assert '[data-testid="stPlotlyChart"]' in SMAI_GLOBAL_CSS
    assert '[data-testid="stVegaLiteChart"] canvas' in SMAI_GLOBAL_CSS
    assert "contain: inline-size;" in SMAI_GLOBAL_CSS
    assert "touch-action: manipulation;" in SMAI_GLOBAL_CSS
    assert "min-height: 44px;" in SMAI_GLOBAL_CSS
    assert "content-visibility: auto;" in SMAI_GLOBAL_CSS
    assert "contain-intrinsic-size: auto 18rem;" in SMAI_GLOBAL_CSS
    assert "Keep compact, scan-oriented KPI rows at two columns on a phone." in SMAI_GLOBAL_CSS
    assert "Two mutually exclusive actions stay together" in SMAI_GLOBAL_CSS
    assert '[data-testid="stMetric"]' in SMAI_GLOBAL_CSS
    assert "@media (max-width: 767px)" in SMAI_GLOBAL_CSS
    assert "@media (min-width: 1025px)" in SMAI_GLOBAL_CSS
    assert "repeat(3, minmax(0, 1fr))" in SMAI_GLOBAL_CSS
    assert "repeat(2, minmax(0, 1fr))" in SMAI_GLOBAL_CSS
    assert "overflow-wrap: anywhere;" in SMAI_GLOBAL_CSS
    assert "word-break: break-word;" in SMAI_GLOBAL_CSS
    assert "flex-wrap: wrap;" in SMAI_GLOBAL_CSS
    assert '[data-testid="stToastContainer"]' in SMAI_GLOBAL_CSS
    assert "bottom: max(0.85rem, env(safe-area-inset-bottom)) !important;" in SMAI_GLOBAL_CSS
    assert '[data-testid="stToast"]' in SMAI_GLOBAL_CSS
    assert "background: rgba(4, 18, 35, 0.98) !important;" in SMAI_GLOBAL_CSS


def test_global_theme_tokens_define_dark_financial_ai_palette():
    assert THEME_COLORS["bg_app"] == "#020510"
    assert THEME_COLORS["bg_card"] == "#111F35"
    assert THEME_COLORS["text_heading"] == "#EAF1FB"
    assert THEME_COLORS["text_value"] == "#F1F5F9"
    assert THEME_COLORS["text_ai_title"] == "#67E8F9"
    assert THEME_COLORS["text_positive"] == "#6EE7B7"
    assert THEME_COLORS["ai_cyan"] == "#22D3EE"
    assert THEME_COLORS["signal_buy"] == "#34D399"
    assert CHART_COLORS["prediction"] == THEME_COLORS["chart_prediction"]

    assert "--bg-page: #070D19;" in SMAI_GLOBAL_CSS
    assert "--bg-app: #020510;" in SMAI_GLOBAL_CSS
    assert ".smai-ai-card" in SMAI_GLOBAL_CSS
    assert "--text-value: #F1F5F9;" in SMAI_GLOBAL_CSS
    assert "font-size: 90%;" in SMAI_GLOBAL_CSS
    assert "rgba(30, 42, 62, 0.18)" in SMAI_GLOBAL_CSS
    assert ".smai-app-logo" in SMAI_GLOBAL_CSS
    assert "drop-shadow(0 0 18px rgba(34, 211, 238, 0.16))" in SMAI_GLOBAL_CSS
    assert '[data-testid="stAppViewContainer"]' in SMAI_GLOBAL_CSS
    assert "background-color: var(--bg-page) !important;" in SMAI_GLOBAL_CSS
    assert "max-width: none;" in SMAI_GLOBAL_CSS
    assert '[data-testid="stButton"] button [data-testid="stMarkdownContainer"] p' in (
        SMAI_GLOBAL_CSS
    )
    assert '[data-testid="stButton"] button *' in SMAI_GLOBAL_CSS
    assert '.smai-favorite-button-anchor[data-active="true"]' in SMAI_GLOBAL_CSS
    assert "background: linear-gradient(135deg, #075985 0%, #1D4ED8 100%)" in SMAI_GLOBAL_CSS
    assert "background: linear-gradient(135deg, #F59E0B 0%, #FACC15 100%)" in SMAI_GLOBAL_CSS
    assert (
        '.smai-favorite-button-anchor + div[data-testid="stButton"] button:focus-visible'
        in SMAI_GLOBAL_CSS
    )
    assert "border-color: #FDE047 !important;" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-card" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-radar-grid" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-filter-chip-anchor" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-card--upside" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-card--sharp-downside" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-movement" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-data-needed" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-remove-anchor" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-detail-anchor" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-cockpit-anchor" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-metric-grid" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-decision-title" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-decision-empty" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-metric--muted" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-refresh--fresh" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-refresh--failed" in SMAI_GLOBAL_CSS
    assert ".investment-news-symbol-chip-open-anchor" in SMAI_GLOBAL_CSS
    assert '"Inter", "Noto Sans JP", "BIZ UDPGothic"' in SMAI_GLOBAL_CSS
    assert "color: #F8FDFF;" in SMAI_GLOBAL_CSS
    assert "rgba(11, 58, 102, 0.98)" in SMAI_GLOBAL_CSS
    assert "0 0 12px rgba(34, 211, 238, 0.32)" in SMAI_GLOBAL_CSS
    assert "rgba(103, 232, 249, 0.98)" in SMAI_GLOBAL_CSS
    assert "background-position: 100% 50%;" in SMAI_GLOBAL_CSS
    assert ".ai-title" in SMAI_GLOBAL_CSS
    assert ".table-value" in SMAI_GLOBAL_CSS
    assert ".card-meta" in SMAI_GLOBAL_CSS
    assert ".smai-investment-signal-badge.buy" in SMAI_GLOBAL_CSS
    assert '[data-testid="stVerticalBlockBorderWrapper"]' in SMAI_GLOBAL_CSS
    assert ".smai-page-title::before" in SMAI_GLOBAL_CSS
    assert "rgba(17, 31, 53, 0.46)" in SMAI_GLOBAL_CSS
    assert ".smai-metric-card:hover" in SMAI_GLOBAL_CSS
    assert RANKING_GRID_CUSTOM_CSS[".ag-header"]["background-color"].startswith("#122038")
    assert RANKING_GRID_CUSTOM_CSS[".ag-cell"]["white-space"] == "nowrap"
    assert RANKING_GRID_CUSTOM_CSS[".ag-cell"]["text-overflow"] == "ellipsis"
    assert RANKING_GRID_CUSTOM_CSS[".ag-cell-value"]["white-space"] == "nowrap"


def test_global_css_defines_ranking_deep_dive_cta_layout():
    assert ".smai-ranking-deep-dive-select-anchor" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-deep-dive-cta-label" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-deep-dive-cta-anchor" in SMAI_GLOBAL_CSS
    assert "min-height: 3.95rem;" in SMAI_GLOBAL_CSS
    assert "rgba(14, 116, 144, 1)" in SMAI_GLOBAL_CSS
    assert "0 0 34px rgba(34, 211, 238, 0.22)" in SMAI_GLOBAL_CSS
    assert (
        ".smai-workflow-loading--blocking {\n    position: fixed;\n    z-index: 2000;\n    inset: 0;"
        in SMAI_GLOBAL_CSS
    )


def test_global_css_defines_ranking_history_cards_and_detail_layout():
    assert ".smai-ranking-history-card--alt" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-history-card--pinned" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-history-detail-summary" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-history-metric-card" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-history-nav-anchor--primary" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-history-nav-anchor--secondary" in SMAI_GLOBAL_CSS
