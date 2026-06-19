from backend.assistant import (
    AssistantGuidedWorkflow,
    AssistantWorkflowStep,
    build_assistant_context,
    build_deterministic_guided_workflow,
    validate_assistant_guided_workflow,
)


def test_ranking_intent_builds_guided_workflow_without_auto_ranking_creation():
    context = build_assistant_context(
        current_page="assistant",
        user_question="ランキング上位を見たい",
    )

    workflow = build_deterministic_guided_workflow(context)

    assert workflow is not None
    assert workflow.generated_by == "deterministic"
    assert workflow.current_page == "assistant"
    assert [step.action_id for step in workflow.steps] == [
        "open_ranking",
        "open_cockpit",
        "update_research",
        "create_decision_report",
    ]
    assert all(step.action_id != "create_ranking" for step in workflow.steps)
    assert workflow.steps[2].requires_confirmation
    assert workflow.steps[3].requires_confirmation
    assert validate_assistant_guided_workflow(workflow).valid


def test_cockpit_intent_uses_active_symbol_and_waits_for_research_confirmation():
    context = build_assistant_context(
        current_page="cockpit",
        user_question="この銘柄を詳しく確認したい",
        page_state={"selected_symbol": "7203.T"},
        material_state={
            "price_data_status": "available",
            "forecast_status": "available",
            "research_status": "missing",
        },
    )

    workflow = build_deterministic_guided_workflow(context)

    assert workflow is not None
    assert workflow.target_symbol == "7203.T"
    assert workflow.steps[0].action_id == "open_cockpit"
    research_step = next(step for step in workflow.steps if step.action_id == "update_research")
    assert research_step.status == "waiting_confirmation"
    assert "実行前に必ず確認" in research_step.summary


def test_report_intent_keeps_report_creation_confirmable():
    context = build_assistant_context(
        current_page="cockpit",
        user_question="確認レポートまで作りたい",
        page_state={"selected_symbol": "7203.T"},
        material_state={
            "price_data_status": "available",
            "forecast_status": "available",
            "research_status": "available",
        },
    )

    workflow = build_deterministic_guided_workflow(context)

    assert workflow is not None
    assert workflow.title == "確認レポートまで進めるフロー"
    assert [step.action_id for step in workflow.steps] == [
        "summarize_next_checks",
        "update_research",
        "create_decision_report",
        "download_decision_report",
    ]
    report_step = next(
        step for step in workflow.steps if step.action_id == "create_decision_report"
    )
    assert report_step.requires_confirmation
    assert validate_assistant_guided_workflow(workflow).valid


def test_guided_workflow_not_generated_for_unrelated_light_chat():
    context = build_assistant_context(
        current_page="assistant",
        user_question="こんにちは",
    )

    assert build_deterministic_guided_workflow(context) is None


def test_guided_workflow_validation_rejects_unknown_action():
    workflow = AssistantGuidedWorkflow(
        title="確認フロー",
        summary="確認します。",
        user_intent="test",
        current_page="assistant",
        steps=[
            AssistantWorkflowStep(
                step_id="s1",
                title="未知の操作",
                summary="未知の操作です。",
                kind="navigation",
                action_id="unknown_action",
            )
        ],
    )

    result = validate_assistant_guided_workflow(workflow)

    assert not result.valid
    assert "unknown workflow action_id: unknown_action" in result.errors


def test_guided_workflow_validation_rejects_external_fetch_without_confirmation():
    workflow = AssistantGuidedWorkflow(
        title="確認フロー",
        summary="確認します。",
        user_intent="test",
        current_page="cockpit",
        steps=[
            AssistantWorkflowStep(
                step_id="s1",
                title="AI調査を更新",
                summary="最新情報を確認します。",
                kind="confirmable_action",
                action_id="update_research",
                requires_confirmation=False,
            )
        ],
    )

    result = validate_assistant_guided_workflow(workflow)

    assert not result.valid
    assert "confirmable workflow step requires confirmation: s1" in result.errors
    assert "workflow external fetch requires confirmation: update_research" in result.errors


def test_guided_workflow_validation_rejects_create_ranking_ready_state():
    workflow = AssistantGuidedWorkflow(
        title="確認フロー",
        summary="確認します。",
        user_intent="test",
        current_page="ranking",
        steps=[
            AssistantWorkflowStep(
                step_id="s1",
                title="ランキングを作成",
                summary="ランキングを作ります。",
                kind="confirmable_action",
                action_id="create_ranking",
                requires_confirmation=True,
                status="waiting_confirmation",
            )
        ],
    )

    result = validate_assistant_guided_workflow(workflow)

    assert not result.valid
    assert "create_ranking is not connected for guided workflow" in result.errors
