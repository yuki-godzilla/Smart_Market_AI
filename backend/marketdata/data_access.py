from datetime import UTC, datetime
from decimal import Decimal
from typing import TypedDict

from backend.core.config import DataAccessConfig
from backend.core.data_contracts import Bar, FxRate, Interval, Quote, Symbol
from backend.core.errors import DataSourceError


class MockBarPoint(TypedDict):
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class DataAccess:
    def __init__(self, cfg: DataAccessConfig | None = None) -> None:
        self.cfg = cfg or DataAccessConfig()
        if self.cfg.provider != "mock":
            raise DataSourceError(
                "Only the mock provider is supported in the MarketData MVP",
                details={"provider": self.cfg.provider},
            )

    async def fetch_ohlcv(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        interval: Interval = "1d",
    ) -> list[Bar]:
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
        if method not in {"spot", "close", "twap"}:
            raise DataSourceError("Unsupported FX method", details={"method": method})

        ts = _as_utc(at) if at else datetime.now(UTC)
        rates: list[FxRate] = []
        for pair in pairs:
            if pair != "USDJPY":
                raise DataSourceError("Unsupported FX pair", details={"pair": pair})
            rates.append(FxRate(pair="USDJPY", rate=Decimal("150.00"), ts=ts, source="mock"))

        return rates

    def healthcheck(self) -> dict[str, str]:
        return {"provider": self.cfg.provider, "status": "ok"}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _mock_symbol(raw_symbol: str) -> Symbol:
    try:
        return _MOCK_SYMBOLS[raw_symbol]
    except KeyError as exc:
        raise DataSourceError("Unsupported mock symbol", details={"symbol": raw_symbol}) from exc


def _latest_bar_at(raw_symbol: str, at: datetime) -> MockBarPoint:
    matching = [point for point in _MOCK_OHLCV[raw_symbol] if point["ts"] <= at]
    if not matching:
        raise DataSourceError(
            "No mock quote available at requested time", details={"symbol": raw_symbol}
        )
    return matching[-1]


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
