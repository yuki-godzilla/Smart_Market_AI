from datetime import UTC, date, datetime

from backend.core.config import DataAccessConfig
from backend.marketdata import DataAccess, MarketDataProviderAdapter


def _mock_data_access() -> DataAccess:
    return DataAccess(DataAccessConfig(provider="mock"))


def test_data_access_satisfies_market_data_provider_adapter_protocol():
    adapter: MarketDataProviderAdapter = _mock_data_access()

    assert isinstance(adapter, MarketDataProviderAdapter)
    assert adapter.healthcheck() == {"provider": "mock", "status": "ok"}


def test_market_data_provider_adapter_protocol_exposes_async_contracts():
    adapter: MarketDataProviderAdapter = _mock_data_access()

    assert callable(adapter.fetch_ohlcv)
    assert callable(adapter.fetch_quotes)
    assert callable(adapter.get_fx_rates)
    assert callable(adapter.fetch_fundamentals)
    assert callable(adapter.healthcheck)


async def _fetch_one_bar(adapter: MarketDataProviderAdapter) -> int:
    bars = await adapter.fetch_ohlcv(
        ["AAPL"],
        start=datetime(2026, 4, 7, tzinfo=UTC),
        end=datetime(2026, 4, 7, tzinfo=UTC),
    )
    return len(bars)


def test_market_data_provider_adapter_can_be_used_as_async_boundary():
    import asyncio

    assert asyncio.run(_fetch_one_bar(_mock_data_access())) == 1


def test_data_access_fetches_mock_fundamentals():
    import asyncio

    fundamentals = asyncio.run(_mock_data_access().fetch_fundamentals(["AAPL"], date(2026, 4, 9)))

    assert fundamentals[0].symbol == "AAPL"
    assert fundamentals[0].provider == "mock"
    assert fundamentals[0].dividend_yield is not None
    assert fundamentals[0].market_cap_jpy is not None
