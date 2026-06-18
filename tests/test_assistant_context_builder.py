from backend.assistant import build_assistant_context


def test_context_builder_handles_ranking_state_without_raw_data():
    context = build_assistant_context(
        current_page="ranking",
        user_question="上がりそうな株を探して",
        page_state={
            "ranking_policy": "AI総合",
            "candidate_count": 3747,
            "raw_dataframe": [{"ignored": True}],
        },
        material_state={"ranking_result_status": "available", "top_symbols_available": "true"},
    )

    assert context.current_page == "ranking"
    assert context.user_question == "上がりそうな株を探して"
    assert "AI総合" in context.summary
    assert context.page_state["candidate_count"] == 3747
    assert "raw_dataframe" in context.page_state
    assert isinstance(context.page_state["raw_dataframe"], list)
    assert any(action.action_id == "create_ranking" for action in context.available_actions)
    assert context.missing_materials == []


def test_context_builder_marks_cockpit_missing_research():
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

    assert context.current_page == "cockpit"
    assert "7203.T" in context.summary
    assert "AI調査 / Research Evidence" in context.missing_materials
    assert any(action.action_id == "update_research" for action in context.available_actions)
    assert context.warnings


def test_context_builder_unknown_page_still_returns_actions():
    context = build_assistant_context(current_page="unknown", user_question="次は？")

    assert context.current_page == "unknown"
    assert [action.action_id for action in context.available_actions] == [
        "explain_current_page",
        "summarize_next_checks",
    ]
