import asyncio
from datetime import date
from decimal import Decimal

import pytest

from ui.rebalance_app import (
    DEFAULT_ACCOUNT_ID,
    DEFAULT_AS_OF,
    DEFAULT_CASH_JPY,
    DEFAULT_POSITIONS_JSON,
    DEFAULT_TARGETS_JSON,
    allocation_comparison_rows,
    build_default_rebalance_request,
    build_rebalance_request,
    current_position_rows,
    get_rebalance_sample,
    proposed_trade_rows,
    rebalance_sample_names,
    result_json_download,
    result_summary,
    risk_breach_rows,
    run_rebalance_check,
    runtime_settings_summary,
    sample_widget_key,
    symbol_display_name,
    symbol_reference_rows,
    target_allocation_rows,
    target_allocations_json,
)


def test_build_rebalance_request_from_default_ui_json():
    request = build_rebalance_request(
        account_id=DEFAULT_ACCOUNT_ID,
        as_of=DEFAULT_AS_OF,
        cash_jpy=DEFAULT_CASH_JPY,
        positions_json=DEFAULT_POSITIONS_JSON,
        targets_json=DEFAULT_TARGETS_JSON,
    )

    assert request.account_id == DEFAULT_ACCOUNT_ID
    assert request.positions[0].symbol == "7203.T"
    assert request.targets[1].symbol == "AAPL"
    assert request.cash_jpy == DEFAULT_CASH_JPY


def test_build_default_rebalance_request_matches_ui_defaults():
    request = build_default_rebalance_request()

    assert request.account_id == DEFAULT_ACCOUNT_ID
    assert request.as_of == DEFAULT_AS_OF
    assert request.cash_jpy == DEFAULT_CASH_JPY
    assert request.positions[0].symbol == "7203.T"
    assert request.targets[1].symbol == "AAPL"


def test_rebalance_samples_include_no_trades_case():
    sample_names = rebalance_sample_names()
    sample = get_rebalance_sample("No trades")

    assert sample_names == ["Default rebalance", "No trades"]
    assert sample.cash_jpy == Decimal("0")
    assert '"target_weight": "1.0"' in sample.targets_json


def test_get_rebalance_sample_rejects_unknown_name():
    with pytest.raises(ValueError) as exc_info:
        get_rebalance_sample("missing")

    assert str(exc_info.value) == "Unknown rebalance sample: missing"


def test_sample_widget_key_is_stable_and_sample_specific():
    assert sample_widget_key("Default rebalance", "cash_jpy") == (
        "sample_default_rebalance_cash_jpy"
    )
    assert sample_widget_key("No trades", "cash_jpy") == "sample_no_trades_cash_jpy"


def test_target_allocations_json_builds_current_mvp_symbol_targets():
    payload = target_allocations_json(
        toyota_weight=Decimal("0.75"),
        apple_weight=Decimal("0.25"),
    )

    assert '"symbol": "7203.T"' in payload
    assert '"target_weight": "0.75"' in payload
    assert '"symbol": "AAPL"' in payload
    assert '"target_weight": "0.25"' in payload


def test_symbol_display_helpers_explain_current_mvp_symbols():
    assert symbol_display_name("AAPL") == "AAPL (Apple Inc.)"
    assert symbol_display_name("7203.T") == "7203.T (Toyota Motor)"
    assert symbol_display_name("MSFT") == "MSFT"
    assert symbol_reference_rows() == [
        {"symbol": "7203.T", "name": "Toyota Motor"},
        {"symbol": "AAPL", "name": "Apple Inc."},
    ]


def test_build_rebalance_request_rejects_invalid_positions_json():
    with pytest.raises(ValueError) as exc_info:
        build_rebalance_request(
            account_id="acct-1",
            as_of=date(2026, 4, 9),
            cash_jpy=Decimal("29000"),
            positions_json="{invalid",
            targets_json=DEFAULT_TARGETS_JSON,
        )

    assert str(exc_info.value) == "positions must be valid JSON"


def test_build_rebalance_request_rejects_non_array_targets_json():
    with pytest.raises(ValueError) as exc_info:
        build_rebalance_request(
            account_id="acct-1",
            as_of=date(2026, 4, 9),
            cash_jpy=Decimal("29000"),
            positions_json=DEFAULT_POSITIONS_JSON,
            targets_json='{"symbol": "AAPL"}',
        )

    assert str(exc_info.value) == "targets must be a JSON array"


def test_runtime_settings_summary_reports_default_provider(monkeypatch):
    monkeypatch.delenv("SMAI_CONFIG_FILE", raising=False)

    summary = runtime_settings_summary()

    assert summary["provider"] == "mock"
    assert summary["config_file"] == "defaults"
    assert summary["csv_data_dir"] == "data/marketdata"


def test_rebalance_result_formatters_create_table_rows():
    request = build_rebalance_request(
        account_id="acct-1",
        as_of=date(2026, 4, 9),
        cash_jpy=Decimal("29000"),
        positions_json=DEFAULT_POSITIONS_JSON,
        targets_json=DEFAULT_TARGETS_JSON,
    )
    result = asyncio.run(run_rebalance_check(request))

    summary = result_summary(result)
    assert summary["account_id"] == "acct-1"
    assert summary["trade_count"] == "1"
    assert summary["risk_status"] == "BLOCK"

    assert current_position_rows(result.proposal)[0]["symbol"] == "7203.T (Toyota Motor)"
    assert target_allocation_rows(result.proposal)[1]["symbol"] == "AAPL (Apple Inc.)"
    assert allocation_comparison_rows(result.proposal) == [
        {
            "symbol": "7203.T (Toyota Motor)",
            "current_weight": "0.5",
            "target_weight": "0.5",
            "drift": "0",
        },
        {
            "symbol": "AAPL (Apple Inc.)",
            "current_weight": "0",
            "target_weight": "0.5",
            "drift": "0.5",
        },
    ]
    assert proposed_trade_rows(result.proposal)[0]["side"] == "BUY"
    assert risk_breach_rows(result) == [
        {"breach": "R5:min_dividend_yield:AAPL"},
        {"breach": "R3:max_concentration"},
    ]


def test_result_json_download_contains_portfolio_risk_result():
    request = build_default_rebalance_request()
    result = asyncio.run(run_rebalance_check(request))

    payload = result_json_download(result)

    assert '"proposal"' in payload
    assert '"risk_decision"' in payload
    assert '"status": "BLOCK"' in payload
