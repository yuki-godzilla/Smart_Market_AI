# 04-4_Onepager_Risk

#### [BACK TO DETAIL DESIGN README](./04_Detail_Design_README.md)

## 0) Current Sync Status

この文書は **2026-05-17 時点の実装に同期済み**です。
Risk MVP は `backend/risk/service.py` と `/risk/pre-trade-check` で実装済みです。

## 1) Purpose & Scope

売買案 `TradeIntent` の事前チェックを行い、`ALLOW` / `REVIEW` / `BLOCK` を返します。
SMAIは broker へ発注しないため、Risk は「実注文前の安全ゲート」ではなく、現在は **投資判断補助・リバランス案確認のためのガードレール** として使います。

## 2) Public Interfaces

```python
class RiskService:
    async def pre_trade_check(
        self,
        basket: list[TradeIntent],
        as_of: date,
        account_id: str,
    ) -> RiskDecision: ...
```

API:

```text
POST /risk/pre-trade-check
```

Related workflow:

```text
POST /portfolio/rebalance-check
  -> PortfolioRiskWorkflow.propose_and_check
  -> RiskService.pre_trade_check when proposed trades exist
```

## 3) Data Contracts

```python
class RiskDecision(StrictBaseModel):
    decision_id: str
    status: Literal["ALLOW", "BLOCK", "REVIEW"]
    breaches: list[str]
    evaluated_rules_version: str = "risk-mvp-v1"
```

Input:

- `TradeIntent`: `symbol`, `side`, `qty`, `price_hint`, `currency`
- `DailySnapshot`: built by `FeatureBuilder`

## 4) Algorithms & Rules

Implemented rule codes:

| Rule | Condition | Status impact |
|---|---|---|
| R1 | `notional > max_notional_per_symbol` | BLOCK |
| R2 | `basket_total > max_notional_per_basket` | BLOCK |
| R3 | `max_concentration > max_concentration` | BLOCK |
| R4 | `adv_20d < min_adv` or missing | REVIEW |
| R5 | `dividend_yield < min_dividend_yield` or missing | REVIEW |
| R6 | `vol_20d > max_volatility` | REVIEW |

Status resolution:

- Any R1 / R2 / R3 -> `BLOCK`
- Other breaches only -> `REVIEW`
- No breaches -> `ALLOW`

`decision_id` is deterministic hash of account, date, and basket.

## 5) Error Handling

- Empty basket -> `ComputationError`
- Missing `price_hint` and missing snapshot price -> `ComputationError`
- FeatureBuilder / DataAccess failures propagate as domain errors

## 6) Config Knobs

```yaml
risk:
  thresholds:
    max_notional_per_symbol: 3000000
    max_notional_per_basket: 10000000
    max_concentration: 0.25
    min_adv: 50000000
    min_dividend_yield: 0.03
    max_volatility: 0.6
```

## 7) Test Plan

Existing related tests:

- `tests/test_risk_service.py`
- `tests/test_risk_api.py`
- `tests/test_portfolio_workflow.py`
- `tests/test_portfolio_api.py`

Recommended targeted check:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests/test_risk_service.py tests/test_risk_api.py
```

## 8) Out of Scope / Deferred

- user-specific risk tolerance profile
- account buying power / tax lots
- real broker compliance checks
- portfolio-level VaR / stress test
- automatic order blocking because no broker execution exists

## 9) Next Implementation Target

次にやるなら、Risk breach を UI / report で初心者向けに説明する mapping を増やすのが効果的です。
例: `R3:max_concentration` -> 「1銘柄に偏りすぎています」。
