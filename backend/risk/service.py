from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Literal

from pydantic import Field

from backend.core.config import RiskConfig
from backend.core.data_contracts import DailySnapshot, StrictBaseModel, TradeIntent
from backend.core.errors import ComputationError
from backend.marketdata.feature_builder import FeatureBuilder

RiskDecisionStatus = Literal["ALLOW", "BLOCK", "REVIEW"]


class RiskDecision(StrictBaseModel):
    """Pre-trade decision emitted by the Risk MVP."""

    decision_id: str = Field(min_length=1)
    status: RiskDecisionStatus
    breaches: list[str] = Field(default_factory=list)
    evaluated_rules_version: str = "risk-mvp-v1"


class RiskService:
    """Minimal pre-trade risk engine based on snapshots and configured thresholds."""

    def __init__(
        self,
        feature_builder: FeatureBuilder,
        cfg: RiskConfig | None = None,
    ) -> None:
        """Create a risk service backed by a feature builder."""

        self.feature_builder = feature_builder
        self.cfg = cfg or RiskConfig()

    async def pre_trade_check(
        self,
        basket: list[TradeIntent],
        as_of: date,
        account_id: str,
    ) -> RiskDecision:
        """Evaluate a trade basket and return an ALLOW, REVIEW, or BLOCK decision."""

        if not basket:
            raise ComputationError("Basket must contain at least one trade intent")

        symbols = [intent.symbol for intent in basket]
        snapshots = await self.feature_builder.build_daily_snapshot(symbols, as_of)
        snapshots_by_symbol = {snapshot.symbol: snapshot for snapshot in snapshots}

        breaches: list[str] = []
        notionals_by_symbol: dict[str, Decimal] = {}
        basket_total = Decimal("0")

        for intent in basket:
            snapshot = snapshots_by_symbol[intent.symbol]
            notional = _resolve_notional(intent, snapshot)
            notionals_by_symbol[intent.symbol] = notionals_by_symbol.get(
                intent.symbol, Decimal("0")
            )
            notionals_by_symbol[intent.symbol] += notional
            basket_total += notional

            if notional > Decimal(self.cfg.thresholds.max_notional_per_symbol):
                breaches.append(f"R1:max_notional_per_symbol:{intent.symbol}")

            if self.cfg.thresholds.min_adv > 0:
                if snapshot.adv_20d is None or snapshot.adv_20d < Decimal(
                    self.cfg.thresholds.min_adv
                ):
                    breaches.append(f"R4:min_adv:{intent.symbol}")

            if self.cfg.thresholds.min_dividend_yield > 0:
                if snapshot.dividend_yield is None or snapshot.dividend_yield < Decimal(
                    str(self.cfg.thresholds.min_dividend_yield)
                ):
                    breaches.append(f"R5:min_dividend_yield:{intent.symbol}")

            if self.cfg.thresholds.max_volatility > 0:
                if snapshot.vol_20d is not None and snapshot.vol_20d > Decimal(
                    str(self.cfg.thresholds.max_volatility)
                ):
                    breaches.append(f"R6:max_volatility:{intent.symbol}")

        if basket_total > Decimal(self.cfg.thresholds.max_notional_per_basket):
            breaches.append("R2:max_notional_per_basket")

        if basket_total > 0 and notionals_by_symbol:
            max_concentration = max(notionals_by_symbol.values()) / basket_total
            if max_concentration > Decimal(str(self.cfg.thresholds.max_concentration)):
                breaches.append("R3:max_concentration")

        status = _resolve_status(breaches)
        return RiskDecision(
            decision_id=_decision_id(account_id, basket, as_of),
            status=status,
            breaches=breaches,
        )


def _resolve_notional(intent: TradeIntent, snapshot: DailySnapshot) -> Decimal:
    """Resolve a notional value from the order hint or the latest snapshot price."""

    price = intent.price_hint if intent.price_hint is not None else snapshot.last
    if price is None:
        raise ComputationError(
            "Trade intent requires price_hint or snapshot.last",
            details={"symbol": intent.symbol},
        )
    return intent.qty * price


def _resolve_status(breaches: list[str]) -> RiskDecisionStatus:
    """Map rule breaches to a single overall decision status."""

    if any(breach.startswith(("R1:", "R2:", "R3:")) for breach in breaches):
        return "BLOCK"
    if breaches:
        return "REVIEW"
    return "ALLOW"


def _decision_id(account_id: str, basket: list[TradeIntent], as_of: date) -> str:
    """Build a deterministic identifier for a pre-trade decision."""

    payload = "|".join(
        [
            account_id,
            as_of.isoformat(),
            *[
                f"{intent.symbol}:{intent.side}:{intent.qty}:{intent.price_hint}:{intent.currency}"
                for intent in basket
            ],
        ]
    )
    return sha256(payload.encode("utf-8")).hexdigest()[:16]
