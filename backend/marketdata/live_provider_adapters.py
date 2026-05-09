from dataclasses import dataclass


@dataclass(frozen=True)
class LiveProviderAdapterSpec:
    """Planned live-provider adapter metadata.

    These specs describe the future adapter boundary without importing optional
    network-dependent libraries on the deterministic MVP path.
    """

    provider: str
    adapter_protocol: str
    adapter_module: str
    optional_dependency: str
    smoke_check_status: str


LIVE_PROVIDER_ADAPTER_SPECS: dict[str, LiveProviderAdapterSpec] = {
    "yahoo": LiveProviderAdapterSpec(
        provider="yahoo",
        adapter_protocol="MarketDataProviderAdapter",
        adapter_module="backend.marketdata.providers.yahoo",
        optional_dependency="yfinance",
        smoke_check_status="implemented_live_opt_in",
    ),
    "polygon": LiveProviderAdapterSpec(
        provider="polygon",
        adapter_protocol="MarketDataProviderAdapter",
        adapter_module="backend.marketdata.providers.polygon",
        optional_dependency="polygon-api-client",
        smoke_check_status="not_implemented",
    ),
}


def live_provider_adapter_details(provider: str) -> dict[str, object]:
    """Return planned adapter metadata for live-provider diagnostics."""

    spec = LIVE_PROVIDER_ADAPTER_SPECS.get(provider)
    if spec is None:
        return {
            "adapter_registered": False,
        }
    return {
        "adapter_registered": True,
        "adapter_protocol": spec.adapter_protocol,
        "adapter_module": spec.adapter_module,
        "optional_dependency": spec.optional_dependency,
        "smoke_check_status": spec.smoke_check_status,
    }
