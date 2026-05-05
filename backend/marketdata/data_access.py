import csv
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

from backend.core.config import DataAccessConfig
from backend.core.data_contracts import Bar, FxRate, Interval, Quote, Symbol
from backend.core.errors import DataSourceError


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
        if self.cfg.provider not in {"mock", "csv"}:
            raise DataSourceError(
                "Only mock and csv providers are supported in the MarketData MVP",
                details={"provider": self.cfg.provider},
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
                currency=row["currency"],
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


_MOCK_SYMBOLS = {
    "AAPL": Symbol(raw="AAPL", exchange="NASDAQ", code="AAPL", currency="USD"),
    "7203.T": Symbol(raw="7203.T", exchange="TSE", code="7203", currency="JPY"),
}

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
    ],
}
