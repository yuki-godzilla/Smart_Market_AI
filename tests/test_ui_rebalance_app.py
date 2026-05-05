import asyncio
from datetime import date
from decimal import Decimal

import pytest

from ui.rebalance_app import (
    DEFAULT_POSITIONS_JSON,
    DEFAULT_TARGETS_JSON,
    build_rebalance_request,
    current_position_rows,
    proposed_trade_rows,
    result_summary,
    risk_breach_rows,
    run_rebalance_check,
    target_allocation_rows,
)


def test_build_rebalance_request_from_default_ui_json():
    request = build_rebalance_request(
        account_id="acct-1",
        as_of=date(2026, 4, 9),
        cash_jpy=Decimal("29000"),
        positions_json=DEFAULT_POSITIONS_JSON,
        targets_json=DEFAULT_TARGETS_JSON,
    )

    assert request.account_id == "acct-1"
    assert request.positions[0].symbol == "7203.T"
    assert request.targets[1].symbol == "AAPL"
    assert request.cash_jpy == Decimal("29000")


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

    assert current_position_rows(result.proposal)[0]["symbol"] == "7203.T"
    assert target_allocation_rows(result.proposal)[1]["symbol"] == "AAPL"
    assert proposed_trade_rows(result.proposal)[0]["side"] == "BUY"
    assert risk_breach_rows(result) == [
        {"breach": "R5:min_dividend_yield:AAPL"},
        {"breach": "R3:max_concentration"},
    ]
