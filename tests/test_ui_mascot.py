from __future__ import annotations

from ui.components.mascot import MASCOT_VARIANT_DEFAULTS, mascot_panel_html


def test_mascot_panel_html_embeds_lightweight_webp_and_variant_copy():
    markup = mascot_panel_html("ranking", layout="compact")

    assert 'class="smai-mascot smai-mascot--compact"' in markup
    assert 'data-variant="ranking"' in markup
    assert "data:image/webp;base64," in markup
    assert MASCOT_VARIANT_DEFAULTS["ranking"]["title"] in markup
    assert "売買推奨" not in MASCOT_VARIANT_DEFAULTS["ranking"]["message"]


def test_mascot_panel_html_escapes_custom_copy():
    markup = mascot_panel_html(
        "guide",
        title="<SMAI>",
        message="確認 <script> ポイント",
        layout="sidebar",
        tone="caution",
    )

    assert "&lt;SMAI&gt;" in markup
    assert "確認 &lt;script&gt; ポイント" in markup
    assert 'data-tone="caution"' in markup
    assert "smai-mascot--sidebar" in markup
