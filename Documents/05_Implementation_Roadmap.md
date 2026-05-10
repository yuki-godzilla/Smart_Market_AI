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

Status: implementation complete; live smoke pending

目的: 外部 MarketData provider から実データを取得し、取得結果と provider 状態を Streamlit UI 上で確認できる最小経路を作る。

Scope:

- Done: live provider adapter metadata を `backend/marketdata/live_provider_adapters.py` に分離する
- Done: live provider adapter interface を `backend/marketdata/provider_adapters.py` の `MarketDataProviderAdapter` protocol として定義する
- Done: provider adapter factory を `backend/marketdata/provider_factory.py` に追加する
- Done: Streamlit UI に deterministic provider で動く Market Data preview tab を追加する
- Done: `yahoo` provider を opt-in live adapter として `backend/marketdata/providers/yahoo.py` に追加する
- Done: `yahoo` の取得結果を `Bar` / `Quote` / `FxRate` へ正規化する
- Done: live provider の取得結果を Streamlit UI の Market Data tab で確認できる経路を追加する
- Done: UI 上で取得した quote / OHLCV summary / FX rate / provider metadata を確認できるようにする
- Done: provider unavailable、schema mismatch を domain error と UI/API response に mapping する
- Done: CI は外部 API に依存させない
- Pending: network と `yfinance` cache 書き込みが可能な環境で、`yahoo` live provider の生きたデータを Streamlit UI 上で smoke check する

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
- Done: return、volatility、momentum、ADV、drawdown、data completeness を計算する
- Done: 欠損特徴量と data completeness から `OK` / `WARN` / `BLOCK` の data quality 判定を計算し、UI で確認できるようにする
- Done: `dividend_yield`、`market_cap_jpy` など外部データ由来項目を provider 共通 contract で取り込み、UI で確認できるようにする
- as-of date、provider metadata、feature version を保持する

完了条件:

- 銘柄ごとに同じ形式の特徴量を取得できる
- 欠損理由を追跡できる
- data quality 判定と理由を追跡できる
- `dividend_yield`、`market_cap_jpy` を Feature Snapshot 上で確認できる
- screening / forecast / report から再利用できる

- UI 上で feature snapshot、provider metadata、欠損理由、data quality 判定を確認できる
- 外部 provider 由来の特徴量は、可能であれば live data 取得後の snapshot として確認できる

### Phase 12: Screening Score MVP

目的: 銘柄スコアを計算し、スコア理由を説明できるようにする。

Scope:

- Done: `ScreeningService` を追加する
- Done: momentum、liquidity、risk、data quality などの sub score を定義する
- Done: `ScreeningScore` と score breakdown を返す
- Done: Streamlit の Market Data tab では入力銘柄の score を確認できるようにする
- Done: API から ranking を確認できるようにする
- Done: スコアの summary と技術的な理由を初心者向け日本語ラベルとして返す
- Deferred: 複数銘柄 ranking を UI 上でどう見せるかは、初心者向け UI Design phase で設計する

完了条件:

- Done: 複数銘柄を deterministic に順位付けできる
- Done: score breakdown がテストされている
- Done: API で順位の理由を確認できる
- Done: UI / JSON / CSV export で入力銘柄の score と理由を確認できる
- Done: UI / API / JSON / CSV export で初心者向けの日本語説明を確認できる

- Done: UI 上で入力銘柄の総合 score、sub score、data quality warning を確認できる
- Done: UI 上の Market Data preview では、入力していないサンプル銘柄を暗黙に混ぜない
- Deferred: watchlist、プリセット銘柄群、銘柄名検索を使った ranking UI は Phase 19 で扱う
- 外部 provider 由来データを使う場合は、live data 取得結果を元にした score で確認できる

### Phase 13: Forecast Lab Baseline

目的: 複数 forecast model を比較するための最小基盤を作る。

Scope:

- Done: `ForecastModel` protocol を定義する
- Done: naive、moving average、momentum baseline を実装する
- Done: walk-forward 評価を用意する
- Done: MAE、RMSE、direction accuracy などの metrics を返す
- Done: 選択銘柄の終値 chart を Streamlit Market Data tab に表示する
- Done: baseline model ごとの予測線を終値 chart に重ねて表示する
- Done: model 別 forecast close と metrics を UI に表示する
- Pending: Forecast result を API / export へ接続する

完了条件:

- Done: 複数 baseline を同じ interface で実行できる
- Done: data leakage を避ける評価手順がある
- Done: forecast result と metrics を UI で表示できる
- Pending: forecast result と metrics を保存できる

- Done: UI 上で forecast horizon、model 別 metrics、評価期間を確認できる
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

### Phase 19: UI Design And Beginner Experience

目的: 投資初心者でも symbol や指標名に迷わず、候補銘柄の確認から理由理解まで進められる UI 体験を作る。

Scope:

- `Market Data` など開発者向けの画面名を、ユーザー向けの「銘柄チェック」「候補ランキング」などへ整理する
- symbol 手入力だけでなく、watchlist、プリセット銘柄群、銘柄名検索から始められるようにする
- 複数銘柄 ranking は、単一銘柄チェックとは別の UI 体験として設計する
- score、sub score、data quality、欠損理由を初心者向けの日本語ラベルと説明に変換する
- ranking、Feature Snapshot、forecast、risk、report への導線を整理する
- 注意表示は「購入推奨ではなく判断補助」であることを明確にしつつ、画面を邪魔しない配置にする
- desktop / mobile の主要 viewport で、表・カード・説明文が読める layout にする

完了条件:

- symbol を知らないユーザーでも、プリセットまたは検索から銘柄チェックを開始できる
- 複数銘柄 ranking では、比較対象、並び順、score 理由、data quality warning が分かる
- UI 上で総合 score、sub score、data quality warning、主要な理由を日本語で理解できる
- 銘柄比較から詳細確認、report preview までの導線が分かる
- UI に影響する変更はスクリーンショットまたは手動確認観点で検証できる
- 外部 provider 由来データを使う場合は、provider、as-of、取得時刻、データ品質がユーザーに見える

### Phase 20: Low-Cost AI Assistant Experience

目的: 外部 AI API の利用を前提にせず、まずはルールベースとテンプレートで「AI が投資判断を補助してくれる」体験を作る。

Scope:

- Screening Score、Feature Snapshot、forecast、risk、data quality を入力にした explanation layer を作る
- `missing:momentum_5d` などの技術的な理由を初心者向け日本語文に変換する
- 銘柄比較コメント、注意点、次に確認すべき観点をテンプレートで生成する
- AI API を使わない deterministic assistant を既定実装にする
- 将来 OpenAI API、ローカル LLM、他 provider に差し替えられる adapter 境界を設計する
- 「購入推奨」ではなく「判断補助」であることを UI と report に明記する

完了条件:

- API 課金なしで、スコアと特徴量に基づく自然文の説明を生成できる
- 同じ入力に対して同じ説明が返る deterministic tests がある
- UI 上で「なぜこの銘柄が上位か」「どこに注意すべきか」を日本語で確認できる
- report export に assistant summary を含められる
- LLM を使う場合も optional adapter とし、既定の local checks は外部 API に依存しない

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
- Feature Store Lite の外部データ由来項目を拡張する
- Screening Score MVP の score breakdown を設計する
- Forecast Lab Baseline の評価手順を定義する
- 初心者向け UI Design phase の具体的な画面構成と確認観点を設計する
- Low-Cost AI Assistant phase のルールベース説明と optional LLM adapter 境界を設計する
