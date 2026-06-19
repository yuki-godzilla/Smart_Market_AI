from datetime import UTC, datetime

from backend.assistant import (
    ActionExecutionStatus,
    AssistantActionResult,
    build_assistant_context,
    build_deterministic_guided_workflow,
)
from backend.assistant.workflow_runtime import (
    apply_action_result,
    cancel_session,
    mark_running,
    retry_step,
    skip_step,
    start_session,
)


def test_start_session_gates_and_sets_confirmable_step_waiting():
    workflow = _workflow()
    session = start_session(workflow)

    assert session is not None
    assert session.status == "active"
    assert session.active_step_id == "workflow_update_research"
    assert _step_status(session, "workflow_review_cockpit") == "planned"
    assert _step_status(session, "workflow_update_research") == "waiting_confirmation"
    assert _step_status(session, "workflow_create_report") == "waiting_confirmation"


def test_start_session_rejects_unsafe_workflow_wording():
    workflow = _workflow().model_copy(update={"summary": "この銘柄は買うべきです。"})

    assert start_session(workflow) is None


def test_confirmable_step_does_not_run_without_confirmation():
    session = start_session(_workflow())
    assert session is not None

    rejected = mark_running(session, "workflow_update_research")

    assert _step_status(rejected, "workflow_update_research") == "waiting_confirmation"
    assert "実行前確認" in rejected.warnings[-1]

    running = mark_running(session, "workflow_update_research", confirmed=True)
    assert _step_status(running, "workflow_update_research") == "running"
    assert running.active_step_id == "workflow_update_research"


def test_update_research_success_marks_done_and_waits_for_report_confirmation():
    session = start_session(_workflow())
    assert session is not None

    updated = apply_action_result(
        session,
        "workflow_update_research",
        _research_result("success", followups=["create_decision_report"]),
    )

    assert updated.status == "active"
    assert updated.active_step_id == "workflow_create_report"
    assert _step_status(updated, "workflow_update_research") == "done"
    assert _step_status(updated, "workflow_create_report") == "waiting_confirmation"


def test_update_research_partial_keeps_warning_and_next_report_confirmation():
    session = start_session(_workflow())
    assert session is not None

    updated = apply_action_result(
        session,
        "workflow_update_research",
        _research_result(
            "partial_success",
            warnings=["一部の取得元は時間切れになりました。"],
            followups=["create_decision_report", "retry_update_research"],
        ),
    )

    research_step = _step(updated, "workflow_update_research")
    assert research_step.status == "done"
    assert research_step.result_status == "partial_success"
    assert research_step.warnings == ["一部の取得元は時間切れになりました。"]
    assert updated.active_step_id == "workflow_create_report"


def test_update_research_failure_stops_session_without_auto_report():
    session = start_session(_workflow())
    assert session is not None

    updated = apply_action_result(
        session,
        "workflow_update_research",
        _research_result(
            "failed",
            followups=["answer_with_existing_materials", "retry_update_research"],
        ),
    )

    assert updated.status == "failed"
    assert updated.active_step_id is None
    assert _step_status(updated, "workflow_update_research") == "failed"
    assert _step_status(updated, "workflow_create_report") == "waiting_confirmation"


def test_failed_update_research_can_be_skipped_to_existing_materials():
    session = start_session(_workflow())
    assert session is not None
    failed = apply_action_result(
        session,
        "workflow_update_research",
        _research_result(
            "failed",
            followups=["answer_with_existing_materials", "retry_update_research"],
        ),
    )

    recovered = skip_step(
        failed,
        "workflow_update_research",
        "今ある材料で確認するため、AI調査更新をスキップしました。",
    )

    assert recovered.status == "active"
    assert recovered.active_step_id == "workflow_create_report"
    assert _step_status(recovered, "workflow_update_research") == "skipped"
    assert _step_status(recovered, "workflow_create_report") == "waiting_confirmation"


def test_failed_update_research_can_be_retried_with_confirmation():
    session = start_session(_workflow())
    assert session is not None
    failed = apply_action_result(
        session,
        "workflow_update_research",
        _research_result(
            "failed",
            followups=["answer_with_existing_materials", "retry_update_research"],
        ),
    )

    retried = retry_step(failed, "workflow_update_research")

    research_step = _step(retried, "workflow_update_research")
    assert retried.status == "active"
    assert retried.active_step_id == "workflow_update_research"
    assert research_step.status == "waiting_confirmation"
    assert research_step.result_status is None
    assert research_step.completed_at is None


def test_done_step_cannot_be_retried():
    session = start_session(_workflow())
    assert session is not None
    updated = apply_action_result(
        session,
        "workflow_update_research",
        _research_result("success", followups=["create_decision_report"]),
    )

    rejected = retry_step(updated, "workflow_update_research")

    assert _step_status(rejected, "workflow_update_research") == "done"
    assert "再試行できる状態" in rejected.warnings[-1]


def test_create_decision_report_success_can_complete_session():
    session = start_session(_workflow())
    assert session is not None
    updated = apply_action_result(
        session,
        "workflow_update_research",
        _research_result("success", followups=["create_decision_report"]),
    )

    completed = apply_action_result(
        updated,
        "workflow_create_report",
        AssistantActionResult(
            action_id="create_decision_report",
            status="success",
            title="確認レポートを作成しました",
            summary="材料と注意点を整理しました。",
            user_message="確認用レポートを生成しました。",
            completed_at=_now(),
        ),
    )

    assert completed.status == "completed"
    assert completed.active_step_id is None
    assert completed.completed_at is not None
    assert _step_status(completed, "workflow_create_report") == "done"


def test_done_step_is_not_marked_running_again_by_default():
    session = start_session(_workflow())
    assert session is not None
    updated = apply_action_result(
        session,
        "workflow_update_research",
        _research_result("success", followups=["create_decision_report"]),
    )

    rerun = mark_running(updated, "workflow_update_research", confirmed=True)

    assert _step_status(rerun, "workflow_update_research") == "done"
    assert "再実行しません" in rerun.warnings[-1]


def test_skip_and_cancel_workflow_session_are_stateful():
    session = start_session(_workflow())
    assert session is not None

    skipped = skip_step(session, "workflow_review_cockpit", "画面確認は済みです。")
    assert _step_status(skipped, "workflow_review_cockpit") == "skipped"

    cancelled = cancel_session(skipped, "ユーザーが中止しました。")
    assert cancelled.status == "cancelled"
    assert cancelled.active_step_id is None
    assert cancelled.cancelled_reason == "ユーザーが中止しました。"
    assert _step_status(cancelled, "workflow_update_research") == "cancelled"


def _workflow():
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
    return workflow


def _research_result(
    status: ActionExecutionStatus,
    *,
    warnings: list[str] | None = None,
    followups: list[str] | None = None,
) -> AssistantActionResult:
    return AssistantActionResult(
        action_id="update_research",
        status=status,
        title="AI調査を更新しました",
        summary="7203.T の根拠資料を確認しました。",
        user_message="取得結果を確認しました。",
        warnings=warnings or [],
        completed_at=_now(),
        followup_actions=followups or [],
    )


def _step(session, step_id: str):
    return next(step for step in session.steps if step.step_id == step_id)


def _step_status(session, step_id: str) -> str:
    return _step(session, step_id).status


def _now() -> datetime:
    return datetime(2026, 6, 19, 10, 0, tzinfo=UTC)
