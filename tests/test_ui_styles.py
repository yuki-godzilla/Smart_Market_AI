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
    assert ".investment-news-freshness-badge" in SMAI_GLOBAL_CSS
    assert ".investment-news-freshness-time" in SMAI_GLOBAL_CSS
    assert ".investment-news-ticker-title" in SMAI_GLOBAL_CSS
    assert ".investment-news-card.compact" in SMAI_GLOBAL_CSS
    assert "height: auto;" in SMAI_GLOBAL_CSS
    assert "animation: investment-news-ticker-scroll 68s linear infinite;" in SMAI_GLOBAL_CSS
    assert "@keyframes investment-news-ticker-scroll" in SMAI_GLOBAL_CSS
    assert ".smai-insight" in SMAI_GLOBAL_CSS
    assert ".smai-insight-hero" in SMAI_GLOBAL_CSS
    assert ".smai-insight-range" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-condition-card" in SMAI_GLOBAL_CSS
    assert ".smai-ranking-weight-grid" in SMAI_GLOBAL_CSS
    assert "@media print" in SMAI_GLOBAL_CSS
    assert "break-inside: avoid;" in SMAI_GLOBAL_CSS
    assert "@keyframes smai-copilot-float" in SMAI_GLOBAL_CSS
    assert "translateY(-3px) scale(1.012)" in SMAI_GLOBAL_CSS
    assert ".smai-app-logo" in SMAI_GLOBAL_CSS
    assert "justify-items: center;" in SMAI_GLOBAL_CSS
    assert "width: min(43rem, 72vw);" in SMAI_GLOBAL_CSS
    assert "object-position: center center;" in SMAI_GLOBAL_CSS
    assert "object-fit: contain;" in SMAI_GLOBAL_CSS
    assert "@media (prefers-reduced-motion: reduce)" in SMAI_GLOBAL_CSS


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
    assert '[data-testid="stAppViewContainer"]' in SMAI_GLOBAL_CSS
    assert "background-color: var(--bg-page) !important;" in SMAI_GLOBAL_CSS
    assert "max-width: none;" in SMAI_GLOBAL_CSS
    assert '[data-testid="stButton"] button [data-testid="stMarkdownContainer"] p' in (
        SMAI_GLOBAL_CSS
    )
    assert '[data-testid="stButton"] button *' in SMAI_GLOBAL_CSS
    assert '"Inter", "Noto Sans JP", "BIZ UDPGothic"' in SMAI_GLOBAL_CSS
    assert "color: #F8FDFF;" in SMAI_GLOBAL_CSS
    assert "rgba(11, 58, 102, 0.98)" in SMAI_GLOBAL_CSS
    assert "0 0 12px rgba(34, 211, 238, 0.32)" in SMAI_GLOBAL_CSS
    assert "rgba(45, 212, 191, 0.98)" in SMAI_GLOBAL_CSS
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
