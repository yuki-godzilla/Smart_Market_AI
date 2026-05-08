import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.core.config import DataAccessConfig
from backend.core.errors import DataSourceError
from backend.marketdata import MarketDataProviderAdapter, create_market_data_provider_adapter


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


def test_provider_factory_returns_yahoo_stub_when_explicitly_enabled():
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    assert isinstance(adapter, MarketDataProviderAdapter)
    assert adapter.healthcheck() == {
        "provider": "yahoo",
        "status": "not_implemented",
        "adapter": "YahooMarketDataProviderAdapter",
    }


def test_yahoo_stub_reports_request_details_until_implemented():
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    with pytest.raises(DataSourceError) as exc_info:
        asyncio.run(adapter.fetch_quotes(["AAPL"], at=datetime(2026, 4, 9, tzinfo=UTC)))

    assert exc_info.value.message == "Yahoo market-data provider adapter is not implemented yet"
    details = exc_info.value.details
    assert details["provider"] == "yahoo"
    assert details["adapter_module"] == "backend.marketdata.providers.yahoo"
    assert details["optional_dependency"] == "yfinance"
    assert details["opt_in_status"] == "explicitly_enabled_stub"
    assert details["request"] == {
        "operation": "fetch_quotes",
        "symbols": ["AAPL"],
        "at": "2026-04-09T00:00:00+00:00",
    }
