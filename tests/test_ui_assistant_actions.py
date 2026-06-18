import json
from datetime import UTC, datetime

from backend.assistant import AssistantActionResult, get_assistant_action
from ui.components.assistant_action_confirm import assistant_action_confirmation_html
from ui.components.assistant_action_result import assistant_action_result_card_html
from ui.views.copilot import copilot_answer_detail_html


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
    assert "外部取得を行いません" in markup
    assert "Ranking score / Forecast / Investment Score / AI総合は変更しません" in markup
    assert "broker連携" in markup


def test_confirmation_html_warns_for_external_fetch_actions():
    action = get_assistant_action("update_research")
    assert action is not None

    markup = assistant_action_confirmation_html(
        action=action,
        target_label="7203.T",
        materials=("Research Evidence: なし",),
    )

    assert "外部データ取得を行います" in markup
    assert "時間がかかる場合" in markup


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
