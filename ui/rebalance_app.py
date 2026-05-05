from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.main import RebalanceCheckRequest, create_portfolio_risk_workflow
from backend.core.config import CONFIG_FILE_ENV, get_settings
from backend.portfolio.service import RebalanceProposal
from backend.portfolio.workflow import PortfolioRiskResult

DEFAULT_ACCOUNT_ID = "acct-1"
DEFAULT_AS_OF = date(2026, 4, 9)
DEFAULT_CASH_JPY = Decimal("29000")
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


def build_default_rebalance_request() -> RebalanceCheckRequest:
    """Build the deterministic sample request used by docs, tests, and the UI."""

    return build_rebalance_request(
        account_id=DEFAULT_ACCOUNT_ID,
        as_of=DEFAULT_AS_OF,
        cash_jpy=DEFAULT_CASH_JPY,
        positions_json=DEFAULT_POSITIONS_JSON,
        targets_json=DEFAULT_TARGETS_JSON,
    )


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


def runtime_settings_summary() -> dict[str, str]:
    """Return the active local runtime settings relevant to the UI."""

    settings = get_settings()
    return {
        "provider": settings.dataaccess.provider,
        "csv_data_dir": settings.dataaccess.csv_data_dir,
        "config_file": os.getenv(CONFIG_FILE_ENV) or "defaults",
    }


async def run_rebalance_check(request: RebalanceCheckRequest) -> PortfolioRiskResult:
    """Run the same Portfolio-to-Risk workflow used by the FastAPI endpoint."""

    return await create_portfolio_risk_workflow().propose_and_check(
        account_id=request.account_id,
        positions=request.positions,
        targets=request.targets,
        as_of=request.as_of,
        cash_jpy=request.cash_jpy,
    )


def result_summary(result: PortfolioRiskResult) -> dict[str, str]:
    """Return a compact summary row for the Streamlit result header."""

    proposal = result.proposal
    return {
        "account_id": proposal.account_id,
        "as_of": proposal.as_of.isoformat(),
        "total_value_jpy": _format_decimal(proposal.current.total_value_jpy),
        "cash_jpy": _format_decimal(proposal.current.cash_jpy),
        "trade_count": str(len(proposal.trades)),
        "risk_status": result.risk_decision.status if result.risk_decision else "NO_TRADES",
    }


def current_position_rows(proposal: RebalanceProposal) -> list[dict[str, str]]:
    """Format valued current positions for table display."""

    return [
        {
            "symbol": position.symbol,
            "qty": _format_decimal(position.qty),
            "currency": position.currency,
            "last": _format_decimal(position.last),
            "fx_rate_jpy": _format_decimal(position.fx_rate_jpy),
            "value_jpy": _format_decimal(position.value_jpy),
        }
        for position in proposal.current.positions
    ]


def target_allocation_rows(proposal: RebalanceProposal) -> list[dict[str, str]]:
    """Format target allocations for table display."""

    return [
        {
            "symbol": target.symbol,
            "currency": target.currency,
            "target_weight": _format_decimal(target.target_weight),
        }
        for target in proposal.targets
    ]


def proposed_trade_rows(proposal: RebalanceProposal) -> list[dict[str, str]]:
    """Format proposed trades for table display."""

    return [
        {
            "symbol": trade.symbol,
            "side": trade.side,
            "qty": _format_decimal(trade.qty),
            "price_hint": _format_optional_decimal(trade.price_hint),
            "currency": trade.currency,
        }
        for trade in proposal.trades
    ]


def risk_breach_rows(result: PortfolioRiskResult) -> list[dict[str, str]]:
    """Format risk rule breaches for table display."""

    if result.risk_decision is None:
        return []
    return [{"breach": breach} for breach in result.risk_decision.breaches]


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


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _format_optional_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return _format_decimal(value)
