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
- 追加 provider / SBI / NISA / fund metadata source adapter
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
- Research RAG は local-first の根拠レイヤーとして追加し、Research Score へつなげる。
- Assistant / LLM / external source / Execution は、判断材料の構造化が安定してから追加する。

### 5.1 UI 確認方針

UI 上の体験に影響する機能は、バックエンド実装だけでは完了としません。
各フェーズの完了条件には、Streamlit UI または将来の UI 画面で、ユーザーが変更内容を確認できることを含めます。
ただし、通常の自動テストと local checks は外部 API に依存させず、mock / csv / fixture による deterministic な検証を維持します。

### 5.2 Phase 16S: Stabilization And Final UI Smoke

Status: next verification

目的: Phase 16 までに実装した主要画面を、次の UI / report / RAG 実装に進める前の安定基準として確認する。

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

Status: in progress; backend local evidence slice started

Current implementation direction:

- Phase 20 は、RAG で銘柄を推奨したりランキング順位を直接変えたりする段階ではなく、既存の `銘柄コックピット` / `銘柄ランキング` / `Decision Report` に資料根拠を添える local-first evidence layer として実装する。
- 初期 MVP はローカル資料だけを対象にする。外部 scraping、外部 LLM、embedding / vector DB は通常経路に入れず、後続 phase の optional adapter として扱う。
- 9,179件の銘柄DB全体を一括RAG対象にせず、ランキング後の上位候補、コックピットで選択した銘柄、Decision Report の対象銘柄から段階的に使う。
- 初期出力は `Research Summary`、`Research Evidence`、`Research Data Quality` を中心にする。資料がない銘柄では「根拠不足」を明示し、推定で埋めない。
- `Research Score` と Investment Score / ranking への重み統合は Phase 21 に回す。

Recommended MVP slice:

- R0: Research RAG design cleanup。`Documents/04_Detail_Design/04-8_Onepager_Research_RAG.md` の文字化け部分を、Phase 20 方針に沿って読める日本語へ整える。
- R1: Local Document Ingestion MVP。`backend/research/` に document metadata contract と ingestion service を追加し、`data/research_docs/` 配下の Markdown / Text / CSV fixture を登録できるようにする。
- R2: Text Extraction & Chunk Store。ローカル資料を source / title / published_at / section / chunk_index / reliability と紐づく検索可能 chunk に分割する。
- R3: Keyword Retrieval MVP。symbol と query から evidence chunk を返す deterministic keyword search を実装する。top_k、freshness、source_type、reliability を保持する。
- R4: Research Summary MVP。コックピット向けに、成長材料、株主還元、事業リスク、財務安全性、確認不足を evidence 付きで要約する。LLM は使わず rule / template を既定にする。
- R4.5: UI / Report integration。銘柄コックピットに Research Summary を追加し、ランキングには「根拠あり / 最新資料が古い / 根拠不足」の状態だけを軽く表示する。Decision Report には Research Evidence section を追加する。

Current implemented slice:

- `backend/research` provides local UTF-8 document ingestion, hash dedupe, chunking, keyword evidence search, deterministic Research Summary, and data-quality warnings.
- `設定 / データ情報` has a `Research RAG / 根拠資料` expander for session-local Markdown / Text / CSV upload and registration.
- `銘柄コックピット` shows a `Research RAG / 根拠資料` section with an explicit `AIデータ取得` button beside the section header; price-data fetch does not automatically run Research RAG. The summary shows source document names, dates, evidence counts, and detailed evidence rows inside a collapsed detail expander.
- `銘柄ランキング` row-click `銘柄データ` modal has an `AI Research` tab with an explicit `AIで資料を確認` button. It reuses the same Research Summary panel for growth, shareholder return, financial safety, business risk, confirmation gaps, source document names, dates, and evidence counts.
- Cockpit Decision Report includes `Research Evidence` only when `AIデータ取得` has produced a report and registered documents or evidence exist, so existing no-document reports remain unchanged.

Recommended completion criteria:

- local fixture だけで ingestion -> chunk -> keyword search -> Research Summary が動く。
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

### 5.7 Phase 21: Research Score And Investment Integration

Status: planned

Current integration direction:

- Phase 21 は、Phase 20 の evidence / summary を、説明可能な Research Score として定量化し、Investment Score、ranking、Decision Report に optional input として接続する。
- Research Score は evidence と紐づく補助スコアにする。資料不足時は欠損または低信頼として扱い、推定で埋めない。
- 初期の Investment Score weight は 0.0 または低めの optional weight とし、既存の Screening / Forecast / Risk / Data Quality score を壊さない。
- Ranking では Research Score を既定の主要ソート条件にせず、深掘り候補の確認材料、または opt-in sort profile として扱う。
- Decision Report では Research Score の内訳と evidence を同じ section で確認できるようにする。

Recommended integration slice:

- R5: Vector Search / Hybrid Search optional adapter。keyword retrieval を baseline に残し、embedding / vector は optional にする。
- R6: Research Score MVP。growth、profitability、shareholder_return、financial_safety、business_risk、disclosure_quality、freshness を rule/template で採点し、evidence_count と confidence を保持する。
- R7: Investment Score / Ranking / Report integration。Research Score を設定で管理できる optional weight として Investment Score に接続し、ranking / cockpit / report に内訳を表示する。
- R8: External Source Adapter。EDINET / TDnet / IR site / news などは明示 opt-in adapter として扱い、通常 checks には入れない。

Recommended completion criteria:

- Research Score は evidence と紐づいて説明できる。
- Investment Score に Research Score を統合する重みが設定で管理できる。
- evidence 不足時は score 欠損または低信頼として表示される。
- Ranking / Report では Research Score が売買推奨ではなく確認材料として表示される。
- external source adapter は通常 checks に入れない。

目的: Research RAG の evidence / summary を Investment Score、ranking、Decision Report に接続する。

Implementation order:

- R5: Vector Search / Hybrid Search。optional adapter として扱い、keyword retrieval を baseline に残す。
- R6: Research Score MVP。
- R7: Investment Score / Ranking / Report integration。
- R8: External Source Adapter。live scraping / external source は明示 opt-in とする。

Completion criteria:

- Research Score は evidence と紐づいて説明できる。
- Investment Score に Research Score を統合する重みが設定で管理できる。
- evidence 不足時は score 欠損または低信頼として表示される。
- external source adapter は通常 checks に入れない。

### 5.8 Phase 22: Low-Cost Assistant Experience

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

### 5.9 Phase 23: Optional Adapters And Advanced Intelligence

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

- When EDINET / TDnet / IR-site / provider-profile adapters can fetch current documents on explicit user action, `data/research_docs/` should no longer be the primary manual input path.
- Keep `data/research_docs/` as local cache / audit archive / offline fixture storage while external adapters are optional. Do not delete it until provider manifests, source URLs, fetched_at timestamps, hashes, and reproducible cached payloads are available.
- After external adapters are stable, deprecate manual `設定 / データ情報` upload as the normal user path and replace it with explicit `外部資料を取得` / `資料キャッシュを更新` actions.
- Long-term target: `data/research_docs/` becomes generated/cache data or test fixture storage, not hand-maintained business data. User-facing docs should describe it as cache/archive. Manual upload remains an advanced fallback for private notes or documents not available from public sources.

### 5.10 Phase 24: Advanced Export And Execution Gate

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
ここにある項目は、上の Phase 17〜24 の順序を崩さず、該当 phase の中で必要になった時点で取り込みます。
詳細な future candidate はここに集約し、本文の実装順と重複する Appendix は置きません。
### 6.1 Research RAG

- Local document ingestion
- Text extraction and chunk store
- Keyword retrieval
- Research summary
- Vector / hybrid retrieval
- Research Score
- Investment Score / ranking / report integration
- External source adapter

### 6.2 Assistant / LLM / News

- Template assistant MVP
- News / sentiment local CSV provider
- Assistant x news integration
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
