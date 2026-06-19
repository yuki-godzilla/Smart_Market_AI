from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.assistant import (  # noqa: E402
    AssistantActionResult,
    build_assistant_context,
    build_deterministic_assistant_tool_plan,
    build_deterministic_guided_workflow,
    get_assistant_action,
    start_session,
)
from ui.components.assistant_action_confirm import (  # noqa: E402
    assistant_action_confirmation_html,
)
from ui.components.assistant_action_result import assistant_action_result_card_html  # noqa: E402
from ui.views.copilot import copilot_answer_detail_html  # noqa: E402

DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs/work/playwright_assistant_action_smoke"
HTML_PATH = "assistant_action_states.html"
SCREENSHOT_PATH = "assistant_action_states.png"

FORBIDDEN_COPY = (
    "買うべきです",
    "売るべきです",
    "投資すべきです",
    "この銘柄は上がります",
    "必ず上がる",
    "儲かる",
    "利益が期待できます",
    "自動売買",
    "注文を送信",
)
RAW_DETAIL_MARKERS = (
    "Traceback",
    "RuntimeError",
    "request_id=abc",
    "token=secret",
    "raw provider body",
    "provider raw",
)


def main() -> None:
    args = _parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / HTML_PATH
    screenshot_path = output_dir / SCREENSHOT_PATH
    html_path.write_text(_html_document(_static_body()), encoding="utf-8")

    results: dict[str, object] = {"static_component_smoke": "pending"}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 1800})
        browser_errors = _capture_browser_errors(page)
        page.goto(html_path.as_uri())
        _assert_static_component_states(page)
        page.screenshot(path=str(screenshot_path), full_page=True)
        _assert_no_browser_errors(browser_errors)
        results["static_component_smoke"] = {
            "status": "ok",
            "html": str(html_path),
            "screenshot": str(screenshot_path),
        }

        if args.app_url:
            app_page = browser.new_page(viewport={"width": 1440, "height": 900})
            app_errors = _capture_browser_errors(app_page)
            _assert_streamlit_app_states(app_page, args.app_url)
            _assert_no_browser_errors(app_errors)
            results["streamlit_app_smoke"] = {"status": "ok", "url": args.app_url}

        browser.close()

    print(json.dumps(results, ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Network-free Playwright smoke for SMAI Assistant Tool Plan and "
            "confirmable action UI states."
        )
    )
    parser.add_argument(
        "--app-url",
        default="",
        help=(
            "Optional running Streamlit base URL. When set, the script also checks "
            "Assistant, Cockpit, Ranking, and Investment Radar page loading."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for generated HTML and screenshot artifacts.",
    )
    parser.add_argument("--headed", action="store_true", help="Run browser visibly.")
    return parser.parse_args()


def _static_body() -> str:
    return "\n".join(
        [
            _section(
                "基本表示・初期状態 fixture",
                """
                <div class="smai-copilot-chat-topbar">
                  <h1>SMAIアシスタント</h1>
                  <p>LLM待機中 / 送信時にGateway接続を確認します。</p>
                </div>
                <div class="smai-copilot-material-status">
                  <span>参照中の材料</span>
                  <span>価格: あり</span>
                  <span>AI予測: あり</span>
                  <span>Research Evidence: 未確認</span>
                </div>
                <form class="smai-copilot-composer-toolbar">
                  <label>質問</label>
                  <input value="" placeholder="価格・予測・ニュース・根拠資料について確認したいことを入力..." />
                  <button type="button">送信</button>
                </form>
                """,
            ),
            _tool_plan_section(
                title="Tool Plan: Cockpit missing Research",
                current_page="cockpit",
                question="この銘柄どう見ればいい？",
                page_state={"selected_symbol": "7203.T"},
                material_state={
                    "price_data_status": "available",
                    "forecast_status": "available",
                    "research_status": "missing",
                },
            ),
            _tool_plan_section(
                title="Tool Plan: Navigation actions",
                current_page="assistant",
                question="候補を探したい",
                page_state={},
                material_state={},
            ),
            _tool_plan_section(
                title="Tool Plan: Ranking context",
                current_page="ranking",
                question="上がりそうな株を探して",
                page_state={"ranking_policy": "AI総合", "candidate_count": 3747},
                material_state={
                    "ranking_result_status": "available",
                    "top_symbols_available": "true",
                },
            ),
            _tool_plan_section(
                title="Tool Plan: News context",
                current_page="news",
                question="今日のニュース材料を見たい",
                page_state={},
                material_state={"news_status": "missing"},
            ),
            _workflow_section(
                title="Guided Workflow: Cockpit to Report",
                current_page="cockpit",
                question="この銘柄を詳しく確認したい",
                page_state={"selected_symbol": "7203.T"},
                material_state={
                    "price_data_status": "available",
                    "forecast_status": "available",
                    "research_status": "missing",
                },
            ),
            _section(
                "Confirmation: create_decision_report",
                assistant_action_confirmation_html(
                    action=_action("create_decision_report"),
                    target_label="7203.T - Toyota",
                    materials=("価格: あり", "AI予測: あり", "Research Evidence: あり"),
                ),
            ),
            _section(
                "Confirmation: update_research",
                assistant_action_confirmation_html(
                    action=_action("update_research"),
                    target_label="7203.T - Toyota",
                    materials=("価格: あり", "AI予測: あり", "Research Evidence: なし"),
                ),
            ),
            _section(
                "Action Results: create_decision_report",
                "\n".join(
                    [
                        assistant_action_result_card_html(_create_report_success()),
                        assistant_action_result_card_html(_create_report_cancelled()),
                        assistant_action_result_card_html(_create_report_failure()),
                    ]
                ),
            ),
            _section(
                "Action Results: update_research",
                "\n".join(
                    [
                        assistant_action_result_card_html(_research_success()),
                        assistant_action_result_card_html(_research_partial()),
                        assistant_action_result_card_html(_research_failure()),
                    ]
                ),
            ),
        ]
    )


def _tool_plan_section(
    *,
    title: str,
    current_page: str,
    question: str,
    page_state: dict[str, object],
    material_state: dict[str, object],
) -> str:
    context = build_assistant_context(
        current_page=current_page,
        user_question=question,
        page_state=page_state,
        material_state=material_state,
    )
    plan = build_deterministic_assistant_tool_plan(context)
    turn = {
        "intent": "stock_summary",
        "answer": "確認順を整理します。",
        "reasons": "価格チャート",
        "cautions": "売買推奨ではありません。",
        "next_checkpoints": "根拠資料を確認します。",
        "memo_points": "",
        "assistant_tool_plan": plan.model_dump_json(),
    }
    return _section(title, copilot_answer_detail_html(turn))


def _workflow_section(
    *,
    title: str,
    current_page: str,
    question: str,
    page_state: dict[str, object],
    material_state: dict[str, object],
) -> str:
    context = build_assistant_context(
        current_page=current_page,
        user_question=question,
        page_state=page_state,
        material_state=material_state,
    )
    workflow = build_deterministic_guided_workflow(context)
    if workflow is None:
        raise RuntimeError(f"guided workflow was not generated: {question}")
    session = start_session(workflow)
    if session is None:
        raise RuntimeError(f"guided workflow did not pass the workflow session gate: {question}")
    turn = {
        "intent": "stock_summary",
        "answer": "確認順を整理します。",
        "reasons": "価格チャート",
        "cautions": "売買推奨ではありません。",
        "next_checkpoints": "根拠資料を確認します。",
        "memo_points": "",
        "assistant_guided_workflow": workflow.model_dump_json(),
        "assistant_workflow_session": session.model_dump_json(),
        "assistant_tool_plan": "",
    }
    return _section(title, copilot_answer_detail_html(turn))


def _assert_static_component_states(page: Page) -> None:
    page.get_by_text("SMAIアシスタント").first.wait_for()
    page.get_by_text("LLM待機中").first.wait_for()
    page.get_by_text("参照中の材料").first.wait_for()
    page.get_by_placeholder("価格・予測・ニュース・根拠資料について確認したいことを入力").wait_for()
    page.get_by_role("button", name="送信").wait_for()

    page.get_by_text("次にできること").first.wait_for()
    page.get_by_text("AI調査を更新").first.wait_for()
    page.get_by_text("確認レポートを作る").first.wait_for()
    page.get_by_text("確認フロー").first.wait_for()
    page.get_by_text("価格・予測を確認").first.wait_for()
    page.get_by_text("根拠資料を確認").first.wait_for()
    page.get_by_text("このフローは確認手順の案内です").first.wait_for()
    page.get_by_text("進行状態: 進行中").first.wait_for()
    page.get_by_text("確認待ち").first.wait_for()
    page.get_by_text("実行前確認").first.wait_for()
    page.get_by_text("売買推奨ではありません").first.wait_for()
    assert page.locator('a[href="?smai_page=ranking"]').count() >= 1
    assert page.locator('a[href="?smai_page=cockpit"]').count() >= 1
    assert page.locator('a[href="?smai_page=news"]').count() >= 1

    page.get_by_text("最新情報の取得は行いません").first.wait_for()
    page.get_by_text("最新のニュース・開示・IR候補を確認します").first.wait_for()
    page.get_by_text("スコア・予測・AI総合は変更しません").first.wait_for()
    page.get_by_text("broker連携や注文操作は行いません").first.wait_for()

    page.get_by_text("確認レポートを作成しました").first.wait_for()
    page.get_by_text("確認レポートをキャンセルしました").first.wait_for()
    page.get_by_text("AI調査を更新しました").first.wait_for()
    page.get_by_text("AI調査を一部更新しました").first.wait_for()
    page.get_by_text("AI調査を更新できませんでした").first.wait_for()
    page.get_by_text("取得件数: 3件").first.wait_for()
    page.get_by_text("資料別件数: tdnet 1件 / news 2件").first.wait_for()
    page.get_by_text("注意点: 2件").first.wait_for()
    page.get_by_text("時間切れ: company_ir_site").first.wait_for()
    page.get_by_text("該当なし: edinet").first.wait_for()
    page.get_by_text("確認レポートを作る").first.wait_for()
    page.get_by_text("AI調査をもう一度更新する").first.wait_for()
    page.get_by_text("今ある材料で確認する").first.wait_for()

    body = page.locator("body").inner_text()
    for phrase in FORBIDDEN_COPY:
        assert phrase not in body, f"forbidden investment-advice copy leaked: {phrase}"
    for marker in RAW_DETAIL_MARKERS:
        assert marker not in body, f"raw/debug detail leaked: {marker}"
    assert "unknown_action" not in body


def _assert_streamlit_app_states(page: Page, base_url: str) -> None:
    for page_key, expected_text in {
        "copilot": "SMAIアシスタント",
        "ranking": "銘柄ランキング",
        "cockpit": "銘柄コックピット",
        "news": "投資レーダー",
    }.items():
        page.goto(_with_smai_page(base_url, page_key), wait_until="domcontentloaded", timeout=60000)
        page.get_by_text(expected_text).first.wait_for(timeout=60000)
        if page_key == "cockpit":
            page.get_by_text("まずデータ取得").first.wait_for(timeout=60000)
            page.get_by_text("銘柄と期間を選ぶと、価格・予測材料を確認します。").first.wait_for(
                timeout=60000
            )
            assert "銘柄、取得期間、データ取得元" not in page.locator("body").inner_text()
    page.goto(_with_smai_page(base_url, "copilot"), wait_until="domcontentloaded", timeout=60000)
    page.get_by_text("新しい会話").first.wait_for(timeout=60000)
    page.get_by_role("button", name="送信").wait_for(timeout=60000)


def _capture_browser_errors(page: Page) -> list[str]:
    errors: list[str] = []

    def on_console(message) -> None:  # type: ignore[no-untyped-def]
        if message.type == "error":
            errors.append(f"console error: {message.text}")

    def on_page_error(error) -> None:  # type: ignore[no-untyped-def]
        errors.append(f"page error: {error}")

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    return errors


def _assert_no_browser_errors(errors: list[str]) -> None:
    if errors:
        raise AssertionError("\n".join(errors))


def _with_smai_page(base_url: str, page_key: str) -> str:
    parts = urlsplit(base_url)
    path = parts.path or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, f"smai_page={page_key}", ""))


def _action(action_id: str):
    action = get_assistant_action(action_id)
    if action is None:
        raise RuntimeError(f"missing action: {action_id}")
    return action


def _create_report_success() -> AssistantActionResult:
    return AssistantActionResult(
        action_id="create_decision_report",
        status="success",
        title="確認レポートを作成しました",
        summary="7203.T の確認材料を、Decision Report下書きとして整理しました。",
        user_message="確認用レポートを生成しました。",
        warnings=["このレポートは売買推奨ではありません。"],
        completed_at=_now(),
        followup_actions=["download_decision_report", "open_research_section"],
    )


def _create_report_cancelled() -> AssistantActionResult:
    return AssistantActionResult(
        action_id="create_decision_report",
        status="cancelled",
        title="確認レポートをキャンセルしました",
        summary="ユーザー操作により、実行前にキャンセルしました。",
        user_message="この操作ではデータ取得、レポート作成、スコア変更は行っていません。",
        completed_at=_now(),
        followup_actions=["summarize_next_checks"],
    )


def _create_report_failure() -> AssistantActionResult:
    return AssistantActionResult(
        action_id="create_decision_report",
        status="failed",
        title="確認レポートを作成できませんでした",
        summary="価格やAI予測などの確認材料が不足しています。",
        user_message="価格やAI予測など、確認レポートに必要な材料が不足しています。",
        error_code="insufficient_materials",
        completed_at=_now(),
        requires_followup=True,
        followup_actions=["fetch_symbol_data", "open_cockpit"],
    )


def _research_success() -> AssistantActionResult:
    return AssistantActionResult(
        action_id="update_research",
        status="success",
        title="AI調査を更新しました",
        summary="7203.T の根拠資料を3件反映しました。",
        user_message="IR、開示、ニュースなどの確認材料をAI調査に反映しました。",
        details={
            "symbol": "7203.T",
            "entry_count": 3,
            "source_counts": {"tdnet": 1, "news": 2},
            "warning_count": 0,
            "failed_sources": [],
            "timeout_sources": [],
            "no_result_sources": [],
        },
        completed_at=_now(),
        followup_actions=[
            "open_research_section",
            "create_decision_report",
            "summarize_next_checks",
        ],
    )


def _research_partial() -> AssistantActionResult:
    return AssistantActionResult(
        action_id="update_research",
        status="partial_success",
        title="AI調査を一部更新しました",
        summary="7203.T の根拠資料を2件反映しました。",
        user_message="取得できた材料をAI調査に反映しました。",
        details={
            "symbol": "7203.T",
            "entry_count": 2,
            "source_counts": {"news": 1, "tdnet": 1},
            "warning_count": 2,
            "failed_sources": [],
            "timeout_sources": ["company_ir_site"],
            "no_result_sources": ["edinet"],
        },
        warnings=["一部の取得元は時間切れになりました。"],
        completed_at=_now(),
        followup_actions=[
            "open_research_section",
            "create_decision_report",
            "retry_update_research",
        ],
    )


def _research_failure() -> AssistantActionResult:
    return AssistantActionResult(
        action_id="update_research",
        status="failed",
        title="AI調査を更新できませんでした",
        summary="外部情報の取得結果を確認できませんでした。",
        user_message="外部情報を取得できませんでした。取得済み材料で確認してください。",
        details={
            "symbol": "7203.T",
            "entry_count": 0,
            "source_counts": {},
            "warning_count": 1,
            "failed_sources": ["google_news_rss"],
            "timeout_sources": ["yahoo_finance"],
            "no_result_sources": [],
        },
        error_code="external_fetch_failed",
        completed_at=_now(),
        requires_followup=True,
        followup_actions=[
            "answer_with_existing_materials",
            "open_cockpit",
            "retry_update_research",
        ],
    )


def _section(title: str, body: str) -> str:
    return f'<section class="smoke-section"><h2>{title}</h2>{body}</section>'


def _now() -> datetime:
    return datetime(2026, 6, 19, 10, 0, tzinfo=UTC)


def _html_document(body: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>SMAI Assistant action smoke</title>
  <style>
    body {{
      margin: 0;
      background: #07111f;
      color: #e5edf7;
      font-family: "Yu Gothic", "Meiryo", Arial, sans-serif;
      line-height: 1.65;
    }}
    main {{
      display: grid;
      gap: 18px;
      max-width: 1180px;
      margin: 24px auto;
      padding: 0 16px 40px;
    }}
    .smoke-section,
    .smai-copilot-tool-plan,
    .smai-copilot-action-confirm,
    .smai-copilot-action-result,
    .smai-copilot-chat-topbar,
    .smai-copilot-material-status,
    .smai-copilot-composer-toolbar {{
      border: 1px solid #27415f;
      border-radius: 8px;
      background: #0d1a2b;
      padding: 16px;
    }}
    .smoke-section {{
      display: grid;
      gap: 12px;
    }}
    h1, h2, h3, h4, p {{
      margin-top: 0;
    }}
    ul {{
      padding-left: 1.2rem;
    }}
    a {{
      color: #7dd3fc;
    }}
    input {{
      min-width: 420px;
      padding: 10px;
      border-radius: 6px;
      border: 1px solid #3d5874;
      background: #091424;
      color: #e5edf7;
    }}
    button {{
      margin-left: 8px;
      padding: 10px 14px;
      border-radius: 6px;
      border: 1px solid #38bdf8;
      color: #e5edf7;
      background: #0f3b57;
    }}
    .smai-copilot-tool-plan-title,
    .smai-copilot-action-result > span {{
      display: inline-block;
      color: #93c5fd;
      font-weight: 700;
      margin-bottom: 6px;
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
