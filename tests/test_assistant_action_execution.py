from datetime import UTC, datetime

from backend.assistant import (
    AssistantActionExecutor,
    build_assistant_action_audit_entry,
    build_assistant_context,
    get_assistant_action,
)
from backend.reporting import build_decision_report_context, build_report_section


def _sample_report_context(*, symbol: str | None = "7203.T"):
    price = build_report_section(
        title="価格チャート",
        source_kind="cockpit",
        symbol=symbol,
        summary={"価格": "直近反発", "trend": "上向き"},
    )
    forecast = build_report_section(
        title="AI予測インサイト",
        source_kind="cockpit",
        symbol=symbol,
        summary={"予測": "やや上向き", "downside": "中"},
    )
    return build_decision_report_context(
        title="銘柄コックピット",
        sections=[price, forecast],
        created_at=datetime(2026, 6, 19, 9, 0, tzinfo=UTC),
    )


def _assistant_context(*, symbol: str | None = "7203.T", price: str = "available"):
    page_state = {"selected_symbol": symbol} if symbol else {}
    return build_assistant_context(
        current_page="cockpit",
        user_question="確認レポートを作って",
        page_state=page_state,
        material_state={
            "price_data_status": price,
            "forecast_status": "available",
            "research_status": "available",
        },
    )


def test_unknown_action_returns_not_available():
    result = AssistantActionExecutor().execute(
        "unknown_action",
        _assistant_context(),
        confirmed=True,
    )

    assert result.status == "not_available"
    assert result.error_code == "unknown_action"


def test_confirmable_action_without_confirmation_is_skipped():
    result = AssistantActionExecutor().execute(
        "create_decision_report",
        _assistant_context(),
        payload={"report_context": _sample_report_context()},
        confirmed=False,
    )

    assert result.status == "skipped"
    assert result.error_code == "confirmation_required"


def test_create_decision_report_success_returns_report_payload_and_audit_entry():
    context = _assistant_context()
    result = AssistantActionExecutor().execute(
        "create_decision_report",
        context,
        payload={"report_context": _sample_report_context()},
        confirmed=True,
    )

    assert result.status == "success"
    assert result.details["symbol"] == "7203.T"
    assert result.details["report_context_json"]
    assert "# SMAIアシスタント Decision Report下書き" in result.details["report_markdown"]
    assert any("売買推奨ではありません" in warning for warning in result.warnings)

    audit = build_assistant_action_audit_entry(
        result=result,
        action=get_assistant_action("create_decision_report"),
        context=context,
        confirmed=True,
    )

    assert audit.action_id == "create_decision_report"
    assert audit.action_type == "report"
    assert audit.confirmed
    assert audit.status == "success"
    assert audit.symbol == "7203.T"


def test_create_decision_report_missing_symbol_fails_safely():
    result = AssistantActionExecutor().execute(
        "create_decision_report",
        _assistant_context(symbol=None),
        payload={"report_context": _sample_report_context(symbol=None)},
        confirmed=True,
    )

    assert result.status == "failed"
    assert result.error_code == "symbol_missing"
    assert "対象銘柄" in result.user_message


def test_create_decision_report_insufficient_materials_fails_safely():
    result = AssistantActionExecutor().execute(
        "create_decision_report",
        _assistant_context(price="missing"),
        payload={},
        confirmed=True,
    )

    assert result.status == "failed"
    assert result.error_code == "insufficient_materials"
    assert "材料" in result.user_message


def test_followup_actions_are_not_executed_in_phase_30c_mvp():
    result = AssistantActionExecutor().execute(
        "update_research",
        _assistant_context(),
        confirmed=True,
    )

    assert result.status == "not_available"
    assert result.error_code == "not_implemented"
    assert "後続接続" in result.summary
