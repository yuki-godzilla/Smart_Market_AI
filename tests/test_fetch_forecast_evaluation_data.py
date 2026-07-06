from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from tools.fetch_forecast_evaluation_data import (
    DEFAULT_SYMBOLS,
    _write_ohlcv,
    main,
)


def test_live_fetch_requires_explicit_opt_in():
    with pytest.raises(SystemExit):
        main([])


def test_live_fetch_default_universe_covers_jp_us_stock_and_etf():
    assert {"7203.T", "1306.T", "AAPL", "SPY"}.issubset(DEFAULT_SYMBOLS)


def test_live_fetch_writer_is_deterministic(tmp_path):
    symbol = Symbol(
        raw="AAPL",
        exchange="NASDAQ",
        code="AAPL",
        currency="USD",
    )
    bars = [
        Bar(
            symbol=symbol,
            ts=datetime(2026, 1, 2, tzinfo=UTC),
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=Decimal("1000"),
            interval="1d",
            provider="yahoo",
        )
    ]

    path = tmp_path / "ohlcv.csv"
    _write_ohlcv(path, bars)

    text = path.read_text(encoding="utf-8")
    assert text.startswith("symbol,ts,open,high,low,close,volume\n")
    assert "AAPL,2026-01-02T00:00:00+00:00,100,102,99,101,1000" in text
