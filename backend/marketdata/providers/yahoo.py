from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from backend.core.config import DataAccessConfig
from backend.core.data_contracts import Bar, FundamentalSnapshot, FxRate, Interval, Quote, Symbol
from backend.core.errors import DataSourceError, ProviderUnavailableError, SchemaMismatchError
from backend.marketdata.live_provider_adapters import live_provider_adapter_details
from backend.marketdata.provider_registry import provider_capability_details

YAHOO_FX_TICKERS = {
    "USDJPY": "JPY=X",
    "HKDJPY": "HKDJPY=X",
    "KRWJPY": "KRWJPY=X",
    "VNDJPY": "VNDJPY=X",
    "IDRJPY": "IDRJPY=X",
    "SGDJPY": "SGDJPY=X",
    "THBJPY": "THBJPY=X",
    "MYRJPY": "MYRJPY=X",
    "CNYJPY": "CNYJPY=X",
}
YFINANCE_CACHE_DIR_ENV = "SMAI_YFINANCE_CACHE_DIR"
YAHOO_DOWNLOAD_MAX_ATTEMPTS = 4
YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS = 2.0
YAHOO_MAX_REASONABLE_DIVIDEND_YIELD_RATIO = Decimal("0.20")
YAHOO_PERCENT_STYLE_DIVIDEND_YIELD_THRESHOLD = Decimal("0.20")
YAHOO_OHLCV_COLUMNS = ("Open", "High", "Low", "Close", "Volume")
YAHOO_CLOSE_COLUMNS = ("Close",)
_YAHOO_SESSION: Any | None = None


class YahooMarketDataProviderAdapter:
    """Yahoo market-data adapter backed by yfinance."""

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
            symbol_frame = _drop_invalid_numeric_rows(
                symbol_frame,
                required_columns=YAHOO_OHLCV_COLUMNS,
            )
            if getattr(symbol_frame, "empty", True):
                continue
            symbol = _normalize_symbol(raw_symbol)
            for ts, row in symbol_frame.iterrows():
                bar = _bar_from_history_row(
                    row,
                    ts=ts,
                    symbol=symbol,
                    interval=interval,
                )
                if bar is not None:
                    bars.append(bar)
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
                    pair=cast(Any, pair),
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

        request_context = {
            "operation": operation,
            "symbol": raw_symbol,
            "interval": interval,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "period": period,
        }
        required_columns = _required_history_numeric_columns(operation)

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
                    return _normalize_history_frame_or_raise(
                        retry_frame,
                        operation=operation,
                        symbol=raw_symbol,
                        required_columns=required_columns,
                        provider_details=self._provider_details(
                            **request_context,
                            retry_reason="no_price_data",
                            error=str(exc),
                        ),
                    )
                raise ProviderUnavailableError(
                    "Yahoo market-data provider returned no data",
                    details=self._provider_details(
                        **request_context,
                        retry_reason="no_price_data",
                        error=str(exc),
                    ),
                ) from exc
            retry_reason = None
            if _is_yahoo_transient_request_error(exc):
                retry_reason = "transient_request"
                retry_frame = await self._retry_history_after_transient_request_error(
                    raw_symbol,
                    kwargs,
                )
                if retry_frame is not None:
                    return _normalize_history_frame_or_raise(
                        retry_frame,
                        operation=operation,
                        symbol=raw_symbol,
                        required_columns=required_columns,
                        provider_details=self._provider_details(
                            **request_context,
                            retry_reason=retry_reason,
                            error=str(exc),
                        ),
                    )
            request_details = {**request_context, "error": str(exc)}
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
                return _normalize_history_frame_or_raise(
                    retry_frame,
                    operation=operation,
                    symbol=raw_symbol,
                    required_columns=required_columns,
                    provider_details=self._provider_details(
                        **request_context,
                        retry_reason="empty_history",
                    ),
                )
            raise ProviderUnavailableError(
                "Yahoo market-data provider returned no data",
                details=self._provider_details(**request_context),
            )
        return _normalize_history_frame_or_raise(
            frame,
            operation=operation,
            symbol=raw_symbol,
            required_columns=required_columns,
            provider_details=self._provider_details(**request_context),
        )

    async def _retry_history_after_transient_request_error(
        self,
        raw_symbol: str,
        kwargs: dict[str, object],
    ) -> Any | None:
        await asyncio.sleep(YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS)
        reset_shared_yfinance_session()
        yf = _load_yfinance()
        ticker = yf.Ticker(raw_symbol, session=shared_yfinance_session())
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
                frame = await asyncio.to_thread(
                    _call_yfinance_silently,
                    yf.download,
                    **kwargs,
                )
            except Exception as exc:
                if _is_yahoo_transient_request_error(exc) and attempt < YAHOO_DOWNLOAD_MAX_ATTEMPTS:
                    await asyncio.sleep(YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS * attempt)
                    reset_shared_yfinance_session()
                    kwargs["session"] = shared_yfinance_session()
                    continue
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
                await asyncio.sleep(YAHOO_DOWNLOAD_EMPTY_RETRY_DELAY_SECONDS * attempt)
                reset_shared_yfinance_session()
                kwargs["session"] = shared_yfinance_session()

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


def reset_shared_yfinance_session() -> None:
    """Drop a failed curl session so a transient network error can recover."""

    global _YAHOO_SESSION
    session = _YAHOO_SESSION
    _YAHOO_SESSION = None
    if session is None:
        return
    try:
        session.close()
    except Exception:  # noqa: BLE001 - cleanup must not mask the provider error.
        pass


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
            "curl: (7)",
            "could not connect to server",
            "connection reset",
            "connection refused",
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
    return func(*args, **kwargs)


def _normalize_symbol(raw_symbol: str) -> Symbol:
    exchange_suffixes = (
        (".T", "TSE", "JPY"),
        (".HK", "HKEX", "HKD"),
        (".KS", "KRX", "KRW"),
        (".KQ", "KOSDAQ", "KRW"),
        (".VN", "HOSE", "VND"),
        (".HM", "HNX", "VND"),
        (".JK", "IDX", "IDR"),
        (".SI", "SGX", "SGD"),
        (".BK", "SET", "THB"),
        (".KL", "BURSA", "MYR"),
    )
    for suffix, exchange, currency in exchange_suffixes:
        if raw_symbol.endswith(suffix):
            return Symbol(
                raw=raw_symbol,
                exchange=exchange,
                code=raw_symbol.removesuffix(suffix),
                currency=cast(Any, currency),
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


def _required_history_numeric_columns(operation: str) -> tuple[str, ...]:
    if operation in {"fetch_quotes", "get_fx_rates"}:
        return YAHOO_CLOSE_COLUMNS
    return YAHOO_OHLCV_COLUMNS


def _normalize_history_frame_or_raise(
    frame: Any,
    *,
    operation: str,
    symbol: str,
    required_columns: tuple[str, ...],
    provider_details: dict[str, object],
) -> Any:
    _validate_history_columns(
        frame,
        operation=operation,
        symbol=symbol,
        required_columns=required_columns,
    )
    clean_frame = _drop_invalid_numeric_rows(frame, required_columns=required_columns)
    if not getattr(clean_frame, "empty", True):
        return clean_frame

    details = dict(provider_details)
    request = details.get("request")
    if isinstance(request, dict):
        request = dict(request)
        request["invalid_numeric_rows"] = "all"
        request["required_numeric_columns"] = list(required_columns)
        details["request"] = request
    else:
        details["invalid_numeric_rows"] = "all"
        details["required_numeric_columns"] = list(required_columns)
    raise ProviderUnavailableError(
        "Yahoo market-data provider returned no valid numeric data",
        details=details,
    )


def _drop_invalid_numeric_rows(
    frame: Any,
    *,
    required_columns: tuple[str, ...],
) -> Any:
    if getattr(frame, "empty", True):
        return frame
    try:
        clean_frame = frame.dropna(how="all")
    except Exception:
        clean_frame = frame
    if getattr(clean_frame, "empty", True):
        return clean_frame

    valid_mask: Any | None = None
    for column in required_columns:
        column_mask = _valid_numeric_column_mask(clean_frame, column)
        if column_mask is None:
            return clean_frame.iloc[0:0]
        valid_mask = column_mask if valid_mask is None else valid_mask & column_mask

    if valid_mask is None:
        return clean_frame
    try:
        return clean_frame.loc[valid_mask]
    except Exception:
        return clean_frame


def _valid_numeric_column_mask(frame: Any, column: str) -> Any | None:
    try:
        column_values = frame[column]
    except Exception:
        return None

    try:
        import pandas as pd  # type: ignore[import-not-found]

        numeric_values = pd.to_numeric(column_values, errors="coerce")
        valid_values = numeric_values.notna()
        if hasattr(valid_values, "columns"):
            return valid_values.any(axis=1)
        return valid_values
    except Exception:
        pass

    try:
        column_mask = column_values.map(_is_valid_numeric_value)
    except AttributeError:
        try:
            column_mask = column_values.apply(_is_valid_numeric_value)
        except AttributeError:
            try:
                return _is_valid_numeric_value(column_values)
            except Exception:
                return None
    if hasattr(column_mask, "columns"):
        try:
            return column_mask.any(axis=1)
        except Exception:
            return None
    return column_mask


def _is_valid_numeric_value(value: object) -> bool:
    try:
        _decimal_numeric_value(value)
    except SchemaMismatchError:
        return False
    return True


def _decimal_numeric_value(value: object) -> Decimal:
    if value is None:
        raise SchemaMismatchError("Yahoo market-data response contains an empty numeric value")
    text = str(value).strip()
    if text.lower() in {
        "",
        "nan",
        "nat",
        "none",
        "null",
        "<na>",
        "inf",
        "+inf",
        "-inf",
        "infinity",
        "+infinity",
        "-infinity",
    }:
        raise SchemaMismatchError("Yahoo market-data response contains an empty numeric value")
    try:
        decimal_value = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise SchemaMismatchError(
            "Yahoo market-data response contains an invalid numeric value"
        ) from exc
    if not decimal_value.is_finite():
        raise SchemaMismatchError("Yahoo market-data response contains a non-finite numeric value")
    return decimal_value


def _bar_from_history_row(
    row: Any,
    *,
    ts: object,
    symbol: Symbol,
    interval: Interval,
) -> Bar | None:
    """Build one normalized bar, skipping malformed Yahoo rows defensively.

    Yahoo/yfinance occasionally returns placeholder rows with a partial OHLCV payload
    for Japan tickers around the current trading day.  The frame-level cleaner should
    remove those rows first, but this final guard prevents one dirty row from aborting
    the whole cockpit/ranking request.
    """

    try:
        return Bar(
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
    except SchemaMismatchError:
        return None


def _decimal_cell(row: Any, column: str) -> Decimal:
    try:
        value = row[column]
    except Exception as exc:
        raise SchemaMismatchError(
            "Yahoo market-data response is missing a required column",
            details={"column": column},
        ) from exc

    decimal_value = _first_valid_decimal_value(value)
    if decimal_value is not None:
        return decimal_value

    raise SchemaMismatchError(
        "Yahoo market-data response contains an empty numeric value",
        details={"column": column, "value": _safe_numeric_debug_value(value)},
    )


def _first_valid_decimal_value(value: object) -> Decimal | None:
    try:
        return _decimal_numeric_value(value)
    except SchemaMismatchError:
        pass

    # Duplicate columns or a not-yet-flattened MultiIndex row can make row[column]
    # return a pandas Series.  Use the first finite numeric cell instead of treating
    # the whole Series string representation as invalid.
    if hasattr(value, "tolist"):
        try:
            values = value.tolist()
        except Exception:
            values = []
        if not isinstance(values, list):
            values = [values]
        for item in values:
            try:
                return _decimal_numeric_value(item)
            except SchemaMismatchError:
                continue
    return None


def _safe_numeric_debug_value(value: object) -> str:
    text = str(value)
    if len(text) > 120:
        return text[:117] + "..."
    return text


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
    clean_frame = _drop_invalid_numeric_rows(frame, required_columns=YAHOO_CLOSE_COLUMNS)
    if getattr(clean_frame, "empty", True):
        raise SchemaMismatchError(
            "Yahoo market-data response contains no valid close rows",
            details={"required_columns": list(YAHOO_CLOSE_COLUMNS)},
        )
    return clean_frame.index[-1], clean_frame.iloc[-1]


def _download_symbol_frame(frame: Any, raw_symbol: str) -> Any:
    columns: Any = getattr(frame, "columns", [])
    if not hasattr(columns, "nlevels") or columns.nlevels < 2:
        return frame

    # yfinance can return MultiIndex columns as either
    #   (ticker, field) ... older/group_by="ticker" shape
    # or
    #   (field, ticker) ... newer multi_level_index shape.
    # Support both so domestic tickers such as 7203.T are not converted into an
    # empty/partially invalid frame before OHLCV normalization.
    try:
        if raw_symbol in columns.get_level_values(0):
            return frame[raw_symbol].dropna(how="all")
    except Exception:
        pass
    try:
        if raw_symbol in columns.get_level_values(columns.nlevels - 1):
            return frame.xs(raw_symbol, axis=1, level=columns.nlevels - 1).dropna(how="all")
    except Exception:
        pass
    return frame.iloc[0:0]


def _validate_history_columns(
    frame: Any,
    *,
    operation: str,
    symbol: str,
    required_columns: tuple[str, ...] = YAHOO_OHLCV_COLUMNS,
) -> None:
    missing = [column for column in required_columns if column not in frame]
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
