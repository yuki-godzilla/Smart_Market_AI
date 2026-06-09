from __future__ import annotations

import asyncio
import logging
import os
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
from typing import Any

from backend.core.config import DataAccessConfig
from backend.core.data_contracts import Bar, FundamentalSnapshot, FxRate, Interval, Quote, Symbol
from backend.core.errors import DataSourceError, ProviderUnavailableError, SchemaMismatchError
from backend.marketdata.live_provider_adapters import live_provider_adapter_details
from backend.marketdata.provider_registry import provider_capability_details

YAHOO_FX_TICKERS = {"USDJPY": "JPY=X"}
YFINANCE_CACHE_DIR_ENV = "SMAI_YFINANCE_CACHE_DIR"
YAHOO_DOWNLOAD_MAX_ATTEMPTS = 2
YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS = 0.25
YAHOO_MAX_REASONABLE_DIVIDEND_YIELD_RATIO = Decimal("0.20")
YAHOO_PERCENT_STYLE_DIVIDEND_YIELD_THRESHOLD = Decimal("0.20")
_YAHOO_SESSION: Any | None = None


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
        return await self._download_ohlcv(
            symbols,
            start=start,
            end=end,
            interval=interval,
            operation="fetch_ohlcv",
        )

    async def _download_ohlcv(
        self,
        symbols: list[str],
        *,
        start: datetime,
        end: datetime,
        interval: Interval,
        operation: str,
    ) -> list[Bar]:
        if len(symbols) == 1:
            frame = await self._history(
                symbols[0],
                start=start,
                end=end,
                interval=interval,
                operation=operation,
            )
        else:
            frame = await self._download_history(
                symbols,
                start=start,
                end=end,
                interval=interval,
                operation=operation,
            )
        bars: list[Bar] = []
        for raw_symbol in symbols:
            symbol_frame = _download_symbol_frame(frame, raw_symbol)
            if getattr(symbol_frame, "empty", True):
                continue
            _validate_history_columns(symbol_frame, operation=operation, symbol=raw_symbol)
            symbol = _normalize_symbol(raw_symbol)
            for ts, row in symbol_frame.iterrows():
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
        session = shared_yfinance_session()
        for raw_symbol in symbols:
            ticker = yf.Ticker(raw_symbol, session=session)
            try:
                info = await asyncio.to_thread(_call_yfinance_silently, _ticker_info, ticker)
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
                    dividend_yield=_yahoo_dividend_yield_ratio(info, raw_symbol),
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
        ticker = yf.Ticker(raw_symbol, session=shared_yfinance_session())
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
            frame = await asyncio.to_thread(_call_yfinance_silently, ticker.history, **kwargs)
        except Exception as exc:
            if _is_yahoo_no_price_data_error(exc):
                retry_frame = await self._retry_history_after_no_price_data(
                    ticker,
                    kwargs,
                    interval=interval,
                    end=end,
                )
                if retry_frame is not None:
                    return retry_frame
                raise ProviderUnavailableError(
                    "Yahoo market-data provider returned no data",
                    details=self._provider_details(
                        operation=operation,
                        symbol=raw_symbol,
                        interval=interval,
                        start=start.isoformat() if start else None,
                        end=end.isoformat() if end else None,
                        period=period,
                        retry_reason="no_price_data",
                        error=str(exc),
                    ),
                ) from exc
            retry_reason = None
            if _is_yahoo_transient_request_error(exc):
                retry_reason = "transient_request"
                retry_frame = await self._retry_history_after_transient_request_error(ticker, kwargs)
                if retry_frame is not None:
                    return retry_frame
            request_details = {
                "operation": operation,
                "symbol": raw_symbol,
                "interval": interval,
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
                "period": period,
                "error": str(exc),
            }
            if retry_reason is not None:
                request_details["retry_reason"] = retry_reason
            raise ProviderUnavailableError(
                "Yahoo market-data provider request failed",
                details=self._provider_details(**request_details),
            ) from exc

        if getattr(frame, "empty", True):
            retry_frame = await self._retry_history_after_no_price_data(
                ticker,
                kwargs,
                interval=interval,
                end=end,
            )
            if retry_frame is not None:
                return retry_frame
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

    async def _retry_history_after_transient_request_error(
        self,
        ticker: Any,
        kwargs: dict[str, object],
    ) -> Any | None:
        try:
            frame = await asyncio.to_thread(
                _call_yfinance_silently,
                ticker.history,
                **kwargs,
            )
        except Exception:
            return None
        if not getattr(frame, "empty", True):
            return frame
        return None

    async def _retry_history_after_no_price_data(
        self,
        ticker: Any,
        kwargs: dict[str, object],
        *,
        interval: Interval,
        end: datetime | None,
    ) -> Any | None:
        for retry_kwargs in _history_retry_kwargs_after_no_price_data(
            kwargs,
            interval=interval,
            end=end,
        ):
            try:
                frame = await asyncio.to_thread(
                    _call_yfinance_silently,
                    ticker.history,
                    **retry_kwargs,
                )
            except Exception:
                continue
            if not getattr(frame, "empty", True):
                return frame
        return None

    async def _download_history(
        self,
        raw_symbols: list[str],
        *,
        interval: Interval,
        operation: str,
        start: datetime,
        end: datetime,
    ) -> Any:
        yf = _load_yfinance()
        kwargs: dict[str, object] = {
            "tickers": " ".join(raw_symbols),
            "start": _date_arg(start),
            "end": _exclusive_end_arg(end, interval),
            "interval": interval,
            "auto_adjust": False,
            "actions": False,
            "threads": False,
            "group_by": "ticker",
            "timeout": self.cfg.timeouts_ms.read / 1000,
            "progress": False,
            "session": shared_yfinance_session(),
        }
        for attempt in range(1, YAHOO_DOWNLOAD_MAX_ATTEMPTS + 1):
            try:
                frame = await asyncio.to_thread(_call_yfinance_silently, yf.download, **kwargs)
            except Exception as exc:
                raise ProviderUnavailableError(
                    "Yahoo market-data provider batch request failed",
                    details=self._provider_details(
                        operation=operation,
                        symbols=raw_symbols,
                        interval=interval,
                        start=start.isoformat(),
                        end=end.isoformat(),
                        attempt=attempt,
                        error=str(exc),
                    ),
                ) from exc

            if not getattr(frame, "empty", True):
                return frame

            if attempt < YAHOO_DOWNLOAD_MAX_ATTEMPTS:
                await asyncio.sleep(YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS)

        raise ProviderUnavailableError(
            "Yahoo market-data provider returned no batch data",
            details=self._provider_details(
                operation=operation,
                symbols=raw_symbols,
                interval=interval,
                start=start.isoformat(),
                end=end.isoformat(),
                attempts=YAHOO_DOWNLOAD_MAX_ATTEMPTS,
                retry_reason="empty_batch_data",
            ),
        )

    def _provider_details(self, **request_details: object) -> dict[str, object]:
        details = _implemented_live_provider_details(self.cfg.provider)
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
        details = _implemented_live_provider_details("yahoo")
        details["opt_in_status"] = "missing_optional_dependency"
        raise ProviderUnavailableError(
            "Yahoo market-data provider dependency is not installed",
            details=details,
        ) from exc
    _configure_yfinance_cache(yf)
    return yf


def shared_yfinance_session() -> Any:
    global _YAHOO_SESSION
    if _YAHOO_SESSION is None:
        from curl_cffi import requests  # type: ignore[import-untyped]

        _YAHOO_SESSION = requests.Session(impersonate="chrome")
    return _YAHOO_SESSION


def _configure_yfinance_cache(yf: Any) -> None:
    cache_dir = Path(os.getenv(YFINANCE_CACHE_DIR_ENV, ".yfinance_cache"))
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache_dir))
    except OSError as exc:
        details = _implemented_live_provider_details("yahoo")
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


def _implemented_live_provider_details(provider: str) -> dict[str, object]:
    details = provider_capability_details(provider)
    details.update(live_provider_adapter_details(provider))
    if details.get("smoke_check_status") == "implemented_live_opt_in":
        details["implemented"] = True
        details["live_adapter"] = "implemented_opt_in"
    return details


def _is_yahoo_no_price_data_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "possibly delisted",
            "no price data found",
            "no price data",
            "yfpricesmissingerror",
        )
    )


def _is_yahoo_transient_request_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "curl: (28)",
            "resolving timed out",
            "operation timed out",
            "connection timed out",
            "timed out after",
        )
    )


def _history_retry_kwargs_after_no_price_data(
    kwargs: dict[str, object],
    *,
    interval: Interval,
    end: datetime | None,
) -> list[dict[str, object]]:
    retry_kwargs: list[dict[str, object]] = []
    without_raise = dict(kwargs)
    without_raise["raise_errors"] = False
    retry_kwargs.append(without_raise)

    if interval == "1d" and end is not None and "end" in kwargs:
        non_expanded_end = _date_arg(end)
        if kwargs.get("end") != non_expanded_end:
            rounded_end = dict(without_raise)
            rounded_end["end"] = non_expanded_end
            retry_kwargs.append(rounded_end)

    return retry_kwargs


def _yfinance_available() -> bool:
    try:
        _load_yfinance()
    except ProviderUnavailableError:
        return False
    return True


def _call_yfinance_silently(func: Any, *args: object, **kwargs: object) -> Any:
    previous_logging_disable_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            return func(*args, **kwargs)
    finally:
        logging.disable(previous_logging_disable_level)


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
    if value is None or str(value).lower() == "nan":
        return None
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation:
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def _yahoo_dividend_yield_ratio(info: dict[str, object], raw_symbol: str) -> Decimal | None:
    trailing_yield = _optional_decimal_info(info, "trailingAnnualDividendYield")
    if trailing_yield is not None and trailing_yield >= 0:
        return _guard_dividend_yield_ratio(trailing_yield)

    dividend_yield = _optional_decimal_info(info, "dividendYield")
    if dividend_yield is None or dividend_yield < 0:
        return None
    return _guard_dividend_yield_ratio(
        _normalize_yahoo_dividend_yield_ratio(dividend_yield, raw_symbol)
    )


def _normalize_yahoo_dividend_yield_ratio(value: Decimal, raw_symbol: str) -> Decimal:
    if raw_symbol.endswith(".T") and value >= Decimal("10") and value == value.to_integral_value():
        return value / Decimal("10000")
    if value > YAHOO_PERCENT_STYLE_DIVIDEND_YIELD_THRESHOLD:
        return value / Decimal("100")
    return value


def _guard_dividend_yield_ratio(value: Decimal) -> Decimal | None:
    if value > YAHOO_MAX_REASONABLE_DIVIDEND_YIELD_RATIO:
        return None
    return value


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


def _download_symbol_frame(frame: Any, raw_symbol: str) -> Any:
    columns = getattr(frame, "columns", [])
    if not hasattr(columns, "nlevels") or columns.nlevels < 2:
        return frame
    try:
        return frame[raw_symbol].dropna(how="all")
    except Exception:
        return frame.iloc[0:0]


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
