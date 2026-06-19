from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.assistant import (  # noqa: E402
    build_assistant_research_tool_plan,
    detect_assistant_intent,
    route_assistant_conversation_mode,
)

FIXTURE_PATH = REPO_ROOT / "tests/fixtures/assistant_scenarios.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs/work/playwright_assistant_scenarios"


def main() -> None:
    parser = argparse.ArgumentParser(description="Network-free Phase 30-H Assistant scenario smoke")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "assistant_scenarios.html"
    screenshot_path = output_dir / "assistant_scenarios.png"
    scenarios = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    html_path.write_text(_document(scenarios), encoding="utf-8")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 1800})
        page.goto(html_path.as_uri())
        _assert_scenarios(page, scenarios)
        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()
    print(
        json.dumps(
            {"status": "ok", "scenario_count": len(scenarios), "html": str(html_path)},
            ensure_ascii=False,
            indent=2,
        )
    )


def _document(scenarios: list[dict[str, object]]) -> str:
    cards = []
    for scenario in scenarios:
        message = str(scenario["input"])
        legacy = detect_assistant_intent(message)
        decision = route_assistant_conversation_mode(message)
        plan = build_assistant_research_tool_plan(message, decision)
        subject = "候補確認"
        if plan is not None:
            subject = plan.company_name or plan.symbol or plan.symbol_query or "テーマ確認"
        cards.append(
            '<article class="scenario" data-scenario="'
            + html.escape(str(scenario["id"]))
            + '"><h2>'
            + html.escape(message)
            + "</h2><p>intent: "
            + html.escape(legacy.intent)
            + "</p><p>mode: "
            + html.escape(decision.conversation_mode)
            + "</p><p>対象: "
            + html.escape(subject)
            + "</p><small>売買推奨ではありません</small></article>"
        )
    loading = """
      <section class="loading" data-state="warming"><b>SMAIナビを起動しています…</b><span>LLM起動確認中</span><span>fallbackあり</span><p>市場ヘッドライン</p><small>前回更新: 2026-06-19 15:30</small></section>
      <section class="loading" data-state="ready"><b>LLM: 準備完了</b><input aria-label="相談内容"><button>送信</button></section>
      <section class="loading" data-state="failed"><b>LLM Gateway未接続</b><span>通常回答で対応中</span><span>fallbackあり</span></section>
    """
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>Assistant Scenario QA</title>
    <style>body{{background:#07111f;color:#e5edf7;font-family:Meiryo,sans-serif;margin:0}}main{{max-width:1180px;margin:auto;padding:24px;display:grid;gap:14px}}.scenario,.loading{{border:1px solid #27415f;border-radius:14px;background:#0d1a2b;padding:16px}}.scenario h2{{font-size:1rem}}.loading{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;color:#a5f3fc}}small{{color:#94a3b8}}</style></head><body><main><h1>SMAI Assistant Scenario QA</h1>{loading}{''.join(cards)}</main></body></html>"""


def _assert_scenarios(page: Page, scenarios: list[dict[str, object]]) -> None:
    page.get_by_text("SMAI Assistant Scenario QA").wait_for()
    assert page.locator("article.scenario").count() == len(scenarios)
    assert len(scenarios) >= 10
    for scenario in scenarios:
        card = page.locator(f'[data-scenario="{scenario["id"]}"]')
        card.get_by_text(str(scenario["input"]), exact=True).wait_for()
        card.get_by_text(f'intent: {scenario["legacy_intent"]}', exact=True).wait_for()
        card.get_by_text(f'mode: {scenario["conversation_mode"]}', exact=True).wait_for()
        text = card.inner_text()
        for forbidden in scenario.get("forbidden", []):
            assert str(forbidden) not in text
    page.locator('[data-state="warming"]').get_by_text("LLM起動確認中").wait_for()
    page.locator('[data-state="warming"]').get_by_text("市場ヘッドライン").wait_for()
    page.locator('[data-state="ready"]').get_by_text("LLM: 準備完了").wait_for()
    page.locator('[data-state="failed"]').get_by_text("通常回答で対応中").wait_for()


if __name__ == "__main__":
    main()
