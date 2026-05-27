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
Phase 16 は UI / Visualization Cockpit 改善の実装完了扱いです。最終 Streamlit browser smoke は推奨確認として残します。
Research RAG は Phase 20 local evidence slice が deterministic foundation として implementation complete です。今後の product direction は、local 登録資料を主データ源にするのではなく、`AI調査を更新` で外部の最新IR・開示・ニュース・provider evidence を取得/参照し、session-local に一時分析する流れを基本にします。local 登録資料は通常 tests / demo seed / archive / fallback の位置づけです。Phase 21 高度Research RAG（根拠抽出・根拠付き回答生成）は query expansion、structured extraction、grounded answer、retrieval quality、evidence reranker、UI / Decision Report 表示、optional vector / hybrid contract と scoring、keyword-fallback hybrid retrieval wrapper、local embedding generation、optional vector-index build workflow、in-memory local vector store、file-backed vector cache の first slice が進行中です。Phase 22 Research Score は backend deterministic service、disabled-by-default Investment Score optional input、Cockpit / Ranking Research Summary display、selected-candidate breakdown context、Cockpit Decision Report section の first slice が開始済みです。Ranking order integration、EDINET / TDnet / company IR site adapters、Assistant、distribution readiness は後続 planned / future scope です。

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
- 追加 provider / fund metadata source adapter
- Research RAG external source adapters / vector or hybrid search / Research Score
- Research Score の ranking 統合と cockpit / report 表示 polish
- Assistant / LLM / news integration
- broker への live order 送信
- Execution workflow
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

### 4.1 Phase 1〜9: MVP Foundation

Phase 1〜9 は、local-first MVP として必要な backend / API / UI / reporting の土台です。
詳細な運用手順は [06_MVP_Operations_Guide.md](./06_MVP_Operations_Guide.md) を参照します。

#### Phase 1: Core Foundation

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

#### Phase 2: MarketData MVP

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

#### Phase 3: Risk MVP

Status: implementation complete

完了済み:

- `backend/risk/service.py`
- `POST /risk/pre-trade-check`
- `ALLOW` / `REVIEW` / `BLOCK`
- concentration、cash、dividend-yield missing などの MVP risk rule
- deterministic tests

#### Phase 4: Portfolio MVP

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

#### Phase 5: API and UI Integration

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

#### Phase 6: CSV Data And Scenario Expansion

Status: implementation complete

完了済み:

- `data/marketdata` sample CSV
- `config/csv_example.yaml`
- `examples/rebalance_scenarios/`
- CSV provider smoke check
- deterministic scenarios

#### Phase 7: Config And Scenario Management

Status: implementation complete

完了済み:

- file-backed rebalance scenario
- `SMAI_REBALANCE_SCENARIO_DIR`
- scenario `description`
- invalid scenario/config error handling
- UI sample selector integration

#### Phase 8: Reporting MVP

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

#### Phase 9: External Data Provider Preparation

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

### 4.2 Phase 10〜16: Investment Intelligence And UI Foundation

Phase 10〜16 は、外部データ取得、Feature Store Lite、Screening、Forecast、Investment Score、Visualization Cockpit をつなげた投資判断補助の中核です。

| Phase | Status | 完了済みの主な範囲 | 残り / 後続 |
| --- | --- | --- | --- |
| Phase 10: External Data Ingestion MVP | implementation complete; live smoke environment-dependent | `yahoo` live provider adapter、provider metadata / error display、deterministic fallback | live smoke 手順の標準化、追加 provider adapter |
| Phase 11: Feature Store Lite | implementation complete | close / return / momentum / ADV / volatility / drawdown、missing / quality summary | feature versioning、persistent feature store |
| Phase 12: Screening Score MVP | implementation complete | `backend/screening`、sub-score、reason labels、Forecast agreement 接続 | watchlist persistence、symbol metadata refresh |
| Phase 13: Forecast Lab Baseline | implementation complete | naive / moving-average / momentum baseline、walk-forward metrics、Forecast chart preview | advanced model adapter の前提整備 |
| Phase 14: Multi-Model Forecasting | implementation complete; live-provider confirmation remains environment-dependent | model registry lite、forecast consensus、forecast range、model agreement | model card / evaluation persistence |
| Phase 15: Model-Informed Scoring | implementation complete; live-provider confirmation remains environment-dependent | `backend/scoring`、Investment Score、configurable weights、API / UI preview / export | Research Score integration、richer risk signal |
| Phase 16: Visualization Cockpit | implementation complete; final Streamlit browser smoke recommended | `銘柄コックピット` / `銘柄ランキング` / `リバランス`、side menu、ranking cache、Yahoo batch OHLCV、symbol-detail modal、cockpit investment memo、Rebalance summary flow | final UI smoke、Decision Report context |

## 5. 実装順ロードマップ

ここから先は、過去の番号順ではなく **次に実装する順番** として扱います。
Phase 1〜16 は完了済みの土台です。以降は、UI の迷いを減らし、データの信頼性を高め、レポート・根拠・対話体験へ広げる順で進めます。

優先順位の考え方:

- まず既存の `銘柄コックピット` / `銘柄ランキング` / `リバランス` を安定させる。
- 次にランキング条件 UI と symbol universe を整え、ユーザーが対象を迷わず絞れるようにする。
- その後、cockpit / ranking / rebalance を横断する Decision Report context を作る。
- Research RAG は外部最新情報を主にした根拠レイヤーとして育て、local fixture foundation と Research Score へつなげる。
- Assistant / LLM / external source / Execution は、判断材料の構造化が安定してから追加する。

### 5.1 UI 確認方針

UI 上の体験に影響する機能は、バックエンド実装だけでは完了としません。
各フェーズの完了条件には、Streamlit UI または将来の UI 画面で、ユーザーが変更内容を確認できることを含めます。
ただし、通常の自動テストと local checks は外部 API に依存させず、mock / csv / fixture による deterministic な検証を維持します。

### 5.2 Phase 16S: Stabilization And Final UI Smoke

Status: maturity review / next verification

目的: Phase 16 までに実装した主要画面を、次の UI / report / RAG 実装に進める前の安定基準として確認する。

Maturity tasks:

- Manual UX Review Checklist creation: [96_Manual_UX_Review_Checklist.md](./96_Manual_UX_Review_Checklist.md) を使い、Symbol Cockpit、Ranking、Rebalance Cockpit、Decision Report、Research Summary / Evidence、Forecast、Risk、Market Data freshness、score explanation を手動レビューできるようにする。
- Functional Spec Issues tracking: [97_Functional_Spec_Issues.md](./97_Functional_Spec_Issues.md) を使い、Investment Score、Database Fit、Metadata Confidence、Research Evidence、NISA / Dividend / Growth / ETF criteria などの仕様曖昧さを管理する。
- Feature role clarification: Ranking、Symbol Cockpit、Rebalance Cockpit、Decision Report、Research Summary / Evidence、Investment Score、Data Quality / Database Fit / Metadata Confidence の役割を [03_Functional_design.md](./03_Functional_design.md) に明記する。
- UI wording safety review: [07_UI_Wording_Policy.md](./07_UI_Wording_Policy.md) に従い、売買指示に見える表現を避け、判断補助・確認候補・比較材料として表現する。
- Score hierarchy clarification: Investment Score、Screening、Forecast agreement、Risk、Data Quality、Database Fit、Metadata Confidence、Research Evidence の関係を、実装修正前に仕様として整理する。
- Distribution readiness preparation: 配布準備は future step とし、まず仕様バグ・UXバグ・投資助言に見える表現を棚卸しする。

Scope:

- `銘柄コックピット` の Yahoo live data 取得、失敗時診断、価格・予測・Investment Score 表示を確認する。
- `銘柄ランキング` の候補条件、ランキング cache、`重視して並べ替え` での表示順変更、部分失敗時の除外表示、深掘り導線を確認する。
- `リバランス` の入力、target allocation、allocation comparison、risk breach 表示を確認する。
- UI 文言が「判断補助」で統一されているか確認する。
- 新機能は追加せず、必要な不具合修正とドキュメント同期だけ行う。

Completion criteria:

- Streamlit browser smoke の確認結果が作業ログまたは引き渡しサマリに残っている。
- `tools/run_local_checks.py` が通る。
- provider 失敗時に raw provider noise ではなく SMAI の診断情報として表示される。
- Rebalance / ranking / cockpit の主要導線が壊れていない。

### 5.3 Phase 17: UI Polish And Ranking Condition Redesign

Status: implementation complete; Streamlit visual smoke completed

目的: `銘柄ランキング` を、単なる検索フィルターではなく、投資対象と投資スタイルを先に決めてから詳細条件を設定する UI に整理する。MVP は株式・ETF中心とし、投資信託は将来対応に回す。

Planned scope:

- Ranking condition model
  - 地域: `国内` / `米国` / `全体`
  - 商品: `株式` / `ETF`
  - 投資スタイル: `配当重視` / `成長重視` / `割安重視` / `安定重視` / `トレンド重視`
  - UI label と internal key を分離した enum / constants / condition object
- UI structure
  - ranking screen の上部で地域・商品・投資スタイルを選択
  - 初期表示は候補が広がりすぎない `国内` + `株式`
  - 地域 × 商品に応じて詳細条件を動的に切り替え
  - 候補数を見せてから Yahoo live data ranking を実行
- Separation of responsibility
  - 投資スタイルは Investment Score の weight preset / sort intent として扱う
  - 詳細条件は provider fetch 前の candidate filter として扱う
  - `総合おすすめ` のような推奨に見える表現は避け、投資判断補助として表現する
- Phase 1 filter coverage
  - 株式: 地域、業種/セクター、時価総額、配当利回り、PER、PBR、ROE、NISA
  - ETF: 地域、投資対象、連動指数、信託報酬/経費率、分配金利回り、複雑さ
  - 投信: MVP 対象外。source seed / metadata schema は future extension として残すが、ranking UI と default universe から除外する
  - Risk / 値動きの大きさは、取得期間の価格データに依存するため ranking result / score breakdown 側で扱う
- Future-ready filter definitions
  - 国内株式: 投資スタイル、業種、時価総額、配当利回り、PER、PBR、ROE、売買代金
  - 米国株式: 投資スタイル、セクター、時価総額、配当利回り、PER、売上成長率、EPS成長率、Beta、ボラティリティ
  - 全体 × 株式: 地域、投資スタイル、業種/セクター、時価総額、配当利回り、PER、ROE、リスク
  - ETF: 投資対象、地域、連動指数、信託報酬/経費率、分配金利回り、純資産総額、流動性、為替ヘッジ、複雑さ
  - 投信: Future phase で、ウォッチリスト、CSV取込、基準価額チャート、Provider連携、投信ランキングを検討する

Implementation rules:

- 既存 `data/marketdata/symbol_universe.csv` で判定できる条件だけを実フィルタとして有効化する。
- 未取得の `売買代金`、`売上成長率`、`EPS成長率`、`Beta` などは、無理に計算せず future metadata として定義・文書化する。投信の `純資産総額`、`NISA対応`、`積立可否` は source-import seed で保持できるが、MVP UI / ranking では使わない。
- `大型株`、`リスク`、`複雑さ` などの曖昧な UI 表現は、内部的に数値しきい値または明示フラグへ変換できる設計にする。
- ETF と投信は internal model で分離する。MVP UI は株式 / ETF のみ表示する。
- docs / tests / UI wording policy と矛盾しないよう、実装時に operations guide と必要な設計文書を同期する。

Completion criteria:

- 地域・商品・投資スタイルの分類が定義されている。
- 商品・地域に応じて詳細条件が切り替わる。
- 投資スタイルと詳細条件の役割が UI / code / docs で分離されている。
- Phase 1 で実データに基づき有効な条件と、future metadata 条件が区別されている。
- 「おすすめ」ではなく、判断材料を整理する ranking として文言が統一されている。
- UI helper tests または deterministic filtering tests が追加・更新されている。

Current implementation note:

- `ui/ranking.py` defines region / product / investment-style labels separately from internal keys.
- `銘柄ランキング` now shows region / product / investment style before provider / period, derives the display weight preset from investment style, and shows dynamic detail filters for stock / ETF categories.
- The detail filter panel is grouped into attribute / numeric / keyword sections, and the comparison-symbol selector stays all-selected by default while its large multiselect tags are kept inside a collapsed expander.
- Acquisition period, candidate count, selected count, and all/partial selection status are shown as a compact one-line comparison status.
- Current enforceable filters remain limited to `symbol_universe.csv` metadata. Default ranking universe is stock / ETF only. 投信 seed/source import は将来対応 metadata として残すが、MVP ranking UI には表示しない。
- Streamlit visual smoke for the Phase 17 ranking-condition UI has been completed by the user.

### 5.4 Phase 18: Symbol Universe And Metadata Refresh

Status: implementation complete; ongoing source refresh is operational maintenance

目的: Ranking condition UI の裏側にある銘柄 universe を、固定 CSV だけでなく、鮮度と出所を管理できる metadata layer に拡張する。

Scope:

- `symbol_universe.csv` の列定義を整理し、地域、商品、業種/セクター、時価総額 tier、配当、PER/PBR/ROE、ETF属性、future 投信属性、metadata freshness を明確化する。
- ranking universe は、当面 SBI証券で取り扱いがあり、現物・NISA・長期投資で検討しやすい商品を初期前提にする。
- CSV / fixture を deterministic baseline として維持する。
- Yahoo fundamentals や将来 provider から metadata を更新する明示 opt-in command を設計する。
- UI / command の初期 default は Yahoo としつつ、内部実装は Yahoo 専用に固定しない。
- 更新結果は cache / CSV / manifest として保存し、通常テストは network 非依存にする。
- 古い metadata、欠損 metadata、future-only metadata を UI で区別する。

Provider policy:

- Yahoo first, not Yahoo only. 画面上の既定 provider と metadata refresh の初期 provider は `yahoo` とする。
- Internal refresh logic は `MetadataProvider` 風の adapter 境界を持たせ、Yahoo 固有の取得・変換・失敗処理を service 本体へ埋め込まない。
- `metadata_source` / manifest / validation result に provider 名、更新日時、成功/失敗件数、更新対象列を残す。
- Future provider として FMP / EODHD / Alpha Vantage / Polygon などを追加できる構造にする。初期実装で複数 provider を実装する必要はない。
- 通常テストと CI は `csv` / fixture / fake provider を使い、live provider smoke は明示 opt-in のまま分離する。

Universe policy:

- 詳細方針は [09_SBI_Symbol_Universe_Policy.md](./09_SBI_Symbol_Universe_Policy.md) を参照する。
- MVP対象は国内株式、米国株式、国内ETF、米国ETF/海外ETF とする。
- 投資信託、ADR、REIT、FX、CFD、先物・オプション、暗号資産、債券、外貨建MMF、貴金属・コモディティ系ETF、レバレッジ、インバースは初期 ranking から除外する。
- `broker`, `tradability`, `nisa_category`, `investment_style`, `is_sbi_supported`, `is_active`, `is_leveraged`, `is_inverse` は `symbol_universe.csv` / schema に保持する。
- local curated / source-import seed は conservative default として `tradability=unknown` を持てる。SBI取扱確認済み master ではないため、初期 policy では `unknown` を通し、`not_tradable` や明示的な対象外 flag だけを除外する。
- SMAI は初期段階で SBI 証券サイトを直接スクレイピングしない。SBI / JPX / NISA 一覧などを source CSV 化し、local master に取り込む。投信協会 / 投信CSV / 基準価額は Future Phase とする。
- 現在の `symbol_universe.csv` は SecurityMaster 相当の local master として扱う。専用 `SecurityMasterRepository` は、API / UI / batch で共通 loader が必要になった段階で `backend/marketdata/security_master/` などへ昇格する。

Implementation order:

1. Network-free schema / validation / Settings status. 完了。
2. Metadata source / freshness columns and summary. 完了。
3. Provider-neutral refresh contract and fake/curated provider test. 完了。
4. Dry-run first refresh command with manifest output. 完了。
5. Metadata field catalog / tier / storage / freshness policy. 完了。
6. Yahoo metadata provider as the first live adapter, behind explicit opt-in. 完了。
7. `--write` path for CSV/manifest update, with validation before and after write. 完了。Cache output is future scope if needed.
8. Local source import for JPX / curated universe expansion. 完了。Initial JPX ETF seed and domestic stock seed imported.
9. SBI ranking universe policy columns and default exclusion helper. 完了。Unknown tradability is allowed by default.
10. SBI / NISA / future 投信 metadata source import. 完了。`--source-profile`、JPX stock/ETF/REIT profile、SBI US stock/ETF seed、NISA eligibility update profile/seed、ranking metadata update profile、mutual fund seed、投信 metadata columns の import path は追加済み。JPX / SBI / NISA / IMAJ / REIT source builders and imports are available, Yahoo live coverage / opt-in metadata refresh has been run for SBI US stock / ETF, and ETF enrichment plus overseas ETF `yahoo_symbol` mapping are implemented. MVP ranking remains stock / ETF only; REIT / mutual fund seed rows are future-extension metadata. Ongoing source refresh and extra live smoke are operational maintenance.
11. SecurityMaster repository separation only if symbol master usage spreads beyond current UI / command helpers.
12. Optional additional provider adapters only when Yahoo coverage or stability is insufficient.

Completion criteria:

- ranking filters が参照する metadata schema が文書化されている。
- metadata freshness / source が内部的に保持できる。
- metadata refresh の provider contract があり、初期 live provider が Yahoo でも provider 差し替え余地が残っている。
- 通常 checks は live provider なしで通る。
- live metadata refresh は明示 opt-in で、失敗しても既存 UI/API を壊さない。
- SBI前提の ranking universe policy が文書化され、schema / tests / ranking 候補抽出へ接続されている。

Operational maintenance after completion:

- NISA / ETF / stock metadata source の継続更新は、Phase 18 の未完了実装ではなく運用タスクとして扱う。
- 残る `risk_band` / `market_cap_tier` / dividend gaps は provider/source 欠損として空欄を許容し、確認済み source または明示 opt-in refresh が得られた時だけ更新する。
- 11件の海外ETF `yahoo_symbol` mapping live smoke は、network 利用可能時の任意運用確認とする。

Current implementation note:

- `ui/symbol_universe.py` defines the current required CSV columns, optional freshness/source columns, enum values, decimal fields, and duplicate ticker validation.
- Phase 16 UI now uses the local symbol master in both ranking and cockpit: ranking rows open a shared symbol-detail modal, the cockpit has a `銘柄データを見る` button next to symbol selection, and post-fetch cockpit results include an investment memo built from score, symbol metadata, valuation, income, and price-trend checks.
- Ranking modal rendering avoids per-row repeated symbol-master scans by reusing a symbol lookup map while building display rows; this keeps long-period ranking result clicks responsive.
- `backend/marketdata/symbol_metadata_schema.py` defines metadata tiers, storage policy, source/freshness requirements, enum values, decimal ranges, and future fund metadata fields.
- `symbol_universe.csv` now stores `metadata_source`, `metadata_as_of`, and `metadata_updated_at`; the current deterministic baseline is marked as `curated_csv` with `2026-05-18` metadata.
- `設定 / データ情報` shows candidate count, metadata source, metadata period, validation summary, and issue rows for `symbol_universe.csv` without blocking the existing ranking UI.
- `backend/marketdata/symbol_metadata_refresh.py` defines the provider-neutral refresh contract, deterministic `curated_csv` provider, provider diagnostics, manifest summary, and validation summary.
- `tools/refresh_symbol_universe_metadata.py` runs dry-run by default and can write CSV / `symbol_universe_manifest.json` only with `--write`; write is refused when post-refresh validation has errors.
- Yahoo live metadata provider is available through `--provider yahoo --allow-live`; it maps selected ticker metadata into catalog fields and records per-symbol failures in the manifest. Normal checks remain network-free.
- `tools/build_symbol_universe_source.py` converts official raw files into local source CSVs. It supports JPX listed-stock raw Excel (`.xls` / `.xlsx`) / CSV for `--source-profile jpx_listed_stock`, JPX ETF / ETN raw Excel (`.xls` / `.xlsx`) / CSV / official HTML for `--source-profile jpx_etf`, JPX REIT official HTML for `--source-profile jpx_reit`, SBI US stock / US ETF raw CSV/Excel/CP932 HTML for `--source-profile sbi_us_stock` / `sbi_us_etf`, and NISA eligibility raw CSV/Excel for `--source-profile nisa_eligibility`. JPX listed-stock builder maps `規模区分` into `market_cap_tier` for the ranking UI. SBI stock builder skips ETF rows embedded in the official stock page; SBI ETF builder imports source ticker and can keep a provider-specific `yahoo_symbol` mapping for non-US exchange codes. ETF builders preserve commodity theme and leveraged / inverse flags so ranking policy can exclude them. NISA builder supports JPX/IMAJ growth-NISA Excel headers with furigana, treats that list as growth-eligible, normalizes IMAJ 5-digit listed-fund codes ending in `0`, and preserves ambiguous rows as `unknown` instead of over-inferring a category. PDF raw files are not part of the routine import path.
- `backend/marketdata/symbol_universe_import.py` and `tools/import_symbol_universe_source.py` merge local source CSV rows into `symbol_universe.csv` with dry-run, manifest, append-only default, optional existing-row update, import defaults, symbol suffix normalization, and validation-before/write.
- `data/marketdata/symbol_universe_sources/jpx_etf_seed.csv` and `jpx_stock_seed.csv` are the first source seeds. 2026-05-19 時点では JPX source として国内株 / 国内 ETF 合計 68件を `symbol_universe.csv` に取り込んでいる。
- SBI証券取扱商品を初期 ranking universe の前提にする policy columns / default exclusion helper を追加した。現時点の CSV は SBI取扱確認済み master ではなく local curated / source-import seed として扱うため、`tradability=unknown` は初期 ranking で通す。
- SBI銘柄マスタ取得方針は、SBI から直接リアルタイム取得するのではなく、SBI / JPX / public source を local source CSV 化して import する。将来 adapter は source import / repository 境界に追加し、ranking logic から分離する。
- `tools/import_symbol_universe_source.py` supports `--source-profile jpx_listed_stock|jpx_stock|jpx_etf|jpx_reit|sbi_us_stock|sbi_us_etf|nisa_eligibility|ranking_metadata|mutual_fund_seed`, filling market/product/currency and policy defaults. `nisa_eligibility` updates only NISA metadata columns for existing rows and rejects unknown symbols instead of appending incomplete rows. `ranking_metadata` updates only existing symbols' ranking filter fields such as PER/PBR/ROE/dividend yield, market-cap tier, risk, and ETF expense ratio. `nisa_eligibility_seed.csv` has updated 31 existing rows. `sbi_us_stock_seed.csv`, `sbi_us_etf_seed.csv`, and `mutual_fund_seed.csv` are available as source seeds. 2026-05-21 時点で JPX listed-stock source、JPX ETF/ETN official HTML source、SBI US stock/ETF official HTML source、JPX REIT official HTML source、JPX NISA 成長投資枠 ETF/ETN source、IMAJ NISA 成長投資枠 listed-fund source を取り込み、candidate master は 9,179件になり、stock 8,081件、ETF 1,034件、REIT 58件、投信 4件、ADR 2件を持つ。SBI US stock builder は `BRKB` / `UHALB` を `BRK-B` / `UHAL-B` に正規化する。
- `tools/check_symbol_universe_metadata_coverage.py` produces `data/marketdata/symbol_universe_metadata_coverage.json` as the current coverage baseline for ranking filter metadata. JPX and SBI stock rows have been supplemented with explicit opt-in Yahoo metadata where available. Current stock coverage is dividend yield 8,033/8,081, PBR 7,630/8,081, ROE 7,466/8,081, and PER 7,457/8,081. ETF coverage is dividend yield 601/1,034, index family 1,034/1,034, expense ratio 1,013/1,034, and complexity 1,034/1,034.
- Yahoo dividend-yield normalization now treats JP stock integer percent values as percent values, preventing over-scaled display such as `23%` when the source value represents `0.23%`.
- `tools/analyze_yahoo_coverage_failures.py` analyzes saved live Yahoo coverage rows without making new network calls. Current SBI US stock failures are 51 no-bars/Yahoo-unsupported plus 2 resolved aliases; SBI US ETF failures are 3 leveraged exclusions plus 11 rows with curated `yahoo_symbol` mappings.
- Ranking UI and default ranking universe are stock / ETF focused. REIT and mutual-fund rows can remain in the local master as future extension data, but `reit` / `mutual_fund` / `fund` / `investment_trust` are excluded from MVP ranking candidates. ETF leveraged/inverse rows and commodity-themed ETF rows remain stored for metadata coverage but are excluded by the ranking-universe policy.
- Ranking sort logic now uses Phase 18 symbol metadata as part of the post-fetch score: selected ranking purpose maps to a purpose-specific profile (`配当・インカム重視`, `成長性重視`, `割安性重視`, `安定性重視`, `トレンド重視`), and each profile blends market/forecast/risk signals with `database_fit_score` and `metadata_confidence_score`.

### 5.5 Phase 19: Decision Report Context MVP

Status: complete

目的: `銘柄コックピット`、`銘柄ランキング`、`リバランス` の結果を、同じ context schema で保存・表示・export できるようにする。

Scope:

Implemented slice:

- `backend/reporting` に Decision Report context v1 と deterministic Markdown / manifest helper を追加。
- cockpit / ranking / rebalance 由来の summary / table rows / warnings / notes を local-first に束ねる最小 schema を追加。
- Phase 18 の銘柄 metadata 整備を踏まえ、`Data coverage and confidence`、`Symbol metadata`、`Decision checkpoints` の標準 report section builder を追加。
- 銘柄コックピットとランキング結果に `Decision Report` expander を追加し、Markdown / JSON download と Markdown preview を確認できるようにした。
- リバランス結果に `投資判断レポート` expander を追加し、現在保有、目標配分、配分差分、売買案、Risk 制約違反、確認ポイントを同じ context schema で Markdown / JSON export できるようにした。
- cockpit / ranking / rebalance の Decision Report に manifest / ZIP download を追加し、context JSON、manifest JSON、Markdown を同じ export package として保存できるようにした。

Report output policy:

- 冒頭では銘柄、作成日時、対象期間、provider、利用元 workflow、非推奨文言を明示する。
- `Data coverage and confidence` では、価格データ期間、data quality、metadata source/as-of、欠損 field、coverage rows を出す。未確認 metadata は 0 と扱わず、空欄の理由として残す。
- `Symbol metadata` では、ticker/name、市場、商品分類、NISA、investment style、時価総額 tier、SBI/ranking policy、metadata freshness を出す。
- `Investment score breakdown` では、Investment Score、Screening、Forecast agreement、Data quality、Risk signal と、その上下要因を出す。
- `Valuation / income / risk` では、PER/PBR/ROE、配当利回り/配当カテゴリ、ETF expense ratio/index family、risk band、warnings を出す。
- `Ranking context` では、順位、並べ替え条件、比較対象数、上位理由、同条件での注意点を出す。
- `Rebalance context` では、risk breach、提案 trade、制約、注文指示ではないことを出す。
- `Decision checkpoints` では、次に確認する業績、決算、配当方針、ETF 指数/経費率、データ欠損を整理し、売買指示にしない。

- cockpit summary / ranking result / ranking error / rebalance result / risk breach を横断する report context contract を定義する。
- 初期 export は Markdown / JSON / CSV / manifest / ZIP を優先する。
- UI リッチな PDF report / Excel report は Phase 19 の完了条件に含めず、将来の Advanced Export として残す。
- UI / report / future assistant が同じ context を参照できるようにする。
- 投資助言ではなく、判断材料と制約を整理する report 文言に統一する。

Completion criteria:

- Decision Report context の最小 schema が定義されている。
- Phase 18 metadata を活かした data confidence / symbol metadata / decision checkpoints の標準 section を作れる。
- cockpit / ranking / rebalance の既存出力から report context を作れる。
- deterministic renderer で Markdown / JSON export ができる。
- report に data quality、provider、対象期間、制約、非推奨文言が含まれる。

### 5.6 Phase 20: Research RAG Evidence Layer

Status: implementation complete; local evidence slice complete

Research freshness principle:

- SMAI の通常 tests / CI は deterministic-first を維持するが、Research RAG と News RAG の product value は情報鮮度が中心になる。
- 実運用では `AI調査を更新` が外部の最新IR・開示・ニュース・provider evidence を取得/参照する標準アクションになる。通常 tests / CI は network 非依存の fake adapter / fixture で確認する。
- 外部 evidence は既定では取得時の一時参照として扱う。RAG summary / Research Score / News 表示には使うが、取得本文・変換Markdown・manifestを自動保存しない。画面やReportには source URL、provider、published_at、fetched_at、freshness_status、短い要約/引用範囲だけを残し、古い情報は warning として表示する。

Current implementation direction:

- Phase 20 は、RAG で銘柄を推奨したりランキング順位を直接変えたりする段階ではなく、既存の `銘柄コックピット` / `銘柄ランキング` / `Decision Report` に資料根拠を添える evidence layer として実装する。
- Phase 20 の local document ingestion は deterministic foundation / fixture path として残す。今後の通常ユーザー導線では、source adapter 経由で公式IR、EDINET / TDnet、company IR site、provider profile、news などを取得/参照する。
- 9,179件の銘柄DB全体を一括RAG対象にせず、ランキング後の上位候補、コックピットで選択した銘柄、Decision Report の対象銘柄から段階的に使う。
- 初期出力は `Research Summary`、`Research Evidence`、`Research Data Quality` を中心にする。資料がない銘柄では「根拠不足」を明示し、推定で埋めない。
- `Research Score` と Investment Score / ranking への重み統合は Phase 22 に回す。

Recommended MVP slice:

- R0: Research RAG design cleanup。`Documents/04_Detail_Design/04-8_Onepager_Research_RAG.md` の文字化け部分を、Phase 20 方針に沿って読める日本語へ整える。
- R1: Local Document Ingestion MVP。`backend/research/` に document metadata contract と ingestion service を追加し、`data/research_docs/` 配下の Markdown / Text / CSV fixture を登録できるようにする。
- R2: Text Extraction & Chunk Store。ローカル資料を source / title / published_at / section / chunk_index / reliability と紐づく検索可能 chunk に分割する。
- R3: Keyword Retrieval MVP。symbol と query から evidence chunk を返す deterministic keyword search を実装する。top_k、freshness、source_type、reliability を保持する。
- R4: Research Summary MVP。コックピット向けに、成長材料、株主還元、事業リスク、財務安全性、確認不足を evidence 付きで要約する。LLM は使わず rule / template を既定にする。
- R4.5: UI / Report integration。銘柄コックピットに Research Summary を追加し、ランキングには「根拠あり / 最新資料が古い / 根拠不足」の状態だけを軽く表示する。Decision Report には Research Evidence section を追加する。

Current implemented slice:

- `backend/research` provides local UTF-8 document ingestion, hash dedupe, chunking, freshness-aware keyword evidence search, source-type filtering, deterministic Research Summary, and data-quality warnings for missing, stale, and low-reliability evidence.
- `設定 / データ情報` has a `Research RAG / 根拠資料` expander for session-local Markdown / Text / CSV upload and registration.
- `銘柄コックピット` shows a `Research Evidence / 根拠資料` section with an explicit `AI調査を更新` operation card; price-data fetch does not automatically run Research RAG. The summary uses decision-oriented metric cards and vertical evidence cards, while source documents, retrieval quality, and detailed evidence rows stay inside a collapsed detail-data expander.
- `銘柄ランキング` row-click `銘柄データ` modal has an `AI Research` tab with an explicit `AIで資料を確認` button. It reuses the same Research Summary panel for growth, shareholder return, financial safety, business risk, confirmation gaps, source document names, dates, and evidence counts.
- `銘柄ランキング` result cards, detailed table, and selected-candidate breakdown show a lightweight Research Evidence status (`根拠あり` / `最新資料が古い` / `根拠不足`) from registered local documents and already fetched Research reports. This does not change ranking order and does not automatically run full Research RAG analysis for every symbol.
- Cockpit Decision Report includes `Research Evidence` only when `AI調査を更新` has produced a report and registered documents or evidence exist, so existing no-document reports remain unchanged.

Recommended completion criteria:

- fake external adapter / local fixture だけで ingestion -> chunk -> keyword search -> Research Summary が動く。
- 通常 tests は external scraping / external LLM / network に依存しない。
- evidence は source_type、title、published_at、section/page、excerpt、relevance、reliability と紐づく。
- コックピットでは選択銘柄の Research Summary と evidence を確認できる。
- ランキングではRAG結果で順位を直接変えず、選択候補の根拠状態を確認できる。
- Decision Report では Research Evidence section と根拠不足 warning を表示できる。
- Research data quality は document_count、latest_document_date、evidence_count、warnings を含む。

目的: 価格・テクニカル指標だけでは拾いにくい長期企業分析の根拠を、local-first な document evidence layer として追加する。

Implementation order:

- R0: 要件・詳細設計。`04-8_Onepager_Research_RAG.md` は design complete。
- R1: Local Document Ingestion MVP。
- R2: Text Extraction & Chunk Store。
- R3: Keyword Retrieval MVP。
- R4: Research Summary MVP。

Completion criteria:

- local document / fixture だけで ingestion、chunk、検索、summary が動く。
- 通常 tests は外部 scraping / external LLM に依存しない。
- evidence は source、timestamp、section、confidence と紐づく。
- UI / report では根拠不足を明示できる。

### 5.7 Phase 21: Advanced Research RAG - Evidence Extraction And Grounded Answers

Status: planned; query expansion / structured extraction / grounded answer / retrieval quality / evidence reranker first slices started

Purpose:

- Phase 20 の local-first Research Evidence layer を壊さず、登録済み Research 資料から欲しい情報を抽出し、抽出結果と ResearchEvidence を必ず紐づける。
- 銘柄コックピット、ランキングの `AI Research` tab、Decision Report で、根拠付きの自然な説明文を表示できるようにする。
- keyword search baseline を維持しながら、query expansion、optional embedding / vector store / hybrid search、evidence reranking を追加できる設計にする。
- Research Score 統合に向けて、根拠数、鮮度、信頼度、source type、根拠多様性を扱える中間 contract を整える。
- Phase 21 でも RAG 単体で売買推奨、buy / sell / hold 判断、ランキング順位や Investment Score の直接変更は行わない。

Phase 20 / Phase 21 boundary:

- Phase 20: local document registration, chunking, deterministic keyword search, Research Evidence, Research Summary, Decision Report connection.
- Phase 21: query expansion, structured evidence extraction, grounded answer generation, optional embedding retrieval, local vector store abstraction, hybrid search, evidence reranking, Research Score integration preparation.
- Phase 21.5: Stock News RAG MVP. Existing Symbol Cockpit に、選択中の銘柄だけを対象にした URL 根拠付き recent news summary を追加する。市場全体ニュース画面、Research Score 化、Investment Score / ranking order への反映は行わない。
- Research Score の採点と Investment Score / ranking / report への score 統合は Phase 22 で扱う。

Scope:

- Structured evidence extraction: `growth`, `shareholder_return`, `financial_safety`, `business_risk`, `confirmation_gap` の観点で、ResearchChunk / ResearchEvidence から主張、要約、不足情報、注意点を抽出する。
- Data contracts: `ResearchExtractedClaim`, `ResearchRetrievalCandidate`, `ResearchRetrievalQuality`, `ResearchEmbedding` などの Pydantic contract 案を整理する。抽出した claim は supporting evidence と切り離さない。
- Query expansion: `config/research_query_terms.yml` などで、成長戦略、株主還元、財務安全性、事業リスク、確認不足に関する表現ゆれを deterministic に管理する。
- Optional embeddings: `ResearchEmbeddingService` を候補とし、既定では disabled。local provider / cache を優先し、外部 embedding API は explicit opt-in にする。
- Local vector store: file-based cache または sqlite-based store を MVP 候補にする。cloud vector DB や heavy dependency は必須にしない。
- Hybrid retrieval: keyword / vector / freshness / reliability / source priority / diversity を組み合わせる `HybridResearchRetrievalService` を候補にする。vector failure 時は keyword fallback + warning とする。
- Evidence reranking: `ResearchEvidenceReranker` で relevance、reliability、freshness、official-source priority、diversity、duplicate suppression を扱う。
- Grounded answer generation: `ResearchGroundedAnswerService` を候補とし、default は template-based generation。LLM generation は optional adapter とし、Evidence にない内容を生成しない。
- UI / Decision Report: Cockpit、ranking modal、Decision Report に Research Summary、観点別抽出結果、Evidence table、Data Quality、Retrieval Quality、Grounded Answer、根拠不足 warning、非推奨注記を表示する方針を整理する。

Current implemented slice:

- Deterministic query expansion baseline is implemented in `backend/research` with `ResearchQueryExpansionService`, `ResearchQueryExpansionResult`, category-aware `ResearchSearchRequest`, and `config/research_query_terms.yml`.
- Structured extraction first slice is implemented with `ResearchExtractedClaim` and `CompanyResearchReport.extracted_claims`. Non-gap claims are generated only from supporting evidence; missing category evidence becomes `confirmation_gap` without changing scoring or ranking.
- Template grounded answer first slice is implemented with `ResearchGroundedAnswerService` and `CompanyResearchReport.grounded_answer`. It uses only extracted claims and referenced evidence, keeps warnings, and explicitly states that the output is not a buy/sell recommendation.
- Retrieval quality first slice is implemented with `ResearchRetrievalQuality` and `CompanyResearchReport.retrieval_quality`. It records the keyword backend, category query set, expanded terms, candidate count, evidence count, and retrieval/data-quality warnings for UI and Decision Report display.
- Evidence reranker first slice is implemented with `ResearchEvidenceReranker`. It keeps `ResearchEvidence` output compatible while deterministically reranking by relevance, reliability, freshness, source-type priority, and duplicate suppression.
- UI / Decision Report display first slice is implemented: cockpit and ranking Research Summary panels now show grounded answer and retrieval quality rows, the detail expander shows extracted claims, and the Research Evidence report section carries grounded answer, retrieval quality, and extracted claim rows without changing ranking or scoring behavior.
- Optional vector / hybrid retrieval first slice is implemented with `ResearchEmbedding`, `ResearchRetrievalCandidate`, `ResearchDisabledVectorStore`, `ResearchHybridScoreWeights`, and `ResearchHybridScorer`. The default vector store remains disabled and returns a retrieval-quality warning; hybrid scoring is deterministic and not wired into the default keyword search path yet.
- Local embedding generation first slice is implemented with `ResearchEmbeddingService`. It generates deterministic hash-based local vectors for `ResearchChunk` text and query text, records `text_hash` / `embedding_model` cache-key fields, and can explicitly upsert generated embeddings into writable vector stores without using external embedding APIs.
- Optional vector-index build workflow first slice is implemented with `ResearchVectorIndexService` and `ResearchVectorIndexSummary`. It rebuilds a writable vector store from already chunked local Research documents, reports chunk / embedded counts and missing text-index warnings, and keeps vector indexing as an explicit optional step.
- Keyword-fallback hybrid retrieval wrapper first slice is implemented with `HybridResearchRetrievalService`. When vector candidates are available it converts hybrid-scored candidates back to `ResearchEvidence`; when vector search is disabled or empty it falls back to the existing keyword retrieval and records fallback warnings in retrieval quality.
- In-memory local vector store first slice is implemented with `ResearchInMemoryVectorStore`. It stores `ResearchRetrievalCandidate` + `ResearchEmbedding` pairs, searches by optional `ResearchSearchRequest.query_vector` with deterministic cosine similarity, filters by symbol/source type, and reports vector retrieval quality without external dependencies.
- File-backed vector cache first slice is implemented with `ResearchFileVectorStore`. It persists the same vector candidate / embedding pairs as UTF-8 JSONL, reloads them across service instances, reports empty or invalid cache conditions through Research search errors / retrieval-quality warnings, and keeps the default keyword retrieval path unchanged.
- `ResearchRetrievalService` can expand category queries while preserving Phase 20 keyword search behavior when no category or expanded terms are supplied.
- `ResearchAnalysisService` uses category-aware expansion for the existing growth / shareholder_return / financial_safety / business_risk topic searches.

Candidate contracts:

```python
class ResearchExtractedClaim(BaseModel):
    schema_version: str = "research-extraction-v1"
    symbol: str
    category: Literal[
        "growth",
        "shareholder_return",
        "financial_safety",
        "business_risk",
        "confirmation_gap",
    ]
    claim: str
    summary: str
    supporting_evidence: list[ResearchEvidence]
    confidence: Decimal
    missing_information: list[str] = []
    caution_note: str | None = None

class ResearchRetrievalCandidate(BaseModel):
    symbol: str
    document_id: str
    chunk_id: str
    title: str
    source_type: str
    published_at: date | None = None
    section_title: str | None = None
    excerpt: str
    keyword_score: Decimal | None = None
    vector_score: Decimal | None = None
    freshness_score: Decimal | None = None
    reliability: Decimal
    final_relevance_score: Decimal
    retrieval_backend: Literal["keyword", "vector", "hybrid"]

class ResearchRetrievalQuality(BaseModel):
    backend: Literal["keyword", "vector", "hybrid"]
    query: str
    expanded_terms: list[str]
    candidate_count: int
    evidence_count: int
    warnings: list[str]
```

Config direction:

```yaml
research:
  retrieval:
    backend: keyword # keyword|vector|hybrid
    top_k: 8
    keyword_weight: 0.45
    vector_weight: 0.45
    freshness_weight: 0.05
    reliability_weight: 0.05
  embeddings:
    enabled: false
    provider: local
    model: null
    cache_dir: data/research_embeddings
  vector_store:
    enabled: false
    provider: local
    path: data/research_vector_store
  query_expansion:
    enabled: true
    dictionary_path: config/research_query_terms.yml
  grounded_answer:
    enabled: true
    provider: template # template|llm
    allow_llm: false
  scoring:
    enabled: false
    default_weight_in_investment_score: 0.0
```

Guardrails:

- RAG output は売買推奨ではなく、判断材料、根拠、注意点、確認不足の整理に限定する。
- Evidence がない主張を生成しない。根拠不足は `confirmation_gap` として明示する。
- 資料がない銘柄を悪い銘柄として扱わない。
- 外部 LLM / 外部 embedding API / 外部 vector DB は explicit opt-in とし、通常 CI は network / scraping / external API に依存しない。
- 公式 IR や開示資料を provider snapshot より優先する。
- 長文の丸写しを避け、短い引用または要約に留める。
- Investment Score への統合は Phase 22 以降で、明示的に有効化された場合のみ行う。

Test plan:

- Unit: query expansion、ResearchExtractedClaim validation、embedding cache key generation、vector store disabled mode、hybrid score calculation、evidence reranking、template answer generation、confirmation_gap generation。
- Integration: sample Markdown/Text/CSV -> chunk -> keyword search -> query expansion -> evidence extraction -> grounded answer -> Decision Report section。
- Fallback: embedding disabled 時は keyword search のみで動作、vector store failure 時は keyword fallback、LLM disabled 時は template answer、evidence 不足時は confirmation_gap。
- Golden: 既知の Research fixture から期待するカテゴリ別抽出、warning、根拠のない主張を生成しないことを確認。
- CI: 外部 API、外部 LLM、live scraping、network に依存しない deterministic fixture を使う。

Acceptance criteria:

- Phase 21 として「高度Research RAG - 根拠抽出・根拠付き回答生成」がロードマップと詳細設計に追加されている。
- Phase 20 の keyword search baseline と local-first / deterministic-first 方針を壊していない。
- embedding / vector / hybrid search が optional として整理されている。
- query expansion、ResearchExtractedClaim、Grounded Answer、Retrieval Quality、UI / Decision Report 反映方針が明記されている。
- LLM 利用は optional adapter として明記され、通常 CI が外部 API や network に依存しない方針が維持されている。

### 5.7.5 Phase 21.5: Stock News RAG MVP

Status: first local deterministic slice implemented

Purpose:

- まずは既存の `銘柄コックピット` に、選択中の銘柄だけを対象にした個別銘柄ニュース深掘りを小さく追加する。
- Research Evidence 内の `ニュースのみ再取得` を候補とし、AI調査更新時または専用ボタン押下時に、銘柄名、ticker、related keywords から news evidence を取得・整理する。
- 根拠 URL 付きの最新ニュース要約、投資観点、材料の方向感、鮮度を表示するところまでを MVP とする。
- ニュースは投資判断補助情報であり、売買推奨、buy / sell / hold 判断、Investment Score、ranking order の変更には使わない。

Initial display fields:

- `title`
- `url`
- `source`
- `published_at`
- `summary`
- `investment_viewpoint`
- `sentiment_for_investment`
- `freshness_status`

Initial data contract sketch:

```python
class StockNewsEvidence:
    symbol: str
    company_name: str | None
    title: str
    url: str
    source: str | None
    published_at: date | None
    summary: str
    investment_viewpoint: Literal[
        "earnings",
        "growth",
        "shareholder_return",
        "risk",
        "macro",
        "other",
    ]
    sentiment_for_investment: Literal[
        "positive",
        "negative",
        "neutral",
        "mixed",
        "unknown",
    ]
    freshness_status: Literal[
        "latest",
        "recent",
        "stale",
        "unknown",
    ]
```

Initial classification policy:

- `investment_viewpoint`: `earnings`, `growth`, `shareholder_return`, `risk`, `macro`, `other` に絞り、初期分類を増やしすぎない。
- `sentiment_for_investment`: `positive`, `negative`, `neutral`, `mixed`, `unknown` とし、buy / sell / hold ではなくニュース材料の方向感として扱う。
- `freshness_status`: `latest`, `recent`, `stale`, `unknown` とし、古いニュースを最新材料のように扱わない。

Phase 21.5 out of scope:

- 新しい `投資ニュース` 画面の実装
- 市場全体トピックの自動抽出
- 注目ジャンル / 業界ランキング
- 関連銘柄の自動抽出
- Watchlist 連動
- Decision Report への自動反映
- Research Score 化
- Investment Score への反映
- ranking order への反映
- ニュースクラスタリング
- impact horizon 分類
- 外部 LLM 必須化
- CI での外部ネットワーク必須化

Guardrails:

- source URL がない内容を断定しない。
- 古いニュースは warning または `freshness_status` で明示する。
- 外部ニュース取得は adapter 化し、`AI調査を更新` / news refresh の標準 source として扱う。
- 通常 tests / CI は external network、live scraping、external LLM に依存させない。
- 外部 LLM は必須にせず、template / deterministic fallback を維持する。
- RAG の出力は投資判断補助であり、最終判断はユーザーが行う。

Current implemented slice:

- `backend/research` has `StockNewsEvidence`, `StockNewsRequest`, `StockNewsReport`, and `StockNewsAnalysisService`.
- The first deterministic test source is registered local Research documents with `source_type="news"`; product direction is to replace the normal user-facing path with external fresh news/source adapters while keeping tests network-free.
- News documents must contain a `url:` / `source_url:` line or another `https://...` URL. Items without source URL are excluded with a warning rather than summarized as fact.
- `銘柄コックピット` integrates Recent News into Research Evidence cards. The dedicated `ニュースのみ再取得` button stores a session-local report and card/detail displays title, URL, source, published_at, summary, investment_viewpoint, sentiment_for_investment, and freshness_status.
- This slice does not change Investment Score, Research Score, Decision Report, or ranking order.

Follow-up child roadmap:

- Phase 21.6: External Research Document Fetch MVP. `AI調査を更新` の標準動作として、EDINET / TDnet / IR site / provider profile などの資料取得/参照 adapter を使う。取得本文は session-local RAG store で一時参照し、既定では `data/research_docs/` や cache/archive に保存しない。表示・Report には source URL、provider、fetched_at、published_at、freshness_status、短い要約/引用範囲を残す。通常 tests / CI は network 非依存の fixture / fake adapter で確認する。
- Phase 21.7: External Stock News Fetch MVP. `AI調査を更新` または news refresh から、選択中の銘柄名 / ticker / related keywords に限定した外部ニュース取得 adapter を使う。取得結果は `StockNewsEvidence` 互換の title / URL / source / published_at / summary / investment_viewpoint / sentiment_for_investment / freshness_status として一時表示する。既定ではニュース本文を保持せず、source URL がない内容は断定せず、外部 LLM は必須にしない。
- Phase 21.6 / 21.7 は、Phase 21.5 の local deterministic slice を test/fallback として残しつつ、通常ユーザー導線では外部最新情報を優先する。外部取得に失敗した場合はローカル fixture / saved archive / fallback evidence 表示に戻れる設計にする。
- External fetch child phases remain decision-support only. Investment Score、Research Score、Decision Report 自動反映、ranking order 変更、buy / sell / hold 判断は行わない。

Current implemented slice:

- `backend/research` has `ExternalResearchFetchRequest`, `ExternalResearchSourcePayload`, `ExternalResearchFetchService`, source trace entries with freshness_status, `ExternalResearchSourceAdapter` protocol, and a default composite adapter.
- `TDnetResearchAdapter` provides the first official timely-disclosure source slice for Japanese listed-company IR links. `YahooFinanceResearchAdapter` continues to provide provider profile and recent news payloads. Tests inject fake HTTP / ticker factories, so no live TDnet or Yahoo call is required in normal checks.
- The current implementation keeps an explicit `allow_network=True` backend safety gate, removes the separate Cockpit `外部資料取得（明示許可）` UI, and makes `AI調査を更新` the standard external source search action while retaining fake-adapter tests and backend safety boundaries.
- External RAG fetch is transient-by-default. Fetched source text is registered into the session-local Research RAG store only for the current analysis / score / display pass, while persistent document payloads, converted Markdown, local paths, document hashes, and manifests are not produced unless the user explicitly chooses a future `資料を保存する` / archive action.
- UI/report display focuses on provider, fetched_at, published_at, source URL, freshness_status / freshness warnings, and generated summary/evidence snippets. Cockpit Decision Report includes an `外部参照ソース` section for these trace rows without including fetched source text, local paths, document hashes, or manifests. It should not imply that the app is building a permanent local document repository from live sources.
- Normal tests use fake adapters only. No live external source, scraping, external LLM, or network call is required for CI.
- A `source_type="news"` payload becomes available to the existing Stock News RAG cockpit flow after registration; provider profile / IR payloads become normal Research Evidence documents.

### 5.8 Phase 22: Research Score And Investment Integration

Status: first backend slice started

Current integration direction:

- Phase 22 は、Phase 20 / Phase 21 の evidence / extracted claims / grounded answers を、説明可能な Research Score として定量化し、Investment Score、ranking、Decision Report に optional input として接続する。
- Research Score は evidence と紐づく補助スコアにする。資料不足時は欠損または低信頼として扱い、推定で埋めない。
- 初期の Investment Score weight は 0.0 または低めの optional weight とし、既存の Screening / Forecast / Risk / Data Quality score を壊さない。
- Ranking では Research Score を既定の主要ソート条件にせず、深掘り候補の確認材料、または opt-in sort profile として扱う。
- Decision Report では Research Score の内訳と evidence を同じ section で確認できるようにする。

Recommended integration slice:

- R5: Vector Search / Hybrid Search optional adapter。keyword retrieval を baseline に残し、embedding / vector は optional にする。
- R6: Research Score MVP。growth、profitability、shareholder_return、financial_safety、business_risk、disclosure_quality、freshness を rule/template で採点し、evidence_count と confidence を保持する。Backend first slice は `ResearchScore` / `ResearchScoreService` として実装済み。
- R7: Investment Score / Ranking / Report integration。Research Score を設定で管理できる optional weight として Investment Score に接続し、ranking / cockpit / report に内訳を表示する。Investment Score first slice は `research_scores_by_symbol` と `scoring.weights.research` default 0.0 として実装済みで、default ranking order は変更しない。Display first slice は Cockpit / Ranking の共通 Research Summary panel に Research Score summary / component / warning rows を出し、AI Research report 由来の score を selected-candidate breakdown に確認材料として出す形で実装済み。Report first slice は Cockpit Decision Report の `Research Score` section として実装済みで、内訳、supporting evidence、confidence、warnings、非推奨注記を Research Evidence と並べて保存する。
- R8: External Source Adapter。TDnet は first slice 実装済み。EDINET / IR site / news などを `AI調査を更新` の標準 source adapter として広げ、通常 checks は fake adapter / fixture で network 非依存にする。

Recommended completion criteria:

- Research Score は evidence と紐づいて説明できる。
- Investment Score に Research Score を統合する重みが設定で管理できる。
- evidence 不足時は score 欠損または低信頼として表示される。
- Cockpit / Ranking の Research Summary と Cockpit Decision Report では Research Score が売買推奨ではなく確認材料として表示される。Ranking order への接続は明示 opt-in の後続で扱う。
- external source adapter は通常 checks に入れない。

目的: Research RAG の evidence / summary を Investment Score、ranking、Decision Report に接続する。

Implementation order:

- R5: Vector Search / Hybrid Search。optional adapter として扱い、keyword retrieval を baseline に残す。
- R6: Research Score MVP。
- R7: Investment Score / Ranking / Report integration。
- R8: External Source Adapter。live scraping / external source は adapter 化し、通常 checks は fake adapter / fixture で代替する。

Phase 22.x Candidate: Investment News Dashboard

- Phase 22 の既存主目的は Research Score と Investment Score / ranking / report への optional integration として維持する。
- `投資ニュース` dashboard は Phase 21.5 で Stock News RAG の型が固まった後の候補として整理する。Phase 22 本体を置き換えず、着手する場合は Phase 22.x または Phase 23+ の UI slice として扱う。
- Dashboard scope: 新画面 `投資ニュース`、今日の注目トピック、注目ジャンル、注目業界、リスクニュース、ニュースカード一覧、source URL / published_at / summary / investment_viewpoint 表示、ポジティブ材料とリスク材料の分離表示、後で銘柄コックピットへ接続できる導線設計。
- Dashboard non-scope: Research Score の Investment Score 統合、ニュースだけでランキングを変更すること、自動売買判断、buy / sell / hold 判断、高度なクラスタリング、Watchlist 連動、portfolio 連動。

Completion criteria:

- Research Score は evidence と紐づいて説明できる。
- Investment Score に Research Score を統合する重みが設定で管理できる。
- evidence 不足時は score 欠損または低信頼として表示される。
- external source adapter は通常 checks に入れない。

### 5.9 Phase 23: Low-Cost Assistant Experience

Status: planned

目的: Decision Report context と Research Summary を入力にし、初心者向けの質問応答・説明を deterministic template で提供する。

Scope:

- `backend/assistant/` の request / response contract を定義する。
- template-based response service を default provider として実装する。
- cockpit / ranking / rebalance / report / research context から assistant context を組み立てる。
- Streamlit に質問パネルまたは assistant view を追加する。
- 応答は理由、注意点、次に確認する観点、非助言文言を含める。

Completion criteria:

- LLM なしで assistant API/UI が動作する。
- 同じ input / context では同じ応答になる。
- 通常 tests は network 非依存で通る。
- Assistant の説明は UI / report と同じ指標名・制約を使う。

Advanced News Intelligence candidates for Phase 23+:

- 関連銘柄の自動抽出
- `投資ニュース` 画面から `銘柄コックピット` への遷移
- Watchlist 銘柄に関連するニュースの優先表示
- Decision Report へのニュース根拠反映
- ニュースクラスタリング
- source reliability 表示
- impact horizon 分類
- Research Score / News Score 化
- Assistant 機能との連携
- 外部ニュースソース adapter の拡充
- ニュースの重複除去
- トピック単位の時系列追跡

News guardrails for Phase 23+:

- ニュース RAG は売買推奨を行わず、buy / sell / hold を直接出さない。
- ニュースだけで Investment Score や ranking order を変更しない。
- source URL がない内容を断定しない。
- 古いニュースは warning または `freshness_status` で明示する。
- 外部ニュース取得は adapter 化し、`AI調査を更新` / news refresh の標準 source として扱う。
- CI / 通常テストは外部ネットワークに依存させない。
- 外部 LLM は必須にせず、template / deterministic fallback を維持する。

### 5.10 Phase 24: Optional Adapters And Advanced Intelligence

Status: planned

目的: default path を deterministic に保ったまま、追加 provider、advanced forecast / research model、LLM adapter、news / sentiment を optional layer として追加する。

Scope:

- `polygon` など追加 live provider adapter。
- advanced forecast model adapter。
- local LLM / cloud LLM assistant provider。
- news / sentiment local CSV provider と optional external provider。
- LLM / news / external provider はすべて明示 opt-in とし、失敗時は deterministic fallback に戻す。

Completion criteria:

- adapter 未設定でも既存機能が壊れない。
- provider / model / LLM の使用状態と fallback 状態が UI/API で分かる。
- 通常 tests は network / cloud API / heavy ML library に依存しない。
- LLM は説明・要約・観点提示に限定し、スコア計算や売買判断の主体にしない。

Research document storage migration:

- `data/research_docs/` remains the local fixture / demo seed / user-saved archive / private-note path, not the primary live product source.
- External live fetch is not a replacement for local storage and should not auto-populate `data/research_docs/` by default.
- If users need persistence later, add an explicit `資料を保存する` / archive action with clear retention wording, source attribution, and cleanup behavior. This must be separate from the default live reference flow.
- Long-term target: external source adapters provide fresh, on-demand evidence for the selected symbol; local storage remains user-controlled rather than a growing implicit cache of fetched documents.

### 5.11 Phase 25: Advanced Export And Execution Gate

Status: future / low priority

目的: Decision Report が安定した後に、PDF / Excel export や broker execution の再開可否を判断する。

Scope:

- UI リッチな PDF report / Excel report。
- report archive / saved watchlist / ranking scenario。
- broker 連携の再評価。
- order sending は、risk / report / audit / user confirmation が揃うまで実装しない。

Completion criteria:

- Execution を再開する場合、注文前の確認、監査ログ、取り消し不能操作の警告、dry-run が必須。
- 投資判断支援と注文執行の境界が UI / docs / code で明確に分離されている。

## 6. 詳細バックログ

この節は、実装順ロードマップの各 phase に紐づく候補の一覧です。
ここにある項目は、上の Phase 17〜25 の順序を崩さず、該当 phase の中で必要になった時点で取り込みます。
詳細な future candidate はここに集約し、本文の実装順と重複する Appendix は置きません。
### 6.1 Research RAG

- Local document ingestion
- Text extraction and chunk store
- Keyword retrieval
- Research summary
- Query expansion
- Structured evidence extraction
- Grounded answer generation
- Evidence reranking
- Retrieval Quality
- Vector / hybrid retrieval
- Research Score
- Investment Score / ranking / report integration
- External source adapter

### 6.2 Assistant / LLM / News

- Template assistant MVP
- Stock News RAG MVP for Symbol Cockpit
- Investment News dashboard
- News / sentiment local CSV provider
- Assistant x news integration
- Advanced News Intelligence
- LLM provider protocol
- Local LLM / Ollama provider
- Cloud LLM / OpenAI provider
- LLM-enhanced report / news explanation
- Hybrid assistant evaluation

### 6.3 Execution

- Dry-run execution model
- Broker adapter protocol
- Pre-submit risk gate
- User confirmation and audit log
- Live order sending

## 7. 検証コマンド

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check . --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy .
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

Markdown UTF-8 check:

```powershell
.\venv_SMAI\Scripts\python.exe -c "from pathlib import Path; [p.read_text(encoding='utf-8') for p in Path('.').rglob('*.md') if '.git' not in p.parts]; print('markdown utf-8 ok')"
```

## 8. Open Items

- Phase 16S の最終 Streamlit browser smoke をいつ実施するか
- Ranking condition model をどのファイルに置き、UI 表示名と internal key をどう分けるか
- provider fundamentals から symbol metadata を更新する command / cache / manifest の粒度
- Decision Report に含める cockpit / ranking / rebalance context の最小 schema
- Research Score を Investment Score に統合する重みと表示順
- Assistant が参照できる context の範囲と privacy boundary
- PDF / Excel export をいつ入れるか
- Execution / broker order をどの段階で再開するか
