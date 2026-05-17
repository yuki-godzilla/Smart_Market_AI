# 04-5_Onepager_Feature_Builder

#### [BACK TO DETAIL DESIGN README](./04_Detail_Design_README.md)

## 0) Current Sync Status

この文書は **2026-05-17 時点の実装に同期済み**です。
FeatureBuilder は `backend/marketdata/feature_builder.py` に実装済みで、Risk / Portfolio / Screening / Investment Score の共通入力です。

## 1) Purpose & Scope

MarketData provider から取得した quotes / OHLCV / fundamentals を、下流サービスが使える `DailySnapshot` / `FeatureSnapshot` に変換します。
現在は軽量な Feature Store Lite として、永続DBではなくリクエスト時に deterministic に構築します。

## 2) Public Interfaces

```python
class FeatureBuilder:
    async def build_daily_snapshot(self, symbols: list[str], as_of: date) -> list[DailySnapshot]: ...
    async def build_feature_snapshot(self, symbols: list[str], as_of: date) -> FeatureSnapshot: ...
    async def compute_adv(self, symbol: str, as_of: date, window: int = 20) -> Decimal: ...
    async def compute_vol(self, symbol: str, as_of: date, window: int = 20, method: str = "close2close") -> Decimal: ...
```

## 3) Data Contracts

Output row: `DailySnapshot`

- price: `last`, `close_1d`
- returns: `return_1d`, `momentum_5d`
- liquidity: `adv_20d`
- risk: `vol_20d`, `drawdown_20d`
- fundamentals: `dividend_yield`, `market_cap_jpy`
- quality: `data_completeness`, `missing`, `data_quality`, `data_quality_reasons`

Grouped output: `FeatureSnapshot`

- `as_of`
- `provider`
- `feature_version`
- `rows`
- `missing_summary`
- `quality_summary`

## 4) Algorithms & Rules

Implemented features:

| Feature | Rule |
|---|---|
| `return_1d` | latest close / previous close - 1 |
| `momentum_5d` | latest close / close 5 bars ago - 1 |
| `adv_20d` | average close * volume over configured window |
| `vol_20d` | annualized volatility, `close2close` default, `parkinson` optional |
| `drawdown_20d` | `(peak high - latest close) / peak high` |
| `data_completeness` | available bars / expected count, capped at 1 |

Data quality:

- `BLOCK`: missing blocking features such as `return_1d` or `drawdown_20d`
- `WARN`: non-blocking missing values or completeness < 0.8
- `OK`: no major missing signals

## 5) Error Handling

- No bars for ADV -> `DataSourceError`
- Fewer than 2 bars for volatility -> `DataSourceError`
- Unsupported volatility method -> `DataSourceError`

Some score inputs tolerate missing values by using neutral or low scores; calculation errors should still surface during feature building.

## 6) Config Knobs

```yaml
feature_builder:
  adv_window: 20
  vol_window: 20
  vol_method: close2close   # close2close | parkinson
```

## 7) Test Plan

Existing related tests:

- `tests/test_marketdata_feature_builder.py`
- `tests/test_screening_service.py`
- `tests/test_scoring_service.py`
- `tests/test_risk_service.py`

Recommended targeted check:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests/test_marketdata_feature_builder.py tests/test_screening_service.py tests/test_scoring_service.py
```

## 8) Out of Scope / Deferred

- persistent feature store database
- scheduled backfill
- advanced technical indicators beyond current MVP
- feature version migration framework
- intraday features

## 9) Next Implementation Target

次の改善候補:

1. `FeatureSnapshot` を Decision Report / Research RAG と結合しやすい report context にする。
2. UIで data quality をより自然な日本語に変換する。
3. CSV scenario を増やしてランキングの比較体験を安定させる。
