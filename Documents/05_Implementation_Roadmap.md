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
- Done: baseline model ごとの予測線を終値 chart に重ね、実績は実線、予測は破線で表示する
- Done: model 別 forecast close と metrics を UI に表示する
- Done: Market Data tab で `mock` / `yahoo` / `csv` provider を選べるようにする
- Done: live provider が失敗した場合、UI 上で error code、message、details をすぐ確認できるようにする
- Done: mock の直近日付 OHLCV を、単調な右肩上がりではなく上下動のあるサンプル系列にする
- Done: Forecast result を `POST /forecast/evaluate` で API から確認できるようにする
- Done: Streamlit UI から forecast horizon を 1〜30 日の範囲で選べるようにする
- Done: chart 上の予測点の日付を、選択した forecast horizon に合わせて表示する
- Done: Market Data tab を左側に移動し、Forecast chart の凡例クリックで系列表示を切り替えられるようにする
- Done: Forecast model の参照期間を取得期間と forecast horizon から自動算出し、UI に自然な日本語で表示する
- Done: Forecast result を JSON / CSV export へ接続する

完了条件:

- Done: 複数 baseline を同じ interface で実行できる
- Done: data leakage を避ける評価手順がある
- Done: forecast result と metrics を UI で表示できる
- Done: forecast result と metrics を API で取得できる
- Done: UI 上で forecast horizon を変更し、model 別 metrics と予測線に反映されたことを確認できる
- Done: forecast result と metrics を保存できる

- Done: UI 上で forecast horizon、model 別 metrics、評価期間を確認できる
- 外部 provider 由来の時系列を使う場合は、live data 取得結果から forecast までつながることを確認できる

### Phase 14: Multi-Model Forecasting

Status: implementation complete; live-provider confirmation remains environment-dependent

目的: 複数モデルの予測結果を並べ、合意度と不確実性を扱えるようにする。

Scope:

- Done: model 別 forecast から median forecast と予測レンジを計算する
- Done: model agreement / disagreement の最小判定を UI で確認できるようにする
- Done: model registry lite を追加する
- Done: horizon、入力時系列、出力形式を baseline model 間で揃える
- Done: ensemble を計算する
- Done: forecast summary を screening score に接続する

完了条件:

- Done: model ごとの予測結果を比較できる
- Done: model 間で意見が割れている銘柄を見つけられる
- Done: forecast summary が investment score に利用できる

- Done: UI 上で model comparison、agreement / disagreement、forecast summary を確認できる
- live data を入力にした場合も、model 別の出力差分を UI で確認できる

### Phase 15: Model-Informed Scoring

Status: implementation complete; live-provider confirmation remains environment-dependent

目的: screening、forecast、risk、data quality を統合した投資判断補助スコアを作る。

Scope:

- Done: investment score contract を定義する
- score breakdown に加点・減点理由を含める
- forecast confidence と model disagreement を score に反映する
- Done: investment score API を追加する
- Done: Market Data tab に Investment Score preview と JSON / CSV 保存を追加する
- Done: YAML で score weight を調整できるようにする
- Done: 既存 screening risk score を risk signal として統合する

最初の実装スライス:

- Done: `backend/scoring` を追加し、screening score と forecast agreement signal を受け取る `InvestmentScore` contract を定義する
- Done: 既存 `ScreeningScore` の互換性を保ち、Phase 15 の総合 score は別 contract として開始する
- Done: deterministic tests で、data quality warning と model disagreement が理由に出ることを確認する
- Done: `POST /scoring/investment-score` で総合 score と内訳を返せる
- Done: UI 上で selected symbol の総合 score と注意点を確認できる
- Done: score weight は `scoring.weights` で調整でき、合計 1.0 を検証する

完了条件:

- Done: 銘柄ごとに総合スコアと内訳を返せる
- Done: データ品質が低い場合や model 不一致が大きい場合に注意表示できる
- Done: deterministic tests で計算結果を検証できる

- Done: UI 上で screening、forecast、risk、data quality を統合した投資判断補助 score を確認できる
- live provider 由来データを使った score と、その算出根拠の UI 確認は環境依存

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
- 市場選択と symbol resolver を設計し、`9983` などの日本株4桁コード、`9983.T` のような Yahoo provider 表記、`AAPL` などの米国 ticker をユーザーが迷わず扱えるようにする
- provider 固有の symbol 補完は UI 上で補完後の symbol を見せ、入力値と provider 問い合わせ値の差分を確認できるようにする
- 複数銘柄 ranking は、単一銘柄チェックとは別の UI 体験として設計する
- score、sub score、data quality、欠損理由を初心者向けの日本語ラベルと説明に変換する
- ranking、Feature Snapshot、forecast、risk、report への導線を整理する
- 注意表示は「購入推奨ではなく判断補助」であることを明確にしつつ、画面を邪魔しない配置にする
- desktop / mobile の主要 viewport で、表・カード・説明文が読める layout にする

完了条件:

- symbol を知らないユーザーでも、プリセットまたは検索から銘柄チェックを開始できる
- 日本株と米国株を少なくとも UI 上で区別でき、Yahoo provider 利用時の `.T` などの suffix 補完が分かる
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

# SMAI Future Implementation Roadmap (LLM Integrated)

## Future Implementation Candidates / 将来実装候補

基本方針:
- local-first / deterministic-first を既定とする
- 外部 API・LLM・ニュース取得は明示 opt-in の追加レイヤーとして扱う
- 投資判断ロジック本体は deterministic に保ち、LLM は説明・要約・対話体験の拡張に使う

---

## Phase F1: Chat AI Assistant MVP / チャット AI アシスタント MVP

### Goal
- MarketData、Feature Store Lite、Screening、Forecast、Risk、Portfolio の結果を、初心者向け日本語で説明できる対話 UI を追加する。
- 初期実装は LLM 依存ではなく、決定的なルール・テンプレート応答で構成する。
- 投資判断の最終決定ではなく、指標の意味、注意点、次に確認すべき観点を案内する。

### Scope
- `backend/assistant/` を追加する
- assistant request / response contract を定義する
- 質問種別分類、context 組み立て、template response generation を分離する
- FastAPI に assistant endpoint を追加する
- Streamlit にチャット/質問パネルを追加する
- 応答に根拠、制約、データ品質、不確実性、投資助言ではない旨を含める

### Implementation slices
- F1-1: request / response contract を追加
- F1-2: deterministic response service を追加
- F1-3: Screening / Forecast / Risk / Portfolio から assistant context を組み立てる adapter を追加
- F1-4: FastAPI endpoint と API test を追加
- F1-5: Streamlit に質問 UI を追加
- F1-6: Operations Guide に使い方と制約を追記

### Acceptance criteria
- network 非依存で通常テストが通る
- 同じ入力と同じ分析コンテキストでは同じ応答になる
- 初心者向け日本語で理由・注意点・次の確認観点を説明できる
- UI/API のどちらでも投資助言ではなく判断補助であることが明示される

---

## Phase F2: News & Sentiment Intelligence MVP / ニュース・センチメント分析 MVP

### Goal
- 銘柄や市場に関連するニュース・イベント・センチメントを、Screening / Forecast / Risk の補助情報として扱えるようにする。
- 初期実装は local fixture / CSV input を既定にし、外部ニュース provider は明示 opt-in にする。
- センチメントはスコア単体ではなく、要約、根拠、鮮度、信頼度、データ品質警告と一緒に表示する。

### Scope
- `backend/news/` を追加する
- news item contract、provider interface、local CSV provider を定義する
- baseline sentiment scorer を追加する
- ticker/news summary endpoint を追加する
- Screening Score に optional sentiment feature を接続できる設計にする
- Streamlit にニュース一覧、センチメント要約、注意点を表示する

### Implementation slices
- F2-1: news item / sentiment summary contract を定義
- F2-2: local CSV schema と deterministic CSV provider を追加
- F2-3: rule-based baseline sentiment scorer を追加
- F2-4: FastAPI endpoint を追加
- F2-5: Screening / Forecast / Risk への optional context integration を追加
- F2-6: Streamlit にニュース/センチメント表示を追加
- F2-7: Operations Guide に CSV 形式と provider opt-in 方針を追記

### Acceptance criteria
- local CSV/fixture だけで API・service tests が通る
- 外部 provider 未設定でも既存 default path は変わらない
- ニュースが古い、少ない、欠損している場合は data quality warning が出る
- sentiment output は代表ニュースまたは理由と紐づく
- sentiment 単体で投資判断を出さない

---

## Phase F3: Assistant x News Integration / チャット AI とニュース分析の統合

### Goal
- Chat AI Assistant がニュース・センチメント情報を説明できるようにする。
- 分析画面で「なぜこの評価なのか」を横断的に確認できるようにする。

### Scope
- assistant context に news / sentiment summary を追加する
- Screening / Forecast / Risk の理由表示にニュース由来の補助理由を統合する
- ニュース関連の質問テンプレートを追加する

### Question templates
- この銘柄で最近注意する材料は？
- スコアに影響しそうなニュースは？
- ニュースの内容はポジティブ？ネガティブ？
- この評価の不確実性はどこにある？

### Acceptance criteria
- ニュースなしでも degraded response を返し、欠損理由を説明する
- ニュースありの場合、鮮度、信頼度、データ品質警告を含める
- LLM adapter を使わない通常テストで統合挙動を検証できる

---

## Phase F4: LLM Adapter Foundation / LLM アダプター基盤

### Goal
- Chat AI Assistant の応答生成を、template provider から optional LLM provider に差し替え可能にする。
- ただし default は deterministic template provider のまま維持する。
- LLM は投資判断ロジックではなく、説明・要約・自然言語化の補助に限定する。

### Scope
- `backend/assistant/llm/` を追加する
- `AssistantResponseProvider` protocol を定義する
- `TemplateAssistantProvider` を default provider として維持する
- `MockLlmAssistantProvider` を追加し、LLM adapter の contract test を可能にする
- `OpenAiAssistantProvider` / `OllamaAssistantProvider` の追加口を設計する
- provider selection を config で切り替え可能にする
- LLM provider 使用時も、入力 context、参照指標、注意書き、制約を response に含める

### Implementation slices
- F4-1: assistant response provider protocol を追加する
- F4-2: 既存 template response service を provider 化する
- F4-3: mock LLM provider を追加する
- F4-4: config に `assistant.provider` を追加する
- F4-5: provider factory を追加する
- F4-6: OpenAI / Ollama provider の interface stub を追加する
- F4-7: Operations Guide に provider 切替方針を追記する

### Acceptance criteria
- default provider は template のまま
- LLM provider 未設定でも既存 assistant は動作する
- 通常テストは network 非依存で通る
- mock LLM provider で adapter contract を検証できる
- LLM 出力にも投資助言ではない旨が含まれる

---

## Phase F5: Local LLM / Ollama Assistant Preview

### Goal
- ローカル LLM を使い、API 課金なしで assistant 応答の自然さを改善する。
- 初期対象は Ollama とし、local-first 方針を維持する。

### Scope
- `OllamaAssistantProvider` を追加する
- Ollama API endpoint、model name、timeout を config 化する
- assistant context を prompt に変換する prompt builder を追加する
- LLM の出力に対して、必須 disclaimer / referenced metrics / data quality warning を後処理で補完する
- LLM 失敗時は template provider に fallback する

### Implementation slices
- F5-1: Ollama provider config を追加する
- F5-2: Ollama API client を追加する
- F5-3: prompt builder を追加する
- F5-4: response post-processor を追加する
- F5-5: fallback to template provider を追加する
- F5-6: Streamlit UI に provider 表示を追加する

### Acceptance criteria
- Ollama 未起動でもアプリ全体は壊れない
- Ollama 使用時は provider、model、fallback 状態が UI/API で分かる
- LLM が失敗した場合は template response に degraded fallback する
- 通常 CI は Ollama に依存しない

---

## Phase F6: Cloud LLM Assistant Preview / OpenAI Adapter

### Goal
- OpenAI API などの cloud LLM を optional provider として利用できるようにする。
- 高精度な説明、銘柄比較、ニュース要約を試せるようにする。

### Scope
- `OpenAiAssistantProvider` を追加する
- API key は環境変数または config で明示 opt-in にする
- token budget、timeout、model name を config 化する
- LLM への入力は最小限の structured context に限定する
- 個人情報や不要な portfolio detail を送らない privacy guard を追加する
- 失敗時は template provider に fallback する

### Implementation slices
- F6-1: OpenAI provider config を追加する
- F6-2: OpenAI client adapter を追加する
- F6-3: prompt/context minimization policy を追加する
- F6-4: privacy guard を追加する
- F6-5: error mapping と fallback を追加する
- F6-6: Operations Guide に API key、コスト、制約を記載する

### Acceptance criteria
- 明示 opt-in なしでは cloud LLM は呼ばれない
- API key 未設定でも通常機能は動作する
- cloud LLM 利用時は provider、model、送信対象 context の概要が分かる
- 失敗時は deterministic response に fallback する
- 通常テストは外部 API 非依存で通る

---

## Phase F7: LLM-Enhanced News Explanation / LLM によるニュース説明強化

### Goal
- ニュース・センチメント情報を、LLM で初心者向けに要約・統合説明できるようにする。
- ただし sentiment score や investment score の計算そのものは deterministic core に残す。

### Scope
- news summary を assistant context に渡す
- 複数ニュースの要点統合 prompt を追加する
- ニュースの鮮度、信頼度、欠損、偏りを説明に含める
- LLM が根拠のない断定をしないよう、参照可能な news item の範囲だけで説明させる
- report export に LLM-enhanced summary を optional で含める

### Implementation slices
- F7-1: news-aware prompt template を追加する
- F7-2: referenced news item tracking を追加する
- F7-3: hallucination guard / unsupported claim guard を追加する
- F7-4: UI に news explanation provider を表示する
- F7-5: report export に optional LLM summary を追加する

### Acceptance criteria
- LLM summary は参照した news item と紐づく
- ニュースが不足している場合は不足を明示する
- sentiment 単体で売買判断を出さない
- LLM を使わない場合も template summary が表示される

---

## Phase F8: Hybrid Assistant Evaluation / ハイブリッド Assistant 評価

### Goal
- template response と LLM response の品質、安定性、コスト、説明責任を比較できるようにする。
- LLM を本格採用する前に、評価可能な状態を作る。

### Scope
- assistant evaluation dataset を fixture として用意する
- template / Ollama / OpenAI の response を比較する
- completeness、clarity、safety、groundedness、cost、latency を評価する
- 人手確認用の Markdown report を出力する
- LLM 採用判断の criteria を定義する

### Implementation slices
- F8-1: evaluation questions fixture を追加する
- F8-2: expected key points を定義する
- F8-3: provider 別 response export を追加する
- F8-4: latency / token / fallback status を記録する
- F8-5: evaluation report を生成する

### Acceptance criteria
- provider ごとの応答差分を確認できる
- LLM の採用メリットとリスクを判断できる
- template provider が最低限の安全な baseline として維持される

---

## Overall Flow

```text
F1: Template Chat Assistant
  ↓
F2: News & Sentiment Intelligence
  ↓
F3: Assistant x News Integration
  ↓
F4: LLM Adapter Foundation
  ↓
F5: Local LLM / Ollama Assistant Preview
  ↓
F6: Cloud LLM / OpenAI Adapter
  ↓
F7: LLM-Enhanced News Explanation
  ↓
F8: Hybrid Assistant Evaluation
```

## LLM Extension Phases / LLM 活用拡張フェーズ

この節は Chat AI Assistant / News & Sentiment の将来フェーズに対する LLM 活用の実装計画である。
既定経路は引き続き local-first / deterministic-first とし、LLM は明示 opt-in の adapter として追加する。
LLM はデータ取得、スコア計算、売買判断、注文実行の主体にしない。既存 backend が生成した構造化コンテキストを、説明・要約・観点提示として自然文に整える補助レイヤーに限定する。

### Phase F4: Optional LLM Adapter / 任意 LLM アダプター

Goal:
- Deterministic Assistant MVP の説明品質を、明示 opt-in の LLM adapter で拡張する。
- LLM は分析・取得・売買判断の主体ではなく、既存 backend が生成した構造化コンテキストを自然文に整える補助レイヤーとして扱う。
- API key、料金、rate limit、provider failure が通常動作や通常テストを壊さない設計にする。

Scope:
- `backend/assistant/` に LLM provider interface を追加し、default provider は deterministic/template のまま維持する。
- LLM に渡す context schema を固定し、MarketData、Screening、Forecast、Risk、Portfolio、News/Sentiment の構造化結果だけを入力にする。
- Prompt builder、response parser、safety validator、fallback handler を分離する。
- LLM 応答には、参照した指標、データ品質警告、不確実性、投資助言ではない旨を必ず含める。
- LLM provider は設定ファイルまたは環境変数で明示 opt-in にする。

Non-goals:
- LLM に MarketData provider、ニュース取得、スコア計算、売買判断、注文実行を直接任せない。
- LLM が返した数値を根拠なく authoritative な分析結果として保存しない。
- LLM 必須の UI/API にしない。

Implementation slices:
- F4-1: assistant provider interface と deterministic provider の明示実装を追加する。
- F4-2: LLM context schema と prompt builder を追加し、snapshot/fixture test で構造を固定する。
- F4-3: LLM response parser と safety validator を追加し、禁止表現、助言化、根拠欠落、警告欠落を検出する。
- F4-4: provider failure、timeout、rate limit、missing API key 時の fallback を実装する。
- F4-5: FastAPI/Streamlit に provider mode 表示を追加し、既定が local/template であることを明示する。
- F4-6: Operations Guide に LLM opt-in 手順、API key 管理、料金・失敗時挙動、通常テストでは network 不要であることを記載する。

Acceptance criteria:
- LLM provider 未設定でも assistant API/UI は deterministic provider で動作する。
- 通常テストは network 非依存で通る。
- LLM provider の失敗時は fallback response を返し、ユーザーに失敗理由と制約が表示される。
- LLM 応答は売買推奨ではなく、説明・要約・観点提示に限定される。
- テストは LLM の文章完全一致ではなく、context 組み立て、fallback、安全要件、必須フィールドを検証する。

### Phase F5: LLM-assisted Report Generation / LLM 支援レポート生成

Goal:
- 既存分析結果をもとに、初心者が読みやすい銘柄・ポートフォリオ・市場概況レポートを生成する。
- Deterministic report template を既定にし、LLM は任意で文章表現や要約品質を高める補助として使う。

Scope:
- Report contract を定義し、summary、key metrics、positive/negative factors、risks、data quality、next checks、disclaimer を構造化する。
- Deterministic report renderer を実装し、LLM が使えない場合も同じ情報構造でレポートを出せるようにする。
- LLM adapter 有効時は、構造化 report draft を入力にして自然文を整える。
- Export は Markdown/CSV など local-first な形式から始める。

Non-goals:
- 個別売買指示、目標株価の断定、自動発注、保証表現は扱わない。
- LLM が独自に未検証データを追加することを許可しない。

Implementation slices:
- F5-1: report contract と deterministic renderer を追加する。
- F5-2: Screening/Forecast/Risk/Portfolio/News の結果を report draft に集約する service を追加する。
- F5-3: Markdown export と API endpoint を追加する。
- F5-4: Streamlit に report preview/export を追加する。
- F5-5: LLM adapter 有効時の prose enhancement を追加し、根拠・警告・disclaimer が欠落しない validator を通す。

Acceptance criteria:
- LLM なしでレポート生成と export が完結する。
- LLM ありでも、数値・根拠・警告は backend の構造化データからのみ出力される。
- レポートには判断補助であり投資助言ではない旨が含まれる。
- fixture-based tests で report draft、deterministic output、LLM fallback、安全要件を検証できる。
