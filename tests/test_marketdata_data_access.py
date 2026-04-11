import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.core.config import DataAccessConfig
from backend.core.errors import DataSourceError
from backend.marketdata import DataAccess


def test_fetch_ohlcv_returns_mock_bars():
    da = DataAccess()

    bars = asyncio.run(
        da.fetch_ohlcv(
            ["AAPL"],
            start=datetime(2026, 4, 7, tzinfo=UTC),
            end=datetime(2026, 4, 9, tzinfo=UTC),
        )
    )

    assert len(bars) == 3
    assert bars[0].symbol.raw == "AAPL"
    assert bars[0].symbol.exchange == "NASDAQ"
    assert bars[0].close == Decimal("170.00")
    assert bars[0].provider == "mock"


def test_fetch_quotes_returns_latest_available_quote():
    da = DataAccess()

    quotes = asyncio.run(da.fetch_quotes(["7203.T"], at=datetime(2026, 4, 9, 12, 0, tzinfo=UTC)))

    assert len(quotes) == 1
    assert quotes[0].symbol.code == "7203"
    assert quotes[0].last == Decimal("2900")


def test_get_fx_rates_returns_usdjpy():
    da = DataAccess()

    rates = asyncio.run(da.get_fx_rates(["USDJPY"], at=datetime(2026, 4, 9, tzinfo=UTC)))

    assert len(rates) == 1
    assert rates[0].pair == "USDJPY"
    assert rates[0].rate == Decimal("150.00")
    assert rates[0].source == "mock"


def test_unsupported_provider_is_rejected():
    with pytest.raises(DataSourceError) as exc_info:
        DataAccess(DataAccessConfig(provider="yahoo"))

    assert exc_info.value.details == {"provider": "yahoo"}


def test_unsupported_symbol_is_rejected():
    da = DataAccess()

    with pytest.raises(DataSourceError) as exc_info:
        asyncio.run(
            da.fetch_ohlcv(
                ["MSFT"],
                start=datetime(2026, 4, 7, tzinfo=UTC),
                end=datetime(2026, 4, 9, tzinfo=UTC),
            )
        )

    assert exc_info.value.details == {"symbol": "MSFT"}


def test_unsupported_fx_pair_is_rejected():
    da = DataAccess()

    with pytest.raises(DataSourceError) as exc_info:
        asyncio.run(da.get_fx_rates(["EURJPY"]))

    assert exc_info.value.details == {"pair": "EURJPY"}


def test_healthcheck_reports_mock_provider():
    assert DataAccess().healthcheck() == {"provider": "mock", "status": "ok"}
