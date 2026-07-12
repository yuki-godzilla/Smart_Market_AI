"""Opt-in real-Streamlit smoke for the standard hybrid RAG result path."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")


def _start_default_user(page) -> None:
    profile_picker = page.get_by_text("どのユーザーで使いますか？", exact=True)
    try:
        # The profile picker is rendered after Streamlit's initial shell.  A
        # synchronous count immediately after navigation can race that render.
        profile_picker.wait_for(state="visible", timeout=10_000)
    except playwright.TimeoutError:
        return
    page.locator('a.smai-profile-link[aria-label="SMAIデフォルトを選択"]:visible').first.click()
    # Selecting a profile triggers a Streamlit rerun.  Wait for the selected
    # profile card before following the start link; otherwise a fast browser
    # can continue on a half-rendered Cockpit where form labels are absent.
    page.locator('.smai-profile-card[data-selected="true"]').first.wait_for(
        state="visible", timeout=30_000
    )
    page.locator("a#smai-profile-start:visible").click()


@pytest.mark.skipif(
    os.getenv("SMAI_RUN_RAG_UI_SMOKE") != "1",
    reason="Set SMAI_RUN_RAG_UI_SMOKE=1 with Streamlit running to enable.",
)
def test_cockpit_ai_research_exposes_hybrid_retrieval_mode() -> None:
    """Use the real Cockpit action and retain a transparent hybrid-search result."""

    base_url = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
    output_path = Path("outputs/work/rag_hybrid_streamlit_smoke_7203_T.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1366, "height": 768})
            # Streamlit keeps a WebSocket open for session updates, so its page
            # does not reliably become "networkidle".  The visible Cockpit
            # heading below is the meaningful readiness condition.
            page.goto(base_url, wait_until="domcontentloaded", timeout=120_000)
            _start_default_user(page)
            page.get_by_role("heading", name="銘柄コックピット", exact=True).wait_for(
                state="visible", timeout=60_000
            )
            provider = page.get_by_label("データ取得元")
            provider.wait_for(state="visible", timeout=60_000)
            provider.click()
            page.get_by_role("option", name="mock", exact=True).click()
            symbol_query = page.get_by_label("キーワード")
            symbol_query.wait_for(state="visible", timeout=30_000)
            symbol_query.fill("7203.T")
            symbol_query.press("Enter")
            page.wait_for_timeout(1_000)
            page.get_by_label("銘柄").click()
            page.get_by_role("option", name="7203.T", exact=False).click()
            page.get_by_role("button", name="データを取得", exact=True).click()
            page.get_by_text("01 判断サマリー", exact=True).wait_for(
                state="visible", timeout=120_000
            )
            page.get_by_role("button", name="AI調査を開始・更新", exact=True).click()
            page.get_by_text("企業リサーチサマリー", exact=True).wait_for(
                state="visible", timeout=120_000
            )
            retrieval_mode = page.get_by_text(re.compile(r"^検索方式:"), exact=False).last
            retrieval_mode.wait_for(state="visible", timeout=30_000)
            retrieval_mode.scroll_into_view_if_needed()

            assert "ハイブリッド検索" in retrieval_mode.inner_text()
            assert page.locator('[data-testid="stException"], .stException').count() == 0
            dimensions = page.locator("body").evaluate(
                "(element) => ({scrollWidth: element.scrollWidth, clientWidth: element.clientWidth})"
            )
            assert dimensions["scrollWidth"] <= dimensions["clientWidth"] + 2
            page.screenshot(path=str(output_path), full_page=False)
        finally:
            browser.close()
