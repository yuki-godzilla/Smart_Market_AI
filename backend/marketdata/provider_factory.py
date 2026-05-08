from backend.core.config import DataAccessConfig
from backend.marketdata.data_access import DataAccess
from backend.marketdata.provider_adapters import MarketDataProviderAdapter


def create_market_data_provider_adapter(
    cfg: DataAccessConfig | None = None,
) -> MarketDataProviderAdapter:
    """Create the configured market-data provider adapter.

    The current deterministic providers are served by DataAccess. Future live
    adapters should be registered here after they satisfy MarketDataProviderAdapter.
    """

    return DataAccess(cfg)
