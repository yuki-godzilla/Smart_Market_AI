import asyncio
from datetime import date
from decimal import Decimal

from backend.core.data_contracts import Position
from backend.marketdata import DataAccess, FeatureBuilder
from backend.portfolio import PortfolioRiskWorkflow, PortfolioService, TargetAllocation
from backend.risk import RiskService


def _workflow() -> PortfolioRiskWorkflow:
    feature_builder = FeatureBuilder(DataAccess())
    return PortfolioRiskWorkflow(
        PortfolioService(feature_builder),
        RiskService(feature_builder),
    )


def test_propose_and_check_sends_generated_trades_to_risk():
    result = asyncio.run(
        _workflow().propose_and_check(
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

    assert [trade.symbol for trade in result.proposal.trades] == ["AAPL"]
    assert result.risk_decision is not None
    assert result.risk_decision.status == "BLOCK"
    assert result.risk_decision.breaches == [
        "R5:min_dividend_yield:AAPL",
        "R3:max_concentration",
    ]


def test_propose_and_check_skips_risk_when_no_trades_are_generated():
    result = asyncio.run(
        _workflow().propose_and_check(
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
                    target_weight=Decimal("1"),
                )
            ],
            date(2026, 4, 9),
        )
    )

    assert result.proposal.trades == []
    assert result.risk_decision is None
