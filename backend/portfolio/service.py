from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field

from backend.core.config import PortfolioConfig
from backend.core.data_contracts import Currency, Position, StrictBaseModel, TradeIntent
from backend.core.errors import ComputationError
from backend.marketdata.feature_builder import FeatureBuilder

_JPY_RATE = Decimal("1")
_QTY_STEP = Decimal("0.0001")


class ValuedPosition(StrictBaseModel):
    """Position enriched with price, FX, and JPY value."""

    symbol: str = Field(min_length=1)
    qty: Decimal = Field(ge=0)
    currency: Currency
    last: Decimal = Field(gt=0)
    fx_rate_jpy: Decimal = Field(gt=0)
    value_jpy: Decimal = Field(ge=0)


class PortfolioSnapshot(StrictBaseModel):
    """Point-in-time portfolio valuation for the MVP."""

    account_id: str = Field(min_length=1)
    as_of: date
    positions: list[ValuedPosition] = Field(default_factory=list)
    cash_jpy: Decimal = Field(default=Decimal("0"), ge=0)
    total_value_jpy: Decimal = Field(ge=0)


class TargetAllocation(StrictBaseModel):
    """Desired symbol weight used by the no-solver rebalance MVP."""

    symbol: str = Field(min_length=1)
    currency: Currency
    target_weight: Decimal = Field(ge=0, le=1)


RebalanceSolverBackend = Literal["none"]


class RebalanceProposal(StrictBaseModel):
    """Trade intents generated from current value and target weights."""

    account_id: str = Field(min_length=1)
    as_of: date
    current: PortfolioSnapshot
    targets: list[TargetAllocation] = Field(default_factory=list)
    trades: list[TradeIntent] = Field(default_factory=list)
    solver_backend: RebalanceSolverBackend = "none"


class PortfolioService:
    """Minimal deterministic portfolio service without an optimization solver."""

    def __init__(
        self,
        feature_builder: FeatureBuilder,
        cfg: PortfolioConfig | None = None,
    ) -> None:
        """Create a portfolio service backed by a feature builder."""

        self.feature_builder = feature_builder
        self.cfg = cfg or PortfolioConfig()
        if self.cfg.solver.backend != "none":
            raise ComputationError(
                "Only the none portfolio solver is supported in the Portfolio MVP",
                details={"backend": self.cfg.solver.backend},
            )

    async def snapshot(
        self,
        account_id: str,
        positions: list[Position],
        as_of: date,
        cash_jpy: Decimal = Decimal("0"),
    ) -> PortfolioSnapshot:
        """Value current positions in JPY using daily snapshots and configured FX."""

        valued_positions: list[ValuedPosition] = []
        if positions:
            symbols = [position.symbol for position in positions]
            snapshots = await self.feature_builder.build_daily_snapshot(symbols, as_of)
            snapshots_by_symbol = {snapshot.symbol: snapshot for snapshot in snapshots}

            for position in positions:
                snapshot = snapshots_by_symbol[position.symbol]
                last = _require_last(position.symbol, snapshot.last)
                fx_rate = await self._fx_rate_jpy(position.currency)
                valued_positions.append(
                    ValuedPosition(
                        symbol=position.symbol,
                        qty=position.qty,
                        currency=position.currency,
                        last=last,
                        fx_rate_jpy=fx_rate,
                        value_jpy=position.qty * last * fx_rate,
                    )
                )

        total_value = cash_jpy + sum(
            (position.value_jpy for position in valued_positions),
            start=Decimal("0"),
        )
        return PortfolioSnapshot(
            account_id=account_id,
            as_of=as_of,
            positions=valued_positions,
            cash_jpy=cash_jpy,
            total_value_jpy=total_value,
        )

    async def rebalance(
        self,
        account_id: str,
        positions: list[Position],
        targets: list[TargetAllocation],
        as_of: date,
        cash_jpy: Decimal = Decimal("0"),
    ) -> RebalanceProposal:
        """Generate deterministic trade intents from target weights."""

        targets_by_symbol = _targets_by_symbol(targets)
        target_weight_sum = sum(
            (target.target_weight for target in targets_by_symbol.values()),
            start=Decimal("0"),
        )
        if target_weight_sum > Decimal("1"):
            raise ComputationError(
                "Target weights must not exceed 1",
                details={"target_weight_sum": str(target_weight_sum)},
            )

        current = await self.snapshot(account_id, positions, as_of, cash_jpy)
        symbols = sorted(
            {position.symbol for position in current.positions} | set(targets_by_symbol)
        )
        trades: list[TradeIntent] = []

        for symbol in symbols:
            target = targets_by_symbol.get(symbol)
            position_value = _current_value_for_symbol(current, symbol)
            target_value = (
                current.total_value_jpy * target.target_weight
                if target is not None
                else Decimal("0")
            )
            delta_value = target_value - position_value
            if abs(delta_value) <= _tolerance(self.cfg):
                continue

            currency = _currency_for_symbol(symbol, current, target)
            last = await self._last_price(symbol, currency, as_of)
            fx_rate = await self._fx_rate_jpy(currency)
            price_jpy = last * fx_rate
            if price_jpy <= 0:
                raise ComputationError(
                    "Positive JPY price is required for rebalance",
                    details={"symbol": symbol},
                )

            trades.append(
                TradeIntent(
                    symbol=symbol,
                    side="BUY" if delta_value > 0 else "SELL",
                    qty=(abs(delta_value) / price_jpy).quantize(_QTY_STEP),
                    price_hint=last,
                    currency=currency,
                )
            )

        return RebalanceProposal(
            account_id=account_id,
            as_of=as_of,
            current=current,
            targets=list(targets_by_symbol.values()),
            trades=trades,
            solver_backend="none",
        )

    async def _last_price(self, symbol: str, currency: Currency, as_of: date) -> Decimal:
        snapshots = await self.feature_builder.build_daily_snapshot([symbol], as_of)
        return _require_last(symbol, snapshots[0].last)

    async def _fx_rate_jpy(self, currency: Currency) -> Decimal:
        if currency == "JPY":
            return _JPY_RATE
        rates = await self.feature_builder.data_access.get_fx_rates(["USDJPY"])
        return rates[0].rate


def _targets_by_symbol(targets: list[TargetAllocation]) -> dict[str, TargetAllocation]:
    result: dict[str, TargetAllocation] = {}
    for target in targets:
        if target.symbol in result:
            raise ComputationError(
                "Duplicate target allocation symbol",
                details={"symbol": target.symbol},
            )
        result[target.symbol] = target
    return result


def _current_value_for_symbol(snapshot: PortfolioSnapshot, symbol: str) -> Decimal:
    return sum(
        (position.value_jpy for position in snapshot.positions if position.symbol == symbol),
        start=Decimal("0"),
    )


def _currency_for_symbol(
    symbol: str,
    snapshot: PortfolioSnapshot,
    target: TargetAllocation | None,
) -> Currency:
    if target is not None:
        return target.currency
    for position in snapshot.positions:
        if position.symbol == symbol:
            return position.currency
    raise ComputationError("Currency is required for rebalance", details={"symbol": symbol})


def _require_last(symbol: str, value: Decimal | None) -> Decimal:
    if value is None or value <= 0:
        raise ComputationError(
            "Snapshot last price is required for portfolio valuation",
            details={"symbol": symbol},
        )
    return value


def _tolerance(cfg: PortfolioConfig) -> Decimal:
    return Decimal(str(cfg.solver.tolerance))
