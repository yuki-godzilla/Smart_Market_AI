"""Responsive interaction smoke checks for the two utility primary screens."""

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


def _start_app_session(page) -> None:
    page.wait_for_timeout(5_000)
    if not page.get_by_text("どのユーザーで使いますか？", exact=True).count():
        page.locator('section[data-testid="stSidebar"]').wait_for(state="visible", timeout=60_000)
        return
    page.locator('a.smai-profile-link[aria-label="SMAIデフォルトを選択"]:visible').first.click()
    page.locator("a#smai-profile-start:visible").click()
    page.get_by_role("heading", name="銘柄コックピット", exact=True).wait_for(
        state="visible", timeout=60_000
    )


def _open_sidebar_target(page, label: str) -> None:
    sidebar_control = page.locator('[data-testid="stSidebarCollapsedControl"] button')
    if sidebar_control.count() and sidebar_control.is_visible():
        sidebar_control.click()
        page.wait_for_timeout(500)
    page.locator('section[data-testid="stSidebar"]').get_by_role(
        "button", name=label, exact=True
    ).click()
    sidebar_close = page.locator('[data-testid="stSidebarCollapseButton"] button')
    if sidebar_close.count() and sidebar_close.is_visible():
        sidebar_close.click()


def _assert_responsive_contract(page) -> None:
    dimensions = page.locator("body").evaluate(
        "(element) => ({scrollWidth: element.scrollWidth, clientWidth: element.clientWidth})"
    )
    assert dimensions["scrollWidth"] <= dimensions["clientWidth"] + 2
    assert page.locator('[data-testid="stException"], .stException').count() == 0


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_RESPONSIVE_SMOKE") != "1",
    reason="Set SMAI_RUN_RESPONSIVE_SMOKE=1 with Streamlit running to enable.",
)
def test_rebalance_responsive_viewports() -> None:
    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_dir = Path("docs/responsive/screenshots/rebalance")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            for name, width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(base_url, wait_until="networkidle", timeout=120_000)
                _start_app_session(page)
                _open_sidebar_target(page, "リバランス")
                page.get_by_text("リバランス", exact=True).first.wait_for(
                    state="visible", timeout=60_000
                )
                page.get_by_role("button", name="配分見直しを確認", exact=True).click()
                page.get_by_text("サマリー", exact=True).wait_for(state="visible", timeout=30_000)
                page.get_by_text("リスク判定", exact=True).first.wait_for(
                    state="visible", timeout=30_000
                )
                _assert_responsive_contract(page)
                page.screenshot(path=str(screenshot_dir / f"{name}.png"), full_page=False)
                page.close()
        finally:
            browser.close()


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_RESPONSIVE_SMOKE") != "1",
    reason="Set SMAI_RUN_RESPONSIVE_SMOKE=1 with Streamlit running to enable.",
)
def test_settings_responsive_viewports() -> None:
    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_dir = Path("docs/responsive/screenshots/settings")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            for name, width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(base_url, wait_until="networkidle", timeout=120_000)
                _start_app_session(page)
                _open_sidebar_target(page, "設定 / データ情報")
                page.get_by_text("設定 / データ情報", exact=True).last.wait_for(
                    state="visible", timeout=60_000
                )
                page.get_by_text("サンプル銘柄", exact=True).wait_for(
                    state="visible", timeout=30_000
                )
                page.get_by_text("ランキング銘柄候補", exact=True).click()
                page.get_by_text("候補テーブルを表示（最大100件）", exact=True).click()
                page.get_by_text("候補CSV 全", exact=False).wait_for(
                    state="visible", timeout=30_000
                )
                _assert_responsive_contract(page)
                page.screenshot(path=str(screenshot_dir / f"{name}.png"), full_page=False)
                page.close()
        finally:
            browser.close()
