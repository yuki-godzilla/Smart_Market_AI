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
def test_cockpit_responsive_viewports() -> None:
    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_dir = Path("docs/responsive/screenshots/cockpit")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            for name, width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(base_url, wait_until="networkidle", timeout=120_000)
                page.wait_for_timeout(3_000)

                body_width = page.locator("body").evaluate(
                    "(element) => ({"
                    "scrollWidth: element.scrollWidth, "
                    "clientWidth: element.clientWidth"
                    "})"
                )
                assert body_width["scrollWidth"] <= body_width["clientWidth"] + 2
                assert page.locator('[data-testid="stException"], .stException').count() == 0
                assert page.get_by_role("button").count() > 0

                page.screenshot(
                    path=str(screenshot_dir / f"{name}.png"),
                    full_page=True,
                )
                page.close()
        finally:
            browser.close()


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_RESPONSIVE_CHART_SMOKE") != "1",
    reason="Set SMAI_RUN_RESPONSIVE_CHART_SMOKE=1 with Streamlit running to enable.",
)
def test_cockpit_chart_renders_inside_mobile_viewport() -> None:
    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_path = Path("docs/responsive/screenshots/cockpit/chart_iphone13mini.png")
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            page.goto(base_url, wait_until="networkidle", timeout=120_000)
            page.get_by_label("データ取得元").click()
            page.get_by_role("option", name="mock", exact=True).click()
            page.get_by_label("キーワード").fill("7203")
            page.wait_for_timeout(1_000)
            page.get_by_label("銘柄").click()
            page.get_by_role("option", name="7203.T", exact=False).click()
            page.get_by_role("button", name="データを取得", exact=True).click()
            page.wait_for_timeout(30_000)
            page.screenshot(path=str(screenshot_path), full_page=True)
            chart = page.locator('[data-testid="stVegaLiteChart"]').first
            if chart.count() == 0:
                visible_text = page.locator("body").inner_text()
                pytest.fail(f"Chart was not rendered. Visible page tail:\n{visible_text[-3000:]}")
            chart.wait_for(state="visible", timeout=30_000)

            chart_box = chart.bounding_box()
            assert chart_box is not None
            assert chart_box["width"] > 0
            assert chart_box["height"] > 0
            assert chart_box["x"] + chart_box["width"] <= 377
            assert chart.locator("canvas, svg").count() > 0
            assert page.locator('[data-testid="stException"], .stException').count() == 0

            chart.scroll_into_view_if_needed()
            page.screenshot(path=str(screenshot_path), full_page=False)
        finally:
            browser.close()
