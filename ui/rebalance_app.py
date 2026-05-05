from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.main import RebalanceCheckRequest, create_portfolio_risk_workflow
from backend.portfolio.workflow import PortfolioRiskResult

DEFAULT_POSITIONS_JSON = """[
  {
    "symbol": "7203.T",
    "qty": "10",
    "avg_price": "2800",
    "currency": "JPY"
  }
]"""

DEFAULT_TARGETS_JSON = """[
  {
    "symbol": "7203.T",
    "currency": "JPY",
    "target_weight": "0.5"
  },
  {
    "symbol": "AAPL",
    "currency": "USD",
    "target_weight": "0.5"
  }
]"""


def build_rebalance_request(
    *,
    account_id: str,
    as_of: date,
    cash_jpy: Decimal,
    positions_json: str,
    targets_json: str,
) -> RebalanceCheckRequest:
    """Build and validate a rebalance-check request from UI text inputs."""

    return RebalanceCheckRequest.model_validate(
        {
            "account_id": account_id,
            "as_of": as_of,
            "positions": _load_json_list(positions_json, "positions"),
            "targets": _load_json_list(targets_json, "targets"),
            "cash_jpy": cash_jpy,
        }
    )


async def run_rebalance_check(request: RebalanceCheckRequest) -> PortfolioRiskResult:
    """Run the same Portfolio-to-Risk workflow used by the FastAPI endpoint."""

    return await create_portfolio_risk_workflow().propose_and_check(
        account_id=request.account_id,
        positions=request.positions,
        targets=request.targets,
        as_of=request.as_of,
        cash_jpy=request.cash_jpy,
    )


def _load_json_list(value: str, field_name: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON") from exc
    if not isinstance(data, list):
        raise ValueError(f"{field_name} must be a JSON array")
    if not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{field_name} must contain JSON objects")
    return data
