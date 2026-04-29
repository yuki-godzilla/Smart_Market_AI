from datetime import date
from decimal import Decimal

from backend.core.data_contracts import Position, StrictBaseModel
from backend.portfolio.service import PortfolioService, RebalanceProposal, TargetAllocation
from backend.risk import RiskDecision, RiskService


class PortfolioRiskResult(StrictBaseModel):
    """Combined portfolio proposal and optional pre-trade risk decision."""

    proposal: RebalanceProposal
    risk_decision: RiskDecision | None = None


class PortfolioRiskWorkflow:
    """Coordinate Portfolio rebalance proposals with Risk pre-trade checks."""

    def __init__(
        self,
        portfolio_service: PortfolioService,
        risk_service: RiskService,
    ) -> None:
        """Create a workflow from already configured services."""

        self.portfolio_service = portfolio_service
        self.risk_service = risk_service

    async def propose_and_check(
        self,
        account_id: str,
        positions: list[Position],
        targets: list[TargetAllocation],
        as_of: date,
        cash_jpy: Decimal = Decimal("0"),
    ) -> PortfolioRiskResult:
        """Generate a rebalance proposal and check its trades through Risk."""

        proposal = await self.portfolio_service.rebalance(
            account_id=account_id,
            positions=positions,
            targets=targets,
            as_of=as_of,
            cash_jpy=cash_jpy,
        )
        risk_decision = None
        if proposal.trades:
            risk_decision = await self.risk_service.pre_trade_check(
                proposal.trades,
                as_of,
                account_id,
            )

        return PortfolioRiskResult(
            proposal=proposal,
            risk_decision=risk_decision,
        )
