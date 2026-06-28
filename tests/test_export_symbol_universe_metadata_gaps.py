from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "export_symbol_universe_metadata_gaps.py"
)
spec = importlib.util.spec_from_file_location("export_symbol_universe_metadata_gaps", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_build_gap_candidates_filters_market_and_missing_metrics():
    rows = [
        {
            "symbol": "A",
            "name": "Alpha",
            "market": "korea",
            "asset_type": "stock",
            "pbr": "",
            "per": "10",
        },
        {
            "symbol": "B",
            "name": "Beta",
            "market": "jp",
            "asset_type": "stock",
            "pbr": "",
            "per": "",
        },
        {
            "symbol": "C",
            "name": "Gamma",
            "market": "korea",
            "asset_type": "stock",
            "pbr": "1.2",
            "per": "12",
        },
    ]

    candidates = module._build_candidates(
        rows,
        markets=["korea"],
        asset_type="",
        metrics=["pbr"],
        include_complete=False,
    )

    assert [row["symbol"] for row in candidates] == ["A"]
    assert candidates[0]["missing_metrics"] == "pbr"
    assert candidates[0]["recommended_source"].startswith("KRX")
