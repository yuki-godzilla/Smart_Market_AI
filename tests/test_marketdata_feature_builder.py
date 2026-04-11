import asyncio
from datetime import date

import pytest

from backend.core.errors import DataSourceError
from backend.marketdata import DataAccess, FeatureBuilder


def test_compute_adv_returns_non_negative_value():
    fb = FeatureBuilder(DataAccess())

    adv = asyncio.run(fb.compute_adv("AAPL", date(2026, 4, 9)))

    assert adv > 0


def test_compute_vol_returns_non_negative_value():
    fb = FeatureBuilder(DataAccess())

    vol = asyncio.run(fb.compute_vol("AAPL", date(2026, 4, 9)))

    assert vol >= 0


def test_compute_vol_supports_parkinson_method():
    fb = FeatureBuilder(DataAccess())

    vol = asyncio.run(fb.compute_vol("7203.T", date(2026, 4, 9), method="parkinson"))

    assert vol >= 0


def test_compute_vol_rejects_unknown_method():
    fb = FeatureBuilder(DataAccess())

    with pytest.raises(DataSourceError) as exc_info:
        asyncio.run(fb.compute_vol("AAPL", date(2026, 4, 9), method="unknown"))

    assert exc_info.value.details == {"method": "unknown"}


def test_build_daily_snapshot_returns_feature_rows():
    fb = FeatureBuilder(DataAccess())

    snapshots = asyncio.run(fb.build_daily_snapshot(["AAPL", "7203.T"], date(2026, 4, 9)))

    assert len(snapshots) == 2
    assert snapshots[0].symbol == "AAPL"
    assert snapshots[0].last is not None
    assert snapshots[0].adv_20d is not None
    assert snapshots[0].vol_20d is not None
    assert snapshots[0].missing == {"dividend_yield": True, "market_cap_jpy": True}
