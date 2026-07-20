from __future__ import annotations

import csv
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from backend.investment_candidates.exporter import (
    EXPORT_COLUMNS,
    RANKING_DEFINITIONS,
    export_investment_candidates,
)
from ui.ranking_export_policy import create_ranking_export_policy


def _universe() -> list[dict[str, str]]:
    rows = []
    for market, symbol, tier in (
        ("jp", "1111.T", "large"),
        ("jp", "2222.T", "small"),
        ("us", "USONE", "large"),
        ("us", "USTWO", "mid"),
    ):
        rows.append(
            {
                "symbol": symbol,
                "name": f"Company {symbol}",
                "market": market,
                "asset_type": "stock",
                "nisa_category": "growth",
                "market_cap_tier": tier,
                "risk_band": "MEDIUM",
                "dividend_yield_pct": "3.2",
                "per": "15",
                "pbr": "1.2",
                "roe_pct": "12",
                "is_active": "true",
            }
        )
    return rows


def _runner(symbols, _start, _end, _provider, _progress):
    if symbols and symbols[0] == "2222.T":
        raise RuntimeError("fixture ranking failure")
    return (
        [
            {
                "symbol": symbol,
                "total_score": "72",
                "screening_score": "68",
                "risk_score": "30",
                "data_quality": "OK",
                "upside_signal": "61",
                "downside_warning": "21",
                "volatility": "14",
                "warnings": "",
            }
            for symbol in symbols
        ],
        [],
    )


def test_candidate_definitions_cover_the_requested_14_region_separated_exports():
    assert len(RANKING_DEFINITIONS) == 14
    assert [item.ranking_id for item in RANKING_DEFINITIONS] == [
        f"{index:02}" for index in range(1, 15)
    ]
    assert all(item.region in {"japan", "us"} for item in RANKING_DEFINITIONS)
    assert all(item.filename.endswith(".csv") for item in RANKING_DEFINITIONS)
    assert {item.period for item in RANKING_DEFINITIONS[:9]} == {"3y"}
    assert {item.period for item in RANKING_DEFINITIONS[9:]} == {"1y"}
    assert RANKING_DEFINITIONS[0].dividend_range == ("2.0", "5.0")
    assert RANKING_DEFINITIONS[4].per_range == ("7", "30")
    assert RANKING_DEFINITIONS[6].allowed_risk_bands == ("MEDIUM", "HIGH")


def test_export_writes_bom_csv_combined_overlap_zip_and_retains_partial_failures(tmp_path):
    summary = export_investment_candidates(
        output_root=tmp_path,
        universe_rows=_universe(),
        runner=_runner,
        ranking_policy=create_ranking_export_policy(),
        top_n=1,
        fetch_limit=300,
        now=datetime(2026, 7, 17, 2, 0, tzinfo=UTC),
    )
    output = Path(summary["export_directory"])
    assert summary["ranking_count"] == 14
    assert summary["failure_count"] >= 1
    assert (output / "01_jp_nisa_long_term_3y.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    with (output / "all_rankings_combined.csv").open(encoding="utf-8-sig", newline="") as stream:
        headers = next(csv.reader(stream))
    assert list(EXPORT_COLUMNS) == headers
    result = json.loads((output / "execution_summary.json").read_text(encoding="utf-8"))
    assert len(result["ranking_results"]) == 14
    with zipfile.ZipFile(summary["zip_file"]) as archive:
        assert "ranking_overlap_summary.csv" in archive.namelist()
        assert "execution_summary.json" in archive.namelist()
        assert "14_us_upside_signal_1y.csv" in archive.namelist()


def test_export_can_evaluate_every_eligible_symbol_without_a_fetch_limit(tmp_path):
    calls: list[list[str]] = []

    def runner(symbols, *_args):
        calls.append(symbols)
        return _runner(symbols, *_args)

    summary = export_investment_candidates(
        output_root=tmp_path,
        universe_rows=_universe(),
        runner=runner,
        ranking_policy=create_ranking_export_policy(),
        top_n=1,
        fetch_limit=None,
        now=datetime(2026, 7, 17, 2, 0, tzinfo=UTC),
    )

    assert summary["failure_count"] >= 1
    assert max(map(len, calls)) > 1
    result = summary["ranking_results"][0]
    assert result["fetch_limit"] is None
    assert result["requested_count"] == result["eligible_count"]
