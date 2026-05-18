from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RankingUniversePolicy:
    """Policy for the initial ranking universe.

    Unknown tradability is allowed by default because the current CSV is a
    seed universe, not a broker-confirmed master.
    """

    broker: str = "sbi_securities"
    include_asset_types: frozenset[str] = frozenset(
        {
            "adr",
            "etf",
            "fund",
            "investment_trust",
            "mutual_fund",
            "reit",
            "stock",
        }
    )
    exclude_asset_types: frozenset[str] = frozenset(
        {
            "bond",
            "cfd",
            "commodity",
            "crypto",
            "futures",
            "fx",
            "mmf",
            "option",
        }
    )
    exclude_leveraged: bool = True
    exclude_inverse: bool = True
    exclude_untradable: bool = True
    require_sbi_supported: bool = True
    require_active: bool = True
    include_nisa_only: bool = False


DEFAULT_RANKING_UNIVERSE_POLICY = RankingUniversePolicy()
NISA_ELIGIBLE_CATEGORIES = {"both", "growth", "tsumitate"}


def symbol_allowed_by_ranking_universe_policy(
    row: Mapping[str, str],
    policy: RankingUniversePolicy = DEFAULT_RANKING_UNIVERSE_POLICY,
) -> bool:
    """Return whether a symbol row is eligible for the default ranking universe."""

    asset_type = _normalized(row.get("asset_type", ""))
    if asset_type in policy.exclude_asset_types:
        return False
    if policy.include_asset_types and asset_type not in policy.include_asset_types:
        return False

    broker = _normalized(row.get("broker", ""))
    if broker and broker != "unknown" and broker != policy.broker:
        return False

    if policy.exclude_untradable and _normalized(row.get("tradability", "")) == "not_tradable":
        return False
    if policy.exclude_leveraged and _truthy(row.get("is_leveraged", "")):
        return False
    if policy.exclude_inverse and _truthy(row.get("is_inverse", "")):
        return False
    if policy.require_sbi_supported and _explicit_false(row.get("is_sbi_supported", "")):
        return False
    if policy.require_active and _explicit_false(row.get("is_active", "")):
        return False
    if policy.include_nisa_only:
        return _normalized(row.get("nisa_category", "")) in NISA_ELIGIBLE_CATEGORIES
    return True


def _normalized(value: str) -> str:
    return value.strip().lower()


def _truthy(value: str) -> bool:
    return _normalized(value) in {"1", "true", "yes", "y"}


def _explicit_false(value: str) -> bool:
    return _normalized(value) in {"0", "false", "no", "n"}
