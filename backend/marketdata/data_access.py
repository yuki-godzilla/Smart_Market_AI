import csv
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

from backend.core.config import DataAccessConfig
from backend.core.data_contracts import (
    Bar,
    Currency,
    FundamentalSnapshot,
    FxRate,
    Interval,
    Quote,
    Symbol,
)
from backend.core.errors import DataSourceError
from backend.marketdata.live_provider_adapters import live_provider_adapter_details
from backend.marketdata.provider_registry import (
    SUPPORTED_PROVIDERS,
    provider_capability_details,
)


class MockBarPoint(TypedDict):
    """In-memory OHLCV row used by the mock market-data provider."""

    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class DataAccess:
    """Read-only market-data access layer.

    The current MVP supports deterministic mock and CSV providers so tests and
    downstream feature work can stay offline.
    """

    def __init__(self, cfg: DataAccessConfig | None = None) -> None:
        """Create a data-access instance from optional provider settings."""

        self.cfg = cfg or DataAccessConfig()
        if self.cfg.provider not in SUPPORTED_PROVIDERS:
            raise _unsupported_provider_error(
                self.cfg.provider,
                allow_external_providers=self.cfg.allow_external_providers,
            )

    async def fetch_ohlcv(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        interval: Interval = "1d",
    ) -> list[Bar]:
        """Return OHLCV bars for the requested symbols and UTC range."""

        if self.cfg.provider == "csv":
            return self._fetch_csv_ohlcv(symbols, start, end, interval)

        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        bars: list[Bar] = []

        for raw_symbol in symbols:
            symbol = _mock_symbol(raw_symbol)
            for point in _MOCK_OHLCV[raw_symbol]:
                ts = point["ts"]
                if start_utc <= ts <= end_utc:
                    bars.append(
                        Bar(
                            symbol=symbol,
                            ts=ts,
                            open=point["open"],
                            high=point["high"],
                            low=point["low"],
                            close=point["close"],
                            volume=point["volume"],
                            interval=interval,
                            provider=self.cfg.provider,
                        )
                    )

        return bars

    async def fetch_quotes(self, symbols: list[str], at: datetime | None = None) -> list[Quote]:
        """Return latest available quotes at or before the requested time."""

        if self.cfg.provider == "csv":
            return self._fetch_csv_quotes(symbols, at)

        at_utc = _as_utc(at) if at else datetime.now(UTC)
        quotes: list[Quote] = []

        for raw_symbol in symbols:
            symbol = _mock_symbol(raw_symbol)
            latest = _latest_bar_at(raw_symbol, at_utc)
            quotes.append(
                Quote(
                    symbol=symbol,
                    bid=latest["close"],
                    ask=latest["close"],
                    last=latest["close"],
                    ts=latest["ts"],
                )
            )

        return quotes

    async def get_fx_rates(
        self,
        pairs: list[str],
        at: datetime | None = None,
        method: str = "spot",
    ) -> list[FxRate]:
        """Return FX rates for supported pairs and methods."""

        if method not in {"spot", "close", "twap"}:
            raise DataSourceError("Unsupported FX method", details={"method": method})

        if self.cfg.provider == "csv":
            return self._fetch_csv_fx_rates(pairs, at)

        ts = _as_utc(at) if at else datetime.now(UTC)
        rates: list[FxRate] = []
        for pair in pairs:
            if pair != "USDJPY":
                raise DataSourceError("Unsupported FX pair", details={"pair": pair})
            rates.append(FxRate(pair="USDJPY", rate=Decimal("150.00"), ts=ts, source="mock"))

        return rates

    async def fetch_fundamentals(
        self,
        symbols: list[str],
        as_of: date,
    ) -> list[FundamentalSnapshot]:
        """Return point-in-time fundamentals for supported symbols."""

        if self.cfg.provider == "csv":
            return self._fetch_csv_fundamentals(symbols, as_of)

        fundamentals: list[FundamentalSnapshot] = []
        for raw_symbol in symbols:
            _mock_symbol(raw_symbol)
            row = _MOCK_FUNDAMENTALS.get(raw_symbol, {})
            fundamentals.append(
                FundamentalSnapshot(
                    symbol=raw_symbol,
                    as_of=as_of,
                    provider=self.cfg.provider,
                    dividend_yield=row.get("dividend_yield"),
                    market_cap_jpy=row.get("market_cap_jpy"),
                )
            )
        return fundamentals

    def healthcheck(self) -> dict[str, str]:
        """Report the active provider status."""

        return {"provider": self.cfg.provider, "status": "ok"}

    def _fetch_csv_ohlcv(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        interval: Interval,
    ) -> list[Bar]:
        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        symbol_contracts = self._csv_symbols()
        rows = self._read_csv_rows(
            "ohlcv.csv",
            required_columns={"symbol", "ts", "open", "high", "low", "close", "volume"},
        )
        bars: list[Bar] = []

        for raw_symbol in symbols:
            symbol = _csv_symbol(raw_symbol, symbol_contracts)
            for row in rows:
                if row["symbol"] != raw_symbol:
                    continue
                ts = _parse_datetime(row["ts"])
                if start_utc <= ts <= end_utc:
                    bars.append(
                        Bar(
                            symbol=symbol,
                            ts=ts,
                            open=Decimal(row["open"]),
                            high=Decimal(row["high"]),
                            low=Decimal(row["low"]),
                            close=Decimal(row["close"]),
                            volume=Decimal(row["volume"]),
                            interval=interval,
                            provider=self.cfg.provider,
                        )
                    )

        return bars

    def _fetch_csv_quotes(self, symbols: list[str], at: datetime | None) -> list[Quote]:
        at_utc = _as_utc(at) if at else datetime.now(UTC)
        symbol_contracts = self._csv_symbols()
        rows = self._read_csv_rows(
            "ohlcv.csv",
            required_columns={"symbol", "ts", "open", "high", "low", "close", "volume"},
        )
        quotes: list[Quote] = []

        for raw_symbol in symbols:
            symbol = _csv_symbol(raw_symbol, symbol_contracts)
            matching = [
                row
                for row in rows
                if row["symbol"] == raw_symbol and _parse_datetime(row["ts"]) <= at_utc
            ]
            if not matching:
                raise DataSourceError(
                    "No csv quote available at requested time",
                    details={"symbol": raw_symbol},
                )
            latest = max(matching, key=lambda row: _parse_datetime(row["ts"]))
            close = Decimal(latest["close"])
            quotes.append(
                Quote(
                    symbol=symbol,
                    bid=close,
                    ask=close,
                    last=close,
                    ts=_parse_datetime(latest["ts"]),
                )
            )

        return quotes

    def _fetch_csv_fx_rates(self, pairs: list[str], at: datetime | None) -> list[FxRate]:
        at_utc = _as_utc(at) if at else datetime.now(UTC)
        rows = self._read_csv_rows(
            "fx_rates.csv", required_columns={"pair", "rate", "ts", "source"}
        )
        rates: list[FxRate] = []

        for pair in pairs:
            if pair != "USDJPY":
                raise DataSourceError("Unsupported FX pair", details={"pair": pair})
            matching = [
                row for row in rows if row["pair"] == pair and _parse_datetime(row["ts"]) <= at_utc
            ]
            if not matching:
                raise DataSourceError(
                    "No csv FX rate available at requested time",
                    details={"pair": pair},
                )
            latest = max(matching, key=lambda row: _parse_datetime(row["ts"]))
            rates.append(
                FxRate(
                    pair="USDJPY",
                    rate=Decimal(latest["rate"]),
                    ts=_parse_datetime(latest["ts"]),
                    source=latest.get("source") or "csv",
                )
            )

        return rates

    def _fetch_csv_fundamentals(
        self,
        symbols: list[str],
        as_of: date,
    ) -> list[FundamentalSnapshot]:
        symbol_contracts = self._csv_symbols()
        rows = self._read_csv_rows(
            "fundamentals.csv",
            required_columns={"symbol", "as_of", "dividend_yield", "market_cap_jpy"},
        )
        fundamentals: list[FundamentalSnapshot] = []

        for raw_symbol in symbols:
            _csv_symbol(raw_symbol, symbol_contracts)
            matching = [
                row
                for row in rows
                if row["symbol"] == raw_symbol and date.fromisoformat(row["as_of"]) <= as_of
            ]
            if not matching:
                fundamentals.append(
                    FundamentalSnapshot(symbol=raw_symbol, as_of=as_of, provider="csv")
                )
                continue
            latest = max(matching, key=lambda row: date.fromisoformat(row["as_of"]))
            fundamentals.append(
                FundamentalSnapshot(
                    symbol=raw_symbol,
                    as_of=date.fromisoformat(latest["as_of"]),
                    provider="csv",
                    dividend_yield=_optional_decimal(latest["dividend_yield"]),
                    market_cap_jpy=_optional_decimal(latest["market_cap_jpy"]),
                )
            )
        return fundamentals

    def _csv_symbols(self) -> dict[str, Symbol]:
        rows = self._read_csv_rows(
            "symbols.csv",
            required_columns={"raw", "exchange", "code", "currency"},
        )
        return {
            row["raw"]: Symbol(
                raw=row["raw"],
                exchange=row["exchange"],
                code=row["code"],
                currency=_parse_currency(row["currency"], row["raw"]),
            )
            for row in rows
        }

    def _read_csv_rows(
        self,
        filename: str,
        required_columns: set[str],
    ) -> list[dict[str, str]]:
        path = Path(self.cfg.csv_data_dir) / filename
        if not path.exists():
            raise DataSourceError("CSV market-data file is missing", details={"path": str(path)})
        with path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            missing_columns = sorted(required_columns - set(reader.fieldnames or []))
            if missing_columns:
                raise DataSourceError(
                    "CSV market-data file is missing required columns",
                    details={"path": str(path), "columns": missing_columns},
                )
            return list(reader)


def _as_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC, treating naive values as already UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _mock_symbol(raw_symbol: str) -> Symbol:
    """Resolve a raw symbol string to a supported mock symbol contract."""

    try:
        return _MOCK_SYMBOLS[raw_symbol]
    except KeyError as exc:
        raise DataSourceError("Unsupported mock symbol", details={"symbol": raw_symbol}) from exc


def _latest_bar_at(raw_symbol: str, at: datetime) -> MockBarPoint:
    """Return the latest mock OHLCV row at or before a timestamp."""

    matching = [point for point in _MOCK_OHLCV[raw_symbol] if point["ts"] <= at]
    if not matching:
        raise DataSourceError(
            "No mock quote available at requested time", details={"symbol": raw_symbol}
        )
    return matching[-1]


def _csv_symbol(raw_symbol: str, symbols: dict[str, Symbol]) -> Symbol:
    try:
        return symbols[raw_symbol]
    except KeyError as exc:
        raise DataSourceError("Unsupported csv symbol", details={"symbol": raw_symbol}) from exc


def _parse_datetime(value: str) -> datetime:
    return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _parse_currency(value: str, raw_symbol: str) -> Currency:
    if value == "JPY":
        return "JPY"
    if value == "USD":
        return "USD"
    raise DataSourceError(
        "Unsupported csv currency",
        details={"symbol": raw_symbol, "currency": value},
    )


def _optional_decimal(value: str) -> Decimal | None:
    if value == "":
        return None
    return Decimal(value)


def _unsupported_provider_error(
    provider: str, *, allow_external_providers: bool
) -> DataSourceError:
    details = provider_capability_details(provider)
    details.update(live_provider_adapter_details(provider))
    if details.get("requires_external_opt_in"):
        if not allow_external_providers:
            details.update(
                {
                    "allow_external_providers": False,
                    "opt_in_status": "explicit_config_required",
                }
            )
            return DataSourceError(
                "Live market-data provider requires explicit opt-in",
                details=details,
            )
        if details.get("implemented") is True:
            details.update(
                {
                    "allow_external_providers": True,
                    "opt_in_status": "explicitly_enabled_factory_required",
                }
            )
            return DataSourceError(
                "Live market-data provider requires the provider factory",
                details=details,
            )
        details.update(
            {
                "allow_external_providers": True,
                "opt_in_status": "explicitly_enabled_not_implemented",
            }
        )
        return DataSourceError(
            "Live market-data providers are not implemented yet",
            details=details,
        )
    details.pop("registered", None)
    return DataSourceError(
        "Unsupported market-data provider",
        details=details,
    )


_MOCK_SYMBOLS = {
    "AAPL": Symbol(raw="AAPL", exchange="NASDAQ", code="AAPL", currency="USD"),
    "7203.T": Symbol(raw="7203.T", exchange="TSE", code="7203", currency="JPY"),
}


_MOCK_FUNDAMENTALS: dict[str, dict[str, Decimal]] = {
    "AAPL": {
        "dividend_yield": Decimal("0.005"),
        "market_cap_jpy": Decimal("450000000000000"),
    },
    "7203.T": {
        "dividend_yield": Decimal("0.028"),
        "market_cap_jpy": Decimal("52000000000000"),
    },
}


def _rolling_mock_ohlcv(
    *,
    base_close: Decimal,
    base_volume: Decimal,
    days: int = 10,
) -> list[MockBarPoint]:
    """Return recent mock bars so current-date UI defaults have data."""

    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    close_offsets = [
        Decimal("0.0"),
        Decimal("-1.8"),
        Decimal("2.4"),
        Decimal("1.1"),
        Decimal("4.2"),
        Decimal("3.0"),
        Decimal("6.7"),
        Decimal("5.9"),
        Decimal("8.4"),
        Decimal("7.6"),
    ]
    volume_offsets = [
        Decimal("0"),
        Decimal("1400000"),
        Decimal("-900000"),
        Decimal("2200000"),
        Decimal("600000"),
        Decimal("3100000"),
        Decimal("-1200000"),
        Decimal("1800000"),
        Decimal("2600000"),
        Decimal("400000"),
    ]
    rows: list[MockBarPoint] = []
    previous_close = base_close
    for offset in range(days):
        ts = datetime.combine(start + timedelta(days=offset), datetime.min.time(), tzinfo=UTC)
        close = base_close + close_offsets[offset % len(close_offsets)]
        open_price = previous_close + (Decimal("0.4") if offset % 2 == 0 else Decimal("-0.6"))
        high = max(open_price, close) + Decimal("1.7")
        low = min(open_price, close) - Decimal("1.9")
        rows.append(
            {
                "ts": ts,
                "open": open_price.quantize(Decimal("0.01")),
                "high": high.quantize(Decimal("0.01")),
                "low": low.quantize(Decimal("0.01")),
                "close": close.quantize(Decimal("0.01")),
                "volume": base_volume + volume_offsets[offset % len(volume_offsets)],
            }
        )
        previous_close = close
    return rows


_MOCK_OHLCV: dict[str, list[MockBarPoint]] = {
    "AAPL": [
        {
            "ts": datetime(2026, 4, 7, tzinfo=UTC),
            "open": Decimal("168.00"),
            "high": Decimal("171.00"),
            "low": Decimal("167.50"),
            "close": Decimal("170.00"),
            "volume": Decimal("61000000"),
        },
        {
            "ts": datetime(2026, 4, 8, tzinfo=UTC),
            "open": Decimal("170.00"),
            "high": Decimal("174.00"),
            "low": Decimal("169.50"),
            "close": Decimal("173.00"),
            "volume": Decimal("59000000"),
        },
        {
            "ts": datetime(2026, 4, 9, tzinfo=UTC),
            "open": Decimal("173.00"),
            "high": Decimal("176.00"),
            "low": Decimal("172.00"),
            "close": Decimal("175.00"),
            "volume": Decimal("62000000"),
        },
        *_rolling_mock_ohlcv(
            base_close=Decimal("175.00"),
            base_volume=Decimal("62000000"),
        ),
    ],
    "7203.T": [
        {
            "ts": datetime(2026, 4, 7, tzinfo=UTC),
            "open": Decimal("2800"),
            "high": Decimal("2860"),
            "low": Decimal("2780"),
            "close": Decimal("2840"),
            "volume": Decimal("22000000"),
        },
        {
            "ts": datetime(2026, 4, 8, tzinfo=UTC),
            "open": Decimal("2840"),
            "high": Decimal("2890"),
            "low": Decimal("2820"),
            "close": Decimal("2875"),
            "volume": Decimal("21000000"),
        },
        {
            "ts": datetime(2026, 4, 9, tzinfo=UTC),
            "open": Decimal("2875"),
            "high": Decimal("2910"),
            "low": Decimal("2860"),
            "close": Decimal("2900"),
            "volume": Decimal("23000000"),
        },
        *_rolling_mock_ohlcv(
            base_close=Decimal("2900"),
            base_volume=Decimal("23000000"),
        ),
    ],
}
