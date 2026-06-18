from backend.assistant import build_assistant_context, build_deterministic_assistant_tool_plan


def test_ranking_question_builds_ranking_tool_plan():
    context = build_assistant_context(
        current_page="ranking",
        user_question="上がりそうな株を探して",
        page_state={"ranking_policy": "AI総合", "candidate_count": 3747},
        material_state={"ranking_result_status": "available", "top_symbols_available": "true"},
    )

    plan = build_deterministic_assistant_tool_plan(context)

    assert plan.current_page == "ranking"
    assert plan.generated_by == "deterministic"
    assert 1 <= len(plan.steps) <= 5
    assert [step.action_id for step in plan.steps[:3]] == [
        "change_ranking_policy",
        "create_ranking",
        "open_symbol_from_ranking",
    ]
    assert plan.safety_note.endswith("売買推奨ではありません。")


def test_cockpit_missing_research_suggests_update_research():
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

    assert "AI調査 / Research Evidence" in plan.missing_materials
    research_step = next(step for step in plan.steps if step.action_id == "update_research")
    assert research_step.requires_confirmation
    assert research_step.priority == "high"


def test_news_missing_snapshot_suggests_confirmed_refresh():
    context = build_assistant_context(
        current_page="news",
        user_question="今日の材料は？",
        material_state={"news_status": "missing"},
    )

    plan = build_deterministic_assistant_tool_plan(context)

    assert plan.steps[0].action_id == "refresh_news"
    assert plan.steps[0].requires_confirmation
