import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import pytest

from backend.core.config import DataAccessConfig
from backend.core.errors import DataSourceError, ProviderUnavailableError
from backend.marketdata import MarketDataProviderAdapter, create_market_data_provider_adapter
from backend.marketdata.providers import yahoo


def test_provider_factory_returns_mock_adapter_by_default():
    adapter = create_market_data_provider_adapter()

    assert isinstance(adapter, MarketDataProviderAdapter)
    assert adapter.healthcheck() == {"provider": "mock", "status": "ok"}


def test_provider_factory_returns_csv_adapter():
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="csv", csv_data_dir="tests/fixtures/marketdata_csv")
    )

    rates = asyncio.run(adapter.get_fx_rates(["USDJPY"], at=datetime(2026, 4, 9, tzinfo=UTC)))

    assert rates[0].rate == Decimal("150.00")
    assert rates[0].source == "csv"


def test_provider_factory_preserves_live_provider_opt_in_error():
    with pytest.raises(DataSourceError) as exc_info:
        create_market_data_provider_adapter(DataAccessConfig(provider="yahoo"))

    details = exc_info.value.details
    assert details["provider"] == "yahoo"
    assert details["adapter_protocol"] == "MarketDataProviderAdapter"
    assert details["opt_in_status"] == "explicit_config_required"


def test_provider_factory_returns_yahoo_adapter_when_explicitly_enabled(monkeypatch):
    monkeypatch.setattr(yahoo, "_yfinance_available", lambda: True)
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    assert isinstance(adapter, MarketDataProviderAdapter)
    assert adapter.healthcheck() == {
        "provider": "yahoo",
        "status": "available",
        "adapter": "YahooMarketDataProviderAdapter",
    }


def test_yahoo_adapter_reports_missing_optional_dependency(monkeypatch):
    def raise_missing_dependency():
        raise ProviderUnavailableError("missing", details={"provider": "yahoo"})

    monkeypatch.setattr(yahoo, "_load_yfinance", raise_missing_dependency)
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    with pytest.raises(ProviderUnavailableError) as exc_info:
        asyncio.run(adapter.fetch_quotes(["AAPL"], at=datetime(2026, 4, 9, tzinfo=UTC)))

    assert exc_info.value.message == "missing"
    assert exc_info.value.details["provider"] == "yahoo"


def test_yahoo_adapter_fetches_live_contracts_from_yfinance(monkeypatch):
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: _FakeYFinance())
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    bars = asyncio.run(
        adapter.fetch_ohlcv(
            ["AAPL"],
            start=datetime(2026, 4, 7, tzinfo=UTC),
            end=datetime(2026, 4, 9, tzinfo=UTC),
        )
    )
    quotes = asyncio.run(adapter.fetch_quotes(["AAPL"], at=datetime(2026, 4, 9, tzinfo=UTC)))
    rates = asyncio.run(adapter.get_fx_rates(["USDJPY"], at=datetime(2026, 4, 9, tzinfo=UTC)))

    assert [bar.close for bar in bars] == [Decimal("170.5"), Decimal("175.25")]
    assert bars[0].symbol.raw == "AAPL"
    assert bars[0].symbol.exchange == "NASDAQ"
    assert bars[0].provider == "yahoo"
    assert quotes[0].last == Decimal("175.25")
    assert rates[0].rate == Decimal("150.12")
    assert rates[0].source == "yahoo"


def test_yahoo_adapter_maps_empty_history_to_provider_unavailable(monkeypatch):
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: _FakeYFinance(empty=True))
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    with pytest.raises(ProviderUnavailableError) as exc_info:
        asyncio.run(adapter.fetch_quotes(["AAPL"], at=datetime(2026, 4, 9, tzinfo=UTC)))

    details = exc_info.value.details
    assert details["provider"] == "yahoo"
    assert details["opt_in_status"] == "explicitly_enabled_live"
    assert details["request"]["operation"] == "fetch_quotes"


class _FakeYFinance:
    def __init__(self, *, empty: bool = False) -> None:
        self.empty = empty

    def Ticker(self, raw_symbol: str) -> "_FakeTicker":
        return _FakeTicker(raw_symbol, empty=self.empty)


class _FakeTicker:
    def __init__(self, raw_symbol: str, *, empty: bool) -> None:
        self.raw_symbol = raw_symbol
        self.empty = empty

    def history(self, **_: object) -> pd.DataFrame:
        if self.empty:
            return pd.DataFrame()
        if self.raw_symbol == "JPY=X":
            return pd.DataFrame(
                {
                    "Open": [Decimal("149.80")],
                    "High": [Decimal("150.50")],
                    "Low": [Decimal("149.70")],
                    "Close": [Decimal("150.12")],
                    "Volume": [Decimal("0")],
                },
                index=pd.to_datetime(["2026-04-09T00:00:00Z"]),
            )
        return pd.DataFrame(
            {
                "Open": [Decimal("169.0"), Decimal("174.0")],
                "High": [Decimal("171.0"), Decimal("176.0")],
                "Low": [Decimal("168.0"), Decimal("173.0")],
                "Close": [Decimal("170.5"), Decimal("175.25")],
                "Volume": [Decimal("61000000"), Decimal("62000000")],
            },
            index=pd.to_datetime(["2026-04-08T00:00:00Z", "2026-04-09T00:00:00Z"]),
        )
