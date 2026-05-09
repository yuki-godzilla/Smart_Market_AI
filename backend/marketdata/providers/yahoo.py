from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.core.config import DataAccessConfig
from backend.core.data_contracts import Bar, FundamentalSnapshot, FxRate, Interval, Quote, Symbol
from backend.core.errors import DataSourceError, ProviderUnavailableError, SchemaMismatchError
from backend.marketdata.live_provider_adapters import live_provider_adapter_details
from backend.marketdata.provider_registry import provider_capability_details

YAHOO_FX_TICKERS = {"USDJPY": "JPY=X"}
YFINANCE_CACHE_DIR_ENV = "SMAI_YFINANCE_CACHE_DIR"


class YahooMarketDataProviderAdapter:
    """Opt-in Yahoo market-data adapter backed by yfinance."""

    def __init__(self, cfg: DataAccessConfig) -> None:
        self.cfg = cfg

    async def fetch_ohlcv(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        interval: Interval = "1d",
    ) -> list[Bar]:
        bars: list[Bar] = []
        for raw_symbol in symbols:
            frame = await self._history(
                raw_symbol,
                start=start,
                end=end,
                interval=interval,
                operation="fetch_ohlcv",
            )
            symbol = _normalize_symbol(raw_symbol)
            for ts, row in frame.iterrows():
                bars.append(
                    Bar(
                        symbol=symbol,
                        ts=_normalize_timestamp(ts),
                        open=_decimal_cell(row, "Open"),
                        high=_decimal_cell(row, "High"),
                        low=_decimal_cell(row, "Low"),
                        close=_decimal_cell(row, "Close"),
                        volume=_decimal_cell(row, "Volume"),
                        interval=interval,
                        provider="yahoo",
                    )
                )
        return bars

    async def fetch_quotes(self, symbols: list[str], at: datetime | None = None) -> list[Quote]:
        quotes: list[Quote] = []
        for raw_symbol in symbols:
            frame = await self._quote_history(raw_symbol, at=at)
            ts, row = _last_row(frame)
            quotes.append(
                Quote(
                    symbol=_normalize_symbol(raw_symbol),
                    bid=None,
                    ask=None,
                    last=_decimal_cell(row, "Close"),
                    ts=_normalize_timestamp(ts),
                )
            )
        return quotes

    async def get_fx_rates(
        self,
        pairs: list[str],
        at: datetime | None = None,
        method: str = "spot",
    ) -> list[FxRate]:
        if method != "spot":
            raise DataSourceError("Unsupported Yahoo FX method", details={"method": method})

        rates: list[FxRate] = []
        for pair in pairs:
            ticker = YAHOO_FX_TICKERS.get(pair)
            if ticker is None:
                raise DataSourceError("Unsupported Yahoo FX pair", details={"pair": pair})

            frame = await self._quote_history(ticker, at=at, operation="get_fx_rates")
            ts, row = _last_row(frame)
            rates.append(
                FxRate(
                    pair="USDJPY",
                    rate=_decimal_cell(row, "Close"),
                    ts=_normalize_timestamp(ts),
                    source="yahoo",
                )
            )
        return rates

    async def fetch_fundamentals(
        self,
        symbols: list[str],
        as_of: date,
    ) -> list[FundamentalSnapshot]:
        fundamentals: list[FundamentalSnapshot] = []
        yf = _load_yfinance()
        for raw_symbol in symbols:
            ticker = yf.Ticker(raw_symbol)
            try:
                info = await asyncio.to_thread(_ticker_info, ticker)
            except Exception as exc:
                raise ProviderUnavailableError(
                    "Yahoo fundamentals request failed",
                    details=self._provider_details(
                        operation="fetch_fundamentals",
                        symbol=raw_symbol,
                        error=str(exc),
                    ),
                ) from exc
            fundamentals.append(
                FundamentalSnapshot(
                    symbol=raw_symbol,
                    as_of=as_of,
                    provider="yahoo",
                    dividend_yield=_optional_decimal_info(info, "dividendYield"),
                    market_cap_jpy=_market_cap_jpy(info, raw_symbol),
                )
            )
        return fundamentals

    def healthcheck(self) -> dict[str, str]:
        status = "available" if _yfinance_available() else "missing_dependency"
        return {
            "provider": self.cfg.provider,
            "status": status,
            "adapter": "YahooMarketDataProviderAdapter",
        }

    async def _quote_history(
        self,
        raw_symbol: str,
        *,
        at: datetime | None,
        operation: str = "fetch_quotes",
    ) -> Any:
        if at is None:
            return await self._history(
                raw_symbol,
                period="5d",
                interval="1d",
                operation=operation,
            )
        return await self._history(
            raw_symbol,
            start=at - timedelta(days=7),
            end=at + timedelta(days=1),
            interval="1d",
            operation=operation,
        )

    async def _history(
        self,
        raw_symbol: str,
        *,
        interval: Interval,
        operation: str,
        start: datetime | None = None,
        end: datetime | None = None,
        period: str | None = None,
    ) -> Any:
        yf = _load_yfinance()
        ticker = yf.Ticker(raw_symbol)
        kwargs: dict[str, object] = {
            "interval": interval,
            "auto_adjust": False,
            "actions": False,
            "timeout": self.cfg.timeouts_ms.read / 1000,
            "raise_errors": True,
        }
        if period is not None:
            kwargs["period"] = period
        if start is not None:
            kwargs["start"] = _date_arg(start)
        if end is not None:
            kwargs["end"] = _exclusive_end_arg(end, interval)

        try:
            frame = await asyncio.to_thread(ticker.history, **kwargs)
        except Exception as exc:
            raise ProviderUnavailableError(
                "Yahoo market-data provider request failed",
                details=self._provider_details(
                    operation=operation,
                    symbol=raw_symbol,
                    interval=interval,
                    start=start.isoformat() if start else None,
                    end=end.isoformat() if end else None,
                    period=period,
                    error=str(exc),
                ),
            ) from exc

        if getattr(frame, "empty", True):
            raise ProviderUnavailableError(
                "Yahoo market-data provider returned no data",
                details=self._provider_details(
                    operation=operation,
                    symbol=raw_symbol,
                    interval=interval,
                    start=start.isoformat() if start else None,
                    end=end.isoformat() if end else None,
                    period=period,
                ),
            )
        _validate_history_columns(frame, operation=operation, symbol=raw_symbol)
        return frame

    def _provider_details(self, **request_details: object) -> dict[str, object]:
        details = provider_capability_details(self.cfg.provider)
        details.update(live_provider_adapter_details(self.cfg.provider))
        details.update(
            {
                "allow_external_providers": self.cfg.allow_external_providers,
                "opt_in_status": "explicitly_enabled_live",
                "request": request_details,
            }
        )
        return details


def _load_yfinance() -> Any:
    try:
        import yfinance as yf  # type: ignore[import-untyped]
    except ImportError as exc:
        details = provider_capability_details("yahoo")
        details.update(live_provider_adapter_details("yahoo"))
        details["opt_in_status"] = "missing_optional_dependency"
        raise ProviderUnavailableError(
            "Yahoo market-data provider dependency is not installed",
            details=details,
        ) from exc
    _configure_yfinance_cache(yf)
    return yf


def _configure_yfinance_cache(yf: Any) -> None:
    cache_dir = Path(os.getenv(YFINANCE_CACHE_DIR_ENV, ".yfinance_cache"))
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache_dir))
    except OSError as exc:
        details = provider_capability_details("yahoo")
        details.update(live_provider_adapter_details("yahoo"))
        details.update(
            {
                "opt_in_status": "cache_unavailable",
                "cache_dir": str(cache_dir),
                "error": str(exc),
            }
        )
        raise ProviderUnavailableError(
            "Yahoo market-data provider cache directory is unavailable",
            details=details,
        ) from exc


def _yfinance_available() -> bool:
    try:
        _load_yfinance()
    except ProviderUnavailableError:
        return False
    return True


def _normalize_symbol(raw_symbol: str) -> Symbol:
    if raw_symbol.endswith(".T"):
        return Symbol(
            raw=raw_symbol,
            exchange="TSE",
            code=raw_symbol.removesuffix(".T"),
            currency="JPY",
        )
    return Symbol(raw=raw_symbol, exchange="NASDAQ", code=raw_symbol, currency="USD")


def _normalize_timestamp(value: object) -> datetime:
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if not isinstance(value, datetime):
        raise SchemaMismatchError(
            "Yahoo market-data timestamp is not a datetime",
            details={"timestamp": str(value)},
        )
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _decimal_cell(row: Any, column: str) -> Decimal:
    try:
        value = row[column]
    except Exception as exc:
        raise SchemaMismatchError(
            "Yahoo market-data response is missing a required column",
            details={"column": column},
        ) from exc

    if value is None or str(value) == "nan":
        raise SchemaMismatchError(
            "Yahoo market-data response contains an empty numeric value",
            details={"column": column},
        )
    return Decimal(str(value))


def _ticker_info(ticker: Any) -> dict[str, object]:
    info = getattr(ticker, "info", {})
    if not isinstance(info, dict):
        raise SchemaMismatchError(
            "Yahoo fundamentals response is not a mapping",
            details={"type": type(info).__name__},
        )
    return info


def _optional_decimal_info(info: dict[str, object], key: str) -> Decimal | None:
    value = info.get(key)
    if value is None or str(value) == "nan":
        return None
    return Decimal(str(value))


def _market_cap_jpy(info: dict[str, object], raw_symbol: str) -> Decimal | None:
    market_cap = _optional_decimal_info(info, "marketCap")
    if market_cap is None:
        return None
    currency = info.get("currency")
    if currency == "JPY" or raw_symbol.endswith(".T"):
        return market_cap
    if currency == "USD" or currency is None:
        return market_cap * Decimal("150")
    return None


def _last_row(frame: Any) -> tuple[object, Any]:
    return frame.index[-1], frame.iloc[-1]


def _validate_history_columns(frame: Any, *, operation: str, symbol: str) -> None:
    missing = [
        column for column in ["Open", "High", "Low", "Close", "Volume"] if column not in frame
    ]
    if missing:
        raise SchemaMismatchError(
            "Yahoo market-data response is missing required columns",
            details={"operation": operation, "symbol": symbol, "missing_columns": missing},
        )


def _date_arg(value: datetime) -> str:
    return value.astimezone(UTC).date().isoformat()


def _exclusive_end_arg(value: datetime, interval: Interval) -> str:
    if interval == "1d":
        value = value + timedelta(days=1)
    return _date_arg(value)
