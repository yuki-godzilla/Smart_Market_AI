from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.data_contracts import Bar, Symbol

client = TestClient(app)


def test_forecast_evaluate_api_returns_available_baselines():
    response = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "start": "2026-04-07",
            "end": "2026-04-09",
            "horizon_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [row["model_name"] for row in payload] == ["naive", "moving_average_3"]
    assert payload[0]["symbol"] == "AAPL"
    assert payload[0]["latest_forecast"]["forecast_close"] == "175.0000"
    assert payload[0]["metrics"]["sample_count"] == 2
    assert payload[1]["metrics"]["sample_count"] == 0


def test_forecast_evaluate_api_rejects_reversed_date_range():
    response = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "start": "2026-04-10",
            "end": "2026-04-09",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "APP-2002"
    assert response.json()["message"] == "Forecast start date must be on or before end date"


def test_forecast_evaluate_api_returns_advanced_linear_adapter(monkeypatch):
    monkeypatch.setattr(
        "backend.app.main.create_market_data_provider_adapter",
        lambda _: _FakeForecastProvider(_bars(72)),
    )

    response = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "start": "2026-01-01",
            "end": "2026-03-15",
            "horizon_days": 5,
            "adapter": "advanced_linear",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    row = payload[0]
    assert row["adapter_name"] == "advanced_linear"
    assert row["model_name"] == "Ridge"
    assert row["symbol"] == "AAPL"
    assert row["horizon_days"] == 5
    assert row["forecast_close"] != row["latest_close"]
    assert row["predicted_return"] != "0.0000"
    assert row["validation_metrics"]["sample_count"] == 67
    assert row["feature_contribution_summary"]
    assert any("not investment advice" in warning for warning in row["warnings"])


def test_forecast_evaluate_api_returns_advanced_quantile_adapter(monkeypatch):
    monkeypatch.setattr(
        "backend.app.main.create_market_data_provider_adapter",
        lambda _: _FakeForecastProvider(_bars(72)),
    )

    response = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "start": "2026-01-01",
            "end": "2026-03-15",
            "horizon_days": 5,
            "adapter": "advanced_quantile",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    row = payload[0]
    assert row["adapter_name"] == "advanced_quantile"
    assert row["model_name"] == "HistoricalQuantile"
    assert row["forecast_close_lower"] is not None
    assert row["forecast_close_upper"] is not None
    assert row["predicted_return_lower"] is not None
    assert row["predicted_return_upper"] is not None
    assert row["validation_metrics"]["sample_count"] == 67


def test_forecast_evaluate_api_returns_advanced_tree_sklearn_adapter(monkeypatch):
    monkeypatch.setattr(
        "backend.app.main.create_market_data_provider_adapter",
        lambda _: _FakeForecastProvider(_bars(72)),
    )

    response = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "start": "2026-01-01",
            "end": "2026-03-15",
            "horizon_days": 5,
            "adapter": "advanced_tree_sklearn",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    row = payload[0]
    assert row["adapter_name"] == "advanced_tree_sklearn"
    assert row["model_name"] == "ExtraTreesRegressor"
    assert row["forecast_close"] != row["latest_close"]
    assert row["validation_metrics"]["sample_count"] == 67
    assert row["feature_contribution_summary"]


def test_forecast_evaluate_api_returns_advanced_linear_common_horizon(monkeypatch):
    monkeypatch.setattr(
        "backend.app.main.create_market_data_provider_adapter",
        lambda _: _FakeForecastProvider(_bars(72)),
    )

    response = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "start": "2026-01-01",
            "end": "2026-03-15",
            "horizon_days": 10,
            "adapter": "advanced_linear",
        },
    )

    assert response.status_code == 200
    row = response.json()[0]
    assert row["adapter_name"] == "advanced_linear"
    assert row["horizon_days"] == 10
    assert row["validation_metrics"]["sample_count"] == 62


def test_forecast_evaluate_api_rejects_unknown_adapter(monkeypatch):
    monkeypatch.setattr(
        "backend.app.main.create_market_data_provider_adapter",
        lambda _: _FakeForecastProvider(_bars(72)),
    )

    response = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "start": "2026-01-01",
            "end": "2026-03-15",
            "horizon_days": 5,
            "adapter": "advanced_magic",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "APP-2002"
    assert payload["message"] == "Unsupported forecast adapter"
    assert payload["details"]["supported_adapters"] == [
        "baseline",
        "advanced_linear",
        "advanced_tree_sklearn",
        "advanced_quantile",
    ]


class _FakeForecastProvider:
    def __init__(self, bars: list[Bar]) -> None:
        self._bars = bars

    async def fetch_ohlcv(
        self,
        _symbols: list[str],
        *,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        return [bar for bar in self._bars if start <= bar.ts <= end]


def _bars(count: int) -> list[Bar]:
    symbol = Symbol(raw="AAPL", exchange="NASDAQ", code="AAPL", currency="USD")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars: list[Bar] = []
    close = Decimal("100")
    for index in range(count):
        drift = Decimal("0.35")
        cycle = Decimal((index % 7) - 3) / Decimal("20")
        close = close + drift + cycle
        bars.append(
            Bar(
                symbol=symbol,
                ts=start + timedelta(days=index),
                open=close - Decimal("0.4"),
                high=close + Decimal("0.8"),
                low=close - Decimal("0.9"),
                close=close,
                volume=Decimal(1000 + (index * 17) + ((index % 5) * 11)),
                interval="1d",
                provider="fixture",
            )
        )
    return bars
