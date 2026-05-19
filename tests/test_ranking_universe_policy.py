from __future__ import annotations

from backend.marketdata.ranking_universe_policy import (
    RankingUniversePolicy,
    symbol_allowed_by_ranking_universe_policy,
)


def test_ranking_universe_policy_allows_unknown_tradability_seed_rows():
    assert symbol_allowed_by_ranking_universe_policy(
        {
            "asset_type": "stock",
            "broker": "sbi_securities",
            "tradability": "unknown",
            "nisa_category": "unknown",
            "is_sbi_supported": "true",
            "is_active": "true",
            "is_leveraged": "false",
            "is_inverse": "false",
        }
    )


def test_ranking_universe_policy_excludes_initial_out_of_scope_products():
    for asset_type in [
        "adr",
        "fx",
        "cfd",
        "futures",
        "option",
        "crypto",
        "bond",
        "mmf",
        "commodity",
        "fund",
        "investment_trust",
        "mutual_fund",
        "reit",
    ]:
        assert not symbol_allowed_by_ranking_universe_policy({"asset_type": asset_type})


def test_ranking_universe_policy_excludes_risky_or_unavailable_rows():
    base = {
        "asset_type": "etf",
        "broker": "sbi_securities",
        "tradability": "unknown",
        "is_sbi_supported": "true",
        "is_active": "true",
        "is_leveraged": "false",
        "is_inverse": "false",
    }

    assert not symbol_allowed_by_ranking_universe_policy({**base, "tradability": "not_tradable"})
    assert not symbol_allowed_by_ranking_universe_policy({**base, "is_sbi_supported": "false"})
    assert not symbol_allowed_by_ranking_universe_policy({**base, "is_active": "false"})
    assert not symbol_allowed_by_ranking_universe_policy({**base, "is_leveraged": "true"})
    assert not symbol_allowed_by_ranking_universe_policy({**base, "is_inverse": "true"})


def test_ranking_universe_policy_can_require_nisa_eligible_rows():
    policy = RankingUniversePolicy(include_nisa_only=True)

    assert symbol_allowed_by_ranking_universe_policy(
        {"asset_type": "stock", "nisa_category": "growth"},
        policy=policy,
    )
    assert not symbol_allowed_by_ranking_universe_policy(
        {"asset_type": "stock", "nisa_category": "unknown"},
        policy=policy,
    )
