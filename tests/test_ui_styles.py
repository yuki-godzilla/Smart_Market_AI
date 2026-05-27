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
    assert ".smai-copilot-panel" in SMAI_GLOBAL_CSS
    assert ".smai-insight" in SMAI_GLOBAL_CSS
    assert "@keyframes smai-copilot-float" in SMAI_GLOBAL_CSS
    assert "translateY(-3px) scale(1.012)" in SMAI_GLOBAL_CSS
    assert "@media (prefers-reduced-motion: reduce)" in SMAI_GLOBAL_CSS


def test_global_theme_tokens_define_dark_financial_ai_palette():
    assert THEME_COLORS["bg_app"] == "#020510"
    assert THEME_COLORS["bg_card"] == "#111F35"
    assert THEME_COLORS["ai_cyan"] == "#22D3EE"
    assert THEME_COLORS["signal_buy"] == "#34D399"
    assert CHART_COLORS["prediction"] == THEME_COLORS["chart_prediction"]

    assert "--bg-app: #020510;" in SMAI_GLOBAL_CSS
    assert ".smai-ai-card" in SMAI_GLOBAL_CSS
    assert ".smai-investment-signal-badge.buy" in SMAI_GLOBAL_CSS
    assert '[data-testid="stVerticalBlockBorderWrapper"]' in SMAI_GLOBAL_CSS
    assert ".smai-page-title::before" in SMAI_GLOBAL_CSS
    assert ".smai-metric-card:hover" in SMAI_GLOBAL_CSS
    assert RANKING_GRID_CUSTOM_CSS[".ag-header"]["background-color"].startswith("#122038")
