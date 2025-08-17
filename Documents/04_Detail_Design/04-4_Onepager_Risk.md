# 04-4\_Onepager\_Risk

#### [BACK TO README](../../README.md)

## 1) Purpose & Scope

* **Purpose**: 取引前チェック（pre-trade）とポートフォリオ制約検証（position-level / basket-level）を行い、**安全に執行可能な注文だけを通す**。
* **Scope**: ルール評価エンジン、しきい値管理、例外（override）フロー、観測可能性、コンフィグ駆動。JP/USの**現物株**を対象。
* **Out of Scope**: オプション/先物のグリークス、VaR/ES等の高度なリスク計測（将来拡張）。

### 1.1 前提（01の要件反映）

* 投資対象は**高配当銘柄**で日本株に限定せず（JP+US）。
* ベース通貨は **JPY**。USD建て評価は DataAccess の FX（USDJPY）で換算。
* 日足（1d）中心、検証用途で1m/5mも参照可能。

## 2) Public Interfaces (Python想定)

```python
class RiskService:
    def pre_trade_check(self, basket: list[ProposedOrder], as_of: datetime, account_id: str) -> RiskDecision:
        """バスケットのリスク承認/棄却/要承認を返す"""

    def explain(self, decision_id: str) -> RiskExplanation:
        """どのルールで引っ掛かったか、しきい値と実測値を返す"""

    def list_rules(self) -> list[RiskRuleSummary]:
        """有効なルールセットとバージョン一覧を返す"""

    def override_request(self, decision_id: str, reason: str, approver: str) -> OverrideTicket:
        """例外承認ワークフローの起票"""
```

* 例外: `DataUnavailableError`, `ConfigError`, `ComputationError`, `TimeoutError`
* 非機能I/F: `healthcheck()`, `metrics()`, `reload_config()`

## 3) Data Contracts (Pydantic)

```python
class ProposedOrder(BaseModel):
    symbol: str          # 7203.T / AAPL
    side: Literal['BUY','SELL']
    qty: Decimal
    price_hint: Decimal | None = None   # 指値評価用
    currency: Literal['JPY','USD']

class Snapshot(BaseModel):
    symbol: str
    last: Decimal | None
    close_1d: Decimal | None
    dividend_yield: Decimal | None      # 年率（例: 0.045 = 4.5%）
    market_cap: Decimal | None          # JPY換算
    vol_20d: Decimal | None             # 実現ボラ
    ts: datetime

class RiskDecision(BaseModel):
    decision_id: str
    status: Literal['ALLOW','BLOCK','REVIEW']
    breaches: list[str]
    evaluated_rules_version: str

class RiskRuleSummary(BaseModel):
    rule_id: str
    name: str
    severity: Literal['LOW','MEDIUM','HIGH']

class RiskExplanation(BaseModel):
    decision_id: str
    details: list[dict]  # {rule_id, name, threshold, actual, comparator, severity}

class OverrideTicket(BaseModel):
    ticket_id: str
    decision_id: str
    status: Literal['PENDING','APPROVED','REJECTED']
    approver: str
```

## 4) Algorithms & Rules（初期セット）

* **A1: 立会時間チェック（市場時間外）** → `REVIEW`（許容するが注意） / 強制ブロックはブローカ依存
* **A2: 価格検証** `type='LMT'` かつ `limit_price>0`、成行は許容
* **R1: 1銘柄上限金額** `notional_per_symbol <= cfg.max_notional_per_symbol`
* **R2: バスケット総額上限** `sum(notional) <= cfg.max_notional_per_basket`
* **R3: 集中度** `max(notional_by_symbol)/sum(notional) <= cfg.max_concentration`
* **R4: 流動性フィルタ** `adv_20d >= cfg.min_adv`（乏しい場合は`REVIEW`）
* **R5: 配当利回りフィルタ** `dividend_yield >= cfg.min_dividend_yield`（不足で`REVIEW`）
* **R6: ボラ制限** `vol_20d <= cfg.max_volatility`（超過で`REVIEW`/`BLOCK`切替可）
* **R7: 為替スプレッド警告** `fx_spread_bps <= cfg.max_fx_spread_bps`（超過で`REVIEW`）
* **R8: ティッカー停止/規制**（取引停止シグナルは`BLOCK`）

> すべて **JPY換算**（DataAccessのFXレートで評価）。ADV/配当/ボラはDataAccess/FeatureBuilderが提供。

## 5) Decision Table（例）

| 条件                        | 判定     |
| ------------------------- | ------ |
| いずれかのBLOCKルール違反（停止/規制など）  | BLOCK  |
| BLOCKは無いが、REVIEW対象に1つ以上該当 | REVIEW |
| 上記以外                      | ALLOW  |

## 6) Exception Flow（Override）

* `REVIEW`/`BLOCK` の決定は `override_request()` で起票→`approver` が承認すると `ALLOW` に昇格。
* 監査ログに**元の判定/しきい値/実測値/承認者/コメント**を保存（保持期間=90日）。

## 7) Observability

* ログ: `corr_id, decision_id, rule_id, actual, threshold, status`
* メトリクス: `risk_decisions_total{status}`, `rule_breaches_total{rule_id}`, `override_rate`
* トレース: DataAccess呼び出しとルール評価をSpan化

## 8) Config Knobs（config.yml）

```yaml
risk:
  version: "v1"
  timeouts_ms:
    quotes: 2000
    fundamentals: 4000
  thresholds:
    max_notional_per_symbol: 3_000_000      # JPY
    max_notional_per_basket: 10_000_000     # JPY
    max_concentration: 0.25                 # 25%
    min_adv: 50_000_000                     # 5,000万円/日 相当
    min_dividend_yield: 0.03                # 3%
    max_volatility: 0.6                     # 60%（20d実ボラ）
    max_fx_spread_bps: 20
  review_policies:
    allow_after_hours: true
    block_trading_halts: true
```

## 9) Data Access依存

* `quotes`: `fetch_quotes(symbols)` → last/close\_1d
* `fundamentals`: 配当利回り/時価総額（必要に応じ外部API or CSV）
* `analytics`: ADV/ボラ（FeatureBuilderで計算）
* `fx`: `get_fx_rates(["USDJPY"])`

## 10) Test Plan

* **Unit**: JPY換算、閾値比較、集中度/総額計算、ハンドリング（REVIEW/BLOCK/ALLOW）
* **Integration**: DataAccessモックでデータ欠損→フォールバック、FX遅延、ADV不足
* **Property-based**: 乱数バスケットで不変条件（合計/集中度）検証
* **E2E**: Executionとの結合で pre\_trade→place\_orders のブロック/許可シナリオ

## 11) 未決事項（TBD）

* 配当利回り/ADV/ボラの取得元の確定（Yahoo/Polygon/CSV）
* `REVIEW` と `BLOCK` の線引きポリシー微調整
* 例外承認のUI（誰が承認／SLA）
* 監査ログの保持期間（セキュリティ方針に合わせる）
