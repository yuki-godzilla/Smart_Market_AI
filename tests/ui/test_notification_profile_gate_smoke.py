from __future__ import annotations

import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

VIEWPORTS = (
    ("iphone13mini", 375, 812),
    ("ipad8_portrait", 810, 1080),
    ("pc_1366", 1366, 768),
)


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_NOTIFICATION_UI_SMOKE") != "1",
    reason="Set SMAI_RUN_NOTIFICATION_UI_SMOKE=1 with Streamlit running to enable.",
)
def test_profile_gate_then_fixed_user_area_at_responsive_viewports() -> None:
    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_dir = Path("docs/responsive/screenshots/notifications")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            for name, width, height in VIEWPORTS:
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()
                page.goto(base_url, wait_until="networkidle", timeout=120_000)
                page.get_by_text("どのユーザーで使いますか？", exact=True).wait_for(
                    state="visible", timeout=30_000
                )

                assert page.get_by_text("銘柄コックピット", exact=True).count() == 0
                assert page.locator('[data-testid="stSidebar"]').is_hidden()
                assert page.locator(".smai-profile-card img").count() >= 1
                assert page.get_by_text("SMAIデフォルト", exact=True).is_visible()
                assert page.get_by_text("Yuki", exact=True).is_visible()
                dimensions = page.locator("body").evaluate(
                    "(element) => ({scrollWidth: element.scrollWidth, "
                    "clientWidth: element.clientWidth})"
                )
                assert dimensions["scrollWidth"] <= dimensions["clientWidth"] + 2
                page.screenshot(
                    path=str(screenshot_dir / f"profile_gate_{name}.png"),
                    full_page=True,
                )

                page.get_by_role("button", name="Yukiを選択", exact=True).click()
                page.get_by_role("button", name="このユーザーで開始", exact=True).click()
                page.get_by_text("銘柄コックピット", exact=True).wait_for(
                    state="visible", timeout=60_000
                )
                user_area = page.get_by_role("button", name="SMAI_USER_AREA", exact=False)
                user_area.wait_for(state="visible", timeout=30_000)
                user_area.click()
                assert page.get_by_role("button", name="通知センター", exact=True).is_visible()
                assert page.get_by_text("カテゴリ", exact=True).count() == 0
                assert page.locator(".smai-notification-card").count() == 0
                page.get_by_role("button", name="通知センター", exact=True).click()
                page.get_by_role("heading", name="通知センター", exact=True).wait_for(
                    state="visible", timeout=30_000
                )
                assert page.get_by_text("カテゴリ", exact=True).is_visible()
                assert page.locator('[data-testid="stException"], .stException').count() == 0
                dimensions = page.locator("body").evaluate(
                    "(element) => ({scrollWidth: element.scrollWidth, "
                    "clientWidth: element.clientWidth})"
                )
                assert dimensions["scrollWidth"] <= dimensions["clientWidth"] + 2
                page.screenshot(
                    path=str(screenshot_dir / f"user_area_{name}.png"),
                    full_page=False,
                )
                context.close()
        finally:
            browser.close()
