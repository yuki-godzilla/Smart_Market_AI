from datetime import datetime

from backend.core.config import DataAccessConfig
from backend.core.data_contracts import Bar, FxRate, Interval, Quote
from backend.core.errors import DataSourceError
from backend.marketdata.live_provider_adapters import live_provider_adapter_details
from backend.marketdata.provider_registry import provider_capability_details


class YahooMarketDataProviderAdapter:
    """Opt-in Yahoo market-data adapter stub.

    The class satisfies the provider adapter protocol but intentionally avoids
    importing yfinance until the real live adapter is implemented.
    """

    def __init__(self, cfg: DataAccessConfig) -> None:
        self.cfg = cfg

    async def fetch_ohlcv(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        interval: Interval = "1d",
    ) -> list[Bar]:
        raise self._not_implemented_error(
            operation="fetch_ohlcv",
            symbols=symbols,
            start=start.isoformat(),
            end=end.isoformat(),
            interval=interval,
        )

    async def fetch_quotes(self, symbols: list[str], at: datetime | None = None) -> list[Quote]:
        details = {"operation": "fetch_quotes", "symbols": symbols}
        if at is not None:
            details["at"] = at.isoformat()
        raise self._not_implemented_error(**details)

    async def get_fx_rates(
        self,
        pairs: list[str],
        at: datetime | None = None,
        method: str = "spot",
    ) -> list[FxRate]:
        details = {"operation": "get_fx_rates", "pairs": pairs, "method": method}
        if at is not None:
            details["at"] = at.isoformat()
        raise self._not_implemented_error(**details)

    def healthcheck(self) -> dict[str, str]:
        return {
            "provider": self.cfg.provider,
            "status": "not_implemented",
            "adapter": "YahooMarketDataProviderAdapter",
        }

    def _not_implemented_error(self, **request_details: object) -> DataSourceError:
        details = provider_capability_details(self.cfg.provider)
        details.update(live_provider_adapter_details(self.cfg.provider))
        details.update(
            {
                "allow_external_providers": self.cfg.allow_external_providers,
                "opt_in_status": "explicitly_enabled_stub",
                "request": request_details,
            }
        )
        return DataSourceError(
            "Yahoo market-data provider adapter is not implemented yet",
            details=details,
        )
