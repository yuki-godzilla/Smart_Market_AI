# 04-6\_Onepager\_Portfolio

#### [BACK TO README](../../README.md)

## 1) Purpose & Scope

* **Purpose**: 投資家のポートフォリオ全体を管理し、制約（リスク/配当/集中度）を満たすリバランス提案や発注候補を生成する。
* **Scope**: 制約定義・ソルバ設定・数値安定性ガード、ポートフォリオ状態のスナップショット生成、リバランス案計算、リスク・実行サービスとのI/F。
* **Out of Scope**: 高度な最適化（CVaR, ESGスコア統合等）、税制や手数料計算の詳細。

### 1.1 前提（01の要件反映）

* 高配当銘柄（JP+US）を対象。ベース通貨は **JPY**。
* 分析粒度は 1d が中心。
* 投資家は個人想定、シンプルな制約セットから開始。

## 2) Public Interfaces (Python想定)

```python
class PortfolioService:
    def snapshot(self, account_id: str, as_of: date) -> PortfolioSnapshot:
        """保有状況と評価額のスナップショットを返す"""

    def rebalance(self, target_constraints: ConstraintSet, as_of: date) -> RebalanceProposal:
        """制約を満たすようにリバランス案を生成"""

    def evaluate(self, proposal: RebalanceProposal, as_of: date) -> EvaluationResult:
        """提案が制約を満たしているか検証"""
```

* 例外: `ConstraintViolationError`, `SolverError`, `DataUnavailableError`
* 非機能I/F: `healthcheck()`, `metrics()`, `reload_constraints()`

## 3) Data Contracts (Pydantic)

```python
class Position(BaseModel):
    symbol: str
    qty: Decimal
    avg_price: Decimal
    currency: Literal['JPY','USD']

class PortfolioSnapshot(BaseModel):
    account_id: str
    as_of: date
    positions: list[Position]
    total_value_jpy: Decimal
    dividend_yield: Decimal | None

class ConstraintSet(BaseModel):
    max_concentration: Decimal
    min_dividend_yield: Decimal
    target_volatility: Decimal | None
    max_positions: int | None

class RebalanceProposal(BaseModel):
    as_of: date
    trades: list[ProposedOrder]
    expected_yield: Decimal | None
    expected_vol: Decimal | None

class EvaluationResult(BaseModel):
    status: Literal['SATISFIED','VIOLATED']
    violations: list[str]
```

## 4) Algorithms & Rules

* **Snapshot**:

  * DataAccess/FeatureBuilder の価格・配当・FXを用いてJPY換算。
  * `dividend_yield` = Σ(銘柄配当額) / `total_value_jpy`。
* **Constraints**（初期セット）:

  * `max_concentration`: 1銘柄比率 <= 25%
  * `min_dividend_yield`: >= 3%
  * `target_volatility`: <= 0.6（オプション、vol\_20d換算）
  * `max_positions`: 20（超過した場合は縮小提案）
* **Rebalance**:

  * ソルバ: 線形計画法ベース（例: pulp/ortools）。
  * 目的関数: `maximize(dividend_yield - λ * volatility)`（λ=調整パラ）。
  * 数値安定性: Decimal使用、係数は正規化。小数点誤差は閾値以下なら許容。
* **Evaluate**:

  * 提案後に再度制約計算。違反があれば `VIOLATED`。

## 5) Observability

* ログ: `corr_id, account_id, constraint_id, value, threshold, status`
* メトリクス: `rebalance_runtime_ms`, `constraint_violation_total`, `proposal_yield_avg`
* トレース: DataAccess/FeatureBuilder 呼び出し span 化

## 6) Config Knobs（config.yml）

```yaml
portfolio:
  constraints:
    max_concentration: 0.25
    min_dividend_yield: 0.03
    target_volatility: 0.6
    max_positions: 20
  solver:
    backend: pulp
    tolerance: 1e-6
```

## 7) Test Plan

* **Unit**: JPY換算、集中度/利回り計算、制約違反検出
* **Integration**: DataAccess/FeatureBuilder 経由で snapshot→rebalance→evaluate の一連フロー
* **Property-based**: ランダムポートフォリオ生成で不変条件（Σweights=1 等）検証
* **E2E**: サンプル口座でリバランス提案→Execution(ドライラン) まで

## 8) 未決事項（TBD）

* ソルバの選定（pulp, ortools, commercial?）
* リバランスの目的関数調整（単純最大利回り vs リスク調整後）
* 取引コスト/税制の扱い
* 制約セットのユーザー編集UI
