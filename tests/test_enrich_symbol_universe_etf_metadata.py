from __future__ import annotations

from pathlib import Path

from tools.enrich_symbol_universe_etf_metadata import (
    build_manifest,
    corrected_yahoo_expense_ratio_pct,
    enrich_etf_metadata,
    infer_etf_index_family,
)


def test_infer_etf_index_family_uses_name_aliases_theme_and_tags():
    row = {
        "symbol": "1343.T",
        "name": "NEXT FUNDS J-REIT ETF",
        "aliases": "東証REIT指数（配当込み）",
        "theme": "reit",
        "tags": "low_cost,balanced",
    }

    assert infer_etf_index_family(row) == "reit"


def test_corrected_yahoo_expense_ratio_pct_scales_percentage_like_values():
    assert (
        corrected_yahoo_expense_ratio_pct(
            {
                "asset_type": "etf",
                "metadata_source": "yahoo",
                "expense_ratio_pct": "15",
            }
        )
        == "0.15"
    )


def test_corrected_yahoo_expense_ratio_pct_keeps_ratio_based_values():
    assert (
        corrected_yahoo_expense_ratio_pct(
            {
                "asset_type": "etf",
                "metadata_source": "yahoo",
                "expense_ratio_pct": "0.24",
            }
        )
        == ""
    )


def test_enrich_etf_metadata_updates_missing_index_family_and_expense_ratio():
    rows = [
        {
            "symbol": "SCHD",
            "name": "Schwab U.S. Dividend Equity ETF",
            "asset_type": "etf",
            "metadata_source": "yahoo",
            "index_family": "",
            "expense_ratio_pct": "6",
            "aliases": "",
            "theme": "index",
            "tags": "dividend,low_cost",
        },
        {
            "symbol": "AAPL",
            "name": "Apple",
            "asset_type": "stock",
            "metadata_source": "yahoo",
            "index_family": "",
            "expense_ratio_pct": "",
        },
    ]

    changes = enrich_etf_metadata(rows)

    assert rows[0]["index_family"] == "dividend"
    assert rows[0]["expense_ratio_pct"] == "0.06"
    assert rows[1]["index_family"] == ""
    assert changes[0]["changed_fields"] == ["index_family", "expense_ratio_pct"]
    manifest = build_manifest(changes, csv_path=Path("symbol_universe.csv"))
    assert manifest["changed_rows"] == 1
    assert manifest["index_family_updates"] == {"dividend": 1}
    assert manifest["expense_ratio_scale_corrections"] == 1


def test_enrich_etf_metadata_applies_curated_provider_overrides():
    rows = [
        {
            "symbol": "PXIU",
            "name": "TRex 2倍 ロング UPXI デイリー ETF",
            "asset_type": "etf",
            "metadata_source": "yahoo",
            "index_family": "",
            "expense_ratio_pct": "0.95",
            "aliases": "",
            "theme": "index",
            "complexity": "beginner",
            "is_leveraged": "false",
            "is_inverse": "false",
            "tags": "",
        }
    ]

    changes = enrich_etf_metadata(
        rows,
        overrides={
            "PXIU": {
                "index_family": "single_stock",
                "complexity": "leveraged",
                "is_leveraged": "true",
                "is_inverse": "false",
            }
        },
    )

    assert rows[0]["index_family"] == "single_stock"
    assert rows[0]["complexity"] == "leveraged"
    assert rows[0]["is_leveraged"] == "true"
    assert changes[0]["changed_fields"] == ["index_family", "complexity", "is_leveraged"]
