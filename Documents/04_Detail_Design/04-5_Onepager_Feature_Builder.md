# 04-5\_Onepager\_Feature\_Builder

#### [BACK TO README](../../README.md)

## 1) Purpose & Scope

* **Purpose**: Market Data(DataAccess) から取得した生データを、Risk/Portfolio/Forecast が直接利用できる**派生特徴量**へ変換する。
* **Scope**: 集計（OHLCV→日次/週次）、指標計算（ADV、実現ボラ、リターン、配当利回り、為替換算済み時価総額等）、欠損ハンドリング、スナップショット生成。
* **Out of Scope**: 学習用の重い特徴量エンジニアリング（AutoML、複雑なテクニカルの全網羅）。

### 1.1 前提（01の要件反映）

* 対象は JP+US の高配当銘柄ユニバース。ベース通貨は **JPY**。
* 粒度は 1d を主。検証用途で 1m/5m も最小限サポート。

## 2) Public Interfaces (Python想定)

```python
class FeatureBuilder:
    def build_daily_snapshot(self, symbols: list[str], as_of: date) -> list[DailySnapshot]:
        """Risk/Portfolioの即時判定に必要な指標を一括算出"""

    def compute_adv(self, symbol: str, as_of: date, window: int = 20) -> Decimal:
        ...

    def compute_vol(self, symbol: str, as_of: date, window: int = 20, method: Literal['close2close','parkison']='close2close') -> Decimal:
        ...

    def get_dividend_yield(self, symbol: str, as_of: date) -> Decimal | None:
        ...

    def rolling_returns(self, symbol: str, start: date, end: date, window: int = 20) -> list[ReturnPoint]:
        ...
```

* 例外: `DataUnavailableError`, `SchemaValidationError`, `ComputationError`, `TimeoutError`
* 非機能I/F: `warmup_cache(symbols)`, `healthcheck()`

## 3) Data Contracts (Pydantic)

```python
class DailySnapshot(BaseModel):
    symbol: str
    as_of: date
    last: Decimal | None
    close_1d: Decimal | None
    adv_20d: Decimal | None
    vol_20d: Decimal | None
    dividend_yield: Decimal | None
    market_cap_jpy: Decimal | None
    missing: dict[str, bool]            # 指標ごとの欠損フラグ

class ReturnPoint(BaseModel):
    ts: date
    ret: Decimal
```

## 4) Algorithms & Rules

* **基礎集計**:

  * `ADV(window)`：`sum(volume[i])/window`（JPY換算は `close[i]*volume[i]` を FXで換算後に平均）
  * `Vol(window)`：`stdev(log(close_t/close_{t-1})) * sqrt(252)`（`close2close`）。Parkinson法は `sqrt(1/(4 ln2) * mean((ln(high/low))^2))`。
  * `DividendYield`：`trailing_12m_dividends / price`。T12Mが無い場合は最新配当×頻度で近似（要データ源）
  * `MarketCapJPY`：`shares_outstanding * last_price * FX(USDJPY)`
* **欠損/営業日**:

  * JP/US の取引カレンダで**営業日**を定義。クローズ価格が無い日は`NA`（埋めない）。
  * `ADV/Vol`は**実データ日数で割る**（欠損が多い場合、`missing.adv_20d=True` でフラグ）
* **為替/TZ**:

  * すべて UTC に正規化。JPY換算は DataAccess の `get_fx_rates(["USDJPY"])`。

## 5) Caching & Performance（03のSLO準拠）

* キー：`symbol + as_of + feature_set`。
* TTL：`daily=24h`、途中日付は `stale-while-revalidate`。P95 レイテンシ `build_daily_snapshot(50 symbols) < 500ms`（キャッシュヒット時 < 80ms）。

## 6) Observability

* ログ：`corr_id, symbol_count, latency_ms, cache_hit_ratio, missing_flags`
* メトリクス：`feature_compute_latency_ms_pXX`, `feature_missing_ratio{feature}`

## 7) Config Knobs（config.yml）

```yaml
feature_builder:
  adv_window: 20
  vol_window: 20
  vol_method: close2close
  calendar:
    jp: JPX
    us: NYSE
  cache:
    backend: redis|memory
    ttl_daily_sec: 86400
```

## 8) Test Plan

* **Unit**：ADV/Vol/Returns の計算検証、欠損時の分母調整、JPY換算の正しさ
* **Goldenテスト**：既知データセットに対する期待値比較
* **Integration**：DataAccess モック→FeatureBuilder→Risk の一連フロー

## 9) 未決事項（TBD）

* 配当データ源（Yahoo/CSV/外部API）と T12M 算出方法
* US銘柄の `shares_outstanding` 取得ソース
* Parkinson 法の採用有無（必要なら安定化ガード）
