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
def test_my_radar_responsive_viewports() -> None:
    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_dir = Path("docs/responsive/screenshots/my_radar")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            for name, width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(base_url, wait_until="networkidle", timeout=120_000)
                if page.get_by_text("どのユーザーで使いますか？", exact=True).count():
                    page.get_by_text("SMAIデフォルト", exact=True).click()
                    page.get_by_text("このユーザーで開始", exact=True).click()
                    page.get_by_role("heading", name="銘柄コックピット", exact=True).wait_for(
                        state="visible",
                        timeout=60_000,
                    )
                sidebar_control = page.locator('[data-testid="stSidebarCollapsedControl"] button')
                if sidebar_control.count() and sidebar_control.is_visible():
                    sidebar_control.click()
                page.get_by_role("button", name="Myウォッチリスト", exact=True).click()
                sidebar_close = page.locator('[data-testid="stSidebarCollapseButton"] button')
                if sidebar_close.count() and sidebar_close.is_visible():
                    sidebar_close.click()
                page.wait_for_timeout(3_000)

                body_width = page.locator("body").evaluate(
                    "(element) => ({"
                    "scrollWidth: element.scrollWidth, "
                    "clientWidth: element.clientWidth"
                    "})"
                )
                assert body_width["scrollWidth"] <= body_width["clientWidth"] + 2
                assert page.locator('[data-testid="stException"], .stException').count() == 0
                assert page.get_by_text("Myウォッチリスト", exact=True).count() > 0
                assert page.get_by_text("ウォッチリストグループ", exact=True).count() > 0
                assert page.get_by_role("button", name="＋ グループを作成").is_visible()
                assert page.get_by_role("button").count() > 0
                page.get_by_role("button", name="＋ グループを作成").click()
                dialog = page.get_by_role("dialog")
                dialog.wait_for(state="visible", timeout=30_000)
                dialog.locator("input").first.wait_for(state="visible", timeout=30_000)
                assert dialog.locator("input").count() >= 1
                assert dialog.locator("textarea").is_visible()
                assert dialog.locator('[data-testid="stSelectbox"]').count() == 1
                dialog.get_by_role("button", name="キャンセル").click()
                dialog.wait_for(state="detached", timeout=30_000)

                page.screenshot(
                    path=str(screenshot_dir / f"{name}.png"),
                    full_page=True,
                )
                page.close()
        finally:
            browser.close()
