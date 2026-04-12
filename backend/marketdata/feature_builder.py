from datetime import UTC, date, datetime, time
from decimal import Decimal
from math import log, sqrt
from statistics import pstdev

from backend.core.config import FeatureBuilderConfig
from backend.core.data_contracts import Bar, DailySnapshot
from backend.core.errors import DataSourceError
from backend.marketdata.data_access import DataAccess


class FeatureBuilder:
    """Build lightweight features from market data for downstream services."""

    def __init__(
        self,
        data_access: DataAccess,
        cfg: FeatureBuilderConfig | None = None,
    ) -> None:
        """Create a feature builder backed by a DataAccess instance."""

        self.data_access = data_access
        self.cfg = cfg or FeatureBuilderConfig()

    async def build_daily_snapshot(self, symbols: list[str], as_of: date) -> list[DailySnapshot]:
        """Build DailySnapshot rows for risk and portfolio MVP workflows."""

        snapshots: list[DailySnapshot] = []
        quotes = await self.data_access.fetch_quotes(symbols, at=_end_of_day_utc(as_of))
        quotes_by_symbol = {quote.symbol.raw: quote for quote in quotes}

        for symbol in symbols:
            quote = quotes_by_symbol[symbol]
            snapshots.append(
                DailySnapshot(
                    symbol=symbol,
                    as_of=as_of,
                    last=quote.last,
                    close_1d=quote.last,
                    adv_20d=await self.compute_adv(symbol, as_of, self.cfg.adv_window),
                    vol_20d=await self.compute_vol(
                        symbol,
                        as_of,
                        self.cfg.vol_window,
                        self.cfg.vol_method,
                    ),
                    dividend_yield=None,
                    market_cap_jpy=None,
                    missing={"dividend_yield": True, "market_cap_jpy": True},
                )
            )

        return snapshots

    async def compute_adv(self, symbol: str, as_of: date, window: int = 20) -> Decimal:
        """Compute average traded value from close price and volume."""

        bars = await self._window_bars(symbol, as_of)
        selected = bars[-window:]
        if not selected:
            raise DataSourceError(
                "No bars available for ADV calculation", details={"symbol": symbol}
            )

        total = sum((bar.close * bar.volume for bar in selected), start=Decimal("0"))
        return total / Decimal(len(selected))

    async def compute_vol(
        self,
        symbol: str,
        as_of: date,
        window: int = 20,
        method: str = "close2close",
    ) -> Decimal:
        """Compute annualized realized volatility for a symbol."""

        bars = await self._window_bars(symbol, as_of)
        selected = bars[-(window + 1) :]
        if len(selected) < 2:
            raise DataSourceError(
                "At least two bars are required for volatility", details={"symbol": symbol}
            )

        if method == "close2close":
            returns = [
                log(float(selected[index].close / selected[index - 1].close))
                for index in range(1, len(selected))
            ]
            return Decimal(str(pstdev(returns) * sqrt(252)))

        if method == "parkinson":
            values = [log(float(bar.high / bar.low)) ** 2 for bar in selected if bar.low > 0]
            return Decimal(str(sqrt(sum(values) / (4 * log(2) * len(values)))))

        raise DataSourceError("Unsupported volatility method", details={"method": method})

    async def _window_bars(self, symbol: str, as_of: date) -> list[Bar]:
        """Load sorted historical bars through the requested as-of date."""

        bars = await self.data_access.fetch_ohlcv(
            [symbol],
            start=datetime(1900, 1, 1, tzinfo=UTC),
            end=_end_of_day_utc(as_of),
        )
        bars.sort(key=lambda bar: bar.ts)
        return bars


def _end_of_day_utc(value: date) -> datetime:
    """Convert a date to the final representable UTC datetime for that day."""

    return datetime.combine(value, time.max, tzinfo=UTC)
