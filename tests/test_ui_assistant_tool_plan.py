from backend.assistant import build_assistant_context, build_deterministic_assistant_tool_plan
from ui.views.copilot import copilot_answer_detail_html


def test_copilot_answer_detail_html_renders_next_action_plan():
    context = build_assistant_context(
        current_page="cockpit",
        user_question="この銘柄どう見ればいい？",
        page_state={"selected_symbol": "7203.T"},
        material_state={
            "price_data_status": "available",
            "forecast_status": "available",
            "research_status": "missing",
        },
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

    markup = copilot_answer_detail_html(turn)

    assert "次にできること" in markup
    assert "AI調査を更新" in markup
    assert "実行前確認" in markup
    assert "売買推奨ではありません" in markup
    assert "smai-copilot-tool-plan--next-actions" in markup


def test_copilot_answer_detail_html_links_navigation_actions_only():
    context = build_assistant_context(
        current_page="assistant",
        user_question="候補を探したい",
    )
    plan = build_deterministic_assistant_tool_plan(context)
    turn = {
        "intent": "app_help",
        "answer": "次に開く画面を整理します。",
        "reasons": "",
        "cautions": "",
        "next_checkpoints": "",
        "memo_points": "",
        "assistant_tool_plan": plan.model_dump_json(),
    }

    markup = copilot_answer_detail_html(turn)

    assert "候補探しならランキングへ" in markup
    assert 'href="?smai_page=ranking"' in markup
    assert 'href="?smai_page=cockpit"' in markup
    assert 'target="_self"' in markup
    assert "ランキングを作成" not in markup


def test_copilot_answer_detail_html_includes_planner_metadata_in_technical_details():
    turn = {
        "intent": "stock_summary",
        "answer": "確認順を整理します。",
        "reasons": "価格チャート",
        "cautions": "売買推奨ではありません。",
        "next_checkpoints": "根拠資料を確認します。",
        "memo_points": "",
        "assistant_tool_plan": "",
        "assistant_planner_source": "fallback",
        "assistant_planner_fallback_reason": "planner_validation_failure",
        "assistant_planner_gateway_status": "ok",
    }

    markup = copilot_answer_detail_html(turn)

    assert "planner" in markup
    assert "fallback" in markup
    assert "planner_validation_failure" in markup
