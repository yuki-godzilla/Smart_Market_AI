from datetime import date, datetime
from typing import Protocol, runtime_checkable

from backend.core.data_contracts import Bar, FundamentalSnapshot, FxRate, Interval, Quote


@runtime_checkable
class MarketDataProviderAdapter(Protocol):
    """Common interface for deterministic and future live market-data providers."""

    async def fetch_ohlcv(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        interval: Interval = "1d",
    ) -> list[Bar]:
        """Return normalized OHLCV bars for requested symbols and time range."""

    async def fetch_quotes(self, symbols: list[str], at: datetime | None = None) -> list[Quote]:
        """Return normalized quotes for requested symbols."""

    async def get_fx_rates(
        self,
        pairs: list[str],
        at: datetime | None = None,
        method: str = "spot",
    ) -> list[FxRate]:
        """Return normalized FX rates for requested currency pairs."""

    async def fetch_fundamentals(
        self,
        symbols: list[str],
        as_of: date,
    ) -> list[FundamentalSnapshot]:
        """Return normalized point-in-time fundamentals for requested symbols."""

    def healthcheck(self) -> dict[str, str]:
        """Return provider health details for diagnostics."""
