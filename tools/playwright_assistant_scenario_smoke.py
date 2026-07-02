from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.assistant import (  # noqa: E402
    AssistantLoadingHeadline,
    AssistantLoadingHeadlines,
    AssistantWarmupStatus,
    build_assistant_research_tool_plan,
    decide_assistant_action_cards,
    detect_assistant_intent,
    route_assistant_conversation_mode,
)
from ui.components.mascot import MASCOT_TITLE_ASSETS, STATIC_ASSET_DIR  # noqa: E402
from ui.views.copilot import copilot_loading_panel_html  # noqa: E402

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
    loading_screenshot_path = output_dir / "assistant_scenarios_loading.png"
    screenshot_path = output_dir / "assistant_scenarios.png"
    scenarios = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    html_path.write_text(_document(scenarios), encoding="utf-8")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 1800})
        page.goto(html_path.as_uri())
        page.locator('[data-state="warming"]').get_by_text("LLM起動確認中").wait_for()
        page.screenshot(path=str(loading_screenshot_path), full_page=True)
        _assert_scenarios(page, scenarios)
        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()
    print(
        json.dumps(
            {
                "status": "ok",
                "scenario_count": len(scenarios),
                "html": str(html_path),
                "loading_screenshot": str(loading_screenshot_path),
            },
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
        card_decision = decide_assistant_action_cards(message, legacy.intent)
        plan = build_assistant_research_tool_plan(message, decision)
        subject = "候補確認"
        if plan is not None:
            subject = plan.company_name or plan.symbol or plan.symbol_query or "テーマ確認"
        action_card = (
            '<div class="action-card">次にできること</div>' if card_decision.show_cards else ""
        )
        cards.append(
            '<article class="scenario" data-scenario="'
            + html.escape(str(scenario["id"]))
            + '"><h2>'
            + html.escape(message)
            + "</h2><p>intent: "
            + html.escape(legacy.intent)
            + "</p><p>mode: "
            + html.escape(decision.conversation_mode)
            + "</p><p>action-level: "
            + str(card_decision.level)
            + "</p><p>対象: "
            + html.escape(subject)
            + "</p>"
            + action_card
            + "<small>売買推奨ではありません</small></article>"
        )
    loading_panel = copilot_loading_panel_html(
        AssistantWarmupStatus(
            state="warming",
            step="LLM Gatewayに接続中",
            message="準備中もSMAI標準ナビを利用できます。",
            attempt=1,
        ),
        headlines=AssistantLoadingHeadlines(
            items=(
                AssistantLoadingHeadline(
                    title="半導体関連の決算材料を確認しています",
                    category="米国株",
                    source="前回ニュース",
                ),
                AssistantLoadingHeadline(
                    title="金融株は金利動向との関係を確認します",
                    category="国内株",
                    source="市場サマリ",
                ),
            ),
            updated_at=datetime(2026, 6, 19, 15, 30, tzinfo=UTC),
            source="cache",
            stale=False,
        ),
        radar_asset_uri=(
            STATIC_ASSET_DIR / "mascot" / MASCOT_TITLE_ASSETS["investment_radar"]
        ).as_uri(),
    )
    loading = f"""
      <div data-state="warming">{loading_panel}</div>
      <section class="ready" data-state="ready" hidden><b>準備完了</b><span>SMAIナビの準備ができました。</span></section>
      <div class="composer"><input id="draft" aria-label="相談内容" placeholder="相談内容"><button>送信</button></div>
      <section class="loading" data-state="failed"><b>LLM Gateway未接続</b><span>通常回答で対応中</span><span>fallbackあり</span><input aria-label="fallback相談内容"></section>
      <script>setTimeout(() => {{ document.querySelector('[data-state="warming"]').hidden = true; document.querySelector('[data-state="ready"]').hidden = false; }}, 700);</script>
    """
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>Assistant Scenario QA</title>
    <style>body{{background:#07111f;color:#e5edf7;font-family:Meiryo,sans-serif;margin:0}}main{{max-width:1180px;margin:auto;padding:24px;display:grid;gap:14px}}.scenario,.loading,.ready,.composer{{border:1px solid #27415f;border-radius:14px;background:#0d1a2b;padding:16px}}.scenario h2{{font-size:1rem}}.loading,.ready,.composer,.headline{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;color:#a5f3fc}}[hidden]{{display:none!important}}.radar{{width:48px;height:48px;border-radius:50%;border:1px solid #67e8f9;background:repeating-radial-gradient(circle,transparent 0 7px,rgba(34,211,238,.2) 8px 9px);box-shadow:0 0 14px rgba(34,211,238,.3)}}small{{color:#94a3b8}}</style></head><body><main><h1>SMAI Assistant Scenario QA</h1>{loading}{''.join(cards)}</main></body></html>"""


def _assert_scenarios(page: Page, scenarios: list[dict[str, object]]) -> None:
    page.get_by_text("SMAI Assistant Scenario QA").wait_for()
    warming = page.locator('[data-state="warming"]')
    warming.get_by_text("LLM起動確認中").wait_for()
    warming.get_by_text("市場ヘッドライン").wait_for()
    warming.locator('[data-testid="assistant-loading-radar-icon"]').wait_for()
    draft = page.get_by_label("相談内容", exact=True)
    draft.fill("入力途中のテキスト")
    assert page.locator("article.scenario").count() == len(scenarios)
    assert len(scenarios) >= 10
    for scenario in scenarios:
        card = page.locator(f'[data-scenario="{scenario["id"]}"]')
        card.get_by_text(str(scenario["input"]), exact=True).wait_for()
        card.get_by_text(f'intent: {scenario["legacy_intent"]}', exact=True).wait_for()
        card.get_by_text(f'mode: {scenario["conversation_mode"]}', exact=True).wait_for()
        if "action_card_level" in scenario:
            card.get_by_text(
                f'action-level: {scenario["action_card_level"]}', exact=True
            ).wait_for()
            action_cards = card.locator(".action-card")
            assert action_cards.count() == (1 if scenario["action_card_level"] == 2 else 0)
        text = card.inner_text()
        forbidden_items = scenario.get("forbidden", [])
        if isinstance(forbidden_items, list):
            for forbidden in forbidden_items:
                assert str(forbidden) not in text
    page.locator('[data-state="ready"]').get_by_text("準備完了", exact=True).wait_for()
    assert warming.is_hidden()
    assert draft.input_value() == "入力途中のテキスト"
    failed = page.locator('[data-state="failed"]')
    failed.get_by_text("通常回答で対応中").wait_for()
    failed.get_by_label("fallback相談内容").wait_for()


if __name__ == "__main__":
    main()
