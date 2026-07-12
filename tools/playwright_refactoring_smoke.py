from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("SMAI_STREAMLIT_URL", "http://127.0.0.1:8501")
OUTPUT_DIR = Path("outputs/work/refactoring_ui_smoke")


def _open_sidebar_target(page, label: str) -> None:
    collapsed = page.locator('[data-testid="stSidebarCollapsedControl"] button')
    if collapsed.count() and collapsed.is_visible():
        collapsed.click()
        page.wait_for_timeout(300)
    page.locator('section[data-testid="stSidebar"]').get_by_text(label, exact=True).click()
    page.wait_for_timeout(1_500)


def _close_sidebar(page) -> None:
    control = page.locator('[data-testid="stSidebarCollapseButton"] button')
    if control.count() and control.is_visible():
        control.click()
        page.wait_for_timeout(300)


def _assert_rendered(page, expected_text: str) -> dict[str, object]:
    page.get_by_text(expected_text, exact=True).first.wait_for(state="visible", timeout=15_000)
    exception_count = page.locator('[data-testid="stException"], .stException').count()
    assert exception_count == 0
    return {
        "title": expected_text,
        "buttons": page.get_by_role("button").count(),
        "links": page.get_by_role("link").count(),
        "exceptions": exception_count,
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {}
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20_000)
            profile_picker = page.get_by_text("どのユーザーで使いますか？", exact=True)
            try:
                profile_picker.wait_for(state="visible", timeout=10_000)
            except Exception:
                pass
            else:
                page.locator('a.smai-profile-link[aria-label="Yukiを選択"]:visible').first.click()
                page.locator('.smai-profile-card[data-selected="true"]').first.wait_for(
                    state="visible", timeout=30_000
                )
                page.locator("a#smai-profile-start:visible").click()
                page.get_by_role("heading", name="銘柄コックピット", exact=True).wait_for(
                    state="visible", timeout=60_000
                )

            for key, label, expected in (
                ("ranking", "銘柄ランキング", "銘柄ランキング"),
                ("cockpit", "銘柄コックピット", "銘柄コックピット"),
                ("assistant", "SMAIアシスタント", "SMAIアシスタント"),
            ):
                _open_sidebar_target(page, label)
                results[key] = _assert_rendered(page, expected)
                _close_sidebar(page)
                page.screenshot(path=str(OUTPUT_DIR / f"{key}_pc.png"), full_page=False)

            page.set_viewport_size({"width": 810, "height": 1080})
            _open_sidebar_target(page, "銘柄ランキング")
            results["ranking_tablet"] = _assert_rendered(page, "銘柄ランキング")
            _close_sidebar(page)
            tablet_body_width = page.locator("body").evaluate(
                "element => ({scrollWidth: element.scrollWidth, clientWidth: element.clientWidth})"
            )
            assert tablet_body_width["scrollWidth"] <= tablet_body_width["clientWidth"] + 2
            results["ranking_tablet"]["body_width"] = tablet_body_width
            page.screenshot(path=str(OUTPUT_DIR / "ranking_tablet.png"), full_page=False)

            page.set_viewport_size({"width": 375, "height": 812})
            _open_sidebar_target(page, "SMAIアシスタント")
            page.wait_for_timeout(500)
            results["assistant_mobile"] = _assert_rendered(page, "SMAIアシスタント")
            _close_sidebar(page)
            body_width = page.locator("body").evaluate(
                "element => ({scrollWidth: element.scrollWidth, clientWidth: element.clientWidth})"
            )
            assert body_width["scrollWidth"] <= body_width["clientWidth"] + 2
            results["assistant_mobile"]["body_width"] = body_width
            page.screenshot(path=str(OUTPUT_DIR / "assistant_mobile.png"), full_page=False)
        finally:
            browser.close()

    (OUTPUT_DIR / "result.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
