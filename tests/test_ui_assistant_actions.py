import json
from datetime import UTC, datetime

from backend.assistant import AssistantActionResult, get_assistant_action
from ui.components.assistant_action_confirm import assistant_action_confirmation_html
from ui.components.assistant_action_result import assistant_action_result_card_html
from ui.views.copilot import _first_confirmable_action_id, copilot_answer_detail_html


def test_confirmation_html_explains_create_report_safety_boundary():
    action = get_assistant_action("create_decision_report")
    assert action is not None

    markup = assistant_action_confirmation_html(
        action=action,
        target_label="7203.T - Toyota",
        materials=("価格: あり", "AI予測: あり", "Research Evidence: あり"),
    )

    assert "実行前確認" in markup
    assert "7203.T - Toyota" in markup
    assert "最新情報の取得は行いません" in markup
    assert "スコア・予測・AI総合は変更しません" in markup
    assert "broker連携" in markup


def test_confirmation_html_warns_for_external_fetch_actions():
    action = get_assistant_action("update_research")
    assert action is not None

    markup = assistant_action_confirmation_html(
        action=action,
        target_label="7203.T",
        materials=("Research Evidence: なし",),
    )

    assert "最新のニュース・開示・IR候補を確認します" in markup
    assert "取得には少し時間がかかる場合" in markup
    assert "一部だけ取得できることもあります" in markup
    assert "この操作だけでは、スコアや予測値は変更されません" in markup


def test_action_result_card_distinguishes_success_and_followups():
    result = AssistantActionResult(
        action_id="create_decision_report",
        status="success",
        title="確認レポートを作成しました",
        summary="7203.T の確認材料を整理しました。",
        user_message="確認用レポートを生成しました。",
        warnings=["売買推奨ではありません。"],
        completed_at=datetime(2026, 6, 19, 9, 0, tzinfo=UTC),
        followup_actions=["download_decision_report", "open_research_section"],
    )

    markup = assistant_action_result_card_html(result)

    assert "実行結果: 成功" in markup
    assert "確認レポートを作成しました" in markup
    assert "レポートを見る / 保存する" in markup
    assert "売買推奨ではありません" in markup


def test_action_result_card_renders_update_research_partial_followups():
    result = AssistantActionResult(
        action_id="update_research",
        status="partial_success",
        title="AI調査を一部更新しました",
        summary="7203.T の根拠資料を2件反映しました。",
        user_message="取得できた材料をAI調査に反映しました。",
        details={
            "entry_count": 2,
            "source_counts": {"news": 1, "tdnet": 1},
            "warning_count": 2,
            "timeout_sources": ["company_ir"],
            "no_result_sources": ["edinet"],
        },
        warnings=["EDINETは該当情報なしでした。"],
        completed_at=datetime(2026, 6, 19, 9, 0, tzinfo=UTC),
        followup_actions=[
            "open_research_section",
            "create_decision_report",
            "retry_update_research",
        ],
    )

    markup = assistant_action_result_card_html(result)

    assert "実行結果: 一部成功" in markup
    assert "AI調査を一部更新しました" in markup
    assert "取得件数: 2件" in markup
    assert "資料別件数: news 1件 / tdnet 1件" in markup
    assert "注意点: 2件" in markup
    assert "時間切れ: company_ir" in markup
    assert "該当なし: edinet" in markup
    assert "確認レポートを作る" in markup
    assert "AI調査をもう一度更新する" in markup


def test_first_confirmable_action_prefers_update_research_when_planned_first():
    turn = {
        "assistant_tool_plan": json.dumps(
            {
                "steps": [
                    {"action_id": "update_research", "requires_confirmation": True},
                    {
                        "action_id": "create_decision_report",
                        "requires_confirmation": True,
                    },
                ]
            },
            ensure_ascii=False,
        )
    }

    assert _first_confirmable_action_id(turn) == "update_research"


def test_first_confirmable_action_skips_already_recorded_action_result():
    result = AssistantActionResult(
        action_id="update_research",
        status="success",
        title="AI調査を更新しました",
        summary="7203.T の根拠資料を2件反映しました。",
        user_message="確認材料をAI調査に反映しました。",
    )
    turn = {
        "assistant_action_results": json.dumps(
            [result.model_dump(mode="json")], ensure_ascii=False
        ),
        "assistant_tool_plan": json.dumps(
            {
                "steps": [
                    {"action_id": "update_research", "requires_confirmation": True},
                    {
                        "action_id": "create_decision_report",
                        "requires_confirmation": True,
                    },
                ]
            },
            ensure_ascii=False,
        ),
    }

    assert _first_confirmable_action_id(turn) == "create_decision_report"


def test_copilot_answer_detail_html_renders_action_result_cards():
    result = AssistantActionResult(
        action_id="create_decision_report",
        status="cancelled",
        title="確認レポートをキャンセルしました",
        summary="実行前にキャンセルしました。",
        user_message="データ取得やスコア変更は行っていません。",
        completed_at=datetime(2026, 6, 19, 9, 0, tzinfo=UTC),
    )
    turn = {
        "intent": "stock_summary",
        "answer": "確認順を整理します。",
        "reasons": "価格チャート",
        "cautions": "売買推奨ではありません。",
        "next_checkpoints": "根拠資料を確認します。",
        "memo_points": "",
        "assistant_action_results": json.dumps(
            [result.model_dump(mode="json")], ensure_ascii=False
        ),
        "assistant_tool_plan": "",
    }

    markup = copilot_answer_detail_html(turn)

    assert "実行結果: キャンセル" in markup
    assert "データ取得やスコア変更は行っていません" in markup
