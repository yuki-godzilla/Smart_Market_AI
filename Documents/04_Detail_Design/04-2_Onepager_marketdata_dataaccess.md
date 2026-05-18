# 04-2_Onepager_Marketdata_DataAccess

#### [BACK TO DETAIL DESIGN README](./04_Detail_Design_README.md)

## 0) Current Sync Status

この文書は **2026-05-18 時点の実装に同期済み**です。
現在の MarketData は `mock` / `csv` を通常利用し、`yahoo` は `yfinance` backed の明示 opt-in live adapter 経路を持ちます。
`polygon` は provider metadata / adapter boundary のみで、本体実装は未完了です。

| 項目 | 状態 |
|---|---|
| `DataAccess` mock provider | implemented |
| CSV provider | implemented |
| provider registry | implemented |
| live provider adapter foundation | implemented |
| Yahoo provider file | implemented opt-in adapter |
| Polygon provider file | not implemented |
| external provider default enable | disabled |
| async external API retry/circuit breaker | not implemented |
| cache backend implementation | config only / not implemented as storage layer |

## 1) Purpose & Scope

市場データ取得を統一I/Fにまとめ、FeatureBuilder / Risk / Portfolio / Screening / Forecast / Scoring が同じデータ契約で動けるようにします。
現在は deterministic local-first を優先し、通常テストでは外部ネットワークに依存しません。

## 2) Public Interfaces

実装上の主要I/Fは以下です。

```python
class MarketDataProviderAdapter(Protocol):
    async def fetch_ohlcv(self, symbols, start, end, interval="1d") -> list[Bar]: ...
    async def fetch_quotes(self, symbols, at=None) -> list[Quote]: ...
    async def get_fx_rates(self, pairs, at=None, method="spot") -> list[FxRate]: ...
    async def fetch_fundamentals(self, symbols, as_of) -> list[FundamentalSnapshot]: ...
    def healthcheck(self) -> dict[str, str]: ...
```

具象実装:

- `backend/marketdata/data_access.py::DataAccess`
- `backend/marketdata/provider_factory.py::create_market_data_provider_adapter`
- `backend/marketdata/provider_registry.py`
- `backend/marketdata/live_provider_adapters.py`

## 3) Data Contracts

`backend/core/data_contracts.py` が正です。

- `Symbol`: `raw`, `exchange`, `code`, `currency`
- `Bar`: `symbol`, `ts`, `open`, `high`, `low`, `close`, `volume`, `interval`, `provider`
- `Quote`: `symbol`, `bid`, `ask`, `last`, `ts`
- `FxRate`: current support is `USDJPY`
- `FundamentalSnapshot`: `dividend_yield`, `market_cap_jpy`
- `DailySnapshot`: downstream feature row
- `FeatureSnapshot`: feature snapshot with provider and data quality summaries

## 4) Algorithms & Rules

### Provider selection

- default: `mock`
- `csv`: `config/csv_example.yaml` などで指定
- `yahoo`: `allow_external_providers: true` または Streamlit provider selector での明示選択が必要
- `polygon`: metadata のみ。adapter 本体は未実装

補足: `provider_registry.SUPPORTED_PROVIDERS` は `DataAccess` が直接扱う deterministic provider (`mock`, `csv`) の一覧です。
`yahoo` の実装有無は `live_provider_adapters.py` と provider factory の opt-in 経路で確認します。

### CSV assumptions

CSV provider は `csv_data_dir` 配下のファイルを読む想定です。
現在の用途は、外部APIなしでシナリオを増やし、UI / scoring / forecast の挙動を安定確認することです。

### FX

- base currency is JPY.
- supported pair is currently `USDJPY`.
- Portfolio valuation uses JPY as base and converts USD positions through `USDJPY`.

### Fundamentals

`dividend_yield` and `market_cap_jpy` are used by FeatureBuilder / Screening / Risk. Missing fundamentals are allowed but reflected in data quality warnings.

## 5) Error Handling

- unsupported provider -> `DataSourceError`
- unsupported FX pair / method -> `DataSourceError`
- invalid CSV shape / missing columns -> `DataSourceError`
- unknown config keys -> Pydantic validation error through `Settings`

API layer maps domain errors via `AppError` handlers when surfaced through endpoints.

## 6) Config Knobs

Current config model:

```yaml
dataaccess:
  provider: mock        # mock | csv | yahoo | polygon
  csv_data_dir: data/marketdata
  allow_external_providers: false
  cache:
    backend: memory
    ttl_intraday_sec: 60
    ttl_daily_sec: 86400
  timeouts_ms:
    connect: 1000
    read: 5000
```

Note: cache fields are configuration contracts; full cache storage behavior is not yet a separate implemented layer.

## 7) Test Plan

Existing related tests:

- `tests/test_marketdata_data_access.py`
- `tests/test_marketdata_provider_adapters.py`
- `tests/test_marketdata_live_provider_adapters.py`
- `tests/test_marketdata_provider_factory.py`
- `tests/test_marketdata_provider_registry.py`
- `tests/test_marketdata_feature_builder.py`

Recommended checks:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests/test_marketdata_data_access.py tests/test_marketdata_feature_builder.py
```

## 8) Out of Scope / Deferred

- paid provider production integration
- persistent cache layer
- full market calendar service
- intraday strategy execution support
- data lake / backfill orchestration

## 9) Next Implementation Target

MarketData の次の改善は、Research RAG より前にやるなら以下が自然です。

1. live provider smoke を通常CIから分離したまま整備する。
2. provider fundamentals 由来の symbol metadata refresh command を設計する。
3. FeatureSnapshot の品質サマリを UI / report でさらに読みやすく表示する。
