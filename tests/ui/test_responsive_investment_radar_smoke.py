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
    screenshot_dir = Path("docs/responsive/screenshots/investment_radar")
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
                sidebar_close = page.locator('[data-testid="stSidebarCollapseButton"] button')
                if sidebar_close.count() and sidebar_close.is_visible():
                    sidebar_close.evaluate("(element) => element.click()")
                    page.keyboard.press("Escape")
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
                heatmap_tile = page.locator("a.investment-stock-heatmap-tile").first
                heatmap_header = page.locator(".investment-stock-heatmap-group-header").first
                assert heatmap_tile.count() > 0
                assert heatmap_header.count() > 0
                assert str(heatmap_tile.get_attribute("href")).startswith("?smai_start_profile=")
                header_box = heatmap_header.bounding_box()
                assert header_box is not None
                assert header_box["height"] >= 40

                page.screenshot(
                    path=str(screenshot_dir / f"{name}.png"),
                    full_page=True,
                )
                page.close()
        finally:
            browser.close()
