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
