from __future__ import annotations

from ui.components.mascot import (
    MASCOT_ASSET_DIR,
    MASCOT_LOADING_ASSET,
    MASCOT_VARIANT_ASSETS,
    MASCOT_VARIANT_DEFAULTS,
    app_header_html,
    mascot_loading_html,
    mascot_panel_html,
)


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


def test_app_header_html_embeds_small_mascot_and_escapes_message():
    markup = app_header_html("Smart <Market>", message="SMAI <ナビ>")

    assert 'class="smai-app-header"' in markup
    assert "Smart &lt;Market&gt;" in markup
    assert "SMAI &lt;ナビ&gt;" in markup
    assert 'class="smai-app-mascot"' in markup
    assert "data:image/webp;base64," in markup


def test_mascot_loading_html_uses_animation_classes():
    markup = mascot_loading_html(
        "cockpit",
        title="取得中",
        message="確認材料を整理中",
        tone="forecast",
    )

    assert "smai-mascot--loading" in markup
    assert 'data-tone="forecast"' in markup
    assert "smai-mascot-image--loading" in markup
    assert "smai-loading-dots" in markup
    assert "取得中" in markup


def test_mascot_expression_assets_exist_for_situation_variants():
    assert MASCOT_VARIANT_ASSETS["ranking"] == "smai-mascot-ranking.webp"
    assert MASCOT_VARIANT_ASSETS["caution"] == "smai-mascot-caution.webp"
    assert MASCOT_VARIANT_ASSETS["report"] == "smai-mascot-report.webp"
    assert MASCOT_LOADING_ASSET == "smai-mascot-loading.webp"

    for filename in {MASCOT_LOADING_ASSET, *MASCOT_VARIANT_ASSETS.values()}:
        assert (MASCOT_ASSET_DIR / filename).is_file()
