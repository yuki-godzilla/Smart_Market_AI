from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.core.data_contracts import DailySnapshot, FeatureSnapshot, FxRate, Symbol, TradeIntent


def test_trade_intent_accepts_valid_buy_order():
    intent = TradeIntent(
        symbol="7203.T",
        side="BUY",
        qty=Decimal("100"),
        price_hint=Decimal("2800.5"),
        currency="JPY",
    )

    assert intent.symbol == "7203.T"
    assert intent.qty == Decimal("100")


def test_trade_intent_rejects_negative_quantity():
    with pytest.raises(ValidationError):
        TradeIntent(symbol="AAPL", side="BUY", qty=Decimal("-1"), currency="USD")


def test_daily_snapshot_defaults_missing_flags():
    snapshot = DailySnapshot(symbol="AAPL", as_of=date(2026, 4, 11))

    assert snapshot.missing == {}
    assert snapshot.data_quality == "OK"
    assert snapshot.data_quality_reasons == []


def test_feature_snapshot_carries_provider_metadata():
    row = DailySnapshot(
        symbol="AAPL",
        as_of=date(2026, 4, 11),
        missing={"dividend_yield": True},
    )
    snapshot = FeatureSnapshot(
        as_of=date(2026, 4, 11),
        provider="mock",
        rows=[row],
        missing_summary={"dividend_yield": 1},
    )

    assert snapshot.feature_version == "feature-snapshot-v1"
    assert snapshot.provider == "mock"
    assert snapshot.missing_summary == {"dividend_yield": 1}
    assert snapshot.quality_summary == {}
    assert snapshot.rows[0].last is None


def test_fx_rate_requires_supported_pair():
    fx = FxRate(pair="USDJPY", rate=Decimal("151.25"), ts=datetime.now(UTC))

    assert fx.rate == Decimal("151.25")


def test_symbol_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Symbol(raw="AAPL", exchange="NASDAQ", code="AAPL", currency="USD", country="US")
