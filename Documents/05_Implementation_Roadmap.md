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

Phase 1 から Phase 15 までは、現在の実装上は implementation complete 扱いです。
Phase 16 は UI / Visualization Cockpit 改善中です。
Research RAG は設計済みですが、実装は planned です。

実装済みの主な範囲:

- Core contracts / config / errors
- deterministic な `mock` / `csv` MarketData provider
- 明示 opt-in の `yahoo` live provider adapter 経路
- provider registry / factory / capability metadata
- Feature Snapshot / Feature Store Lite 相当
- Screening Score
- Forecast Lab baseline
- Multi-Model Forecasting baseline
- Forecast Summary / model agreement / forecast range
- Investment Score
- configurable `scoring.weights`
- Risk MVP
- Portfolio MVP
- Portfolio-to-Risk workflow
- FastAPI endpoints
  - `GET /health`
  - `POST /risk/pre-trade-check`
  - `POST /portfolio/rebalance-check`
  - `POST /screening/score`
  - `POST /forecast/evaluate`
  - `POST /scoring/investment-score`
- Swagger / OpenAPI metadata
- `SMAI_CONFIG_FILE` による YAML settings loading
- Streamlit UI
  - `銘柄コックピット`
  - `銘柄ランキング`
  - `Rebalance Cockpit`
- file-backed rebalance scenarios
- JSON / CSV / Markdown / manifest / ZIP report export
- Windows 環境向け single-process Black check helper

未実装または今後の範囲:

- `polygon` などの追加 live provider adapter 本体
- provider fundamentals 由来の symbol metadata refresh command
- Research RAG layer（IR資料検索・根拠提示・Research Score）
- Decision Report の本格 workflow
- broker への live order 送信
- Execution workflow
- AI assistant experience
- PDF / Excel export

## 3. 実装方針

- 既定経路は local / deterministic に保つ。
- 外部 API は明示 opt-in の場合だけ使う。
- CI と通常の local checks は外部 API に依存させない。
- まず軽量な baseline を作り、後から高度なモデルや optional adapter を追加する。
- ユーザーに見える機能では、最終結果だけでなく理由・内訳・制約・根拠資料を表示する。
- 売買推奨ではなく、投資判断補助として表現する。
- 実装状態が変わったら `PROJECT_CONTEXT.md` と関連ドキュメントを同期する。

## 4. 完了済みフェーズ

### Phase 1: Core Foundation

Status: implementation complete

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

Status: implementation complete

完了済み:

- `mock` provider
- `csv` provider
- `fetch_ohlcv`
- `fetch_quotes`
- `get_fx_rates`
- `fetch_fundamentals`
- `compute_adv`
- `compute_vol`
- `build_daily_snapshot`
- local sample CSV

残り:

- 配当利回り、発行株式数、営業日 calendar などの正式データ連携の拡充

### Phase 3: Risk MVP

Status: implementation complete

完了済み:

- `backend/risk/service.py`
- `POST /risk/pre-trade-check`
- `ALLOW` / `REVIEW` / `BLOCK`
- concentration、cash、dividend-yield missing などの MVP risk rule
- deterministic tests

### Phase 4: Portfolio MVP

Status: implementation complete

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

Status: implementation complete

完了済み:

- FastAPI app wiring
- Swagger / OpenAPI metadata
- Portfolio / Risk / Screening / Forecast / Scoring endpoints
- Streamlit UI
- sample selector
- target controls
- allocation comparison
- result download

### Phase 6: CSV Data And Scenario Expansion

Status: implementation complete

完了済み:

- `data/marketdata` sample CSV
- `config/csv_example.yaml`
- `examples/rebalance_scenarios/`
- CSV provider smoke check
- deterministic scenarios

### Phase 7: Config And Scenario Management

Status: implementation complete

完了済み:

- file-backed rebalance scenario
- `SMAI_REBALANCE_SCENARIO_DIR`
- scenario `description`
- invalid scenario/config error handling
- UI sample selector integration

### Phase 8: Reporting MVP

Status: implementation complete

完了済み:

- `RebalanceReportContext`
- JSON download
- CSV downloads
- Markdown report
- manifest
- ZIP export
- validated request JSON export
- Forecast / Screening / Investment Score の JSON / CSV export helper

残り:

- PDF / Excel export
- broader reporting workflow

### Phase 9: External Data Provider Preparation

Status: implementation complete

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

- additional live provider adapter
- live provider smoke check 手順の拡充

## 5. 次期ロードマップ

次期重点は **Multi-Model Investment Intelligence** です。

注文執行ではなく、外部データ取得、特徴量管理、銘柄スコアリング、複数モデル予測、可視化、判断補助レポートを優先します。
Execution / broker order 送信は重要な将来領域ですが、今回のロードマップでは優先度を下げます。

### UI 確認方針

Phase 10 以降で UI 上の体験に影響する機能は、バックエンド実装だけでは完了としません。
各フェーズの完了条件には、Streamlit UI または将来の UI 画面で、ユーザーが変更内容を確認できることを含めます。
ただし、通常の自動テストと local checks は外部 API に依存させず、mock / csv / fixture による deterministic な検証を維持します。

### Phase 10: External Data Ingestion MVP

Status: implementation complete; live smoke environment-dependent

目的: 外部 MarketData provider から実データを取得し、取得結果と provider 状態を Streamlit UI 上で確認できる最小経路を作る。

Done:

- provider registry / factory
- explicit opt-in gate
- `yahoo` live provider adapter path
- provider metadata / error display
- deterministic fallback path

Remaining:

- live smoke 手順の標準化
- `polygon` など追加 provider adapter

### Phase 11: Feature Store Lite

Status: implementation complete

目的: provider に依存しない特徴量 snapshot を作る。

Done:

- `FeatureBuilder.build_feature_snapshot`
- close / return / momentum / ADV / volatility / drawdown
- missing summary / quality summary / completeness
- provider and as-of metadata

Remaining:

- feature versioning
- persistent feature store

### Phase 12: Screening Score MVP

Status: implementation complete

目的: 複数銘柄を説明可能に ranking する。

Done:

- `backend/screening`
- Screening Score contract
- sub-scores
- reason labels
- Forecast agreement 接続
- API / UI export helper

Remaining:

- watchlist persistence
- symbol metadata refresh と universe 管理

### Phase 13: Forecast Lab Baseline

Status: implementation complete

目的: deterministic baseline で forecast を評価できるようにする。

Done:

- `backend/forecast/service.py`
- naive / moving-average / momentum baseline
- walk-forward metrics
- Forecast chart preview
- Forecast metrics JSON / CSV export

### Phase 14: Multi-Model Forecasting

Status: implementation complete; live-provider confirmation remains environment-dependent

Done:

- Forecast model registry lite
- model availability by bar count
- Forecast consensus
- ensemble / median forecast
- forecast range
- model agreement
- Screening Score への forecast signal 接続

Remaining:

- advanced forecast model adapter
- model card / model evaluation persistence

### Phase 15: Model-Informed Scoring

Status: implementation complete; live-provider confirmation remains environment-dependent

目的: Screening / Forecast / Risk / Data Quality を統合した投資判断補助 score を作る。

Done:

- `backend/scoring`
- `InvestmentScore` contract
- `InvestmentScoringService`
- configurable `scoring.weights`
- Screening risk score を初期 risk signal として利用
- `POST /scoring/investment-score`
- Market Data tab Investment Score preview
- JSON / CSV downloads
- warning / reason / decision-support note
- `ScreeningScore` との互換性維持

Remaining:

- Research Score integration
- richer risk signal
- report context integration

### Phase 16: Visualization Cockpit

Status: in progress

目的: Phase 15 までに整えた scoring / forecast / screening / risk の下回りを、ユーザーが一目で判断材料として読める UI にする。

Done:

- Market Data tab を `銘柄コックピット` / `銘柄ランキング` に分割
- 銘柄コックピットで価格・予測チャートを主役化
- Investment Score summary / score breakdown chart
- Forecast agreement / forecast spread / best RMSE model summary
- Ranking preset: balance / forecast agreement / data quality / lower risk
- Ranking candidate filters modal
- static / curated metadata による fetch-before filtering
- ticker + company name 表示
- ranking result から cockpit への handoff
- Rebalance JSON input を advanced input へ移動
- Rebalance Cockpit summary flow
- target allocation percentage display/input
- allocation comparison chart
- beginner-friendly risk breach confirmation points

In progress:

- Rebalance Cockpit wording/layout の磨き込み
- ranking-to-cockpit flow の改善
- Decision Report に渡せる context の整理

Remaining:

- symbol metadata refresh command
- saved watchlist / ranking scenario
- cockpit / ranking / rebalance を横断した report context

## 6. Research RAG Roadmap: Long-term Company Intelligence

Research RAG は、価格・テクニカル指標だけでは拾いにくい長期企業分析の根拠を扱う将来領域です。
現時点では設計済み・実装 planned として扱います。

### Phase R0: Research RAG 要件・詳細設計

Status: design complete

Done:

- `04-8_Onepager_Research_RAG.md`
- requirements / architecture / functional design / roadmap への反映

### Phase R1: Local Document Ingestion MVP

Status: planned

### Phase R2: Text Extraction & Chunk Store

Status: planned

### Phase R3: Keyword Retrieval MVP

Status: planned

### Phase R4: Research Summary MVP

Status: planned

### Phase R5: Vector Search / Hybrid Search

Status: planned

### Phase R6: Research Score MVP

Status: planned

### Phase R7: Investment Score / Ranking / Report 統合

Status: planned

### Phase R8: External Source Adapter

Status: planned

## 7. Future Phases

### Phase 17: Research Model Adapters

Status: planned

高度な forecast / research model を optional adapter として接続する。
通常の CI / local checks には重い ML library を必須にしない。

### Phase 18: Decision Report

Status: planned

Phase 16 の cockpit summary と ranking result を report context として再利用する。
初期は Markdown / JSON / CSV / ZIP を優先し、PDF / Excel は後続。

### Phase 19: UI Design And Beginner Experience

Status: planned

Phase 16 で作った cockpit / ranking / rebalance の情報設計を、初心者向けの画面名、導線、文言に磨き込む。

### Phase 20: Low-Cost AI Assistant Experience

Status: planned

Phase 16 の cockpit summary と Phase 18 の report context を入力にし、同じ材料から UI / report / assistant の説明を揃える。

## 8. 検証コマンド

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy backend
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

Markdown UTF-8 check:

```powershell
.\venv_SMAI\Scripts\python.exe -c "from pathlib import Path; [p.read_text(encoding='utf-8') for p in Path('.').rglob('*.md') if '.git' not in p.parts]; print('markdown utf-8 ok')"
```

## 9. Open Items

- provider fundamentals から symbol metadata を更新するコマンドをどの粒度で作るか
- Research Score を Investment Score に統合する重みと表示順
- Decision Report に含める cockpit / ranking / rebalance context の最小 schema
- PDF / Excel export をいつ入れるか
- Execution / broker order をどの段階で再開するか

---

# Appendix: SMAI Future Implementation Roadmap (LLM Integrated)

この Appendix は future candidate の一覧です。現在の実装済み範囲ではありません。Phase 16 / Research RAG / Decision Report の次に検討する候補として扱います。

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
