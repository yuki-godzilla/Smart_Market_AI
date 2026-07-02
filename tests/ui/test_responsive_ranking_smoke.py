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
    page.locator('a.smai-profile-link[aria-label="Yukiを選択"]:visible').first.click()
    page.wait_for_timeout(800)
    page.locator("a#smai-profile-start:visible").click()
    page.wait_for_timeout(8_000)


def _open_sidebar_target(page, label: str) -> None:
    sidebar_control = page.locator('[data-testid="stSidebarCollapsedControl"] button')
    if sidebar_control.count() and sidebar_control.is_visible():
        sidebar_control.click()
        page.wait_for_timeout(600)
    page.locator('section[data-testid="stSidebar"]').get_by_text(label, exact=True).click()


def _assert_modal_centered(page, viewport_width: int, viewport_height: int) -> None:
    overlay = page.locator('[data-testid="stDialog"]').last
    overlay.wait_for(state="visible", timeout=20_000)
    overlay_box = overlay.bounding_box()
    dialog_box = overlay.locator('[role="dialog"]').first.bounding_box()

    assert overlay_box is not None
    assert dialog_box is not None
    assert abs(overlay_box["x"]) <= 2
    assert abs(overlay_box["y"]) <= 2
    assert overlay_box["width"] >= viewport_width - 4
    assert overlay_box["height"] >= viewport_height - 4

    dialog_center_x = dialog_box["x"] + (dialog_box["width"] / 2)
    dialog_center_y = dialog_box["y"] + (dialog_box["height"] / 2)
    assert abs(dialog_center_x - (viewport_width / 2)) <= max(16, viewport_width * 0.08)
    assert abs(dialog_center_y - (viewport_height / 2)) <= max(24, viewport_height * 0.20)


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_RESPONSIVE_SMOKE") != "1",
    reason="Set SMAI_RUN_RESPONSIVE_SMOKE=1 with Streamlit running to enable.",
)
def test_ranking_responsive_viewports() -> None:
    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    screenshot_dir = Path("docs/responsive/screenshots/ranking")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            for name, width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(base_url, wait_until="networkidle", timeout=120_000)
                _start_app_session(page)
                _open_sidebar_target(page, "銘柄ランキング")
                sidebar_close = page.locator('[data-testid="stSidebarCollapseButton"] button')
                if sidebar_close.count() and sidebar_close.is_visible():
                    sidebar_close.click()
                page.wait_for_timeout(3_000)
                page.get_by_role("button", name="📚 ランキング履歴", exact=True).click()
                page.wait_for_timeout(1_500)
                assert page.get_by_text("ランキング履歴", exact=True).count() > 0
                assert (
                    page.locator(".smai-ranking-history-card").count() > 0
                    or page.get_by_text(
                        "保存済みのランキング履歴はありません。",
                        exact=False,
                    ).count()
                    > 0
                )
                cards = page.locator(".smai-ranking-history-card")
                for card_index in range(cards.count()):
                    card_shape = cards.nth(card_index).evaluate(
                        "(element) => ({"
                        "tag: element.tagName, "
                        "children: element.children.length, "
                        "scrollWidth: element.scrollWidth, "
                        "clientWidth: element.clientWidth"
                        "})"
                    )
                    assert card_shape["tag"] == "A"
                    assert card_shape["children"] == 5
                    assert card_shape["scrollWidth"] <= card_shape["clientWidth"] + 2
                    assert (
                        cards.nth(card_index).locator(".smai-ranking-history-card-action").count()
                        == 1
                    )
                detail_links = page.get_by_role(
                    "link",
                    name="ランキング履歴の詳細を見る",
                    exact=True,
                )
                if detail_links.count():
                    detail_links.first.click()
                    page.wait_for_timeout(1_500)
                    assert page.get_by_text("ランキング履歴詳細", exact=True).count() > 0
                    assert page.locator('[data-testid="stException"], .stException').count() == 0
                    assert page.locator(".smai-ranking-condition-card").count() == 2
                    assert 1 <= page.locator(".smai-metric-card").count() <= 5
                    page.get_by_role("button", name="ランキング画面へ戻る", exact=True).click()
                    page.wait_for_timeout(1_500)
                else:
                    page.get_by_role("button", name="← ランキングへ戻る", exact=True).click()
                    page.wait_for_timeout(1_500)
                page.get_by_role("button", name="国・市場を選ぶ", exact=True).click()
                _assert_modal_centered(page, width, height)

                body_width = page.locator("body").evaluate(
                    "(element) => ({"
                    "scrollWidth: element.scrollWidth, "
                    "clientWidth: element.clientWidth"
                    "})"
                )
                assert body_width["scrollWidth"] <= body_width["clientWidth"] + 2
                assert page.locator('[data-testid="stException"], .stException').count() == 0
                assert page.get_by_text("銘柄ランキング", exact=True).count() > 0
                assert page.get_by_role("button").count() > 0

                page.screenshot(
                    path=str(screenshot_dir / f"{name}_filter_modal.png"),
                    full_page=True,
                )
                page.close()
        finally:
            browser.close()
