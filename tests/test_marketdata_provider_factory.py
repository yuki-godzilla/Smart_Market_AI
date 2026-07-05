import asyncio
import logging
from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from backend.core.config import DataAccessConfig
from backend.core.errors import DataSourceError, ProviderUnavailableError, SchemaMismatchError
from backend.marketdata import MarketDataProviderAdapter, create_market_data_provider_adapter
from backend.marketdata.providers import yahoo


def test_provider_factory_returns_yahoo_adapter_by_default(monkeypatch):
    monkeypatch.setattr(yahoo, "_yfinance_available", lambda: True)

    adapter = create_market_data_provider_adapter()

    assert isinstance(adapter, MarketDataProviderAdapter)
    assert adapter.healthcheck() == {
        "provider": "yahoo",
        "status": "available",
        "adapter": "YahooMarketDataProviderAdapter",
    }


def test_provider_factory_returns_mock_adapter_when_configured_for_tests():
    adapter = create_market_data_provider_adapter(DataAccessConfig(provider="mock"))

    assert isinstance(adapter, MarketDataProviderAdapter)
    assert adapter.healthcheck() == {"provider": "mock", "status": "ok"}


def test_provider_factory_returns_csv_adapter():
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="csv", csv_data_dir="tests/fixtures/marketdata_csv")
    )

    rates = asyncio.run(adapter.get_fx_rates(["USDJPY"], at=datetime(2026, 4, 9, tzinfo=UTC)))

    assert rates[0].rate == Decimal("150.00")
    assert rates[0].source == "csv"

    fundamentals = asyncio.run(adapter.fetch_fundamentals(["AAPL"], as_of=date(2026, 4, 9)))
    assert fundamentals[0].dividend_yield == Decimal("0.005")
    assert fundamentals[0].market_cap_jpy == Decimal("450000000000000")


def test_provider_factory_preserves_live_provider_disabled_error():
    with pytest.raises(DataSourceError) as exc_info:
        create_market_data_provider_adapter(
            DataAccessConfig(provider="yahoo", allow_external_providers=False)
        )

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
    fake_yfinance = _FakeYFinance()
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
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
    fundamentals = asyncio.run(adapter.fetch_fundamentals(["AAPL"], as_of=date(2026, 4, 9)))

    assert [bar.close for bar in bars] == [Decimal("170.5"), Decimal("175.25")]
    assert fake_yfinance.download_calls == 0
    assert fake_yfinance.ticker_sessions == [
        "shared-session",
        "shared-session",
        "shared-session",
        "shared-session",
    ]
    assert bars[0].symbol.raw == "AAPL"
    assert bars[0].symbol.exchange == "NASDAQ"
    assert bars[0].provider == "yahoo"
    assert quotes[0].last == Decimal("175.25")
    assert rates[0].rate == Decimal("150.12")
    assert rates[0].source == "yahoo"
    assert fundamentals[0].dividend_yield == Decimal("0.006")
    assert fundamentals[0].market_cap_jpy == Decimal("480000000000000")


def test_yahoo_adapter_normalizes_percent_style_dividend_yield(monkeypatch):
    fake_yfinance = _FakeYFinance(ticker_info={"dividendYield": Decimal("1.32")})
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    fundamentals = asyncio.run(adapter.fetch_fundamentals(["6479.T"], as_of=date(2026, 6, 1)))

    assert fundamentals[0].dividend_yield == Decimal("0.0132")


def test_yahoo_adapter_scales_jp_integer_dividend_yield_basis_points(monkeypatch):
    fake_yfinance = _FakeYFinance(ticker_info={"dividendYield": Decimal("23")})
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    fundamentals = asyncio.run(adapter.fetch_fundamentals(["7203.T"], as_of=date(2026, 6, 1)))

    assert fundamentals[0].dividend_yield == Decimal("0.0023")


def test_yahoo_adapter_drops_abnormal_dividend_yield(monkeypatch):
    fake_yfinance = _FakeYFinance(ticker_info={"dividendYield": Decimal("293.19")})
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    fundamentals = asyncio.run(adapter.fetch_fundamentals(["GMEX"], as_of=date(2026, 6, 1)))

    assert fundamentals[0].dividend_yield is None


def test_yahoo_adapter_fetches_multiple_ohlcv_symbols_with_download(monkeypatch):
    fake_yfinance = _FakeYFinance()
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    bars = asyncio.run(
        adapter.fetch_ohlcv(
            ["AAPL", "MSFT"],
            start=datetime(2026, 4, 7, tzinfo=UTC),
            end=datetime(2026, 4, 9, tzinfo=UTC),
        )
    )

    assert fake_yfinance.download_calls == 1
    assert fake_yfinance.last_download_kwargs["threads"] is False
    assert fake_yfinance.last_download_kwargs["session"] == "shared-session"
    assert [bar.symbol.raw for bar in bars] == ["AAPL", "AAPL", "MSFT", "MSFT"]
    assert [bar.close for bar in bars] == [
        Decimal("170.5"),
        Decimal("175.25"),
        Decimal("270.5"),
        Decimal("275.25"),
    ]


def test_yahoo_adapter_retries_empty_batch_download_once(monkeypatch):
    fake_yfinance = _FakeYFinance(empty_download_attempts=1)
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    monkeypatch.setattr(yahoo, "YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS", 0)
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    bars = asyncio.run(
        adapter.fetch_ohlcv(
            ["AAPL", "MSFT"],
            start=datetime(2026, 4, 7, tzinfo=UTC),
            end=datetime(2026, 4, 9, tzinfo=UTC),
        )
    )

    assert fake_yfinance.download_calls == 2
    assert [bar.symbol.raw for bar in bars] == ["AAPL", "AAPL", "MSFT", "MSFT"]
    assert [bar.close for bar in bars] == [
        Decimal("170.5"),
        Decimal("175.25"),
        Decimal("270.5"),
        Decimal("275.25"),
    ]


def test_yahoo_adapter_uses_ticker_history_for_single_ohlcv(monkeypatch):
    fake_yfinance = _FakeYFinance(empty_download_attempts=10)
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    monkeypatch.setattr(yahoo, "YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS", 0)
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

    assert fake_yfinance.download_calls == 0
    assert fake_yfinance.ticker_sessions == ["shared-session"]
    assert [bar.close for bar in bars] == [Decimal("170.5"), Decimal("175.25")]


def test_yahoo_adapter_drops_trailing_empty_japan_history_row(monkeypatch):
    history_frame = pd.DataFrame(
        {
            "Open": [Decimal("2890"), Decimal("2900"), float("nan")],
            "High": [Decimal("2910"), Decimal("2920"), float("nan")],
            "Low": [Decimal("2880"), Decimal("2895"), float("nan")],
            "Close": [Decimal("2905"), Decimal("2915"), float("nan")],
            "Volume": [Decimal("21000000"), Decimal("22000000"), float("nan")],
        },
        index=pd.to_datetime(
            [
                "2026-06-22T00:00:00+09:00",
                "2026-06-23T00:00:00+09:00",
                "2026-06-24T00:00:00+09:00",
            ]
        ),
    )
    fake_yfinance = _FakeYFinance(history_frame=history_frame)
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    bars = asyncio.run(
        adapter.fetch_ohlcv(
            ["7203.T"],
            start=datetime(2026, 6, 22, tzinfo=UTC),
            end=datetime(2026, 6, 23, tzinfo=UTC),
        )
    )

    assert [bar.symbol.raw for bar in bars] == ["7203.T", "7203.T"]
    assert [bar.symbol.currency for bar in bars] == ["JPY", "JPY"]
    assert [bar.close for bar in bars] == [Decimal("2905"), Decimal("2915")]


def test_yahoo_download_symbol_frame_supports_price_ticker_multiindex():
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], ["7203.T", "6758.T"]]
    )
    frame = pd.DataFrame(
        [
            [
                Decimal("1"),
                Decimal("2"),
                Decimal("3"),
                Decimal("4"),
                Decimal("5"),
                Decimal("6"),
                Decimal("7"),
                Decimal("8"),
                Decimal("9"),
                Decimal("10"),
            ]
        ],
        columns=columns,
        index=pd.to_datetime(["2026-06-23T00:00:00Z"]),
    )

    symbol_frame = yahoo._download_symbol_frame(frame, "7203.T")

    assert list(symbol_frame.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert symbol_frame.iloc[0]["Close"] == Decimal("7")


def test_yahoo_bar_from_history_row_skips_lingering_invalid_close():
    symbol = yahoo._normalize_symbol("7203.T")
    row = pd.Series(
        {
            "Open": Decimal("2900"),
            "High": Decimal("2920"),
            "Low": Decimal("2895"),
            "Close": float("nan"),
            "Volume": Decimal("22000000"),
        }
    )

    assert (
        yahoo._bar_from_history_row(
            row,
            ts=pd.Timestamp("2026-06-23T00:00:00+09:00"),
            symbol=symbol,
            interval="1d",
        )
        is None
    )


def test_yahoo_adapter_quote_uses_last_valid_close_row(monkeypatch):
    history_frame = pd.DataFrame(
        {
            "Open": [Decimal("174"), float("nan")],
            "High": [Decimal("176"), float("nan")],
            "Low": [Decimal("173"), float("nan")],
            "Close": [Decimal("175.25"), float("nan")],
            "Volume": [Decimal("62000000"), float("nan")],
        },
        index=pd.to_datetime(["2026-04-09T00:00:00Z", "2026-04-10T00:00:00Z"]),
    )
    fake_yfinance = _FakeYFinance(history_frame=history_frame)
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    quotes = asyncio.run(adapter.fetch_quotes(["AAPL"], at=datetime(2026, 4, 10, tzinfo=UTC)))

    assert quotes[0].last == Decimal("175.25")


def test_yahoo_adapter_fx_uses_last_valid_close_row_even_when_volume_is_empty(monkeypatch):
    history_frame = pd.DataFrame(
        {
            "Open": [float("nan"), float("nan")],
            "High": [float("nan"), float("nan")],
            "Low": [float("nan"), float("nan")],
            "Close": [Decimal("150.12"), float("nan")],
            "Volume": [float("nan"), float("nan")],
        },
        index=pd.to_datetime(["2026-04-09T00:00:00Z", "2026-04-10T00:00:00Z"]),
    )
    fake_yfinance = _FakeYFinance(history_frame=history_frame)
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    rates = asyncio.run(adapter.get_fx_rates(["USDJPY"], at=datetime(2026, 4, 10, tzinfo=UTC)))

    assert rates[0].rate == Decimal("150.12")


def test_yahoo_adapter_reports_all_invalid_history_rows(monkeypatch):
    history_frame = pd.DataFrame(
        {
            "Open": [float("nan")],
            "High": [float("nan")],
            "Low": [float("nan")],
            "Close": [float("nan")],
            "Volume": [float("nan")],
        },
        index=pd.to_datetime(["2026-06-24T00:00:00+09:00"]),
    )
    fake_yfinance = _FakeYFinance(history_frame=history_frame)
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    with pytest.raises(ProviderUnavailableError) as exc_info:
        asyncio.run(
            adapter.fetch_ohlcv(
                ["7203.T"],
                start=datetime(2026, 6, 22, tzinfo=UTC),
                end=datetime(2026, 6, 23, tzinfo=UTC),
            )
        )

    assert exc_info.value.message == "Yahoo market-data provider returned no valid numeric data"
    request = exc_info.value.details["request"]
    assert request["invalid_numeric_rows"] == "all"
    assert request["required_numeric_columns"] == ["Open", "High", "Low", "Close", "Volume"]


@pytest.mark.parametrize(
    "value",
    [None, "", "NaN", "nan", Decimal("NaN"), float("inf"), float("-inf")],
)
def test_yahoo_decimal_cell_rejects_empty_or_non_finite_values(value):
    row = pd.Series({"Close": value})

    with pytest.raises(SchemaMismatchError):
        yahoo._decimal_cell(row, "Close")


def test_yahoo_adapter_reports_empty_single_history(monkeypatch):
    fake_yfinance = _FakeYFinance(empty=True)
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    monkeypatch.setattr(yahoo, "YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS", 0)
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    with pytest.raises(ProviderUnavailableError) as exc_info:
        asyncio.run(
            adapter.fetch_ohlcv(
                ["AAPL"],
                start=datetime(2026, 4, 7, tzinfo=UTC),
                end=datetime(2026, 4, 9, tzinfo=UTC),
            )
        )

    assert fake_yfinance.download_calls == 0
    request = exc_info.value.details["request"]
    assert request["operation"] == "fetch_ohlcv"
    assert exc_info.value.message == "Yahoo market-data provider returned no data"


def test_yahoo_adapter_reports_single_history_request_failure(monkeypatch):
    fake_yfinance = _FakeYFinance(
        empty_download_attempts=10,
        history_error=RuntimeError("DNS timeout"),
    )
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    monkeypatch.setattr(yahoo, "YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS", 0)
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    with pytest.raises(ProviderUnavailableError) as exc_info:
        asyncio.run(
            adapter.fetch_ohlcv(
                ["AAPL"],
                start=datetime(2026, 4, 7, tzinfo=UTC),
                end=datetime(2026, 4, 9, tzinfo=UTC),
            )
        )

    assert fake_yfinance.download_calls == 0
    assert exc_info.value.message == "Yahoo market-data provider request failed"
    request = exc_info.value.details["request"]
    assert request["operation"] == "fetch_ohlcv"
    assert request["error"] == "DNS timeout"


def test_yahoo_adapter_retries_single_history_without_raise_errors(monkeypatch):
    fake_yfinance = _FakeYFinance(
        history_error=RuntimeError("$6758.T: possibly delisted; no price data found"),
        history_error_when_raise_errors=True,
    )
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    bars = asyncio.run(
        adapter.fetch_ohlcv(
            ["6758.T"],
            start=datetime(2025, 6, 9, tzinfo=UTC),
            end=datetime(2026, 6, 9, tzinfo=UTC),
        )
    )

    assert fake_yfinance.download_calls == 0
    assert [call["raise_errors"] for call in fake_yfinance.history_calls[:2]] == [True, False]
    assert [bar.symbol.raw for bar in bars] == ["6758.T", "6758.T"]
    assert [bar.close for bar in bars] == [Decimal("170.5"), Decimal("175.25")]


def test_yahoo_adapter_retries_single_history_after_transient_request_error(monkeypatch):
    fake_yfinance = _FakeYFinance(
        history_errors=[
            RuntimeError(
                "Failed to perform, curl: (28) Resolving timed out after 5003 milliseconds"
            )
        ],
    )
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    monkeypatch.setattr(yahoo, "reset_shared_yfinance_session", lambda: None)
    monkeypatch.setattr(yahoo, "YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS", 0)
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    bars = asyncio.run(
        adapter.fetch_ohlcv(
            ["6758.T"],
            start=datetime(2025, 6, 9, tzinfo=UTC),
            end=datetime(2026, 6, 9, tzinfo=UTC),
        )
    )

    assert fake_yfinance.download_calls == 0
    assert len(fake_yfinance.history_calls) == 2
    assert [bar.symbol.raw for bar in bars] == ["6758.T", "6758.T"]
    assert [bar.close for bar in bars] == [Decimal("170.5"), Decimal("175.25")]


def test_yahoo_adapter_retries_single_history_after_connection_refused(monkeypatch):
    fake_yfinance = _FakeYFinance(
        history_errors=[
            RuntimeError(
                "Failed to perform, curl: (7) Failed to connect to "
                "query1.finance.yahoo.com port 443: Could not connect to server"
            )
        ],
    )
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: fake_yfinance)
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    monkeypatch.setattr(yahoo, "reset_shared_yfinance_session", lambda: None)
    monkeypatch.setattr(yahoo, "YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS", 0)
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    bars = asyncio.run(
        adapter.fetch_ohlcv(
            ["7203.T"],
            start=datetime(2025, 6, 9, tzinfo=UTC),
            end=datetime(2026, 6, 9, tzinfo=UTC),
        )
    )

    assert len(fake_yfinance.history_calls) == 2
    assert [bar.symbol.raw for bar in bars] == ["7203.T", "7203.T"]


def test_yahoo_adapter_maps_empty_history_to_provider_unavailable(monkeypatch):
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: _FakeYFinance(empty=True))
    monkeypatch.setattr(yahoo, "shared_yfinance_session", lambda: "shared-session")
    adapter = create_market_data_provider_adapter(
        DataAccessConfig(provider="yahoo", allow_external_providers=True)
    )

    with pytest.raises(ProviderUnavailableError) as exc_info:
        asyncio.run(adapter.fetch_quotes(["AAPL"], at=datetime(2026, 4, 9, tzinfo=UTC)))

    details = exc_info.value.details
    assert details["provider"] == "yahoo"
    assert details["implemented"] is True
    assert details["live_adapter"] == "implemented_opt_in"
    assert details["opt_in_status"] == "explicitly_enabled_live"
    assert details["request"]["operation"] == "fetch_quotes"


class _FakeYFinance:
    def __init__(
        self,
        *,
        empty: bool = False,
        empty_download_attempts: int = 0,
        ticker_info: dict[str, object] | None = None,
        history_error: Exception | None = None,
        history_error_when_raise_errors: bool = False,
        history_errors: list[Exception] | None = None,
        history_frame: pd.DataFrame | None = None,
    ) -> None:
        self.empty = empty
        self.empty_download_attempts = empty_download_attempts
        self.ticker_info = ticker_info
        self.history_error = history_error
        self.history_error_when_raise_errors = history_error_when_raise_errors
        self.history_errors = list(history_errors or [])
        self.history_frame = history_frame
        self.download_calls = 0
        self.ticker_sessions: list[object] = []
        self.history_calls: list[dict[str, object]] = []
        self.last_download_kwargs: dict[str, object] = {}

    def Ticker(self, raw_symbol: str, session: object | None = None) -> "_FakeTicker":
        self.ticker_sessions.append(session)
        return _FakeTicker(
            raw_symbol,
            empty=self.empty,
            info=self.ticker_info,
            history_error=self.history_error,
            history_error_when_raise_errors=self.history_error_when_raise_errors,
            history_errors=self.history_errors,
            history_calls=self.history_calls,
            history_frame=self.history_frame,
        )

    def download(self, **kwargs: object) -> pd.DataFrame:
        print("possibly delisted; no timezone found")
        logging.getLogger("yfinance").warning("possibly delisted; no timezone found")
        self.download_calls += 1
        self.last_download_kwargs = kwargs
        if self.empty or self.download_calls <= self.empty_download_attempts:
            return pd.DataFrame()
        tickers = str(kwargs["tickers"]).split()
        fields = ["Open", "High", "Low", "Close", "Volume"]
        columns = pd.MultiIndex.from_product([tickers, fields])
        rows = []
        for base in [Decimal("170"), Decimal("175")]:
            row = []
            for index, _ticker in enumerate(tickers):
                offset = Decimal(index * 100)
                row.extend(
                    [
                        base - Decimal("1") + offset,
                        base + Decimal("1") + offset,
                        base - Decimal("2") + offset,
                        base + (Decimal("0.25") if base == 175 else Decimal("0.5")) + offset,
                        Decimal("60000000") + offset,
                    ]
                )
            rows.append(row)
        return pd.DataFrame(
            rows,
            columns=columns,
            index=pd.to_datetime(["2026-04-08T00:00:00Z", "2026-04-09T00:00:00Z"]),
        )


class _FakeTicker:
    def __init__(
        self,
        raw_symbol: str,
        *,
        empty: bool,
        info: dict[str, object] | None = None,
        history_error: Exception | None = None,
        history_error_when_raise_errors: bool = False,
        history_errors: list[Exception] | None = None,
        history_calls: list[dict[str, object]] | None = None,
        history_frame: pd.DataFrame | None = None,
    ) -> None:
        self.raw_symbol = raw_symbol
        self.empty = empty
        self.history_error = history_error
        self.history_error_when_raise_errors = history_error_when_raise_errors
        self.history_errors = history_errors if history_errors is not None else []
        self.history_calls = history_calls if history_calls is not None else []
        self.history_frame = history_frame
        default_info = {
            "dividendYield": Decimal("0.006"),
            "marketCap": Decimal("3200000000000"),
            "currency": "USD",
        }
        self.info = {**default_info, **(info or {})}

    def history(self, **kwargs: object) -> pd.DataFrame:
        self.history_calls.append(dict(kwargs))
        if self.history_errors:
            raise self.history_errors.pop(0)
        if self.history_error is not None and (
            not self.history_error_when_raise_errors or bool(kwargs.get("raise_errors", True))
        ):
            raise self.history_error
        if self.empty:
            return pd.DataFrame()
        if self.history_frame is not None:
            return self.history_frame.copy()
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
