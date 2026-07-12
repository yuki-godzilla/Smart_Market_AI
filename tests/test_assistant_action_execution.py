import json
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


def test_update_research_requires_confirmation_before_fetcher_runs():
    calls: list[dict[str, object]] = []

    def fake_fetcher(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"status": "success", "entry_count": 1}

    result = AssistantActionExecutor(research_fetcher=fake_fetcher).execute(
        "update_research",
        _assistant_context(),
        confirmed=False,
    )

    assert result.status == "skipped"
    assert result.error_code == "confirmation_required"
    assert calls == []


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


def test_confirmed_action_rejects_a_payload_symbol_that_differs_from_context():
    calls: list[dict[str, object]] = []

    def fake_fetcher(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"status": "success", "entry_count": 1}

    result = AssistantActionExecutor(research_fetcher=fake_fetcher).execute(
        "update_research",
        _assistant_context(symbol="7203.T"),
        payload={"symbol": "AAPL"},
        confirmed=True,
    )

    assert result.status == "validation_error"
    assert result.error_code == "target_mismatch"
    assert calls == []


def test_confirmed_action_rejects_conflicting_symbols_within_the_current_context():
    calls: list[dict[str, object]] = []

    def fake_fetcher(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"status": "success", "entry_count": 1}

    context = _assistant_context(symbol="7203.T").model_copy(
        update={"page_state": {"selected_symbol": "7203.T", "active_symbol": "AAPL"}}
    )
    result = AssistantActionExecutor(research_fetcher=fake_fetcher).execute(
        "update_research",
        context,
        payload={"symbol": "7203.T"},
        confirmed=True,
    )

    assert result.status == "validation_error"
    assert result.error_code == "target_mismatch"
    assert calls == []


def test_confirmed_report_rejects_report_materials_for_a_different_symbol():
    result = AssistantActionExecutor().execute(
        "create_decision_report",
        _assistant_context(symbol="7203.T"),
        payload={"report_context": _sample_report_context(symbol="AAPL")},
        confirmed=True,
    )

    assert result.status == "validation_error"
    assert result.error_code == "target_mismatch"


def test_confirmed_report_rejects_mixed_symbol_materials():
    report_context = _sample_report_context(symbol="7203.T")
    mixed_context = report_context.model_copy(
        update={
            "sections": [
                *report_context.sections,
                _sample_report_context(symbol="AAPL").sections[0],
            ]
        }
    )

    result = AssistantActionExecutor().execute(
        "create_decision_report",
        _assistant_context(symbol="7203.T"),
        payload={"report_context": mixed_context, "symbol": "7203.T"},
        confirmed=True,
    )

    assert result.status == "validation_error"
    assert result.error_code == "target_mismatch"


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


def test_update_research_success_uses_injected_fetcher_and_sanitizes_result():
    calls: list[dict[str, object]] = []

    def fake_fetcher(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "status": "success",
            "entry_count": 2,
            "source_counts": {"tdnet": 1, "news": 1},
            "fetched_at": "2026-06-19T09:00:00+00:00",
            "retention_policy": "session",
            "entries": [{"source_type": "news", "content": "raw provider body"}],
        }

    context = _assistant_context()
    result = AssistantActionExecutor(research_fetcher=fake_fetcher).execute(
        "update_research",
        context,
        payload={"company_name": "Toyota", "related_keywords": ["Toyota"]},
        confirmed=True,
    )

    assert result.status == "success"
    assert result.details["symbol"] == "7203.T"
    assert result.details["entry_count"] == 2
    assert result.details["source_counts"] == {"tdnet": 1, "news": 1}
    assert "entries" not in result.details
    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert "raw provider body" not in dumped
    assert calls == [
        {
            "symbol": "7203.T",
            "company_name": "Toyota",
            "related_keywords": ["Toyota"],
            "allow_network": True,
            "context": {
                "current_page": "cockpit",
                "user_question": "確認レポートを作って",
                "action_id": "update_research",
            },
        }
    ]
    assert "create_decision_report" in result.followup_actions

    audit = build_assistant_action_audit_entry(
        result=result,
        action=get_assistant_action("update_research"),
        context=context,
        confirmed=True,
    )

    assert audit.action_id == "update_research"
    assert audit.action_type == "data_fetch"
    assert audit.confirmed
    assert audit.status == "success"
    assert audit.symbol == "7203.T"


def test_update_research_partial_success_records_provider_gaps_without_raw_errors():
    def fake_fetcher(**_kwargs: object) -> dict[str, object]:
        return {
            "entries": [{"source_type": "news"}, {"source_type": "tdnet"}],
            "warnings": ["EDINETは該当情報なしでした。"],
            "provider_statuses": [
                {"source": "edinet", "provider": "edinet", "status": "no_result"},
                {"source": "company_ir", "provider": "ir", "status": "timeout"},
                {
                    "source": "google_news_rss",
                    "provider": "news",
                    "status": "success",
                    "error_message_short": "request_id=secret",
                },
            ],
        }

    result = AssistantActionExecutor(research_fetcher=fake_fetcher).execute(
        "update_research",
        _assistant_context(),
        confirmed=True,
    )

    assert result.status == "partial_success"
    assert result.details["entry_count"] == 2
    assert result.details["source_counts"] == {"news": 1, "tdnet": 1}
    assert result.details["no_result_sources"] == ["edinet"]
    assert result.details["timeout_sources"] == ["company_ir"]
    assert "request_id" not in json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert "retry_update_research" in result.followup_actions


def test_update_research_fetcher_exception_fails_safely_without_provider_detail():
    def failing_fetcher(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("provider raw request_id=abc token=secret")

    result = AssistantActionExecutor(research_fetcher=failing_fetcher).execute(
        "update_research",
        _assistant_context(),
        confirmed=True,
    )

    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert result.status == "failed"
    assert result.error_code == "external_fetch_failed"
    assert "request_id" not in dumped
    assert "token=secret" not in dumped
    assert "取得済み材料" in result.user_message


def test_update_research_without_fetcher_is_not_available():
    result = AssistantActionExecutor().execute(
        "update_research",
        _assistant_context(),
        confirmed=True,
    )

    assert result.status == "not_available"
    assert result.error_code == "research_fetcher_unavailable"


def test_other_followup_actions_are_not_executed_in_phase_30c_mvp():
    result = AssistantActionExecutor().execute(
        "refresh_news",
        _assistant_context(),
        confirmed=True,
    )

    assert result.status == "not_available"
    assert result.error_code == "not_implemented"
    assert "後続接続" in result.summary
