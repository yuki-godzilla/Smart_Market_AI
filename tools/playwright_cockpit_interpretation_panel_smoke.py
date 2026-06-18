from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.interpretation import CockpitInterpretationResult, InterpretationBullet  # noqa: E402
from ui.app import _cockpit_interpretation_panel_html  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "outputs/work/playwright_cockpit_interpretation_panel_smoke"
HTML_PATH = OUTPUT_DIR / "cockpit_interpretation_panel_states.html"
SCREENSHOT_PATH = OUTPUT_DIR / "cockpit_interpretation_panel_states.png"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        [
            _cockpit_interpretation_panel_html(
                _result(status="disabled", fallback_reason="disabled")
            ),
            _cockpit_interpretation_panel_html(
                _result(status="fallback", fallback_reason="gateway_unavailable")
            ),
            _cockpit_interpretation_panel_html(_result(status="live", fallback_reason=None)),
        ]
    )
    HTML_PATH.write_text(_html_document(body), encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(HTML_PATH.resolve().as_uri())
        page.get_by_text("LLM接続: disabled").wait_for()
        page.get_by_text("LLM接続: fallback").wait_for()
        page.get_by_text("LLM接続: live").wait_for()
        note = page.get_by_text("Ranking・予測・Investment Scoreには反映していません")
        assert note.count() == 3
        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        browser.close()
    print(f"ok html={HTML_PATH} screenshot={SCREENSHOT_PATH}")


def _result(*, status: str, fallback_reason: str | None) -> CockpitInterpretationResult:
    return CockpitInterpretationResult(
        symbol="7203.T",
        company_name="Toyota Motor",
        status=status,  # type: ignore[arg-type]
        overall_reading="価格、予測、根拠資料、AI材料分析を分けて読むための参考メモです。",
        positive_points=[
            InterpretationBullet(
                title="品質項目",
                summary="Investment Scoreの品質項目は確認材料です。",
                evidence_ids=["investment_score"],
                confidence=0.55,
            )
        ],
        caution_points=[
            InterpretationBullet(
                title="予測の不確実性",
                summary="予測は短期の目安として、材料の鮮度と合わせて確認します。",
                evidence_ids=["forecast_summary"],
                confidence=0.45,
            )
        ],
        contradictions=[
            InterpretationBullet(
                title="方向差",
                summary="予測と材料の方向が違う場合は、短期要因と中長期材料を分けます。",
                evidence_ids=["forecast_summary", "llm_factor"],
                confidence=0.4,
            )
        ],
        next_checks=[
            InterpretationBullet(
                title="最新ニュース",
                summary="最新ニュースと適時開示を確認してください。",
                evidence_ids=["research_evidence"],
                confidence=0.55,
            )
        ],
        warnings=["不足項目を確認してください。"],
        provider="ollama" if status == "live" else "deterministic",
        model="qwen3:8b" if status == "live" else "fallback",
        gateway_profile="desktop_fast" if status == "live" else "fallback",
        generated_at=datetime(2026, 6, 18, 10, 0, tzinfo=UTC),
        context_hash="abc123",
        fallback_reason=fallback_reason,  # type: ignore[arg-type]
        is_fallback=status != "live",
    )


def _html_document(body: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>Cockpit interpretation panel smoke</title>
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
    .research-brief-reading-grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
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
