import asyncio
from datetime import date
from decimal import Decimal

from backend.core.config import FeatureBuilderConfig, RiskConfig, RiskThresholdsConfig
from backend.core.data_contracts import TradeIntent
from backend.marketdata import DataAccess, FeatureBuilder
from backend.risk import RiskService


def test_pre_trade_check_allows_small_basket_when_soft_rules_are_relaxed():
    service = RiskService(
        FeatureBuilder(DataAccess(), cfg=FeatureBuilderConfig(adv_window=2, vol_window=2)),
        cfg=RiskConfig(
            thresholds=RiskThresholdsConfig(
                max_notional_per_symbol=3_000_000,
                max_notional_per_basket=10_000_000,
                max_concentration=1.0,
                min_adv=1,
                min_dividend_yield=0,
                max_volatility=1,
            )
        ),
    )

    decision = asyncio.run(
        service.pre_trade_check(
            [
                TradeIntent(
                    symbol="7203.T",
                    side="BUY",
                    qty=Decimal("100"),
                    price_hint=Decimal("2900"),
                    currency="JPY",
                )
            ],
            date(2026, 4, 9),
            "acct-1",
        )
    )

    assert decision.status == "ALLOW"
    assert decision.breaches == []


def test_pre_trade_check_reviews_when_dividend_data_is_missing():
    service = RiskService(
        FeatureBuilder(DataAccess(), cfg=FeatureBuilderConfig(adv_window=2, vol_window=2)),
        cfg=RiskConfig(
            thresholds=RiskThresholdsConfig(
                max_notional_per_symbol=3_000_000,
                max_notional_per_basket=10_000_000,
                max_concentration=1.0,
                min_adv=1,
                min_dividend_yield=0.03,
                max_volatility=1,
            )
        ),
    )

    decision = asyncio.run(
        service.pre_trade_check(
            [
                TradeIntent(
                    symbol="AAPL",
                    side="BUY",
                    qty=Decimal("10"),
                    price_hint=Decimal("175"),
                    currency="USD",
                )
            ],
            date(2026, 4, 9),
            "acct-1",
        )
    )

    assert decision.status == "REVIEW"
    assert "R5:min_dividend_yield:AAPL" in decision.breaches


def test_pre_trade_check_blocks_when_symbol_notional_exceeds_threshold():
    service = RiskService(
        FeatureBuilder(DataAccess(), cfg=FeatureBuilderConfig(adv_window=2, vol_window=2)),
        cfg=RiskConfig(
            thresholds=RiskThresholdsConfig(
                max_notional_per_symbol=100_000,
                max_notional_per_basket=10_000_000,
                max_concentration=1.0,
                min_adv=1,
                min_dividend_yield=0,
                max_volatility=1,
            )
        ),
    )

    decision = asyncio.run(
        service.pre_trade_check(
            [
                TradeIntent(
                    symbol="7203.T",
                    side="BUY",
                    qty=Decimal("100"),
                    price_hint=Decimal("2900"),
                    currency="JPY",
                )
            ],
            date(2026, 4, 9),
            "acct-1",
        )
    )

    assert decision.status == "BLOCK"
    assert "R1:max_notional_per_symbol:7203.T" in decision.breaches
