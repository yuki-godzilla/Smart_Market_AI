from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    """Market-data provider capability metadata."""

    name: str
    implemented: bool
    deterministic: bool
    requires_external_opt_in: bool


PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    "mock": ProviderSpec(
        name="mock",
        implemented=True,
        deterministic=True,
        requires_external_opt_in=False,
    ),
    "csv": ProviderSpec(
        name="csv",
        implemented=True,
        deterministic=True,
        requires_external_opt_in=False,
    ),
    "yahoo": ProviderSpec(
        name="yahoo",
        implemented=True,
        deterministic=False,
        requires_external_opt_in=True,
    ),
    "polygon": ProviderSpec(
        name="polygon",
        implemented=False,
        deterministic=False,
        requires_external_opt_in=True,
    ),
}

SUPPORTED_PROVIDERS = tuple(
    name for name, spec in PROVIDER_REGISTRY.items() if spec.implemented and spec.deterministic
)
IMPLEMENTED_LIVE_PROVIDERS = tuple(
    name
    for name, spec in PROVIDER_REGISTRY.items()
    if spec.implemented and spec.requires_external_opt_in
)
PLANNED_LIVE_PROVIDERS = tuple(
    name
    for name, spec in PROVIDER_REGISTRY.items()
    if not spec.implemented and spec.requires_external_opt_in
)


def provider_capability_details(provider: str) -> dict[str, object]:
    """Return structured capability metadata for provider diagnostics."""

    spec = PROVIDER_REGISTRY.get(provider)
    if spec is None:
        return {
            "provider": provider,
            "registered": False,
            "supported_providers": list(SUPPORTED_PROVIDERS),
            "implemented_live_providers": list(IMPLEMENTED_LIVE_PROVIDERS),
            "planned_live_providers": list(PLANNED_LIVE_PROVIDERS),
        }
    return {
        "provider": spec.name,
        "registered": True,
        "implemented": spec.implemented,
        "deterministic": spec.deterministic,
        "requires_external_opt_in": spec.requires_external_opt_in,
        "supported_providers": list(SUPPORTED_PROVIDERS),
        "implemented_live_providers": list(IMPLEMENTED_LIVE_PROVIDERS),
        "planned_live_providers": list(PLANNED_LIVE_PROVIDERS),
    }
