from backend.core.config import DataAccessConfig
from backend.marketdata.data_access import DataAccess
from backend.marketdata.provider_adapters import MarketDataProviderAdapter
from backend.marketdata.providers import YahooMarketDataProviderAdapter


def create_market_data_provider_adapter(
    cfg: DataAccessConfig | None = None,
) -> MarketDataProviderAdapter:
    """Create the configured market-data provider adapter.

    Deterministic mock/CSV providers are served by DataAccess. Live providers
    such as Yahoo are routed to their adapter when enabled in settings.
    """

    resolved_cfg = cfg or DataAccessConfig()
    if resolved_cfg.provider == "yahoo" and resolved_cfg.allow_external_providers:
        return YahooMarketDataProviderAdapter(resolved_cfg)
    return DataAccess(resolved_cfg)
