from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_openapi_schema_documents_main_api_contracts():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Smart Market AI API"
    assert schema["info"]["version"] == "0.1.0"
    assert [tag["name"] for tag in schema["tags"]] == [
        "Health",
        "Risk",
        "Portfolio",
        "Screening",
        "Forecast",
        "Scoring",
    ]

    paths = schema["paths"]
    assert paths["/health"]["get"]["tags"] == ["Health"]
    assert paths["/risk/pre-trade-check"]["post"]["tags"] == ["Risk"]
    assert paths["/portfolio/rebalance-check"]["post"]["tags"] == ["Portfolio"]
    assert paths["/screening/score"]["post"]["tags"] == ["Screening"]
    assert paths["/forecast/evaluate"]["post"]["tags"] == ["Forecast"]
    assert paths["/scoring/investment-score"]["post"]["tags"] == ["Scoring"]

    portfolio_operation = paths["/portfolio/rebalance-check"]["post"]
    assert portfolio_operation["summary"] == "Generate a rebalance proposal and check risk"
    assert "429" in portfolio_operation["responses"]
    assert "422" in portfolio_operation["responses"]
    assert "502" in portfolio_operation["responses"]
    assert "503" in portfolio_operation["responses"]
    assert "504" in portfolio_operation["responses"]

    screening_operation = paths["/screening/score"]["post"]
    assert screening_operation["summary"] == "Rank symbols with explainable screening scores"
    assert "502" in screening_operation["responses"]

    forecast_operation = paths["/forecast/evaluate"]["post"]
    assert forecast_operation["summary"] == "Evaluate deterministic forecasts for a symbol"
    assert "422" in forecast_operation["responses"]

    scoring_operation = paths["/scoring/investment-score"]["post"]
    assert (
        scoring_operation["summary"]
        == "Score symbols with model-informed investment-support signals"
    )
    assert "502" in scoring_operation["responses"]


def test_openapi_schema_includes_request_examples():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]

    risk_example = schemas["PreTradeCheckRequest"]["examples"][0]
    assert risk_example["basket"][0]["symbol"] == "AAPL"
    assert risk_example["basket"][0]["qty"] == "10"

    portfolio_example = schemas["RebalanceCheckRequest"]["examples"][0]
    assert portfolio_example["positions"][0]["symbol"] == "7203.T"
    assert portfolio_example["targets"][1]["symbol"] == "AAPL"
    assert portfolio_example["cash_jpy"] == "29000"

    screening_example = schemas["ScreeningScoreRequest"]["examples"][0]
    assert screening_example["symbols"] == ["AAPL", "7203.T"]
    assert screening_example["as_of"] == "2026-04-09"

    forecast_example = schemas["ForecastEvaluateRequest"]["examples"][0]
    assert forecast_example["symbol"] == "AAPL"
    assert forecast_example["start"] == "2026-04-07"
    assert forecast_example["end"] == "2026-04-09"
    assert forecast_example["adapter"] == "baseline"
    advanced_forecast_example = schemas["ForecastEvaluateRequest"]["examples"][1]
    assert advanced_forecast_example["adapter"] == "advanced_linear"
    assert advanced_forecast_example["horizon_days"] == 5

    scoring_example = schemas["InvestmentScoreRequest"]["examples"][0]
    assert scoring_example["symbols"] == ["AAPL", "7203.T"]
    assert scoring_example["as_of"] == "2026-04-09"
