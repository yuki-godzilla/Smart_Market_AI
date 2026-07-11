"""Opt-in real-Streamlit user journeys spanning every primary SMAI screen."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")


def _assert_healthy_page(page) -> None:
    dimensions = page.locator("body").evaluate(
        "(element) => ({scrollWidth: element.scrollWidth, clientWidth: element.clientWidth})"
    )
    assert dimensions["scrollWidth"] <= dimensions["clientWidth"] + 2
    assert page.locator('[data-testid="stException"], .stException').count() == 0


def _start_default_user(page) -> None:
    if not page.get_by_text("どのユーザーで使いますか？", exact=True).count():
        return
    page.locator('a.smai-profile-link[aria-label="SMAIデフォルトを選択"]:visible').first.click()
    page.locator("a#smai-profile-start:visible").click()
    page.get_by_role("heading", name="銘柄コックピット", exact=True).wait_for(
        state="visible", timeout=60_000
    )


def _navigate(page, label: str, expected_text: str) -> None:
    sidebar_control = page.locator('[data-testid="stSidebarCollapsedControl"] button')
    if sidebar_control.count() and sidebar_control.is_visible():
        sidebar_control.click()
        page.wait_for_timeout(400)
    sidebar = page.locator('section[data-testid="stSidebar"]')
    sidebar.get_by_role("button", name=label, exact=True).click()
    page.get_by_text(expected_text, exact=True).first.wait_for(state="visible", timeout=60_000)
    sidebar_close = page.locator('[data-testid="stSidebarCollapseButton"] button')
    if sidebar_close.count() and sidebar_close.is_visible():
        sidebar_close.click()
    page.wait_for_timeout(500)
    _assert_healthy_page(page)


def _load_mock_cockpit(page) -> None:
    provider = page.get_by_label("データ取得元")
    provider.wait_for(state="visible", timeout=60_000)
    provider.click()
    page.get_by_role("option", name="mock", exact=True).click()
    page.get_by_label("キーワード").fill("7203.T")
    page.get_by_label("キーワード").press("Enter")
    page.get_by_label("銘柄").click()
    page.get_by_role("option", name="7203.T", exact=False).click()
    page.get_by_role("button", name="データを取得", exact=True).click()
    page.get_by_text("01 判断サマリー", exact=True).wait_for(state="visible", timeout=120_000)
    _assert_healthy_page(page)


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_UI_USER_PATH_SMOKE") != "1",
    reason="Set SMAI_RUN_UI_USER_PATH_SMOKE=1 with Streamlit running to enable.",
)
def test_path_1_confirm_symbol_then_review_watchlist_rebalance_and_settings() -> None:
    """Confirm a symbol, retain it for this session, then review allocation and data settings."""

    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_dir = Path("docs/responsive/screenshots/user_paths")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1366, "height": 768})
            page.goto(base_url, wait_until="networkidle", timeout=120_000)
            _start_default_user(page)
            _load_mock_cockpit(page)

            favorite = page.get_by_role("button", name=re.compile("お気に入り"))
            favorite.first.wait_for(state="visible", timeout=30_000)
            if "追加" in favorite.first.inner_text():
                favorite.first.click()
                page.get_by_role("button", name="★ お気に入り中", exact=True).wait_for(
                    state="visible", timeout=30_000
                )

            _navigate(page, "Myウォッチリスト", "Myウォッチリスト")
            page.get_by_text("7203.T", exact=False).first.wait_for(state="visible", timeout=30_000)

            _navigate(page, "リバランス", "リバランス")
            page.get_by_role("button", name="配分見直しを確認", exact=True).click()
            page.get_by_text("サマリー", exact=True).wait_for(state="visible", timeout=30_000)

            _navigate(page, "設定 / データ情報", "設定 / データ情報")
            page.get_by_text("サンプル銘柄", exact=True).wait_for(state="visible", timeout=30_000)
            _assert_healthy_page(page)
            page.screenshot(path=str(screenshot_dir / "path_1_settings_pc.png"), full_page=False)
        finally:
            browser.close()


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_UI_USER_PATH_SMOKE") != "1",
    reason="Set SMAI_RUN_UI_USER_PATH_SMOKE=1 with Streamlit running to enable.",
)
def test_path_2_scan_market_then_open_symbol_and_compare_ranking_conditions() -> None:
    """Scan market material, open a related symbol, then inspect ranking controls/history."""

    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_dir = Path("docs/responsive/screenshots/user_paths")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1366, "height": 768})
            page.goto(base_url, wait_until="networkidle", timeout=120_000)
            _start_default_user(page)

            _navigate(page, "投資レーダー", "投資レーダー")
            page.get_by_text("ニュース詳細フィルタ", exact=True).click()
            page.locator('[data-testid="stMultiSelect"]').first.click()
            page.keyboard.press("Escape")
            heatmap_tile = page.locator("a.investment-stock-heatmap-tile").first
            heatmap_tile.wait_for(state="visible", timeout=30_000)
            heatmap_tile.click()
            page.get_by_role("heading", name="銘柄コックピット", exact=True).wait_for(
                state="visible", timeout=60_000
            )

            _navigate(page, "銘柄ランキング", "銘柄ランキング")
            page.get_by_role("button", name="📚 ランキング履歴", exact=True).click()
            page.get_by_text("ランキング履歴", exact=True).wait_for(state="visible", timeout=30_000)
            page.get_by_role("button", name="← ランキングへ戻る", exact=True).click()
            page.get_by_role("button", name="国・市場を選ぶ", exact=True).click()
            page.get_by_role("dialog").wait_for(state="visible", timeout=30_000)
            page.get_by_role("button", name="キャンセル", exact=True).last.click()
            _assert_healthy_page(page)
            page.screenshot(path=str(screenshot_dir / "path_2_ranking_pc.png"), full_page=False)
        finally:
            browser.close()


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_UI_USER_PATH_SMOKE") != "1",
    reason="Set SMAI_RUN_UI_USER_PATH_SMOKE=1 with Streamlit running to enable.",
)
def test_path_3_ask_assistant_and_keep_the_composer_usable() -> None:
    """Send a concise assistance request and retain a usable, non-overflowing chat surface."""

    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_dir = Path("docs/responsive/screenshots/user_paths")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1366, "height": 768})
            page.goto(base_url, wait_until="networkidle", timeout=120_000)
            _start_default_user(page)

            _navigate(page, "SMAIアシスタント", "SMAIアシスタント")
            prompt = "ランキングで最初に確認する点を教えて"
            page.get_by_placeholder(
                "価格・予測・ニュース・根拠資料について確認したいことを入力..."
            ).fill(prompt)
            page.get_by_role("button", name="送信", exact=True).click()
            page.get_by_text(prompt, exact=True).wait_for(state="visible", timeout=30_000)
            page.get_by_placeholder(
                "価格・予測・ニュース・根拠資料について確認したいことを入力..."
            ).wait_for(state="visible", timeout=30_000)
            _assert_healthy_page(page)
            page.screenshot(path=str(screenshot_dir / "path_3_assistant_pc.png"), full_page=False)
        finally:
            browser.close()
