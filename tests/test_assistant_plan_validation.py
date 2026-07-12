from backend.assistant import (
    AssistantGuidedWorkflow,
    AssistantToolPlan,
    AssistantToolPlanStep,
    AssistantWorkflowStep,
    build_assistant_context,
    build_deterministic_assistant_tool_plan,
    validate_assistant_guided_workflow,
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


def test_user_visible_disabled_reason_with_unsafe_advice_is_rejected():
    plan = AssistantToolPlan(
        user_intent="確認する",
        current_page="cockpit",
        overall_summary="確認順です。",
        steps=[
            AssistantToolPlanStep(
                step_id="s1",
                title="利用できない操作",
                summary="現在は利用できません。",
                action_id="update_research",
                reason="検証用です。",
                status="blocked",
                disabled_reason="今すぐ買ってください。",
            )
        ],
    )

    result = validate_assistant_tool_plan(plan)

    assert not result.valid
    assert "plan contains investment-advice-like wording" in result.errors


def test_user_visible_plan_warning_with_unsafe_advice_is_rejected():
    plan = AssistantToolPlan(
        user_intent="確認する",
        current_page="cockpit",
        overall_summary="確認順です。",
        warnings=["この銘柄は購入推奨です。"],
    )

    result = validate_assistant_tool_plan(plan)

    assert not result.valid
    assert "plan contains investment-advice-like wording" in result.errors


def test_user_visible_workflow_followup_hint_with_unsafe_advice_is_rejected():
    workflow = AssistantGuidedWorkflow(
        title="確認フロー",
        summary="確認順です。",
        user_intent="確認する",
        current_page="cockpit",
        steps=[
            AssistantWorkflowStep(
                step_id="s1",
                title="資料を見る",
                summary="取得済み資料を確認します。",
                kind="review",
                action_id="open_research_section",
                followup_hint="今すぐ売ってください。",
            )
        ],
    )

    result = validate_assistant_guided_workflow(workflow)

    assert not result.valid
    assert "workflow contains investment-advice-like wording" in result.errors
