# 05_Implementation_Roadmap

#### [BACK TO README](../README.md)

## 1. 目的

この文書は、Smart Market AI の実装ロードマップをまとめます。

役割は次の 3 つです。

- 現在どこまで実装済みかを確認する
- 次に何を優先するかを明確にする
- 実装フェーズごとの完了条件を追跡する

API の起動方法、CSV 形式、UI の使い方、手動確認手順は [06_MVP_Operations_Guide.md](./06_MVP_Operations_Guide.md) に集約しています。

## 2. 現在地

Phase 1 から Phase 9 までは、現在の MVP として完了扱いです。

実装済みの主な範囲:

- Core contracts / config / errors
- deterministic な `mock` / `csv` MarketData provider
- Risk MVP
- Portfolio MVP
- Portfolio-to-Risk workflow
- FastAPI endpoint
  - `GET /health`
  - `POST /risk/pre-trade-check`
  - `POST /portfolio/rebalance-check`
- Swagger / OpenAPI metadata
- `SMAI_CONFIG_FILE` による YAML settings loading
- Streamlit rebalance-check UI
- file-backed rebalance scenarios
- JSON / CSV / Markdown / manifest / ZIP report export
- 外部 MarketData provider の opt-in gate と provider registry

未実装または今後の範囲:

- `polygon` などの追加 live provider adapter 本体
- screening score
- forecast engine
- multi-model forecasting
- investment score
- visualization cockpit
- decision report
- broker への live order 送信
- Execution workflow

## 3. 実装方針

- 既定経路は local / deterministic に保つ。
- 外部 API は明示 opt-in の場合だけ使う。
- CI と通常の local checks は外部 API に依存させない。
- まず軽量な baseline を作り、後から高度なモデルや optional adapter を追加する。
- ユーザーに見える機能では、最終結果だけでなく理由・内訳・制約を表示する。
- 実装状態が変わったら `PROJECT_CONTEXT.md` と関連ドキュメントを同期する。

## 4. 完了済みフェーズ

### Phase 1: Core Foundation

Status: MVP complete

目的: 後続機能が共有する基盤を作る。

完了済み:

- `backend/core/data_contracts.py`
- `backend/core/errors.py`
- `backend/core/config.py`
- Pydantic v2 の domain contracts
- domain-specific error
- YAML settings loading through `SMAI_CONFIG_FILE`

残り:

- `.env` や個別環境変数による設定上書き

### Phase 2: MarketData MVP

Status: MVP complete

目的: 外部 API なしで market data を扱える基盤を作る。

完了済み:

- `mock` provider
- `csv` provider
- `fetch_ohlcv`
- `fetch_quotes`
- `get_fx_rates`
- `compute_adv`
- `compute_vol`
- `build_daily_snapshot`
- local sample CSV

残り:

- live provider adapter
- 配当利回り、発行株式数、営業日 calendar などの正式データ連携

### Phase 3: Risk MVP

Status: MVP complete

目的: 取引前チェックの最小ルールエンジンを作る。

完了済み:

- `backend/risk/service.py`
- `POST /risk/pre-trade-check`
- `ALLOW` / `REVIEW` / `BLOCK`
- concentration、cash、dividend-yield missing などの MVP risk rule
- deterministic tests

### Phase 4: Portfolio MVP

Status: MVP complete

目的: portfolio valuation と no-solver rebalance proposal を作る。

完了済み:

- `backend/portfolio/service.py`
- JPY base valuation
- no-solver rebalance proposal
- generated `TradeIntent`
- Portfolio-to-Risk workflow の service-level 接続

残り:

- optimizer library を使った最適化
- より高度な constraint

### Phase 5: API and UI Integration

Status: MVP complete

目的: backend 機能を API / UI から確認できるようにする。

完了済み:

- FastAPI app wiring
- Swagger / OpenAPI metadata
- `POST /portfolio/rebalance-check`
- Streamlit rebalance-check UI
- sample selector
- target controls
- allocation comparison
- result download

### Phase 6: CSV Data And Scenario Expansion

Status: MVP complete

目的: local / deterministic な検証範囲を広げる。

完了済み:

- `data/marketdata` sample CSV
- `config/csv_example.yaml`
- `examples/rebalance_scenarios/`
- CSV provider smoke check
- deterministic scenarios

### Phase 7: Config And Scenario Management

Status: MVP complete

目的: Python code を編集せずに scenario を追加・切り替えられるようにする。

完了済み:

- file-backed rebalance scenario
- `SMAI_REBALANCE_SCENARIO_DIR`
- scenario `description`
- invalid scenario/config error handling
- UI sample selector integration

### Phase 8: Reporting MVP

Status: MVP complete

目的: 手動確認結果を保存・共有しやすくする。

完了済み:

- `RebalanceReportContext`
- JSON download
- CSV downloads
- Markdown report
- manifest
- ZIP export
- validated request JSON export

残り:

- PDF / Excel export
- broader reporting workflow

### Phase 9: External Data Provider Preparation

Status: MVP complete

目的: MVP の既定経路を network-dependent にせず、将来の live provider 実装口を作る。

完了済み:

- `dataaccess.allow_external_providers`
- provider registry
- `mock` / `csv` / `yahoo` / `polygon` capability metadata
- provider opt-in rejection
- live provider adapter metadata
- `MarketDataProviderAdapter` protocol
- provider adapter factory
- provider unavailable / timeout / rate limit / schema mismatch error mapping
- structured API response tests
- OpenAPI response metadata

残り:

- `yahoo` live adapter
- `polygon` live adapter
- live provider smoke check 手順

## 5. 次期ロードマップ

次期重点は **Multi-Model Investment Intelligence** です。

注文執行ではなく、外部データ取得、特徴量管理、銘柄スコアリング、複数モデル予測、可視化、判断補助レポートを優先します。
Execution / broker order 送信は重要な将来領域ですが、今回のロードマップでは優先度を下げます。

### UI 確認方針

Phase 10 以降で UI 上の体験に影響する機能は、バックエンド実装だけでは完了としません。
各フェーズの完了条件には、Streamlit UI または将来の UI 画面で、ユーザーが変更内容を確認できることを含めます。
特に外部 provider に関する機能では、可能であれば live provider の生きたデータで、provider、as-of、取得時刻、取得結果、失敗理由を確認できる状態を目標にします。
ただし、通常の自動テストと local checks は外部 API に依存させず、mock / csv / fixture による deterministic な検証を維持します。

### Phase 10: External Data Ingestion MVP

Status: started

目的: 外部 MarketData provider から実データを取得し、取得結果と provider 状態を Streamlit UI 上で確認できる最小経路を作る。

Scope:

- Done: live provider adapter metadata を `backend/marketdata/live_provider_adapters.py` に分離する
- Done: live provider adapter interface を `backend/marketdata/provider_adapters.py` の `MarketDataProviderAdapter` protocol として定義する
- Done: provider adapter factory を `backend/marketdata/provider_factory.py` に追加する
- Done: Streamlit UI に deterministic provider で動く Market Data preview tab を追加する
- Done: `yahoo` provider を opt-in live adapter として `backend/marketdata/providers/yahoo.py` に追加する
- Done: `yahoo` の取得結果を `Bar` / `Quote` / `FxRate` へ正規化する
- Done: live provider の取得結果を Streamlit UI の Market Data tab で確認できる経路を追加する
- UI 上で取得した quote / OHLCV summary / FX rate / provider metadata を確認できるようにする
- rate limit、timeout、provider unavailable、schema mismatch を domain error と API response に mapping する
- CI は外部 API に依存させない

完了条件:

- 設定で明示した場合だけ live provider が呼ばれる
- live provider の生きた取得結果を Streamlit UI 上で確認できる
- UI から provider、symbol、as-of / date range、取得結果、失敗理由を確認できる
- live provider なしで local checks が通る
- failure mode が tests / API / docs で説明されている

### Phase 11: Feature Store Lite

目的: screening と forecast で再利用する特徴量 snapshot を定義する。

Scope:

- Done: feature snapshot contract を追加する
- Done: Market Data tab で feature snapshot、provider、version、欠損理由を確認できるようにする
- return、volatility、momentum、ADV、drawdown、data completeness を計算する
- `dividend_yield`、`market_cap_jpy` など外部データ由来項目の扱いを整理する
- as-of date、provider metadata、feature version を保持する

完了条件:

- 銘柄ごとに同じ形式の特徴量を取得できる
- 欠損理由を追跡できる
- screening / forecast / report から再利用できる

- UI 上で feature snapshot、provider metadata、欠損理由を確認できる
- 外部 provider 由来の特徴量は、可能であれば live data 取得後の snapshot として確認できる

### Phase 12: Screening Score MVP

目的: 銘柄を ranking し、スコア理由を説明できるようにする。

Scope:

- `ScreeningService` を追加する
- momentum、liquidity、risk、data quality などの sub score を定義する
- `ScoreBreakdown` を返す
- API / Streamlit から ranking を確認できるようにする

完了条件:

- 複数銘柄を deterministic に順位付けできる
- score breakdown がテストされている
- UI / report で順位の理由を確認できる

- UI 上でランキング、総合 score、sub score、data quality warning を確認できる
- 外部 provider 由来データを使う場合は、live data 取得結果を元にした score で確認できる

### Phase 13: Forecast Lab Baseline

目的: 複数 forecast model を比較するための最小基盤を作る。

Scope:

- `ForecastModel` protocol / base class を定義する
- naive、moving average、momentum baseline を実装する
- time split / walk-forward 評価を用意する
- MAE、RMSE、direction accuracy などの metrics を返す

完了条件:

- 複数 baseline を同じ interface で実行できる
- data leakage を避ける評価手順がある
- forecast result と metrics を保存・表示できる

- UI 上で forecast horizon、model 別 metrics、評価期間を確認できる
- 外部 provider 由来の時系列を使う場合は、live data 取得結果から forecast までつながることを確認できる

### Phase 14: Multi-Model Forecasting

目的: 複数モデルの予測結果を並べ、合意度と不確実性を扱えるようにする。

Scope:

- model registry lite を追加する
- horizon、入力特徴量、出力形式を揃える
- ensemble、median forecast、model agreement / disagreement を計算する
- forecast summary を scoring に接続する

完了条件:

- model ごとの予測結果を比較できる
- model 間で意見が割れている銘柄を見つけられる
- forecast summary が investment score に利用できる

- UI 上で model comparison、agreement / disagreement、forecast summary を確認できる
- live data を入力にした場合も、model 別の出力差分を UI で確認できる

### Phase 15: Model-Informed Scoring

目的: screening、forecast、risk、data quality を統合した投資判断補助スコアを作る。

Scope:

- investment score contract を定義する
- score breakdown に加点・減点理由を含める
- forecast confidence と model disagreement を score に反映する
- YAML で score weight を調整できるようにする

完了条件:

- 銘柄ごとに総合スコアと内訳を返せる
- データ品質が低い場合や model 不一致が大きい場合に注意表示できる
- deterministic tests で計算結果を検証できる

- UI 上で screening、forecast、risk、data quality を統合した投資判断補助 score を確認できる
- live provider 由来データを使った score と、その算出根拠を UI で確認できる

### Phase 16: Visualization Cockpit

目的: ranking、予測、スコア内訳、モデル比較を UI で確認しやすくする。

Scope:

- ranking table
- score breakdown chart
- forecast horizon chart
- model comparison / agreement view
- risk and data-quality warnings

完了条件:

- ユーザーが ranking から詳細へ進める
- 予測とスコア理由を同じ画面で確認できる
- UI は注文送信を行わず、判断補助に限定されている

- 外部 provider 由来の最新に近いデータを使った ranking / forecast / score を UI で確認できる
- UI 上で provider、as-of、取得時刻、データ品質を確認できる

### Phase 17: Research Model Adapters

目的: 最新研究や高度なモデルを optional adapter として試せる構造を作る。

Scope:

- tree model、sequence model、Transformer、foundation model、sentiment model の adapter 方針を整理する
- model card を用意する
- heavy dependency は optional に分離する
- offline fixture で adapter contract をテストする

完了条件:

- 実験モデルを既定経路から分離して追加できる
- model ごとの入力、出力、制約、検証結果を追跡できる
- production-like 経路へ入れる前に評価できる

- UI または research view 上で adapter ごとの予測結果、制約、評価結果を確認できる
- live data を使う adapter は、取得元と as-of を表示したうえで結果を確認できる

### Phase 18: Decision Report

目的: ユーザーが判断材料を読み取れる report を出力する。

Scope:

- score、forecast、risk、data quality を report context にまとめる
- model 間の一致・不一致と注意点を文章化する
- Markdown / JSON / CSV / ZIP export を拡張する

完了条件:

- report だけで主要な判断材料を確認できる
- 予測の限界と注意点が明記されている
- 既存の deterministic export 方針を保っている

- UI から report preview と export を確認できる
- live provider 由来データを使った report では、provider、as-of、取得時刻、主要な注意点を確認できる

## 6. 検証コマンド

基本確認:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
```

個別確認:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend tests --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy .
```

`tools/run_local_checks.py` は、cache-free Black check、`ruff`、`pytest` を順に実行します。
重い確認は必要なタイミングで対象を絞って実行します。

## 7. Open Items

- `setup/SETUP.md` 内の仮想環境名を `venv_SMAI` に統一する
- `SMAI_CONFIG_FILE` 以外の環境変数設定を拡張するか判断する
- network 利用可能な環境で `yahoo` live provider の smoke check を行う
- `polygon` など追加 live provider adapter の優先度を判断する
- Feature Store Lite の contract を定義する
- Screening Score MVP の score breakdown を設計する
- Forecast Lab Baseline の評価手順を定義する
