from __future__ import annotations

import os

import pytest

playwright = pytest.importorskip("playwright.sync_api")


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_USER_PROFILE_SMOKE") != "1",
    reason="Set SMAI_RUN_USER_PROFILE_SMOKE=1 with isolated Streamlit running.",
)
def test_user_creation_and_default_restrictions_at_desktop_and_smartphone() -> None:
    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8503")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            _verify_desktop_user_creation_and_default(browser, base_url)
            _verify_smartphone_add_user_form(browser, base_url)
        finally:
            browser.close()


def _verify_desktop_user_creation_and_default(browser, base_url: str) -> None:
    context = browser.new_context(viewport={"width": 1366, "height": 768})
    page = context.new_page()
    page.goto(base_url, wait_until="networkidle", timeout=120_000)
    page.get_by_text("どのユーザーで使いますか？", exact=True).wait_for(timeout=30_000)

    page.get_by_text("ユーザー追加", exact=True).click()
    page.get_by_role("heading", name="ユーザーを追加", exact=True).wait_for(timeout=30_000)
    page.get_by_role("textbox", name="表示名", exact=True).fill("U1 Verify")
    page.get_by_role("button", name="作成して開始", exact=True).click()
    page.get_by_role("heading", name="銘柄コックピット", exact=True).wait_for(timeout=60_000)

    user_area = page.locator("button.smai-user-trigger")
    user_area.wait_for(timeout=30_000)
    assert "U1 Verify" in user_area.inner_text()
    assert page.locator('[data-testid="stException"], .stException').count() == 0
    _assert_no_page_overflow(page)

    user_area.click()
    page.get_by_role("button", name="ユーザー切替", exact=True).click()
    page.get_by_text("どのユーザーで使いますか？", exact=True).wait_for(timeout=30_000)
    page.get_by_text("SMAIデフォルト", exact=True).click()
    page.get_by_text("このユーザーで開始", exact=True).click()
    page.get_by_role("heading", name="銘柄コックピット", exact=True).wait_for(timeout=60_000)

    default_area = page.locator("button.smai-user-trigger")
    default_area.wait_for(timeout=30_000)
    assert "SMAIデフォルト" in default_area.inner_text()
    assert page.locator(".smai-user-bell").count() == 0
    default_area.click()
    assert page.get_by_role("button", name="ユーザー切替", exact=True).is_visible()
    assert page.get_by_role("button", name="通知センター", exact=True).count() == 0
    assert page.get_by_role("button", name="通知設定", exact=True).count() == 0
    assert page.get_by_role("button", name="ユーザー設定", exact=True).count() == 0
    assert page.locator('[data-testid="stException"], .stException').count() == 0
    _assert_no_page_overflow(page)
    context.close()


def _verify_smartphone_add_user_form(browser, base_url: str) -> None:
    context = browser.new_context(viewport={"width": 375, "height": 812})
    page = context.new_page()
    page.goto(base_url, wait_until="networkidle", timeout=120_000)
    page.get_by_text("どのユーザーで使いますか？", exact=True).wait_for(timeout=30_000)
    page.get_by_text("ユーザー追加", exact=True).click()
    page.get_by_role("heading", name="ユーザーを追加", exact=True).wait_for(timeout=30_000)
    assert page.get_by_role("textbox", name="表示名", exact=True).is_visible()
    assert page.get_by_role("button", name="作成して開始", exact=True).is_visible()
    assert page.get_by_role("button", name="キャンセル", exact=True).is_visible()
    _assert_no_page_overflow(page)
    page.get_by_role("button", name="キャンセル", exact=True).click()
    page.get_by_role("heading", name="ユーザーを追加", exact=True).wait_for(
        state="detached", timeout=30_000
    )
    page.get_by_text("どのユーザーで使いますか？", exact=True).wait_for(timeout=30_000)
    context.close()


def _assert_no_page_overflow(page) -> None:
    dimensions = page.locator("body").evaluate(
        "(element) => ({scrollWidth: element.scrollWidth, clientWidth: element.clientWidth})"
    )
    assert dimensions["scrollWidth"] <= dimensions["clientWidth"] + 2
