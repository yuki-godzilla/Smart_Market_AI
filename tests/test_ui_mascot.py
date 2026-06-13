from __future__ import annotations

from ui.components.mascot import (
    APP_LOGO_ASSET,
    BRAND_ASSET_DIR,
    MASCOT_ASSET_DIR,
    MASCOT_CUTOUT_ASSET,
    MASCOT_LOADING_ASSET,
    MASCOT_REFERENCE_ASSET,
    MASCOT_TITLE_ASSETS,
    MASCOT_VARIANT_ASSETS,
    MASCOT_VARIANT_DEFAULTS,
    app_header_html,
    copilot_presence_panel_html,
    mascot_loading_html,
    mascot_panel_html,
    page_title_html,
    smai_insight_html,
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
    assert '<h1 class="smai-app-title"' not in markup
    assert 'class="smai-app-logo"' in markup
    assert 'alt="Smart &lt;Market&gt;"' in markup
    assert "SMAI &lt;ナビ&gt;" in markup
    assert 'class="smai-app-mascot"' in markup
    assert "data:image/png;base64," in markup
    assert "data:image/webp;base64," in markup


def test_brand_logo_asset_exists_for_app_header():
    assert APP_LOGO_ASSET == "smai-logo.png"
    assert (BRAND_ASSET_DIR / APP_LOGO_ASSET).is_file()


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


def test_page_title_html_uses_screen_specific_mascot_asset_and_escapes_copy():
    markup = page_title_html(
        "銘柄<ランキング>",
        "比較 <候補> を整理します。",
        "ranking",
    )

    assert 'class="smai-page-title"' in markup
    assert 'data-mascot="ranking"' in markup
    assert 'class="smai-page-title-row"' in markup
    assert "銘柄&lt;ランキング&gt;" in markup
    assert "比較 &lt;候補&gt; を整理します。" in markup
    assert "smai-page-title-image" in markup
    assert "data:image/webp;base64," in markup


def test_page_title_html_can_include_top_right_accessory():
    markup = page_title_html(
        "投資レーダー",
        "市場ニュースを確認します。",
        "investment_radar",
        accessory_html='<span class="demo-accessory">情報鮮度 最新</span>',
    )

    assert 'class="smai-page-title-accessory"' in markup
    assert '<span class="demo-accessory">情報鮮度 最新</span>' in markup


def test_cockpit_page_title_uses_copilot_presence_panel():
    markup = page_title_html(
        "銘柄<コックピット>",
        "価格 <予測> と根拠を確認します。",
        "cockpit",
    )

    assert 'class="smai-page-title smai-page-title--copilot"' in markup
    assert 'data-mascot="cockpit"' in markup
    assert "銘柄&lt;コックピット&gt;" in markup
    assert "価格 &lt;予測&gt; と根拠を確認します。" in markup
    assert "SMAIアシスタント" in markup
    assert "Market Ready" in markup
    assert "smai-copilot-panel" in markup
    assert "smai-page-title-art" in markup
    assert "smai-page-title-image" in markup
    assert "data:image/webp;base64," in markup
    assert "data:image/png;base64," in markup


def test_copilot_presence_panel_html_uses_cutout_and_escapes_copy():
    markup = copilot_presence_panel_html(
        status="Ready <OK>",
        message="確認 <script> を整理します。",
        state="ready",
    )

    assert 'class="smai-copilot-panel"' in markup
    assert 'data-state="ready"' in markup
    assert "Ready &lt;OK&gt;" in markup
    assert "確認 &lt;script&gt; を整理します。" in markup
    assert "smai-copilot-status-dot" in markup
    assert "smai-copilot-image" in markup
    assert "data:image/png;base64," in markup


def test_smai_insight_html_connects_comment_area_to_copilot_context():
    markup = smai_insight_html(
        "短期 <確認> は慎重に見ます。",
        title="SMAI <Insight>",
        tone="caution",
    )

    assert 'class="smai-insight"' in markup
    assert 'data-tone="caution"' in markup
    assert "SMAI &lt;Insight&gt;" in markup
    assert "短期 &lt;確認&gt; は慎重に見ます。" in markup
    assert "data:image/png;base64," in markup


def test_mascot_expression_assets_exist_for_situation_variants():
    assert MASCOT_VARIANT_ASSETS["ranking"] == "smai-mascot-ranking.webp"
    assert MASCOT_VARIANT_ASSETS["caution"] == "smai-mascot-caution.webp"
    assert MASCOT_VARIANT_ASSETS["report"] == "smai-mascot-report.webp"
    assert MASCOT_LOADING_ASSET == "smai-mascot-loading.webp"
    assert MASCOT_REFERENCE_ASSET == "smai-mascot-reference.webp"
    assert MASCOT_CUTOUT_ASSET == "smai-mascot-cutout.png"

    for filename in {
        MASCOT_CUTOUT_ASSET,
        MASCOT_REFERENCE_ASSET,
        MASCOT_LOADING_ASSET,
        *MASCOT_VARIANT_ASSETS.values(),
        *MASCOT_TITLE_ASSETS.values(),
    }:
        assert (MASCOT_ASSET_DIR / filename).is_file()


def test_copilot_cutout_asset_is_rgba_png():
    data = (MASCOT_ASSET_DIR / MASCOT_CUTOUT_ASSET).read_bytes()

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    assert data[25] == 6
