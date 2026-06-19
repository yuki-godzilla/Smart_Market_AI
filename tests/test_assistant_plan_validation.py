from backend.assistant import (
    AssistantToolPlan,
    AssistantToolPlanStep,
    build_assistant_context,
    build_deterministic_assistant_tool_plan,
    validate_assistant_tool_plan,
)


def test_valid_deterministic_plan_passes_validation():
    context = build_assistant_context(
        current_page="ranking",
        user_question="ランキングを確認したい",
        material_state={"ranking_result_status": "available", "top_symbols_available": "true"},
    )
    plan = build_deterministic_assistant_tool_plan(context)

    result = validate_assistant_tool_plan(plan)

    assert result.valid
    assert result.errors == []


def test_unknown_action_is_rejected():
    plan = AssistantToolPlan(
        user_intent="test",
        current_page="ranking",
        overall_summary="test",
        steps=[
            AssistantToolPlanStep(
                step_id="s1",
                title="未知の操作",
                summary="未知の操作です。",
                action_id="unknown_action",
                reason="検証用です。",
            )
        ],
    )

    result = validate_assistant_tool_plan(plan)

    assert not result.valid
    assert "unknown action_id: unknown_action" in result.errors


def test_external_action_without_confirmation_is_rejected():
    plan = AssistantToolPlan(
        user_intent="test",
        current_page="cockpit",
        overall_summary="test",
        steps=[
            AssistantToolPlanStep(
                step_id="s1",
                title="AI調査を更新",
                summary="外部取得をします。",
                action_id="update_research",
                reason="検証用です。",
                requires_confirmation=False,
            )
        ],
    )

    result = validate_assistant_tool_plan(plan)

    assert not result.valid
    assert "external fetch requires confirmation: update_research" in result.errors


def test_advice_like_wording_is_rejected():
    plan = AssistantToolPlan(
        user_intent="買うべき銘柄",
        current_page="ranking",
        overall_summary="必ず上がる候補を探します。",
        steps=[],
    )

    result = validate_assistant_tool_plan(plan)

    assert not result.valid
    assert "plan contains investment-advice-like wording" in result.errors


def test_ready_create_ranking_is_rejected_until_connected():
    plan = AssistantToolPlan(
        user_intent="ランキングを確認",
        current_page="ranking",
        overall_summary="確認順です。",
        steps=[
            AssistantToolPlanStep(
                step_id="s1",
                title="ランキングを作成",
                summary="現在条件で候補を並べます。",
                action_id="create_ranking",
                reason="検証用です。",
                status="ready",
            )
        ],
    )

    result = validate_assistant_tool_plan(plan)

    assert not result.valid
    assert "create_ranking is not connected for ready execution" in result.errors


def test_execution_like_wording_is_rejected():
    plan = AssistantToolPlan(
        user_intent="注文を出す",
        current_page="rebalance",
        overall_summary="発注します。",
        steps=[],
    )

    result = validate_assistant_tool_plan(plan)

    assert not result.valid
    assert "plan contains execution-like wording" in result.errors
