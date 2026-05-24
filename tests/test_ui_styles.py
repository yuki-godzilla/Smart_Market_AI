from __future__ import annotations

from ui.styles import badge_html, compact_display_value, metric_card_html


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
        badges=(badge_html("Review", "info"),),
    )

    assert 'class="smai-metric-card"' in markup
    assert "Investment &lt;Score&gt;" in markup
    assert "72" in markup
    assert "確認 &lt;材料&gt;" in markup
    assert 'class="smai-badge info"' in markup
