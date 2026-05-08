from datetime import UTC, datetime

from backend.marketdata import DataAccess, MarketDataProviderAdapter


def test_data_access_satisfies_market_data_provider_adapter_protocol():
    adapter: MarketDataProviderAdapter = DataAccess()

    assert isinstance(adapter, MarketDataProviderAdapter)
    assert adapter.healthcheck() == {"provider": "mock", "status": "ok"}


def test_market_data_provider_adapter_protocol_exposes_async_contracts():
    adapter: MarketDataProviderAdapter = DataAccess()

    assert callable(adapter.fetch_ohlcv)
    assert callable(adapter.fetch_quotes)
    assert callable(adapter.get_fx_rates)
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

    assert asyncio.run(_fetch_one_bar(DataAccess())) == 1
