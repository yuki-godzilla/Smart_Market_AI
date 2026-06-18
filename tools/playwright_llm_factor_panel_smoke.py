from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.llm_factor import EvidenceSource, FakeLLMFactorService  # noqa: E402
from ui.app import _llm_factor_panel_html  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "outputs/work/playwright_llm_factor_panel_smoke"
HTML_PATH = OUTPUT_DIR / "llm_factor_panel_states.html"
SCREENSHOT_PATH = OUTPUT_DIR / "llm_factor_panel_states.png"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    panels = "\n".join(
        [
            _llm_factor_panel_html(_disabled_result()),
            _llm_factor_panel_html(_fallback_result()),
            _llm_factor_panel_html(_live_result()),
        ]
    )
    HTML_PATH.write_text(_html_document(panels), encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(HTML_PATH.resolve().as_uri())
        page.get_by_text("LLM接続: disabled").wait_for()
        page.get_by_text("LLM接続: fallback").wait_for()
        page.get_by_text("LLM接続: live").wait_for()
        note = page.get_by_text("Ranking・予測・Investment Scoreには反映していません")
        assert note.count() == 3
        note.first.wait_for()
        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        browser.close()
    print(f"ok html={HTML_PATH} screenshot={SCREENSHOT_PATH}")


def _disabled_result():
    return _base_result()


def _fallback_result():
    return _base_result().model_copy(
        update={
            "provider": "deterministic",
            "gateway_status": "fallback",
            "fallback_reason": "gateway_unavailable",
            "warnings": ["LLM Gatewayに接続できませんでした。"],
        }
    )


def _live_result():
    return _base_result().model_copy(
        update={
            "model_name": "qwen3:14b",
            "prompt_version": "llm_factor_live_mvp.v1",
            "provider": "ollama",
            "gateway_profile": "desktop_analysis",
            "gateway_status": "ok",
            "sentiment_label": "positive",
            "missing_fields": ["forecast_summary"],
            "warnings": ["不足項目: forecast_summary"],
        }
    )


def _base_result():
    return FakeLLMFactorService().build_reference_result(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        evidence_sources=[
            EvidenceSource(
                title="増配と自社株買いを発表",
                source_type="company_ir",
                source_url="https://example.com/ir/7203",
                source_date=date(2026, 6, 12),
                fetched_at=datetime(2026, 6, 12, 9, 0, tzinfo=UTC),
                provider="fixture",
                summary="増配と自社株買いが確認できます。",
                reliability_score=Decimal("82"),
            )
        ],
        generated_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )


def _html_document(body: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>LLM Factor panel smoke</title>
  <style>
    body {{
      margin: 0;
      background: #07111f;
      color: #e5edf7;
      font-family: "Yu Gothic", "Meiryo", Arial, sans-serif;
    }}
    main {{
      display: grid;
      gap: 16px;
      max-width: 1180px;
      margin: 24px auto;
      padding: 0 16px 32px;
    }}
    .research-result-brief {{
      border: 1px solid #26415f;
      border-radius: 8px;
      background: #0d1a2b;
      padding: 18px;
    }}
    .research-result-brief-header {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 8px;
    }}
    .research-evidence-pill {{
      border: 1px solid #33516f;
      border-radius: 999px;
      padding: 3px 8px;
      color: #c6d6e5;
      font-size: 12px;
    }}
    .research-evidence-pill.positive {{
      border-color: #2ea66f;
      color: #8ff0bd;
    }}
    .research-brief-metric-grid,
    .research-brief-reading-grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .research-evidence-card,
    .research-brief-reading-item {{
      border: 1px solid #27415f;
      border-radius: 8px;
      background: #111f32;
      padding: 12px;
    }}
    ul {{
      padding-left: 1.2rem;
    }}
  </style>
</head>
<body>
  <main>
    {body}
  </main>
</body>
</html>
"""


if __name__ == "__main__":
    main()
