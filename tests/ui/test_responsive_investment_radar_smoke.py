from __future__ import annotations

import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

VIEWPORTS = (
    ("iphone13mini", 375, 812),
    ("ipad8_portrait", 810, 1080),
    ("ipad8_landscape", 1080, 810),
    ("pc_1366", 1366, 768),
)


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_RESPONSIVE_SMOKE") != "1",
    reason="Set SMAI_RUN_RESPONSIVE_SMOKE=1 with Streamlit running to enable.",
)
def test_investment_radar_responsive_viewports() -> None:
    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_dir = Path(
        os.getenv(
            "SMAI_RESPONSIVE_SCREENSHOT_DIR",
            "docs/responsive/screenshots/investment_radar",
        )
    )
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            for name, width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(
                    f"{base_url}?smai_start_profile=local_user&smai_page=news",
                    wait_until="networkidle",
                    timeout=120_000,
                )
                sidebar = page.locator('[data-testid="stSidebar"]')
                if width <= 767:
                    assert sidebar.get_attribute("aria-expanded") == "false"
                if page.get_by_text("どのユーザーで使いますか？", exact=True).count():
                    page.locator(
                        'a.smai-profile-link[aria-label="Yukiを選択"]:visible'
                    ).first.click()
                    page.locator("a#smai-profile-start:visible").click()
                    page.get_by_text("投資レーダー", exact=True).wait_for(
                        state="visible", timeout=60_000
                    )
                page.wait_for_timeout(3_000)

                body_width = page.locator("body").evaluate(
                    "(element) => ({"
                    "scrollWidth: element.scrollWidth, "
                    "clientWidth: element.clientWidth"
                    "})"
                )
                assert body_width["scrollWidth"] <= body_width["clientWidth"] + 2
                assert page.locator('[data-testid="stException"], .stException').count() == 0
                assert page.get_by_text("投資レーダー", exact=True).count() > 0
                assert page.get_by_role("button").count() > 0
                assert page.get_by_role("tab").count() == 4
                heatmap_tile = page.locator("a.investment-stock-heatmap-tile").first
                heatmap_header = page.locator(".investment-stock-heatmap-group-header").first
                assert heatmap_tile.count() > 0
                assert heatmap_header.count() > 0
                assert str(heatmap_tile.get_attribute("href")).startswith("?smai_start_profile=")
                header_box = heatmap_header.bounding_box()
                assert header_box is not None
                assert header_box["height"] >= 40
                assert page.get_by_text("8セクター", exact=False).count() == 0
                assert page.locator(".investment-stock-heatmap-group-kind").count() > 0
                primary_theme_map = page.locator(".investment-stock-heatmap-board").first
                assert (
                    primary_theme_map.locator(":scope > .investment-stock-heatmap-group").count()
                    <= 3
                )
                primary_theme_surface = page.locator("section.investment-stock-heatmap").first
                assert (
                    primary_theme_surface.locator(
                        ".investment-stock-heatmap-legend.evidence"
                    ).count()
                    == 1
                )
                assert (
                    primary_theme_surface.locator(
                        ".investment-stock-heatmap-legend.neutral"
                    ).count()
                    == 1
                )
                assert (
                    primary_theme_surface.locator(
                        'a.investment-stock-heatmap-tile[class*="freshness-"]'
                    ).count()
                    > 0
                )
                if 768 <= width <= 900:
                    grid_column_count = primary_theme_map.evaluate(
                        "(element) => getComputedStyle(element).gridTemplateColumns"
                        ".split(' ').filter(Boolean).length"
                    )
                    assert grid_column_count == 1
                elif 901 <= width <= 1200:
                    grid_column_count = primary_theme_map.evaluate(
                        "(element) => getComputedStyle(element).gridTemplateColumns"
                        ".split(' ').filter(Boolean).length"
                    )
                    assert grid_column_count == 2
                primary_theme_surface.scroll_into_view_if_needed()
                page.screenshot(
                    path=str(screenshot_dir / f"{name}-theme-map.png"),
                    full_page=False,
                )
                if width <= 767:
                    tile_box = heatmap_tile.bounding_box()
                    assert tile_box is not None
                    assert tile_box["height"] >= 44
                    assistant_trigger = page.locator(".smai-floating-assistant-trigger")
                    assistant_box = assistant_trigger.bounding_box()
                    assert assistant_box is not None
                    assert 44 <= assistant_box["width"] <= 80
                    assert assistant_box["height"] >= 44
                    final_map_tile = primary_theme_map.locator(
                        "a.investment-stock-heatmap-tile"
                    ).last
                    final_map_tile.scroll_into_view_if_needed()
                    final_tile_box = final_map_tile.bounding_box()
                    assert final_tile_box is not None
                    assert final_tile_box["y"] + final_tile_box["height"] <= assistant_box["y"]

                page.get_by_role("tab", name="市場ヒートマップ").click()
                assert page.get_by_role("button", name="価格マップを更新").count() == 1
                assert page.get_by_text("価格はまだ取得していません", exact=False).count() == 1

                page.get_by_role("tab", name="ニュース一覧").click()
                assert page.locator(".investment-news-ticker-item").count() <= 3

                page.get_by_role("tab", name="ニュース・根拠").click()
                assert page.get_by_text("ニュース詳細フィルタ", exact=True).count() > 0
                page.get_by_text("詳しい探索条件", exact=True).wait_for(
                    state="visible", timeout=30_000
                )
                radar_heading = page.get_by_text("ニュースからの確認候補", exact=True)
                radar_heading.scroll_into_view_if_needed()
                detail_button = page.get_by_role("button", name="詳細を開く").first
                assert detail_button.count() == 1
                detail_button.click()
                dialog = page.locator('[data-testid="stDialog"]')
                dialog.wait_for(state="visible", timeout=30_000)
                assert (
                    dialog.locator(".investment-radar-candidate-detail-dialog-marker").count() == 1
                )
                assert dialog.get_by_text("選択中の候補", exact=False).count() > 0
                assert dialog.get_by_role("button", name="根拠資料を確認").count() == 1

                dialog_body_width = page.locator("body").evaluate(
                    "(element) => ({"
                    "scrollWidth: element.scrollWidth, "
                    "clientWidth: element.clientWidth"
                    "})"
                )
                assert dialog_body_width["scrollWidth"] <= dialog_body_width["clientWidth"] + 2

                page.screenshot(
                    path=str(screenshot_dir / f"{name}.png"),
                    full_page=True,
                )
                page.close()
        finally:
            browser.close()
