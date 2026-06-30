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
                page.get_by_text("SMAIデフォルト", exact=True).wait_for(
                    state="visible", timeout=30_000
                )
                page.get_by_text("Yuki", exact=True).wait_for(state="visible", timeout=30_000)
                profile_names = page.locator(".smai-profile-name").all_text_contents()
                assert profile_names[:3] == ["Yuki", "SMAIデフォルト", "ユーザー追加"]
                dimensions = page.locator("body").evaluate(
                    "(element) => ({scrollWidth: element.scrollWidth, "
                    "clientWidth: element.clientWidth})"
                )
                assert dimensions["scrollWidth"] <= dimensions["clientWidth"] + 2
                page.screenshot(
                    path=str(screenshot_dir / f"profile_gate_{name}.png"),
                    full_page=True,
                )

                page.evaluate("window.__smaiProfileSelectionMarker = 'kept'")
                page.get_by_text("Yuki", exact=True).click()
                assert page.evaluate("window.__smaiProfileSelectionMarker") == "kept"
                page.get_by_text("Yuki", exact=True).wait_for(state="visible")
                selected_cards = page.locator('.smai-profile-card[data-selected="true"]')
                selected_cards.first.wait_for(state="visible", timeout=30_000)
                page.get_by_text("このユーザーで開始", exact=True).focus()
                page.mouse.move(width - 8, height - 8)
                assert selected_cards.count() >= 1
                assert (
                    page.locator(
                        '.smai-profile-link[data-user-id="local_user"][aria-current="true"]'
                    ).count()
                    >= 1
                )
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(100)
                page.screenshot(
                    path=str(screenshot_dir / f"profile_selected_{name}.png"),
                    full_page=True,
                )
                page.get_by_text("このユーザーで開始", exact=True).click()
                page.get_by_role("heading", name="銘柄コックピット", exact=True).wait_for(
                    state="visible", timeout=60_000
                )
                user_area = page.locator("button.smai-user-trigger")
                user_area.wait_for(state="visible", timeout=30_000)
                assert page.locator(".smai-user-avatar").count() == 1
                if width > 767:
                    assert "Yuki" in user_area.inner_text()
                else:
                    assert page.locator(".smai-user-name").is_hidden()
                initial_box = user_area.bounding_box()
                assert initial_box is not None
                assert 60 <= initial_box["y"] <= 120
                assert initial_box["x"] + initial_box["width"] <= width
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(250)
                scrolled_box = user_area.bounding_box()
                assert scrolled_box is not None
                assert abs(initial_box["y"] - scrolled_box["y"]) <= 2
                user_area.click()
                assert page.get_by_role("button", name="通知センター", exact=True).is_visible()
                assert page.get_by_role("button", name="ユーザー設定", exact=True).is_visible()
                assert page.get_by_role("button", name="通知設定", exact=True).is_visible()
                assert page.get_by_role("button", name="ユーザー切替", exact=True).is_visible()
                assert page.get_by_role("button", name="登録済み端末", exact=True).count() == 0
                page.get_by_role("button", name="通知センター", exact=True).click()
                page.get_by_role("heading", name="通知センター", exact=True).wait_for(
                    state="visible", timeout=30_000
                )
                assert page.locator('[data-testid="stSidebar"]').is_hidden()
                summaries = page.locator(".smai-notification-summary")
                assert summaries.count() >= 4
                assert summaries.filter(has_text="未読").count() >= 1
                assert summaries.filter(has_text="今日の通知").count() >= 1
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
