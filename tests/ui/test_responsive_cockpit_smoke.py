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


def _enter_cockpit(page) -> None:
    cockpit_heading = page.get_by_role("heading", name="銘柄コックピット", exact=True)
    profile_gate = page.get_by_text("どのユーザーで使いますか？", exact=True)
    page.wait_for_timeout(1_000)
    if not (cockpit_heading.count() and cockpit_heading.is_visible()):
        profile_gate.wait_for(state="visible", timeout=30_000)
        page.get_by_text("Yuki", exact=True).click()
        page.locator('.smai-profile-card[data-selected="true"]').first.wait_for(
            state="visible", timeout=30_000
        )
        page.get_by_text("このユーザーで開始", exact=True).click()
    cockpit_heading.wait_for(state="visible", timeout=60_000)
    page.get_by_label("データ取得元").wait_for(state="visible", timeout=60_000)


def _load_mock_cockpit_result(page) -> None:
    _enter_cockpit(page)
    page.get_by_label("データ取得元").click()
    page.get_by_role("option", name="mock", exact=True).click()
    page.get_by_label("キーワード").wait_for(state="visible", timeout=30_000)
    page.get_by_label("キーワード").fill("7203.T")
    page.get_by_label("キーワード").press("Enter")
    page.wait_for_timeout(2_000)
    page.get_by_label("銘柄").click()
    page.get_by_role("option", name="7203.T", exact=False).click()
    page.get_by_role("button", name="データを取得", exact=True).click()
    page.get_by_text("01 判断サマリー", exact=True).wait_for(state="visible", timeout=120_000)
    page.get_by_text("予測設定を変更", exact=True).last.click()
    page.get_by_label("予測日数").last.fill("1")
    page.get_by_label("予測日数").last.press("Enter")
    page.get_by_text("予測期間: 1日", exact=True).wait_for(state="visible", timeout=60_000)
    page.get_by_text("予測設定を変更", exact=True).last.click()
    page.get_by_text("05 確認レポート", exact=True).wait_for(state="visible", timeout=120_000)


def _assert_cockpit_result_contract(page, viewport_width: int) -> None:
    dimensions = page.locator("body").evaluate(
        "(element) => ({scrollWidth: element.scrollWidth, " "clientWidth: element.clientWidth})"
    )
    assert dimensions["scrollWidth"] <= dimensions["clientWidth"] + 2
    assert page.locator('[data-testid="stException"], .stException').count() == 0
    expected_sections = [
        "01 判断サマリー",
        "02 価格・AI予測",
        "03 AI調査・材料分析",
        "04 確認メモ",
        "05 確認レポート",
    ]
    page.wait_for_function(
        "(sections) => sections.every((section) => document.body.innerText.includes(section))",
        arg=expected_sections,
        timeout=120_000,
    )
    section_text = page.locator("body").inner_text()
    section_positions = [section_text.index(section) for section in expected_sections]
    assert section_positions == sorted(section_positions)
    assert section_text.count("04 確認メモ") == 1
    assert "スコアから見た注意点" in section_text

    kpi_labels = page.locator(".smai-card-label").all_text_contents()
    required_kpi_labels = {"投資スコア", "上昇気配", "下降警戒", "データ信頼度"}
    assert required_kpi_labels.issubset(set(kpi_labels))
    assert kpi_labels.count("投資スコア") == 1
    research_card = page.locator(".research-ai-cta--hero")
    assert research_card.count() == 1
    research_text = research_card.inner_text()
    assert "AI調査はまだ未取得です" in research_text
    assert "調査アクション" not in research_text
    assert "確認方針" not in research_text
    assert "売買推奨ではありません" not in research_text
    assert "企業理解のための情報整理" not in research_text
    assert research_card.get_by_text("AI調査はまだ未取得です", exact=True).count() == 1
    research_button = page.get_by_role("button", name="AI調査を開始・更新", exact=True)
    research_button.wait_for(state="visible")
    button_box = research_button.bounding_box()
    assert button_box is not None
    assert button_box["width"] > 0
    assert button_box["height"] >= (40 if viewport_width <= 1024 else 36)
    assert button_box["x"] + button_box["width"] <= viewport_width + 2

    page.get_by_text("詳細データ・開発者向け", exact=True).click()
    tab_names = ["予測", "スコア", "取得元", "特徴量", "エクスポート"]
    for tab_name in tab_names:
        tab = page.get_by_role("tab", name=tab_name, exact=True)
        tab.wait_for(state="visible")
        tab.click()
        assert tab.get_attribute("aria-selected") == "true"
    detail_expander = page.locator("details").filter(has_text="詳細データ・開発者向け").last
    if detail_expander.get_attribute("open") is not None:
        detail_expander.locator(":scope > summary").click()
    page.locator(".smai-dashboard-header").last.scroll_into_view_if_needed()
    page.wait_for_timeout(300)


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
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()
                page.goto(base_url, wait_until="networkidle", timeout=120_000)
                _load_mock_cockpit_result(page)
                _assert_cockpit_result_contract(page, width)

                page.screenshot(
                    path=str(screenshot_dir / f"{name}.png"),
                    full_page=False,
                )
                page.locator(".research-ai-cta--hero").scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                page.screenshot(
                    path=str(screenshot_dir / f"{name}_research.png"),
                    full_page=False,
                )
                context.close()
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
            _load_mock_cockpit_result(page)
            page.screenshot(path=str(screenshot_path), full_page=True)
            chart = page.locator('[data-testid="stVegaLiteChart"]').first
            if chart.count() == 0:
                visible_text = page.locator("body").inner_text()
                chart_test_ids = page.locator('[data-testid*="Chart"]').evaluate_all(
                    "(elements) => elements.map((element) => element.dataset.testid)"
                )
                pytest.fail(
                    "Chart was not rendered with the expected test id. "
                    f"Chart test ids: {chart_test_ids}; canvas count: "
                    f"{page.locator('canvas').count()}.\nVisible page tail:\n{visible_text[-3000:]}"
                )
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
