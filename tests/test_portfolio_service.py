import asyncio
from datetime import date
from decimal import Decimal

import pytest

from backend.core.data_contracts import Position
from backend.core.errors import ComputationError
from backend.marketdata import DataAccess, FeatureBuilder
from backend.portfolio import PortfolioService, TargetAllocation


def _service() -> PortfolioService:
    return PortfolioService(FeatureBuilder(DataAccess()))


def test_snapshot_values_jpy_and_usd_positions_in_jpy():
    snapshot = asyncio.run(
        _service().snapshot(
            "acct-1",
            [
                Position(
                    symbol="7203.T",
                    qty=Decimal("10"),
                    avg_price=Decimal("2800"),
                    currency="JPY",
                ),
                Position(
                    symbol="AAPL",
                    qty=Decimal("2"),
                    avg_price=Decimal("170"),
                    currency="USD",
                ),
            ],
            date(2026, 4, 9),
        )
    )

    assert snapshot.total_value_jpy == Decimal("81500.00")
    values_by_symbol = {position.symbol: position.value_jpy for position in snapshot.positions}
    assert values_by_symbol == {
        "7203.T": Decimal("29000"),
        "AAPL": Decimal("52500.00"),
    }


def test_rebalance_generates_buy_trade_for_underweight_target():
    proposal = asyncio.run(
        _service().rebalance(
            "acct-1",
            [
                Position(
                    symbol="7203.T",
                    qty=Decimal("10"),
                    avg_price=Decimal("2800"),
                    currency="JPY",
                )
            ],
            [
                TargetAllocation(
                    symbol="7203.T",
                    currency="JPY",
                    target_weight=Decimal("0.5"),
                ),
                TargetAllocation(
                    symbol="AAPL",
                    currency="USD",
                    target_weight=Decimal("0.5"),
                ),
            ],
            date(2026, 4, 9),
            cash_jpy=Decimal("29000"),
        )
    )

    assert len(proposal.trades) == 1
    trade = proposal.trades[0]
    assert trade.symbol == "AAPL"
    assert trade.side == "BUY"
    assert trade.qty == Decimal("1.1048")
    assert trade.price_hint == Decimal("175.00")
    assert trade.currency == "USD"


def test_rebalance_sells_position_missing_from_targets():
    proposal = asyncio.run(
        _service().rebalance(
            "acct-1",
            [
                Position(
                    symbol="AAPL",
                    qty=Decimal("1"),
                    avg_price=Decimal("170"),
                    currency="USD",
                )
            ],
            [],
            date(2026, 4, 9),
        )
    )

    assert len(proposal.trades) == 1
    trade = proposal.trades[0]
    assert trade.symbol == "AAPL"
    assert trade.side == "SELL"
    assert trade.qty == Decimal("1.0000")
    assert trade.price_hint == Decimal("175.00")


def test_rebalance_rejects_target_weights_above_one():
    with pytest.raises(ComputationError) as exc_info:
        asyncio.run(
            _service().rebalance(
                "acct-1",
                [],
                [
                    TargetAllocation(
                        symbol="7203.T",
                        currency="JPY",
                        target_weight=Decimal("0.6"),
                    ),
                    TargetAllocation(
                        symbol="AAPL",
                        currency="USD",
                        target_weight=Decimal("0.5"),
                    ),
                ],
                date(2026, 4, 9),
            )
        )

    assert exc_info.value.to_dict() == {
        "code": "APP-2002",
        "message": "Target weights must not exceed 1",
        "details": {"target_weight_sum": "1.1"},
    }
