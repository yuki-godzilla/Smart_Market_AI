from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_openapi_schema_documents_main_api_contracts():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Smart Market AI API"
    assert schema["info"]["version"] == "0.1.0"
    assert [tag["name"] for tag in schema["tags"]] == ["Health", "Risk", "Portfolio"]

    paths = schema["paths"]
    assert paths["/health"]["get"]["tags"] == ["Health"]
    assert paths["/risk/pre-trade-check"]["post"]["tags"] == ["Risk"]
    assert paths["/portfolio/rebalance-check"]["post"]["tags"] == ["Portfolio"]

    portfolio_operation = paths["/portfolio/rebalance-check"]["post"]
    assert portfolio_operation["summary"] == "Generate a rebalance proposal and check risk"
    assert "422" in portfolio_operation["responses"]
    assert "502" in portfolio_operation["responses"]


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
