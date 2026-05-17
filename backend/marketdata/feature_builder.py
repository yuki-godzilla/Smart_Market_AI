from datetime import UTC, date, datetime, time
from decimal import Decimal
from math import log, sqrt
from statistics import pstdev

from backend.core.config import FeatureBuilderConfig
from backend.core.data_contracts import (
    Bar,
    DailySnapshot,
    DataQuality,
    FeatureSnapshot,
    FundamentalSnapshot,
    Quote,
)
from backend.core.errors import DataSourceError
from backend.marketdata.provider_adapters import MarketDataProviderAdapter


class FeatureBuilder:
    """Build lightweight features from market data for downstream services."""

    def __init__(
        self,
        data_access: MarketDataProviderAdapter,
        cfg: FeatureBuilderConfig | None = None,
    ) -> None:
        """Create a feature builder backed by a DataAccess instance."""

        self.data_access = data_access
        self.cfg = cfg or FeatureBuilderConfig()

    async def build_daily_snapshot(self, symbols: list[str], as_of: date) -> list[DailySnapshot]:
        """Build DailySnapshot rows for risk and portfolio MVP workflows."""

        quotes = await self.data_access.fetch_quotes(symbols, at=_end_of_day_utc(as_of))
        fundamentals = await self.data_access.fetch_fundamentals(symbols, as_of=as_of)
        bars = await self.data_access.fetch_ohlcv(
            symbols,
            start=datetime(1900, 1, 1, tzinfo=UTC),
            end=_end_of_day_utc(as_of),
        )
        return build_daily_snapshots_from_market_data(
            symbols=symbols,
            as_of=as_of,
            quotes=quotes,
            fundamentals=fundamentals,
            bars=bars,
            cfg=self.cfg,
        )

    async def build_feature_snapshot(
        self,
        symbols: list[str],
        as_of: date,
    ) -> FeatureSnapshot:
        """Build a reusable feature snapshot with provider metadata."""

        rows = await self.build_daily_snapshot(symbols, as_of)
        health = self.data_access.healthcheck()
        provider = health.get("provider", "unknown")
        return FeatureSnapshot(
            as_of=as_of,
            provider=provider,
            rows=rows,
            missing_summary=_missing_summary(rows),
            quality_summary=_quality_summary(rows),
        )

    async def compute_adv(self, symbol: str, as_of: date, window: int = 20) -> Decimal:
        """Compute average traded value from close price and volume."""

        bars = await self._window_bars(symbol, as_of)
        selected = bars[-window:]
        return _adv_from_selected(selected, symbol=symbol)

    async def compute_vol(
        self,
        symbol: str,
        as_of: date,
        window: int = 20,
        method: str = "close2close",
    ) -> Decimal:
        """Compute annualized realized volatility for a symbol."""

        bars = await self._window_bars(symbol, as_of)
        return _compute_vol_from_bars(bars, window, method, symbol=symbol)

    async def _window_bars(self, symbol: str, as_of: date) -> list[Bar]:
        """Load sorted historical bars through the requested as-of date."""

        bars = await self.data_access.fetch_ohlcv(
            [symbol],
            start=datetime(1900, 1, 1, tzinfo=UTC),
            end=_end_of_day_utc(as_of),
        )
        bars.sort(key=lambda bar: bar.ts)
        return bars


def build_daily_snapshots_from_market_data(
    *,
    symbols: list[str],
    as_of: date,
    quotes: list[Quote],
    fundamentals: list[FundamentalSnapshot],
    bars: list[Bar],
    cfg: FeatureBuilderConfig | None = None,
) -> list[DailySnapshot]:
    """Build DailySnapshot rows from already fetched market-data inputs."""

    resolved_cfg = cfg or FeatureBuilderConfig()
    quotes_by_symbol = {quote.symbol.raw: quote for quote in quotes}
    fundamentals_by_symbol = {row.symbol: row for row in fundamentals}
    bars_by_symbol: dict[str, list[Bar]] = {symbol: [] for symbol in symbols}
    for bar in bars:
        if bar.symbol.raw in bars_by_symbol:
            bars_by_symbol[bar.symbol.raw].append(bar)

    snapshots: list[DailySnapshot] = []
    for symbol in symbols:
        quote = quotes_by_symbol[symbol]
        fundamental = fundamentals_by_symbol.get(symbol)
        symbol_bars = sorted(bars_by_symbol[symbol], key=lambda bar: bar.ts)
        return_1d = _compute_return(symbol_bars, 1)
        momentum_5d = _compute_return(symbol_bars, 5)
        drawdown_20d = _compute_drawdown(symbol_bars, 20)
        data_completeness = _compute_data_completeness(
            symbol_bars,
            max(resolved_cfg.adv_window, resolved_cfg.vol_window + 1, 20),
        )
        missing = {
            "dividend_yield": fundamental is None or fundamental.dividend_yield is None,
            "market_cap_jpy": fundamental is None or fundamental.market_cap_jpy is None,
            "return_1d": return_1d is None,
            "momentum_5d": momentum_5d is None,
            "drawdown_20d": drawdown_20d is None,
        }
        data_quality, data_quality_reasons = _data_quality_for_snapshot(
            missing,
            data_completeness,
        )
        snapshots.append(
            DailySnapshot(
                symbol=symbol,
                as_of=as_of,
                last=quote.last,
                close_1d=quote.last,
                return_1d=return_1d,
                momentum_5d=momentum_5d,
                adv_20d=_compute_adv_from_bars(symbol_bars, resolved_cfg.adv_window),
                vol_20d=_compute_vol_from_bars(
                    symbol_bars,
                    resolved_cfg.vol_window,
                    resolved_cfg.vol_method,
                ),
                drawdown_20d=drawdown_20d,
                data_completeness=data_completeness,
                dividend_yield=fundamental.dividend_yield if fundamental else None,
                market_cap_jpy=fundamental.market_cap_jpy if fundamental else None,
                missing=missing,
                data_quality=data_quality,
                data_quality_reasons=data_quality_reasons,
            )
        )

    return snapshots


def _end_of_day_utc(value: date) -> datetime:
    """Convert a date to the final representable UTC datetime for that day."""

    return datetime.combine(value, time.max, tzinfo=UTC)


def _missing_summary(rows: list[DailySnapshot]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        for feature, is_missing in row.missing.items():
            if is_missing:
                summary[feature] = summary.get(feature, 0) + 1
    return summary


def _quality_summary(rows: list[DailySnapshot]) -> dict[DataQuality, int]:
    summary: dict[DataQuality, int] = {}
    for row in rows:
        summary[row.data_quality] = summary.get(row.data_quality, 0) + 1
    return summary


def _data_quality_for_snapshot(
    missing: dict[str, bool],
    data_completeness: Decimal,
) -> tuple[DataQuality, list[str]]:
    reasons = [
        f"missing:{feature}" for feature, is_missing in sorted(missing.items()) if is_missing
    ]

    blocking_features = {"return_1d", "drawdown_20d"}
    if any(missing.get(feature, False) for feature in blocking_features):
        return "BLOCK", reasons
    if reasons or data_completeness < Decimal("0.8"):
        quality_reasons = list(reasons)
        if data_completeness < Decimal("0.8"):
            quality_reasons.append(f"partial_data_completeness:{data_completeness:.2f}")
        return "WARN", quality_reasons
    return "OK", []


def _compute_adv_from_bars(bars: list[Bar], window: int) -> Decimal:
    return _adv_from_selected(bars[-window:])


def _adv_from_selected(selected: list[Bar], *, symbol: str | None = None) -> Decimal:
    if not selected:
        details: dict[str, object] = {"symbol": symbol} if symbol is not None else {}
        raise DataSourceError("No bars available for ADV calculation", details=details)

    total = sum((bar.close * bar.volume for bar in selected), start=Decimal("0"))
    return total / Decimal(len(selected))


def _compute_vol_from_bars(
    bars: list[Bar],
    window: int,
    method: str,
    *,
    symbol: str | None = None,
) -> Decimal:
    selected = bars[-(window + 1) :]
    if len(selected) < 2:
        details: dict[str, object] = {"symbol": symbol} if symbol is not None else {}
        raise DataSourceError("At least two bars are required for volatility", details=details)

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


def _compute_return(bars: list[Bar], lookback: int) -> Decimal | None:
    if len(bars) <= lookback:
        return None
    previous = bars[-(lookback + 1)].close
    current = bars[-1].close
    if previous <= 0:
        return None
    return (current / previous) - Decimal("1")


def _compute_drawdown(bars: list[Bar], window: int) -> Decimal | None:
    selected = bars[-window:]
    if not selected:
        return None
    peak = max(bar.high for bar in selected)
    if peak <= 0:
        return None
    latest_close = selected[-1].close
    return (peak - latest_close) / peak


def _compute_data_completeness(bars: list[Bar], expected_count: int) -> Decimal:
    if expected_count <= 0:
        return Decimal("1")
    completeness = Decimal(min(len(bars), expected_count)) / Decimal(expected_count)
    return min(completeness, Decimal("1"))
