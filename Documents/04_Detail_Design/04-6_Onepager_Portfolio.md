# 04-6_Onepager_Portfolio

#### [BACK TO DETAIL DESIGN README](./04_Detail_Design_README.md)

## 0) Current Sync Status

この文書は **2026-05-17 時点の実装に同期済み**です。
Portfolio MVP は `backend/portfolio/service.py` と `backend/portfolio/workflow.py` に実装済みです。
現在の solver backend は **`none` のみ**で、`pulp` / `ortools` による最適化は未実装です。

## 1) Purpose & Scope

現在保有ポジションと目標配分から、JPY評価額・売買案・Risk判定を作ります。
目的は「自動最適化」ではなく、まず **透明で説明しやすいリバランス案** を作ることです。

## 2) Public Interfaces

```python
class PortfolioService:
    async def snapshot(
        self,
        account_id: str,
        positions: list[Position],
        as_of: date,
        cash_jpy: Decimal = Decimal("0"),
    ) -> PortfolioSnapshot: ...

    async def rebalance(
        self,
        account_id: str,
        positions: list[Position],
        targets: list[TargetAllocation],
        as_of: date,
        cash_jpy: Decimal = Decimal("0"),
    ) -> RebalanceProposal: ...

class PortfolioRiskWorkflow:
    async def propose_and_check(...) -> PortfolioRiskResult: ...
```

API:

```text
POST /portfolio/rebalance-check
```

UI:

- `ui/rebalance_app.py`
- Rebalance Cockpit in `ui/app.py`

## 3) Data Contracts

Implemented contracts:

- `ValuedPosition`
- `PortfolioSnapshot`
- `TargetAllocation`
- `RebalanceProposal`
- `PortfolioRiskResult`

Input contracts:

- `Position`
- `TradeIntent`

## 4) Algorithms & Rules

### Snapshot

1. Build daily snapshots for position symbols.
2. Resolve latest price.
3. Convert USD positions to JPY through `USDJPY`; JPY positions use rate `1`.
4. Calculate each `value_jpy` and total portfolio value.

### Rebalance

1. Validate duplicate targets.
2. Validate target weights sum does not exceed 1.
3. Build current snapshot.
4. For each current or target symbol, compute target value minus current value.
5. Ignore deltas within tolerance.
6. Convert delta value to `TradeIntent` with quantity quantized to `0.0001`.
7. Return proposal with `solver_backend="none"`.

### Portfolio-to-Risk

If proposal has trades, send them to `RiskService.pre_trade_check`.
If no trades are generated, `risk_decision` is `None`.

## 5) Error Handling

- Unsupported solver backend -> `ComputationError`
- Target weight sum > 1 -> `ComputationError`
- Duplicate target symbol -> `ComputationError`
- Missing or non-positive price -> `ComputationError`
- Unsupported FX pair / provider issue -> propagated from MarketData

## 6) Config Knobs

```yaml
portfolio:
  solver:
    backend: none       # current only supported value
    tolerance: 1.0e-6
```

Although the config type includes `pulp` / `ortools`, the service currently rejects anything other than `none`.

## 7) Test Plan

Existing related tests:

- `tests/test_portfolio_service.py`
- `tests/test_portfolio_workflow.py`
- `tests/test_portfolio_api.py`
- `tests/test_ui_rebalance_app.py`
- `tests/test_manual_workflow_examples.py`

Recommended targeted check:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests/test_portfolio_service.py tests/test_portfolio_workflow.py tests/test_portfolio_api.py tests/test_ui_rebalance_app.py
```

## 8) Out of Scope / Deferred

- optimizer-based allocation solver
- tax lots / realized gain optimization
- NISA枠最適化
- automatic execution
- real brokerage account import

## 9) Next Implementation Target

Portfolio の次の改善は、solver 追加よりも先に以下が良いです。

1. Rebalance Cockpit の入力例・説明文言をさらに初心者向けにする。
2. proposed trades の理由を report context として出せるようにする。
3. Risk breach の日本語説明を増やす。
