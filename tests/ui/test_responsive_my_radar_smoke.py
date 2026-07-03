from __future__ import annotations

import os
import re
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
                page.wait_for_timeout(3_000)
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
                assert page.get_by_role("button", name="＋ グループを作成").count() == 0
                assert page.get_by_role("button").count() > 0
                if name == "pc_1366":
                    assert (
                        page.get_by_role("button", name="グループを編集", exact=True).count() == 1
                    )
                    existing_header = page.get_by_role(
                        "button", name=re.compile(r"^[▶▼].*\d+件$")
                    ).first
                    if existing_header.count():
                        assert "linear-gradient" in existing_header.evaluate(
                            "(element) => getComputedStyle(element).backgroundImage"
                        )
                        assert (
                            existing_header.evaluate(
                                "(element) => getComputedStyle(element).borderLeftWidth"
                            )
                            == "5px"
                        )
                page.get_by_role("button", name="グループを編集", exact=True).click()
                editor = page.get_by_role("dialog")
                editor.wait_for(state="visible", timeout=30_000)
                editor.get_by_role("button", name="保存して閉じる").wait_for(
                    state="visible",
                    timeout=30_000,
                )
                if (
                    name == "pc_1366"
                    and page.locator(".smai-watchlist-group-header-marker").count() == 0
                ):
                    editor.locator('[data-testid="stExpander"] summary').first.click()
                    add_name = editor.locator("input").first
                    add_name.wait_for(state="visible", timeout=30_000)
                    add_name.fill("Tone smoke")
                    editor.get_by_role("button", name="追加", exact=True).click()
                    editor.get_by_role("button", name="保存して閉じる").wait_for(
                        state="visible", timeout=30_000
                    )
                component_frame = editor.locator("iframe")
                component_frame.wait_for(state="visible", timeout=30_000)
                if name == "pc_1366":
                    sortable_container = component_frame.content_frame.locator(
                        ".sortable-container"
                    ).first
                    sortable_container.wait_for(state="visible", timeout=30_000)
                    assert "rgba" in sortable_container.evaluate(
                        "(element) => getComputedStyle(element).backgroundColor"
                    )
                    component = component_frame.content_frame
                    assert component.get_by_role(
                        "button", name=re.compile(r".+を上へ")
                    ).first.is_visible()
                    assert component.get_by_role(
                        "button", name=re.compile(r".+を下へ")
                    ).first.is_visible()
                    edit_group = component.get_by_role("button", name=re.compile(r".+を編集")).first
                    assert edit_group.is_visible()
                    edit_group.click()
                    editor.get_by_text("D&D boardのグループ設定", exact=True).wait_for(
                        state="visible", timeout=30_000
                    )
                assert editor.locator("label").filter(has_text="移動先").count() == 0
                editor.get_by_role("button", name="キャンセル").click()
                editor.wait_for(state="detached", timeout=30_000)

                page.screenshot(
                    path=str(screenshot_dir / f"{name}.png"),
                    full_page=True,
                )
                page.close()
        finally:
            browser.close()
