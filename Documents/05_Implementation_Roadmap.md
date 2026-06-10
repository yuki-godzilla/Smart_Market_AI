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

Phase 1 から Phase 15 までは、現在の実装上は実装完了扱いです。
Phase 16 は UI / Visualization Cockpit 改善の実装完了扱いです。最終 Streamlit browser smoke は推奨確認として残します。
Research RAG は Phase 20 local evidence slice が決定的な土台として実装完了です。今後のプロダクト導線は、local 登録資料を主データ源にするのではなく、`AI調査を更新` で外部の最新IR・開示・ニュース・provider 情報を取得/参照し、session-local に一時分析する流れを基本にします。local 登録資料は通常テスト / demo seed / archive / fallback の位置づけです。Phase 21 高度Research RAG（根拠抽出・根拠付き回答生成）は、query expansion、structured extraction、grounded answer、retrieval quality、evidence reranker、UI / Decision Report 表示、optional vector / hybrid contract、keyword fallback などの初期スライスが進行中です。`ResearchFactSummary` と `CompanyResearchSummaryBuilder` は、企業概要、主な事業、製品・サービス、地域、定量情報、IR情報、最新ニュース・開示を source-backed fact として再分類します。主表示では `企業リサーチサマリー`、`定量情報サマリー`、`IR情報サマリー`、`最新ニュース・開示サマリー` を先に出し、`詳細情報・開発者向け` は Research Score、データ品質、検索品質、抽出主張、根拠資料詳細、外部source取得状況など通常表示と用途が重ならない検証用データに絞ります。ニュースURL表示自体は外部参照ソースで実装済みで、Phase 22 の UX polish では `最新ニュース・開示サマリー` 直後に `ニュース・開示の出典を表示` を追加し、URL付きニュース・TDnet・企業IR・EDINET・Yahoo Finance への簡易導線を出すようにしました。出典リンクは初期折りたたみの小さな citation list として扱い、サマリカードとは視覚的に分けます。EDINET optional metadata/link adapter、TDnet、company IR site、Yahoo Finance の外部取得初期スライスは実装済みです。Phase 22 Research Score は backend deterministic service、disabled-by-default Investment Score optional input、Cockpit / Ranking Research Summary display、selected-candidate breakdown context、Cockpit Decision Report section の初期スライスが実装済みです。Research Score によるランキング順位統合はいまは見送り、コックピット深掘りと Decision Report でユーザーが確認して判断する導線を優先します。

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
- Research RAG の `ResearchFactSummary` 抽出対象拡張、追加 external source adapter、vector / hybrid search の運用UI
- `投資レーダー` dashboard の追加ニュースprovider、詳細フィルタ、Watchlist連動、通知
- 銘柄DB background refresh の live provider refresh wiring。`backend/symbols` の foundation、Streamlit daemon worker、Cockpit / Ranking 共通の visible freshness 表示、Cockpit / Ranking 対象銘柄の自動優先更新、Cockpit の価格・予測取得後 background priority refresh + 30分TTL、Ranking 操作直前の軽量 preflight 更新は実装済み
- Research Score によるランキング順位統合は、現時点では見送り。必要性が再確認された場合のみ後続の opt-in 機能として扱う
- Phase 23 は Optional Adapter / 高度分析を先に進め、銘柄コックピット / ランキング向け advanced forecast model adapter を次の優先候補にする
- Phase 24 Assistant は deterministic backend と Cockpit / Ranking 向け floating `SMAI Copilot` UI の初期 slice まで実装済み。LLM 実装後の `SMAI Copilot` チャット画面、限定自由入力、`smai-ai-gateway/` scaffold、外部 LLM Gateway API client / schema は後続範囲
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

#### Phase 1: コア基盤

状態: 実装完了

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

状態: 実装完了

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

状態: 実装完了

完了済み:

- `backend/risk/service.py`
- `POST /risk/pre-trade-check`
- `ALLOW` / `REVIEW` / `BLOCK`
- concentration、cash、dividend-yield missing などの MVP risk rule
- deterministic tests

#### Phase 4: Portfolio MVP

状態: 実装完了

完了済み:

- `backend/portfolio/service.py`
- JPY base valuation
- no-solver rebalance proposal
- generated `TradeIntent`
- Portfolio-to-Risk workflow の service-level 接続

残り:

- optimizer library を使った最適化
- より高度な constraint

#### Phase 5: API / UI 統合

状態: 実装完了

完了済み:

- FastAPI app wiring
- Swagger / OpenAPI metadata
- Portfolio / Risk / Screening / Forecast / Scoring endpoints
- Streamlit UI
- sample selector
- target controls
- allocation comparison
- result download

#### Phase 6: CSVデータとシナリオ拡張

状態: 実装完了

完了済み:

- `data/marketdata` sample CSV
- `config/csv_example.yaml`
- `examples/rebalance_scenarios/`
- CSV provider smoke check
- deterministic scenarios

#### Phase 7: 設定とシナリオ管理

状態: 実装完了

完了済み:

- file-backed rebalance scenario
- `SMAI_REBALANCE_SCENARIO_DIR`
- scenario `description`
- invalid scenario/config error handling
- UI sample selector integration

#### Phase 8: レポートMVP

状態: 実装完了

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

#### Phase 9: 外部データProvider準備

状態: 実装完了

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

### 4.2 Phase 10〜16: 投資判断支援とUI基盤

Phase 10〜16 は、外部データ取得、Feature Store Lite、Screening、Forecast、Investment Score、Visualization Cockpit をつなげた投資判断補助の中核です。

| Phase | Status | 完了済みの主な範囲 | 残り / 後続 |
| --- | --- | --- | --- |
| Phase 10: 外部データ取得MVP | 実装完了。live smoke は環境依存 | `yahoo` live provider adapter、provider metadata / error display、deterministic fallback | live smoke 手順の標準化、追加 provider adapter |
| Phase 11: Feature Store Lite | 実装完了 | close / return / momentum / ADV / volatility / drawdown、missing / quality summary | feature versioning、persistent feature store |
| Phase 12: Screening Score MVP | 実装完了 | `backend/screening`、sub-score、reason labels、Forecast agreement 接続 | watchlist persistence、symbol metadata refresh |
| Phase 13: Forecast Lab Baseline | 実装完了 | naive / moving-average / momentum baseline、walk-forward metrics、Forecast chart preview | advanced model adapter の前提整備 |
| Phase 14: Multi-Model Forecasting | 実装完了。live-provider確認は環境依存 | model registry lite、forecast consensus、forecast range、model agreement | model card / evaluation persistence |
| Phase 15: Model-Informed Scoring | 実装完了。live-provider確認は環境依存 | `backend/scoring`、Investment Score、configurable weights、API / UI preview / export | Research Score連携、より豊かなrisk signal |
| Phase 16: Visualization Cockpit | 実装完了。最終Streamlit browser smoke推奨 | `銘柄コックピット` / `銘柄ランキング` / `リバランス`、side menu、ranking cache、Yahoo batch OHLCV、symbol-detail modal、cockpit investment memo、Rebalance summary flow | final UI smoke、Decision Report context |

## 5. 実装順ロードマップ

ここから先は、過去の番号順ではなく **次に実装する順番** として扱います。
Phase 1〜16 は完了済みの土台です。以降は、UI の迷いを減らし、データの信頼性を高め、レポート・根拠・対話体験へ広げる順で進めます。

優先順位の考え方:

- まず既存の `銘柄コックピット` / `銘柄ランキング` / `リバランス` を安定させる。
- 次にランキング条件 UI と symbol universe を整え、ユーザーが対象を迷わず絞れるようにする。
- その後、cockpit / ranking / rebalance を横断する Decision Report context を作る。
- Research RAG は外部最新情報を主にした根拠レイヤーとして育て、local fixture foundation と Research Score へつなげる。
- Assistant / LLM / Execution は、advanced forecast adapter などの判断材料強化が進んでから追加する。

### 5.1 UI 確認方針

UI 上の体験に影響する機能は、バックエンド実装だけでは完了としません。
各フェーズの完了条件には、Streamlit UI または将来の UI 画面で、ユーザーが変更内容を確認できることを含めます。
ただし、通常の自動テストと local checks は外部 API に依存させず、mock / csv / fixture による deterministic な検証を維持します。

### 5.2 Phase 16S: 安定化と最終UI確認

状態: 成熟度レビュー / 次回確認

目的: Phase 16 までに実装した主要画面を、次の UI / report / RAG 実装に進める前の安定基準として確認する。

成熟度確認タスク:

- Manual UX Review Checklist creation: [96_Manual_UX_Review_Checklist.md](./96_Manual_UX_Review_Checklist.md) を使い、Symbol Cockpit、Ranking、Rebalance Cockpit、Decision Report、Research Summary / Evidence、Forecast、Risk、Market Data freshness、score explanation を手動レビューできるようにする。
- Functional Spec Issues tracking: [97_Functional_Spec_Issues.md](./97_Functional_Spec_Issues.md) を使い、Investment Score、Database Fit、Metadata Confidence、Research Evidence、NISA / Dividend / Growth / ETF criteria などの仕様曖昧さを管理する。
- Feature role clarification: Ranking、Symbol Cockpit、Rebalance Cockpit、Decision Report、Research Summary / Evidence、Investment Score、Data Quality / Database Fit / Metadata Confidence の役割を [03_Functional_design.md](./03_Functional_design.md) に明記する。
- UI wording safety review: [07_UI_Wording_Policy.md](./07_UI_Wording_Policy.md) に従い、売買指示に見える表現を避け、判断補助・確認候補・比較材料として表現する。
- Score hierarchy clarification: Investment Score、Screening、Forecast agreement、Risk、Data Quality、Database Fit、Metadata Confidence、Research Evidence の関係を、実装修正前に仕様として整理する。
- Cockpit score / forecast / risk wording slice: 2026-06-03 に `銘柄コックピット` の Investment Score、Screening、Forecast、Risk、Data Quality の読み分けをカードhelp、評価内訳、読み分け表で補強済み。実画面での継続確認は UX review に残す。
- Ranking criteria / confidence wording slice: 2026-06-03 に `銘柄ランキング` の評価方針、詳細条件、条件適合度、DB信頼度、NISA、配当 / 分配金、ETF条件の読み方を折りたたみガイドとして補強し、Chrome headless + 8502 実画面で展開確認済み。取得後ランキング結果 / 詳細モーダルの継続確認は UX review に残す。
- Distribution readiness preparation: 配布準備は future step とし、まず仕様バグ・UXバグ・投資助言に見える表現を棚卸しする。

範囲:

- `銘柄コックピット` の Yahoo live data 取得、失敗時診断、価格・予測・Investment Score 表示を確認する。
- `銘柄ランキング` の候補条件、ランキング cache、`重視して並べ替え` での表示順変更、部分失敗時の除外表示、深掘り導線を確認する。
- `リバランス` の入力、target allocation、allocation comparison、risk breach 表示を確認する。
- UI 文言が「判断補助」で統一されているか確認する。
- 新機能は追加せず、必要な不具合修正とドキュメント同期だけ行う。

完了条件:

- Streamlit browser smoke の確認結果が作業ログまたは引き渡しサマリに残っている。
- `tools/run_local_checks.py` が通る。
- provider 失敗時に raw provider noise ではなく SMAI の診断情報として表示される。
- Rebalance / ranking / cockpit の主要導線が壊れていない。

### 5.3 Phase 17: UI改善とランキング条件再設計

状態: 実装完了。Streamlit 画面確認済み

目的: `銘柄ランキング` を、単なる検索フィルターではなく、投資対象と投資スタイルを先に決めてから詳細条件を設定する UI に整理する。MVP は株式・ETF中心とし、投資信託は将来対応に回す。

計画範囲:

- Ranking 条件モデル
  - 地域: `国内` / `米国` / `全体`
  - 商品: `株式` / `ETF` / `指定なし`
  - 投資スタイル: `配当重視` / `成長重視` / `割安重視` / `安定重視` / `トレンド重視`
  - UI label と internal key を分離した enum / constants / condition object
- UI構成
  - ranking screen の上部で地域・商品・投資スタイルを選択
  - 初期表示は候補が広がりすぎない `国内` + `株式`
  - 地域 × 商品に応じて詳細条件を動的に切り替え
  - 候補数を見せてから Yahoo live data ranking を実行
- 役割分離
  - 投資スタイルは Investment Score の weight preset / sort intent として扱う
  - 詳細条件は provider fetch 前の candidate filter として扱う
  - `総合おすすめ` のような推奨に見える表現は避け、投資判断補助として表現する
- 初期フィルター範囲
  - 株式: 地域、業種/セクター、時価総額、配当利回り、PER、PBR、ROE、NISA
  - ETF: 地域、投資対象、連動指数、信託報酬/経費率、分配金利回り、複雑さ
  - 投信: MVP 対象外。source seed / metadata schema は future extension として残すが、ranking UI と default universe から除外する
  - Risk / 値動きの大きさは、取得期間の価格データに依存するため ranking result / score breakdown 側で扱う
- 将来拡張を見据えたフィルター定義
  - 国内株式: 投資スタイル、業種、時価総額、配当利回り、PER、PBR、ROE、売買代金
  - 米国株式: 投資スタイル、セクター、時価総額、配当利回り、PER、売上成長率、EPS成長率、Beta、ボラティリティ
  - 全体 × 株式: 地域、投資スタイル、業種/セクター、時価総額、配当利回り、PER、ROE、リスク
  - ETF: 投資対象、地域、連動指数、信託報酬/経費率、分配金利回り、純資産総額、流動性、為替ヘッジ、複雑さ
  - 投信: Future phase で、ウォッチリスト、CSV取込、基準価額チャート、Provider連携、投信ランキングを検討する

実装ルール:

- 既存 `data/marketdata/symbol_universe.csv` で判定できる条件だけを実フィルタとして有効化する。
- 未取得の `売買代金`、`売上成長率`、`EPS成長率`、`Beta` などは、無理に計算せず future metadata として定義・文書化する。投信の `純資産総額`、`NISA対応`、`積立可否` は source-import seed で保持できるが、MVP UI / ranking では使わない。
- `大型株`、`リスク`、`複雑さ` などの曖昧な UI 表現は、内部的に数値しきい値または明示フラグへ変換できる設計にする。
- ETF と投信は internal model で分離する。MVP UI は株式 / ETF のみ表示する。
- docs / tests / UI wording policy と矛盾しないよう、実装時に operations guide と必要な設計文書を同期する。

完了条件:

- 地域・商品・投資スタイルの分類が定義されている。
- 商品・地域に応じて詳細条件が切り替わる。
- 投資スタイルと詳細条件の役割が UI / code / docs で分離されている。
- Phase 1 で実データに基づき有効な条件と、future metadata 条件が区別されている。
- 「おすすめ」ではなく、判断材料を整理する ranking として文言が統一されている。
- UI helper tests または deterministic filtering tests が追加・更新されている。

現在の実装メモ:

- `ui/ranking.py` defines region / product / investment-style labels separately from internal keys.
- `銘柄ランキング` now shows region / product / investment style before provider / period, derives the display weight preset from investment style, and shows dynamic detail filters for `指定なし` / stock / ETF categories.
- The detail filter panel is grouped into attribute / numeric / keyword sections, and the comparison-symbol selector stays all-selected by default while its large multiselect tags are kept inside a collapsed expander.
- Acquisition period, candidate count, selected count, and all/partial selection status are shown as a compact one-line comparison status.
- Current enforceable filters remain limited to `symbol_universe.csv` metadata. Default ranking universe is stock / ETF only. 投信 seed/source import は将来対応 metadata として残すが、MVP ranking UI には表示しない。
- Phase 17 ranking-condition UI の Streamlit visual smoke はユーザー確認済み。

### 5.4 Phase 18: 銘柄Universeとメタデータ更新

状態: 実装完了。継続的なsource更新は運用保守扱い

目的: Ranking condition UI の裏側にある銘柄 universe を、固定 CSV だけでなく、鮮度と出所を管理できる metadata layer に拡張する。

範囲:

- `symbol_universe.csv` の列定義を整理し、地域、商品、業種/セクター、時価総額 tier、配当、PER/PBR/ROE、ETF属性、future 投信属性、metadata freshness を明確化する。
- ranking universe は、当面 SBI証券で取り扱いがあり、現物・NISA・長期投資で検討しやすい商品を初期前提にする。
- CSV / fixture を deterministic baseline として維持する。
- Yahoo fundamentals や将来 provider から metadata を更新する明示 opt-in command を設計する。
- UI / command の初期 default は Yahoo としつつ、内部実装は Yahoo 専用に固定しない。
- 更新結果は cache / CSV / manifest として保存し、通常テストは network 非依存にする。
- 古い metadata、欠損 metadata、future-only metadata を UI で区別する。

Provider方針:

- Yahoo first, not Yahoo only. 画面上の既定 provider と metadata refresh の初期 provider は `yahoo` とする。
- Internal refresh logic は `MetadataProvider` 風の adapter 境界を持たせ、Yahoo 固有の取得・変換・失敗処理を service 本体へ埋め込まない。
- `metadata_source` / manifest / validation result に provider 名、更新日時、成功/失敗件数、更新対象列を残す。
- Future provider として FMP / EODHD / Alpha Vantage / Polygon などを追加できる構造にする。初期実装で複数 provider を実装する必要はない。
- 通常テストと CI は `csv` / fixture / fake provider を使い、live provider smoke は明示 opt-in のまま分離する。

Universe方針:

- 詳細方針は [09_SBI_Symbol_Universe_Policy.md](./09_SBI_Symbol_Universe_Policy.md) を参照する。
- MVP対象は国内株式、米国株式、国内ETF、米国ETF/海外ETF とする。
- 投資信託、ADR、REIT、FX、CFD、先物・オプション、暗号資産、債券、外貨建MMF、貴金属・コモディティ系ETF、レバレッジ、インバースは初期 ranking から除外する。
- `broker`, `tradability`, `nisa_category`, `investment_style`, `is_sbi_supported`, `is_active`, `is_leveraged`, `is_inverse` は `symbol_universe.csv` / schema に保持する。
- local curated / source-import seed は conservative default として `tradability=unknown` を持てる。SBI取扱確認済み master ではないため、初期 policy では `unknown` を通し、`not_tradable` や明示的な対象外 flag だけを除外する。
- SMAI は初期段階で SBI 証券サイトを直接スクレイピングしない。SBI / JPX / NISA 一覧などを source CSV 化し、local master に取り込む。投信協会 / 投信CSV / 基準価額は Future Phase とする。
- 現在の `symbol_universe.csv` は SecurityMaster 相当の local master として扱う。専用 `SecurityMasterRepository` は、API / UI / batch で共通 loader が必要になった段階で `backend/marketdata/security_master/` などへ昇格する。

実装順:

1. Network-free schema / validation / Settings status. 完了。
2. Metadata source / freshness columns and summary. 完了。
3. Provider-neutral refresh contract and fake/curated provider test. 完了。
4. Dry-run first refresh command with manifest output. 完了。
5. Metadata field catalog / tier / storage / freshness policy. 完了。
6. Yahoo metadata provider as the first live adapter, behind explicit opt-in. 完了。
7. CSV / manifest 更新用の `--write` path。書き込み前後の validation 付き。完了。Cache output は必要になった場合の将来範囲。
8. Local source import for JPX / curated universe expansion. 完了。Initial JPX ETF seed and domestic stock seed imported.
9. SBI ranking universe policy columns and default exclusion helper. 完了。Unknown tradability is allowed by default.
10. SBI / NISA / future 投信 metadata source import。完了。`--source-profile`、JPX stock/ETF/REIT profile、SBI US stock/ETF seed、NISA eligibility update profile/seed、ranking metadata update profile、mutual fund seed、投信 metadata columns の import path は追加済み。JPX / SBI / NISA / IMAJ / REIT source builders と imports は利用可能で、SBI US stock / ETF の Yahoo live coverage / opt-in metadata refresh、ETF enrichment、海外ETF `yahoo_symbol` mapping も実装済み。MVP ranking は stock / ETF のみを対象にし、REIT / mutual fund seed rows は将来拡張metadataとして残す。継続的なsource refresh と追加live smokeは運用保守扱い。
11. SecurityMaster repository separation only if symbol master usage spreads beyond current UI / command helpers.
12. Optional additional provider adapters only when Yahoo coverage or stability is insufficient.

完了条件:

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

現在の実装メモ:

- `ui/symbol_universe.py` defines the current required CSV columns, optional freshness/source columns, enum values, decimal fields, and duplicate ticker validation.
- Phase 16 UI は ranking と cockpit の両方で local symbol master を使う。ranking rows は共通の symbol-detail modal を開き、cockpit では銘柄選択横の `銘柄データを見る` button から同じ情報を確認できる。価格取得後のcockpit結果には、score、symbol metadata、valuation、income、price-trend checks から作る investment memo を表示する。
- Ranking modal rendering avoids per-row repeated symbol-master scans by reusing a symbol lookup map while building display rows; this keeps long-period ranking result clicks responsive.
- `backend/marketdata/symbol_metadata_schema.py` defines metadata tiers, storage policy, source/freshness requirements, enum values, decimal ranges, and future fund metadata fields.
- `symbol_universe.csv` now stores `metadata_source`, `metadata_as_of`, and `metadata_updated_at`; the current deterministic baseline is marked as `curated_csv` with `2026-05-18` metadata.
- `設定 / データ情報` shows candidate count, metadata source, metadata period, validation summary, and issue rows for `symbol_universe.csv` without blocking the existing ranking UI.
- `backend/marketdata/symbol_metadata_refresh.py` defines the provider-neutral refresh contract, deterministic `curated_csv` provider, provider diagnostics, manifest summary, and validation summary.
- `tools/refresh_symbol_universe_metadata.py` は既定で dry-run として動き、CSV / `symbol_universe_manifest.json` への書き込みは `--write` 指定時だけ行う。更新後validationにエラーがある場合、書き込みは拒否する。
- Yahoo live metadata provider は `--provider yahoo --allow-live` で利用できる。選択したticker metadataをcatalog fieldsへ変換し、symbol単位の失敗はmanifestに記録する。通常checksはnetwork-freeのまま維持する。
- `tools/build_symbol_universe_source.py` は公式raw filesをlocal source CSVへ変換する。JPX listed-stock raw Excel (`.xls` / `.xlsx`) / CSV、JPX ETF / ETN raw Excel / CSV / official HTML、JPX REIT official HTML、SBI US stock / US ETF raw CSV / Excel / CP932 HTML、NISA eligibility raw CSV / Excel を扱う。JPX listed-stock builder は `規模区分` を ranking UI 用の `market_cap_tier` に変換する。SBI stock builder は公式stock page内のETF行を除外し、SBI ETF builder はsource tickerを取り込み、非US exchange code向けの provider-specific `yahoo_symbol` mapping を保持できる。ETF builders は commodity theme と leveraged / inverse flags を保持し、ranking policy が除外判定に使えるようにする。NISA builder はふりがな付きJPX/IMAJ growth-NISA Excel headersに対応し、対象listをgrowth-eligibleとして扱い、末尾 `0` のIMAJ 5桁listed-fund codeを正規化する。曖昧な行は過剰推定せず `unknown` として残す。PDF raw files はroutine import pathには含めない。
- `backend/marketdata/symbol_universe_import.py` and `tools/import_symbol_universe_source.py` merge local source CSV rows into `symbol_universe.csv` with dry-run, manifest, append-only default, optional existing-row update, import defaults, symbol suffix normalization, and validation-before/write.
- `data/marketdata/symbol_universe_sources/jpx_etf_seed.csv` and `jpx_stock_seed.csv` are the first source seeds. 2026-05-19 時点では JPX source として国内株 / 国内 ETF 合計 68件を `symbol_universe.csv` に取り込んでいる。
- SBI証券取扱商品を初期 ranking universe の前提にする policy columns / default exclusion helper を追加した。現時点の CSV は SBI取扱確認済み master ではなく local curated / source-import seed として扱うため、`tradability=unknown` は初期 ranking で通す。
- SBI銘柄マスタ取得方針は、SBI から直接リアルタイム取得するのではなく、SBI / JPX / public source を local source CSV 化して import する。将来 adapter は source import / repository 境界に追加し、ranking logic から分離する。
- `tools/import_symbol_universe_source.py` は `--source-profile jpx_listed_stock|jpx_stock|jpx_etf|jpx_reit|sbi_us_stock|sbi_us_etf|nisa_eligibility|ranking_metadata|mutual_fund_seed` をサポートし、market / product / currency とpolicy defaultを補完する。`nisa_eligibility` は既存行のNISA metadata columnsだけを更新し、unknown symbolsは不完全行として追加せず拒否する。`ranking_metadata` は既存symbolsのranking filter fields（PER/PBR/ROE/dividend yield、market-cap tier、risk、ETF expense ratioなど）だけを更新する。`nisa_eligibility_seed.csv` は31件の既存行を更新済み。`sbi_us_stock_seed.csv`、`sbi_us_etf_seed.csv`、`mutual_fund_seed.csv` はsource seedsとして利用できる。2026-05-21 時点で JPX listed-stock source、JPX ETF/ETN official HTML source、SBI US stock/ETF official HTML source、JPX REIT official HTML source、JPX NISA 成長投資枠 ETF/ETN source、IMAJ NISA 成長投資枠 listed-fund source を取り込み、candidate master は 9,179件になり、stock 8,081件、ETF 1,034件、REIT 58件、投信 4件、ADR 2件を持つ。SBI US stock builder は `BRKB` / `UHALB` を `BRK-B` / `UHAL-B` に正規化する。
- `tools/check_symbol_universe_metadata_coverage.py` produces `data/marketdata/symbol_universe_metadata_coverage.json` as the current coverage baseline for ranking filter metadata. JPX and SBI stock rows have been supplemented with explicit opt-in Yahoo metadata where available. Current stock coverage is dividend yield 8,033/8,081, PBR 7,630/8,081, ROE 7,466/8,081, and PER 7,457/8,081. ETF coverage is dividend yield 601/1,034, index family 1,034/1,034, expense ratio 1,013/1,034, and complexity 1,034/1,034.
- Yahoo dividend-yield normalization now treats JP stock integer percent values as percent values, preventing over-scaled display such as `23%` when the source value represents `0.23%`.
- `tools/analyze_yahoo_coverage_failures.py` analyzes saved live Yahoo coverage rows without making new network calls. Current SBI US stock failures are 51 no-bars/Yahoo-unsupported plus 2 resolved aliases; SBI US ETF failures are 3 leveraged exclusions plus 11 rows with curated `yahoo_symbol` mappings.
- Ranking UI and default ranking universe are stock / ETF focused. REIT and mutual-fund rows can remain in the local master as future extension data, but `reit` / `mutual_fund` / `fund` / `investment_trust` are excluded from MVP ranking candidates. ETF leveraged/inverse rows and commodity-themed ETF rows remain stored for metadata coverage but are excluded by the ranking-universe policy.
- Ranking sort logic now uses Phase 18 symbol metadata as part of the post-fetch score: selected ranking purpose maps to a purpose-specific profile (`配当・インカム重視`, `成長性重視`, `割安性重視`, `安定性重視`, `トレンド重視`), and each profile blends market/forecast/risk signals with `database_fit_score` and `metadata_confidence_score`.

### 5.5 Phase 19: Decision Report Context MVP

状態: 完了

目的: `銘柄コックピット`、`銘柄ランキング`、`リバランス` の結果を、同じ context schema で保存・表示・export できるようにする。

範囲:

実装済みスライス:

- `backend/reporting` に Decision Report context v1 と deterministic Markdown / manifest helper を追加。
- cockpit / ranking / rebalance 由来の summary / table rows / warnings / notes を local-first に束ねる最小 schema を追加。
- Phase 18 の銘柄 metadata 整備を踏まえ、`Data coverage and confidence`、`Symbol metadata`、`Decision checkpoints` の標準 report section builder を追加。
- 銘柄コックピットとランキング結果に `Decision Report` expander を追加し、Markdown / JSON download と Markdown preview を確認できるようにした。
- リバランス結果に `投資判断レポート` expander を追加し、現在保有、目標配分、配分差分、売買案、Risk 制約違反、確認ポイントを同じ context schema で Markdown / JSON export できるようにした。
- cockpit / ranking / rebalance の Decision Report に manifest / ZIP download を追加し、context JSON、manifest JSON、Markdown を同じ export package として保存できるようにした。

Report出力方針:

- 冒頭では銘柄、作成日時、対象期間、provider、利用元 workflow、非推奨文言を明示する。
- `Data coverage and confidence` では、価格データ期間、data quality、metadata source/as-of、欠損 field、coverage rows を出す。未確認 metadata は 0 と扱わず、空欄の理由として残す。
- `Symbol metadata` では、ticker/name、市場、商品分類、NISA、investment style、時価総額 tier、SBI/ranking policy、metadata freshness を出す。
- `Investment score breakdown` では、Investment Score、Screening、Forecast agreement、Data quality、Risk signal と、その上下要因を出す。
- `Valuation / income / risk` では、PER/PBR/ROE、配当/分配金利回り・カテゴリ、ETF expense ratio/index family、risk band、warnings を出す。
- `Ranking context` では、順位、並べ替え条件、比較対象数、上位理由、同条件での注意点を出す。
- `Rebalance context` では、risk breach、提案 trade、制約、注文指示ではないことを出す。
- `Decision checkpoints` では、次に確認する業績、決算、配当方針、ETF 指数/経費率、データ欠損を整理し、売買指示にしない。

- cockpit summary / ranking result / ranking error / rebalance result / risk breach を横断する report context contract を定義する。
- 初期 export は Markdown / JSON / CSV / manifest / ZIP を優先する。
- UI リッチな PDF report / Excel report は Phase 19 の完了条件に含めず、将来の高度Export範囲として残す。
- UI / report / future assistant が同じ context を参照できるようにする。
- 投資助言ではなく、判断材料と制約を整理する report 文言に統一する。

完了条件:

- Decision Report context の最小 schema が定義されている。
- Phase 18 metadata を活かした data confidence / symbol metadata / decision checkpoints の標準 section を作れる。
- cockpit / ranking / rebalance の既存出力から report context を作れる。
- deterministic renderer で Markdown / JSON export ができる。
- report に data quality、provider、対象期間、制約、非推奨文言が含まれる。

### 5.6 Phase 20: Research RAG 根拠レイヤー

状態: 実装完了。local evidence slice 完了

Research鮮度方針:

- SMAI の通常 tests / CI は deterministic-first を維持するが、Research RAG と News RAG の product value は情報鮮度が中心になる。
- 実運用では `AI調査を更新` が外部の最新IR・開示・ニュース・provider evidence を取得/参照する標準アクションになる。通常 tests / CI は network 非依存の fake adapter / fixture で確認する。
- 外部 evidence は既定では取得時の一時参照として扱う。RAG summary / Research Score / News 表示には使うが、取得本文・変換Markdown・manifestを自動保存しない。画面やReportには source URL、provider、published_at、fetched_at、freshness_status、短い要約/引用範囲だけを残し、古い情報は warning として表示する。

現在の実装方針:

- Phase 20 は、RAG で銘柄を推奨したりランキング順位を直接変えたりする段階ではなく、既存の `銘柄コックピット` / `銘柄ランキング` / `Decision Report` に資料根拠を添える evidence layer として実装する。
- Phase 20 の local document ingestion は deterministic foundation / fixture path として残す。今後の通常ユーザー導線では、source adapter 経由で公式IR、EDINET（optional metadata/link 初期 slice 実装済み）、TDnet（初期 slice 実装済み）、企業IR site、provider profile、news などを取得/参照する。
- 9,179件の銘柄DB全体を一括RAG対象にせず、ランキング後の上位候補、コックピットで選択した銘柄、Decision Report の対象銘柄から段階的に使う。
- 初期出力は `Research Summary`、`Research Evidence`、`Research Data Quality` を中心にする。資料がない銘柄では「根拠不足」を明示し、推定で埋めない。
- `Research Score` は Phase 22 で、主に銘柄コックピット深掘りと Cockpit Decision Report の確認材料として扱う。Investment Score への接続口は optional のまま残すが、ランキング順位統合は現時点では行わない。

推奨MVPスライス:

- R0: Research RAG design cleanup。`Documents/04_Detail_Design/04-8_Onepager_Research_RAG.md` の文字化け部分を、Phase 20 方針に沿って読める日本語へ整える。
- R1: Local Document Ingestion MVP。`backend/research/` に document metadata contract と ingestion service を追加し、`data/research_docs/` 配下の Markdown / Text / CSV fixture を登録できるようにする。
- R2: Text Extraction & Chunk Store。ローカル資料を source / title / published_at / section / chunk_index / reliability と紐づく検索可能 chunk に分割する。
- R3: Keyword Retrieval MVP。symbol と query から evidence chunk を返す deterministic keyword search を実装する。top_k、freshness、source_type、reliability を保持する。
- R4: Research Summary MVP。コックピット向けに、成長材料、株主還元、事業リスク、財務安全性、確認不足を evidence 付きで要約する。LLM は使わず rule / template を既定にする。
- R4.5: UI / Report integration。銘柄コックピットに Research Summary を追加し、ランキングには「根拠あり / 最新資料が古い / 根拠不足」の状態だけを軽く表示する。Decision Report には Research Evidence section を追加する。

実装済みスライス:

- `backend/research` は、local UTF-8 document ingestion、hash dedupe、chunking、freshness-aware keyword evidence search、source-type filtering、deterministic Research Summary、missing / stale / low-reliability evidence の data-quality warnings を提供する。
- `設定 / データ情報` には、session-local の Markdown / Text / CSV upload と登録に使う `Research RAG / 根拠資料` expander がある。
- `銘柄コックピット` は `Research Evidence / 根拠資料` section と明示的な `AI調査を更新` operation card を表示する。価格データ取得だけでは Research RAG を自動実行しない。summary は判断材料向けの metric card と縦型 evidence card を使い、source documents、retrieval quality、詳細 evidence rows は折りたたみ内に置く。
- `銘柄ランキング` の row-click `銘柄データ` modal には、明示的な `AIで資料を確認` button を持つ `AI Research` tab がある。growth、shareholder return、financial safety、business risk、confirmation gap、source document names、dates、evidence counts は同じ Research Summary panel で確認する。
- `銘柄ランキング` result cards、detailed table、selected-candidate breakdown は、登録済みlocal documents と取得済みResearch reports から軽量な Research Evidence status（`根拠あり` / `最新資料が古い` / `根拠不足`）だけを表示する。ランキング順位は変更せず、全銘柄へ full Research RAG analysis を自動実行しない。
- Cockpit Decision Report は、`AI調査を更新` で report が作成され、documents または evidence がある場合だけ `Research Evidence` を含める。documents がない既存reportは変えない。

推奨完了条件:

- fake external adapter / local fixture だけで ingestion -> chunk -> keyword search -> Research Summary が動く。
- 通常 tests は外部 scraping / 外部LLM / network に依存しない。
- evidence は source_type、title、published_at、section/page、excerpt、relevance、reliability と紐づく。
- コックピットでは選択銘柄の Research Summary と evidence を確認できる。
- ランキングではRAG結果で順位を直接変えず、選択候補の根拠状態を確認できる。
- Decision Report では Research Evidence section と根拠不足 warning を表示できる。
- Research data quality は document_count、latest_document_date、evidence_count、warnings を含む。

目的: 価格・テクニカル指標だけでは拾いにくい長期企業分析の根拠を、local-first な document evidence layer として追加する。

実装順:

- R0: 要件・詳細設計。`04-8_Onepager_Research_RAG.md` は design complete。
- R1: Local Document Ingestion MVP。
- R2: Text Extraction & Chunk Store。
- R3: Keyword Retrieval MVP。
- R4: Research Summary MVP。

完了条件:

- local document / fixture だけで ingestion、chunk、検索、summary が動く。
- 通常 tests は外部 scraping / 外部LLM に依存しない。
- evidence は source、timestamp、section、confidence と紐づく。
- UI / report では根拠不足を明示できる。

### 5.7 Phase 21: 高度Research RAG - 根拠抽出と根拠付き回答

状態: 計画中。query expansion / structured extraction / grounded answer / retrieval quality / evidence reranker の初期スライスは着手済み

目的:

- Phase 20 の local-first Research Evidence layer を壊さず、登録済み Research 資料から欲しい情報を抽出し、抽出結果と ResearchEvidence を必ず紐づける。
- 銘柄コックピット、ランキングの `AI Research` tab、Decision Report で、根拠付きの自然な説明文を表示できるようにする。
- keyword search baseline を維持しながら、query expansion、optional embedding / vector store / hybrid search、evidence reranking を追加できる設計にする。
- Research Score 統合に向けて、根拠数、鮮度、信頼度、source type、根拠多様性を扱える中間 contract を整える。
- Phase 21 でも RAG 単体で売買推奨、buy / sell / hold 判断、ランキング順位や Investment Score の直接変更は行わない。

Phase 20 / Phase 21 の境界:

- Phase 20: local document registration, chunking, deterministic keyword search, Research Evidence, Research Summary, Decision Report connection.
- Phase 21: query expansion, structured evidence extraction, grounded answer generation, optional embedding retrieval, local vector store abstraction, hybrid search, evidence reranking, Research Score integration preparation.
- Phase 21.5: 個別銘柄ニュースRAG MVP。既存の Symbol Cockpit に、選択中の銘柄だけを対象にした URL 根拠付き recent news summary を追加する。市場全体ニュース画面、Research Score 化、Investment Score / ランキング順位への反映は行わない。
- Research Score の採点と Cockpit / Decision Report への表示は Phase 22 で扱う。ランキング順位統合は現時点では行わない。

範囲:

- Structured evidence extraction: `growth`, `shareholder_return`, `financial_safety`, `business_risk`, `confirmation_gap` の観点で、ResearchChunk / ResearchEvidence から主張、要約、不足情報、注意点を抽出する。
- Data contracts: `ResearchExtractedClaim`, `ResearchRetrievalCandidate`, `ResearchRetrievalQuality`, `ResearchEmbedding` などの Pydantic contract 案を整理する。抽出した claim は supporting evidence と切り離さない。
- Query expansion: `config/research_query_terms.yml` などで、成長戦略、株主還元、財務安全性、事業リスク、確認不足に関する表現ゆれを deterministic に管理する。
- Optional embeddings: `ResearchEmbeddingService` を候補とし、既定では disabled。local provider / cache を優先し、外部 embedding API は explicit opt-in にする。
- Local vector store: file-based cache または sqlite-based store を MVP 候補にする。cloud vector DB や heavy dependency は必須にしない。
- Hybrid retrieval: keyword / vector / freshness / reliability / source priority / diversity を組み合わせる `HybridResearchRetrievalService` を候補にする。vector failure 時は keyword fallback + warning とする。
- Evidence reranking: `ResearchEvidenceReranker` で relevance、reliability、freshness、official-source priority、diversity、duplicate suppression を扱う。
- Grounded answer generation: `ResearchGroundedAnswerService` を候補とし、default は template-based generation。LLM generation は optional adapter とし、Evidence にない内容を生成しない。
- UI / Decision Report: Cockpit、ranking modal、Decision Report に Research Summary、観点別抽出結果、Evidence table、Data Quality、Retrieval Quality、Grounded Answer、根拠不足 warning、非推奨注記を表示する方針を整理する。

実装済みスライス:

- Deterministic query expansion baseline is implemented in `backend/research` with `ResearchQueryExpansionService`, `ResearchQueryExpansionResult`, category-aware `ResearchSearchRequest`, and `config/research_query_terms.yml`.
- Structured extraction first slice is implemented with `ResearchExtractedClaim` and `CompanyResearchReport.extracted_claims`. Non-gap claims are generated only from supporting evidence; missing category evidence becomes `confirmation_gap` without changing scoring or ranking.
- Template grounded answer first slice is implemented with `ResearchGroundedAnswerService` and `CompanyResearchReport.grounded_answer`. It uses only extracted claims and referenced evidence, keeps warnings, and explicitly states that the output is not a buy/sell recommendation.
- Retrieval quality first slice is implemented with `ResearchRetrievalQuality` and `CompanyResearchReport.retrieval_quality`. It records the keyword backend, category query set, expanded terms, candidate count, evidence count, and retrieval/data-quality warnings for UI and Decision Report display.
- Evidence reranker first slice is implemented with `ResearchEvidenceReranker`. It keeps `ResearchEvidence` output compatible while deterministically reranking by relevance, reliability, freshness, source-type priority, and duplicate suppression.
- UI / Decision Report display first slice is implemented: cockpit and ranking Research Summary panels now show grounded answer and retrieval quality rows, the detail expander shows extracted claims, and the Research Evidence report section carries grounded answer, retrieval quality, and extracted claim rows without changing ranking or scoring behavior.
- Optional vector / hybrid retrieval の初期スライスは、`ResearchEmbedding`、`ResearchRetrievalCandidate`、`ResearchDisabledVectorStore`、`ResearchHybridScoreWeights`、`ResearchHybridScorer` で実装済み。既定vector storeはdisabledのままで、retrieval-quality warningを返す。hybrid scoringはdeterministicだが、既定keyword search pathにはまだ接続していない。
- Local embedding generation first slice is implemented with `ResearchEmbeddingService`. It generates deterministic hash-based local vectors for `ResearchChunk` text and query text, records `text_hash` / `embedding_model` cache-key fields, and can explicitly upsert generated embeddings into writable vector stores without using external embedding APIs.
- Optional vector-index build workflow first slice is implemented with `ResearchVectorIndexService` and `ResearchVectorIndexSummary`. It rebuilds a writable vector store from already chunked local Research documents, reports chunk / embedded counts and missing text-index warnings, and keeps vector indexing as an explicit optional step.
- Keyword-fallback hybrid retrieval wrapper の初期スライスは `HybridResearchRetrievalService` で実装済み。vector candidates がある場合は、hybrid-scored candidates を `ResearchEvidence` へ戻す。vector search がdisabledまたはemptyの場合は既存keyword retrievalへfallbackし、retrieval qualityにfallback warningsを記録する。
- In-memory local vector store first slice is implemented with `ResearchInMemoryVectorStore`. It stores `ResearchRetrievalCandidate` + `ResearchEmbedding` pairs, searches by optional `ResearchSearchRequest.query_vector` with deterministic cosine similarity, filters by symbol/source type, and reports vector retrieval quality without external dependencies.
- File-backed vector cache first slice is implemented with `ResearchFileVectorStore`. It persists the same vector candidate / embedding pairs as UTF-8 JSONL, reloads them across service instances, reports empty or invalid cache conditions through Research search errors / retrieval-quality warnings, and keeps the default keyword retrieval path unchanged.
- `ResearchRetrievalService` can expand category queries while preserving Phase 20 keyword search behavior when no category or expanded terms are supplied.
- `ResearchAnalysisService` uses category-aware expansion for the existing growth / shareholder_return / financial_safety / business_risk topic searches.

候補contract:

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

設定方針:

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

守る線:

- RAG output は売買推奨ではなく、判断材料、根拠、注意点、確認不足の整理に限定する。
- Evidence がない主張を生成しない。根拠不足は `confirmation_gap` として明示する。
- 資料がない銘柄を悪い銘柄として扱わない。
- 外部 LLM / 外部 embedding API / 外部 vector DB は explicit opt-in とし、通常 CI は network / scraping / external API に依存しない。
- 公式 IR や開示資料を provider snapshot より優先する。
- 長文の丸写しを避け、短い引用または要約に留める。
- Investment Score への統合は Phase 22 以降で、明示的に有効化された場合のみ行う。

テスト方針:

- Unit: query expansion、ResearchExtractedClaim validation、embedding cache key generation、vector store disabled mode、hybrid score calculation、evidence reranking、template answer generation、confirmation_gap generation。
- Integration: sample Markdown/Text/CSV -> chunk -> keyword search -> query expansion -> evidence extraction -> grounded answer -> Decision Report section。
- Fallback: embedding disabled 時は keyword search のみで動作、vector store failure 時は keyword fallback、LLM disabled 時は template answer、evidence 不足時は confirmation_gap。
- Golden: 既知の Research fixture から期待するカテゴリ別抽出、warning、根拠のない主張を生成しないことを確認。
- CI: 外部 API、外部 LLM、live scraping、network に依存しない deterministic fixture を使う。

受け入れ条件:

- Phase 21 として「高度Research RAG - 根拠抽出・根拠付き回答生成」がロードマップと詳細設計に追加されている。
- Phase 20 の keyword search baseline と local-first / deterministic-first 方針を壊していない。
- embedding / vector / hybrid search が optional として整理されている。
- query expansion、ResearchExtractedClaim、Grounded Answer、Retrieval Quality、UI / Decision Report 反映方針が明記されている。
- LLM 利用は optional adapter として明記され、通常 CI が外部 API や network に依存しない方針が維持されている。

### 5.7.5 Phase 21.5: 個別銘柄ニュースRAG MVP

状態: 初期local deterministic slice 実装済み

目的:

- まずは既存の `銘柄コックピット` に、選択中の銘柄だけを対象にした個別銘柄ニュース深掘りを小さく追加する。
- Research Evidence 内の標準導線は `AI調査を更新` に集約し、AI調査更新時に銘柄名、ticker、related keywords から news evidence も取得・整理する。
- 根拠 URL 付きの最新ニュース要約、投資観点、材料の方向感、鮮度を表示するところまでを MVP とする。
- ニュースは投資判断補助情報であり、売買推奨、buy / sell / hold 判断、Investment Score、ランキング順位の変更には使わない。

初期表示項目:

- `title`
- `url`
- `source`
- `published_at`
- `summary`
- `investment_viewpoint`
- `sentiment_for_investment`
- `freshness_status`

初期data contract案:

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

初期分類方針:

- `investment_viewpoint`: `earnings`, `growth`, `shareholder_return`, `risk`, `macro`, `other` に絞り、初期分類を増やしすぎない。
- `sentiment_for_investment`: `positive`, `negative`, `neutral`, `mixed`, `unknown` とし、buy / sell / hold ではなくニュース材料の方向感として扱う。
- `freshness_status`: `latest`, `recent`, `stale`, `unknown` とし、古いニュースを最新材料のように扱わない。

Phase 21.5 の対象外:

- 新しい `投資レーダー` 画面の実装
- 市場全体トピックの自動抽出
- 注目ジャンル / 業界ランキング
- 関連銘柄の自動抽出
- Watchlist 連動
- Decision Report への自動反映
- Research Score 化
- Investment Score への反映
- ランキング順位への反映
- ニュースクラスタリング
- impact horizon 分類
- 外部 LLM 必須化
- CI での外部ネットワーク必須化

守る線:

- source URL がない内容を断定しない。
- 古いニュースは warning または `freshness_status` で明示する。
- 外部ニュース取得は adapter 化し、`AI調査を更新` の標準 source として扱う。
- 通常 tests / CI は外部 network、live scraping、外部LLM に依存させない。
- 外部 LLM は必須にせず、template / deterministic fallback を維持する。
- RAG の出力は投資判断補助であり、最終判断はユーザーが行う。

実装済みスライス:

- `backend/research` は `StockNewsEvidence`、`StockNewsRequest`、`StockNewsReport`、`StockNewsAnalysisService` を持つ。
- 初期の決定的なtest source は `source_type="news"` のlocal Research documents。プロダクト導線では、通常ユーザー向けの情報源を外部fresh news/source adapters へ置き換えつつ、tests は network-free に保つ。
- News documents には `url:` / `source_url:` 行、または別の `https://...` URL が必要。source URL がない item は fact として要約せず、warning 付きで除外する。
- `銘柄コックピット` は標準の `AI調査を更新` action を通じて Recent News を Research Evidence cards に統合する。メインoperation card に news-only button を出さず、card/detail に title、URL、source、published_at、summary、investment_viewpoint、sentiment_for_investment、freshness_status を表示する。
- このsliceは Investment Score、Research Score、Decision Report、ランキング順位を変更しない。

後続child roadmap:

- Phase 21.6: External Research Document Fetch MVP。`AI調査を更新` の標準動作として、EDINET（`EDINET_API_KEY` がある場合のみ live call、未設定時は no-op）、TDnet（初期 slice 実装済み）、IR site / provider profile などの資料取得/参照 adapter を使う。取得本文は session-local RAG store で一時参照し、既定では `data/research_docs/` や cache/archive に保存しない。表示・Report には source URL、provider、fetched_at、published_at、freshness_status、短い要約/引用範囲を残す。通常 tests / CI は network 非依存の fixture / fake adapter で確認する。
- Phase 21.7: External Stock News Fetch MVP. `AI調査を更新` から、選択中の銘柄名 / ticker / related keywords に限定した外部ニュース取得 adapter を使う。初期 backend slice として `ExternalStockNewsAdapter` / `ExternalStockNewsFetchService` / `ExternalResearchStockNewsAdapter` を追加済みで、取得結果を `StockNewsEvidence` 互換の title / URL / source / published_at / summary / investment_viewpoint / sentiment_for_investment / freshness_status として一時表示できる形に正規化する。既定ではニュース本文を保持せず、source URL がない内容は断定せず、外部 LLM は必須にしない。
- Phase 21.6 / 21.7 は、Phase 21.5 の local deterministic slice を test/fallback として残しつつ、通常ユーザー導線では外部最新情報を優先する。外部取得に失敗した場合はローカル fixture / saved archive / fallback evidence 表示に戻れる設計にする。
- External fetch child phases は判断補助に限定する。Investment Score、Research Score、Decision Report 自動反映、ランキング順位変更、buy / sell / hold 判断は行わない。

実装済みスライス:

- `backend/research` は `ExternalResearchFetchRequest`、`ExternalResearchSourcePayload`、`ExternalResearchFetchService`、freshness_status 付き source trace entries、`ExternalResearchSourceAdapter` protocol、default composite adapter を持つ。
- `EDINETResearchAdapter` は `EDINET_API_KEY` 設定時だけ公式の有価証券報告書 metadata/source links を返し、key がない場合は payload を返さない。`TDnetResearchAdapter` は国内上場企業IRの適時開示 source links、`CompanyIRSiteResearchAdapter` は公式website metadata から企業公式IR page、`YahooFinanceResearchAdapter` は provider profile と recent news payloads を返す。`ExternalStockNewsFetchService` は external news adapter output を `StockNewsEvidence` へ正規化し、URL dedupe、freshness warnings、明示的な network opt-in gate を扱う。通常 checks では fake HTTP / JSON / ticker/news factories を注入するため、live EDINET、TDnet、company IR、Yahoo、news-provider call は不要。
- The current implementation keeps an explicit `allow_network=True` backend safety gate, removes the separate Cockpit `外部資料取得（明示許可）` UI, and makes `AI調査を更新` the standard external source search action while retaining fake-adapter tests and backend safety boundaries.
- External RAG fetch is transient-by-default. Fetched source text is registered into the session-local Research RAG store only for the current analysis / score / display pass, while persistent document payloads, converted Markdown, local paths, document hashes, and manifests are not produced unless the user explicitly chooses a future `資料を保存する` / archive action.
- UI/report display focuses on provider, fetched_at, published_at, source URL, freshness_status / freshness warnings, and generated summary/evidence snippets. Cockpit Decision Report includes an `外部参照ソース` section for these trace rows without including fetched source text, local paths, document hashes, or manifests. It should not imply that the app is building a permanent local document repository from live sources.
- 通常 tests は fake adapter のみを使い、CI では live external source、scraping、外部LLM、network call を不要にする。
- A `source_type="news"` payload becomes available to the existing Stock News RAG cockpit flow after registration; provider profile / IR payloads become normal Research Evidence documents.

ローカル読みやすさ改善 slice:

- R9: ResearchBrief / Local Research Memo。表示専用の `ResearchBrief` / `ResearchMetric` 層を追加し、`CompanyResearchReport`、evidence、provider profile、news、TDnet trace を、外部LLMなしで読めるローカル企業調査メモへ変換する初期 slice は実装済み。
- R10: ResearchFactSummary / User-facing Fact Layer。初期 slice は実装済み。`ResearchBrief` の前段に source-backed fact contract を追加し、取得状態ではなく、事業概要、主要事業、地域・収益源、IR / 公式資料、主要定量指標、業績見通し、配当・株主還元方針、直近イベント、良材料候補、注意材料候補、未確認項目をユーザーが読める形で整理する。
- R10.4: CompanyResearchSummary / 企業リサーチレポート。初期 slice は実装済み。`CompanyResearchReport`、`ResearchBrief`、`ExternalResearchFetchResult`、`StockNewsReport`、`InvestmentInsight` から `CompanyResearchEvidence` を正規化し、企業概要、主な事業、製品・サービス、地域、規模感、主要定量指標、IR資料取得状況、最新ニュース、不足している重要情報を生成する。IR / news / metric では found / missing / unparsed / unverified を区別する。根拠資料画面ではこれを主役にし、AI読み取りメモや投資判断メモは後段の補助情報に下げる。
- R10.5: InvestmentInsight / 投資判断サマリー。初期 slice は実装済み。`ResearchBrief` とは別の display-only contract と builder を追加し、`CompanyResearchReport`、`StockNewsReport`、`ExternalResearchFetchResult` を status、confidence、primary action、良い材料、注意材料、公式資料・主要指標の確認不足に再分類する。Research Score、Investment Score、ランキング順位には反映しない。
- R10.6: InvestmentQuestionSummary / 企業理解の確認ポイント。初期 slice は実装済み。`CompanyResearchReport`、`ResearchBrief`、`InvestmentInsight`、`ExternalResearchFetchResult`、`StockNewsReport` から、事業モデル、売上・利益トレンド、収益性、今期見通し、成長ドライバー、リスク、株主還元、バリュエーション、直近ニュース影響、最重要論点の10質問を必ず生成する。情報がない場合は `判断できません` / `未取得` と明示し、根拠レベルを 高 / 中 / 低 / 不足 で表示する。売買推奨や割安・割高の断定はしない。
- R9 では定量指標と定性トピックを分離する。初期指標は売上高、営業利益、純利益、EPS、配当、PER、PBR、ROE、時価総額とし、取得できない重要指標は `missing_metrics` に出す。
- R9 では provider profile を企業概要 / 事業内容に圧縮し、通常表示では raw provider field を隠す。Provider Symbol、Quote Type、Exchange、Currency、raw Sector / Industry、provider field dump は詳細データのみに残す。
- R9 では local keyword rule で成長材料、業績材料、株主還元、リスク、良材料候補、注意材料候補、不足根拠に分類する。文言は買い/売り結論ではなく、候補 / 確認ポイントとして扱う。
- R9 の source confidence は情報源の信頼度だけを示す。official IR / TDnet / EDINET / company IR = high、Yahoo Finance / provider profile / news = medium、keyword-only extraction = low とする。
- R10 は local rule-based extractor を既定とし、通常 tests / CI は fake report / fixture だけで確認する。local lightweight LLM は後続候補に留め、導入する場合も抽出済み fact を入力、validated JSON を出力、失敗時は deterministic fallback とする。
- Cockpit Research Summary の主表示順は、企業リサーチサマリー -> 定量情報サマリー -> IR情報サマリー -> 最新ニュース・開示サマリー -> 投資ヒントとなるニュース -> ニュース・開示の出典 -> 企業理解の確認ポイント -> 詳細情報・開発者向け とする。`詳細情報・開発者向け` には、Research Score、データ品質、検索品質、抽出主張、根拠資料詳細、外部source取得状況など、通常表示と用途が重ならない検証用データだけを置く。
- Research Score は AI整理メモや調査メモの後ろへ寄せ、最初に読む内容が score table ではなく調査メモになるようにする。
- Tests は deterministic を維持する。fake report / fake source trace、regex metric extraction fixture を使い、live network と外部LLMに依存しない。

### 5.8 Phase 22: Research Score とコックピット深掘り導線

状態: 初期backend slice / UI表示slice 実装済み。Cockpit ResearchScore UX polish の初期実装済み。次は実画面回帰確認

現在の統合方針:

- Phase 22 は、Phase 20 / Phase 21 の evidence / extracted claims / grounded answers を、説明可能な Research Score として定量化し、主に `銘柄コックピット` の深掘り画面と Cockpit Decision Report で確認できるようにする。
- Research Score は evidence と紐づく補助スコアにする。資料不足時は欠損または低信頼として扱い、推定で埋めない。
- Investment Score への接続口は optional input として保持するが、初期 weight は 0.0 のままにし、既存の Screening / Forecast / Risk / Data Quality score とランキング順位を変えない。
- Ranking では Research Score を順位計算に混ぜない。比較候補を見つけた後、ユーザーがコックピットで深掘りして判断する導線を優先する。
- Decision Report では Research Score の内訳、confidence、warnings、supporting evidence を Research Evidence と並べて確認できるようにする。
- ランキング順位統合や opt-in sort profile は現時点では実装対象外。必要性が再確認された場合のみ、後続フェーズで別タスクとして扱う。

推奨統合スライス:

- R5: Vector Search / Hybrid Search optional adapter。keyword retrieval を baseline に残し、embedding / vector は optional にする。
- R6: Research Score MVP。growth、profitability、shareholder_return、financial_safety、business_risk、disclosure_quality、freshness を rule/template で採点し、evidence_count と confidence を保持する。Backend 初期 slice は `ResearchScore` / `ResearchScoreService` として実装済み。
- R7: コックピット / Report / optional score plumbing。Research Score を `research_scores_by_symbol` と `scoring.weights.research` default 0.0 で optional input として保持しつつ、通常順位は変えない。Display 初期 slice は Cockpit / Ranking の共通 Research Summary panel に Research Score summary / component / warning rows を出し、AI Research report 由来の score を selected-candidate breakdown に確認材料として出す形で実装済み。Cockpit UX polish slice では、Research Score の折りたたみ内に読み方、要約、観点別内訳、注意点をまとめ、詳細データ側の重複表示を外した。News Source URL UX polish slice では、既存の外部参照ソースURL表示を維持しつつ、`最新ニュース・開示サマリー` と `投資ヒントとなるニュース` は `Market Intelligence` の主表示カードとして扱い、`ニュース・開示の出典を表示（URL付きN件）` は初期折りたたみの小さな citation list としてURL付きニュース、TDnet、企業IR、EDINET、Yahoo Finance を確認できるようにした。Research Summary advanced-detail polish slice では、詳細側を `詳細情報・開発者向け` に一本化したうえで、通常表示と用途が重なるAI整理メモ、読み方サマリー、出典カード再掲を省き、Research Score、データ品質、検索品質、抽出主張、根拠資料詳細、外部source取得状況などの検証用データに絞った。出典リンクは href / target / rel と source-specific action label を維持し、ニュース専用URLが無い場合も、外部参照ソース側に公式資料・provider URLがある可能性を案内する。Research 側 Yahoo / company IR adapter は MarketData 側と同じ yfinance cache / shared session 設定を使うため、AI調査更新時の外部参照ソース取得経路も同じ環境前提で動く。2026-06-02 の回帰では、大阪ガスを含む24銘柄で Cockpit の `根拠資料の確認材料` 文脈と Ranking lookup の `参考情報` 文脈、資料不足 no-op、ETF 表示、旧 `Ranking順位` 表記なしを確認済み。Report 初期 slice は Cockpit Decision Report の `Research Score` section として実装済みで、内訳、supporting evidence、confidence、warnings、非推奨注記を Research Evidence と並べて保存する。
- R8: External Source Adapter。EDINET optional metadata/link adapter、TDnet、企業IR site adapter、Google News RSS headline search、Yahoo Finance profile / news、外部ニュース adapter/service 正規化は初期 slice 実装済み。Google News RSS は Google検索ヘッドラインに近い一般ニュースの幅を補う first adapter とし、会社名・関連キーワード・銘柄コードに決算/業績/株価/配当などの投資文脈語を添えて `source_type=news` に正規化する。Additional paid/API news providers は後続 scope とし、通常 checks は fake adapter / RSS fixture で network 非依存にする。
- R8a: Cockpit 投資ヒントニュース cards。`最新ニュース・開示サマリー` の直後に、URL付きの `StockNewsEvidence` だけを `投資ヒントとなるニュース` / `注目材料 Top 3` として最大3件カード表示する初期 slice を実装済み。TDnet、企業IR、EDINET、provider profile、URL不足ニュースはこの専用カードに混ぜず、下部の `ニュース・開示の出典` / `外部参照ソース` / 詳細データで確認する。カードはIR/開示の根拠カードとは別系統の `Market Intelligence` ヘッドラインUIとし、タイトル、公開日、鮮度、出典、材料分類、確認観点、短い要約、種別アクセント、右側の `元記事を見る` 導線を優先して表示する。カード全体をクリックしてURLを開けるようにし、`target="_blank"` / `rel="noopener noreferrer"`、href保持、raw URL非表示、長い `なぜ見るか`、`追加確認` 説明の通常カード非表示を維持する。売買推奨・ランキング順位・Research Score 算出には使わない。Google News RSS 由来のURL付き一般ニュースはこのカードに入る。

推奨完了条件:

- Research Score は evidence と紐づいて説明できる。
- Research Score の optional weight は設定で管理でき、既定値 0.0 のままランキング順位と通常の Investment Score を変えない。
- evidence 不足時は score 欠損または低信頼として表示される。
- Cockpit Research Summary と Cockpit Decision Report では、Research Score が売買推奨ではなく根拠資料の充実度・鮮度・信頼度の確認材料として表示される。
- Ranking は順位統合ではなく、候補比較からコックピット深掘りへ進む導線を保つ。
- external source adapter は通常 checks に入れない。
- 2026-06-02時点で、Phase 22 Research Score UX polish の実画面回帰スプリントは完了。live external fetch は環境依存のため別 smoke とし、通常確認は fake/local fixture で network 非依存に維持する。

目的: Research RAG の evidence / summary / Research Score を、銘柄コックピット深掘りと Cockpit Decision Report で確認しやすい判断材料にする。

実装順:

- R5: Vector Search / Hybrid Search。optional adapter として扱い、keyword retrieval を baseline に残す。
- R6: Research Score MVP。
- R7: コックピット / Report / optional score plumbing。ランキング順位統合は現時点では行わない。
- R8: External Source Adapter。live scraping / external source は adapter 化し、通常 checks は fake adapter / fixture で代替する。

Phase 22.x: 投資レーダー / Investment News dashboard

状態: 投資レーダー画面、Google News RSS Standard Mode、銘柄ユニバース補完型の投資ヒートマップを実装済み。詳細フィルタ、Watchlist連動、通知、追加providerは後続

目的: 新画面 `投資レーダー` を、単なるニュース一覧ではなく、市場全体の温度感、注目テーマ、関連銘柄への深掘り導線を提供する市場ニュースコックピットとして設計する。ニュースだけで判断を完結させず、気になる材料を `銘柄コックピット` で確認する入口にする。

現在の前提:

- 既存実装では、Cockpit Research Summary 内に `Market Intelligence`、URL付き `投資ヒントとなるニュース`、`ニュース・開示の出典` citation list がある。
- 独立した `投資レーダー` 画面は実装済み。ニュース横断ランキング、News Score 化、Watchlist 連動、通知は未実装。
- Phase 22 本体の Research Score 方針は維持し、Investment News / 投資レーダー dashboard は Phase 22.x の UI / backend snapshot slice として扱う。
- `backend/news/dashboard.py` で deterministic `build_news_dashboard_snapshot` / `build_demo_news_dashboard_snapshot` を実装し、保存済みsnapshotがない場合も network-free demo snapshot で表示できる。
- `backend/news/sources.py` で Standard Mode の市場横断ニュース取得層を追加済み。手動更新時に Google News RSS を12カテゴリで広めに取得し、raw 150〜250件程度の候補からURL/title重複を除き、最大100件の dashboard snapshot に圧縮する。通常 tests は Static adapter / RSS fixture で network-free に維持する。
- `ui/views/news.py` で `投資レーダー` 画面を追加し、side menu / routing / related-symbol cockpit handoff を `ui/components/sidemenu.py` と `ui/app.py` に接続済み。タイトル右上の `情報鮮度` バッジには取得時刻をJSTで小さく表示する。ニュースカードの関連銘柄は `本文に出た銘柄` を最大8件まで優先表示し、残り枠に `SMAI推測候補` を可変で補完する。投資ヒートマップの銘柄タイルはニュース直結の関連銘柄だけでなく、ローカル銘柄ユニバース全体からカテゴリ適合、時価総額帯、データ品質、ニュース鮮度、材料タイプ、市場シグナルを使って注目度順に補完する。企業名を主、シンボルを補助タグとして表示し、クリックで同一アプリ内の `銘柄コックピット` に遷移する。

MVP 必須機能:

- 上部: 市場ニュースヘッドライン
  - 固定サマリーではなく、ニュースティッカー / 速報カード / 重要ニュースの自動ローテーション風 UI を配置する。
  - 表示項目は title、source_name、source_type、published_at、freshness_status、material_type、related_symbols、短いAIコメント、元記事URL。
  - MVP では realtime 通信は不要。fake fixture / snapshot 内のニュースを一定間隔で切り替える UI でよい。
  - ユーザー操作による一時停止、hover 時停止、URLクリックを将来拡張しやすい構造にする。
- ニュース仕入れ Standard Mode
  - 手動更新ではカテゴリ別 Google News RSS を使い、半導体・AI、決算、株主還元、為替・金利、金融、エネルギー、ETF、地政学、政策、日本株、米国株、小売・消費の12カテゴリを初期対象にする。
  - アプリ負荷を抑えるため、raw取得候補は約150〜250件、正規化・重複排除後は最大100件、初期UI表示はヘッドライン/カード/カテゴリレーンで20〜30件程度に抑える。
  - Google RSS / provider 障害時は既存 cache、保存済みがなければ network-free demo snapshot にフォールバックする。
- 中央上: 投資ヒートマップ
  - 株式ヒートマップ風に、投資カテゴリをセクター枠、関連銘柄をタイルとして詰め、値動き / 材料シグナルを注意材料・中立・好材料の温度感として確認できる配色にする。
  - `heat = news_intensity + abs(price_change_pct) + volume_activity_score` を初期案とし、カテゴリ、region、price_change_pct、volume_activity_score、news_count、risk_count、positive_count、official_source_count、freshness_ratio を表示する。
  - 銘柄タイルは `related_symbols` の直接表示だけで終えず、`data/marketdata/symbol_universe.csv` の広い銘柄候補からカテゴリ profile、sector / theme / market / asset_type、時価総額帯、データ品質、ニュース材料スコアを使って注目度順に補完する。
  - タイルにはローカル銘柄名 / 企業名、シンボル、値動き / 材料シグナルを併記し、企業名を読み取りの主情報、シンボルを小さな補助タグとして扱う。長い名称は省略しつつ tooltip / title で確認できるようにする。
  - 値動き / 材料シグナルの方向をタイル色、カテゴリの注目度をセクター枠サイズ、値動きの大きさをタイル内テキストとして見せる。
  - タイルクリックで該当銘柄の `銘柄コックピット` を開き、ニュース画面だけで判断を閉じずに深掘りへ進める。
- 中央下: 3列カード型の投資カテゴリ別ニュースレーン
  - 国内株、米国株、ETF、半導体・AI、金融、エネルギー、為替・金利、決算・業績修正、配当・株主還元、政策・規制、地政学・マクロリスクを初期カテゴリ候補にする。
  - MVPでは各カテゴリの代表カードを3列で並べる。将来はカテゴリ内に 3〜5 件程度のカードを横スクロール / フィルタ付きで増やす。
  - カード項目は title、source_name、source_type、url、published_at、fetched_at、freshness_status、summary、material_type、related_symbols、official_source badge、AI分析コメント、投資確認観点。
- AI分析コメント / 投資確認観点
  - MVP では LLM 生成は不要。material_type / category / source_type に応じた deterministic template comment でよい。
  - `ai_comment: str | None` と `investment_checkpoints: list[str]` を保持し、将来 LLM / RAG 生成へ差し替えやすい関数境界にする。
  - コメントは売買推奨に見えないようにし、買い / 売り / 今すぐ投資 / 必ず上がる / 確実に儲かる等の断定表現を避ける。
- 銘柄コックピットで確認 導線
  - `related_symbols` が1件以上あるニュースカードには、シンボルだけでなくローカル銘柄名 / 企業名が分かるボタンと `銘柄コックピットで確認` 導線を表示する。
  - ニュースだけで銘柄評価、Investment Score、Research Score、ランキング順位を変更しない。

MVP で見送る機能:

- 右側フィルタ、詳細なニュース一覧、高度な検索、ソース別の細かい絞り込み。
- Watchlist 連動、通知、SNS sentiment、高度なクラスタリング。
- News Score、ニュースによる Investment Score / Ranking 順位への統合。
- 売買推奨、自動売買、buy / sell / hold 判断。

実装候補:

- `backend/news/contracts.py`: `NewsHeadlineCard`、`NewsHeatmapCell`、`NewsCategoryLane`、`NewsDashboardSnapshot`。
- `backend/news/dashboard.py`: `build_news_dashboard_snapshot`、`build_demo_news_dashboard_snapshot`、heatmap / category lane 集計。
- `backend/news/sources.py`: `GoogleNewsRSSDashboardAdapter`、`StaticNewsSourceAdapter`、`build_standard_news_dashboard_snapshot`、RSS parsing、dedupe、Standard Mode category queries。
- `ui/views/news.py`: `投資レーダー` 画面。市場ニュースヘッドライン、株式ヒートマップ風の投資ヒートマップ、3列カード型カテゴリ別ニュースレーン、銘柄名付き関連銘柄 handoff を表示する。市場指標が欠ける heatmap cell はニュース材料から代理シグナルを補完する。投資ヒートマップの銘柄タイルは関連銘柄とローカル銘柄ユニバース候補を注目度順に混ぜ、同一アプリURLで `銘柄コックピット` へ遷移する。
- `ui/components/sidemenu.py` / `ui/app.py`: `投資レーダー` を side menu と routing に追加済み。

データ構造案:

```python
class NewsHeadlineCard(BaseModel):
    title: str
    summary: str | None = None
    url: str | None = None
    source_name: str | None = None
    source_type: str
    published_at: datetime | None = None
    fetched_at: datetime | None = None
    freshness_status: str
    category: str
    region: str | None = None
    material_type: str
    related_symbols: list[str] = []
    is_official_source: bool = False
    ai_comment: str | None = None
    investment_checkpoints: list[str] = []

class NewsHeatmapCell(BaseModel):
    category: str
    region: str | None = None
    price_change_pct: float | None = None
    volume_activity_score: float | None = None
    news_count: int
    risk_count: int
    positive_count: int
    official_source_count: int
    freshness_ratio: float
    heat_score: float
    dominant_material_type: str | None = None

class NewsCategoryLane(BaseModel):
    category: str
    headlines: list[NewsHeadlineCard]

class NewsDashboardSnapshot(BaseModel):
    generated_at: datetime
    fetched_at: datetime | None = None
    freshness_status: str
    stream_headlines: list[NewsHeadlineCard]
    heatmap_cells: list[NewsHeatmapCell]
    category_lanes: list[NewsCategoryLane]
```

テスト方針:

- `tests/test_news_dashboard_service.py` を追加し、fake fixture から network-free に snapshot を生成する。
- `tests/test_ui_news_view.py` を追加し、statusless dashboard、heatmap frame、stock-heatmap HTML、safe source link HTML、related-symbol handoff symbol を確認する。
- stream_headlines、heatmap_cells、category_lanes、source URL 保持、related_symbols ありの場合の Cockpit 導線対象、ai_comment、investment_checkpoints を確認する。
- published_at / fetched_at 欠落時も壊れないことを確認する。
- 禁止表現テストとして、買い、売り、今すぐ投資、必ず上がる、確実に儲かる等を含まないことを確認する。

Phase 22.x 完了条件:

- サイドメニューから `投資レーダー` 画面を開ける。
- 上部に流れる市場ニュースヘッドラインが表示される。
- ニュースカードが自動ローテーション風に表示される。
- 値動き、取引量、ニュース量を合わせた株式ヒートマップ風の投資ヒートマップが表示される。ヒートマップタイルにも銘柄名 / 企業名とシンボルが併記され、ニュース直結の関連銘柄だけでなく広い銘柄ユニバースから注目度順に候補が補完される。市場指標が欠ける場合も `ニュース代理` として材料シグナルが表示され、`未取得` だけのヒートマップにならない。タイルクリックで該当銘柄の `銘柄コックピット` に遷移できる。
- 投資カテゴリ別ニュースレーンが3列カードで表示される。
- ニュースカードにAI分析コメント / 投資確認観点が表示される。
- 関連銘柄があるニュースカードに、`本文に出た銘柄` と `SMAI推測候補` を分けた `銘柄コックピットで確認` 導線が表示される。本文抽出は最大8件まで優先し、推測候補は残り枠に可変で補完する。
- 元記事URLがクリック可能。
- 手動更新で Standard Mode の外部RSS取得を実行し、重複除去・最大100件保存・既存cache fallback が働く。
- 右側フィルタ / 詳細一覧は未実装でよい。
- fake fixture による network-free regression test が通る。
- 既存の Research Summary / ニュースURL表示仕様を壊さない。

Phase 22.y: News Background Refresh & Cache Layer

状態: 実装完了

目的: 投資レーダー / Investment News dashboard のニュース取得、分類、AIコメント生成、ヒートマップ生成を、起動時、手動更新、将来の定期更新で繰り返しても、ニュースキャッシュ、更新履歴、取得ログ、エラーログ、一時ファイル、古い snapshot、source raw data、debug dump が無制限に増えないようにする。ローカルアプリとして長期利用してもストレージを圧迫しない設計を MVP 時点から入れる。

現在の実装メモ:

- `backend/news/contracts.py` に `NewsHeadlineCard`、`NewsHeatmapCell`、`NewsCategoryLane`、`NewsDashboardSnapshot`、`NewsUpdateStatus` を追加済み。`StrictBaseModel` により raw provider response など未知 field は拒否する。
- `backend/news/cache.py` に `normalize_snapshot_for_cache`、件数 / 文字数上限 constants、`news_snapshot_item_count`、禁止表現検出 helper、latest snapshot load/save、`.prev` 最大1世代 backup、`.tmp` atomic save、cache cleanup、status file load/save、cache file size helper を追加済み。
- `backend/news/logging_utils.py` に `RotatingFileHandler` ベースの news update logger を追加済み。`backend/news/update_manager.py` に TTL / 最小更新間隔 / bounded retry / failure fallback / status 更新を扱う refresh manager を追加済み。
- network-free tests で cache limit、atomic save、cleanup、log rotation、TTL skip、failure fallback、巨大 raw error 非出力を確認済み。

基本方針:

- メインキャッシュは原則として最新の `NewsDashboardSnapshot` 1件だけを保持する。
  - 保存先候補: `data/cache/news_dashboard_snapshot.json`
  - 更新成功時は既存ファイルを上書きし、古い snapshot を無制限に残さない。
- 直前バックアップは最大1世代まで保持してよい。
  - 保存先候補: `data/cache/news_dashboard_snapshot.prev.json`
  - 更新開始前に現行 snapshot を `.prev` に退避し、更新成功後に新 snapshot を保存する。
  - 更新失敗時は現行または `.prev` を維持する。
  - `.prev.1`、`.prev.2` のような多世代 backup は作らない。
- raw source data は原則として永続化しない。
  - 保存するのは UI 表示と再利用に必要な正規化済みデータのみ。
  - 保存対象は title、summary、url、source_name、source_type、published_at、fetched_at、freshness_status、category、material_type、related_symbols、ai_comment、investment_checkpoints、heatmap_cells、category_lanes。
  - provider raw response、HTML本文全文、取得本文全文、debug dump、大量履歴配列は保存しない。
  - debug flag が有効な場合だけ一時保存を検討し、通常運用では保存しない。

ログ設計:

- ニュース更新処理用ログを追加する場合は、必ず `logging.handlers.RotatingFileHandler` を使う。
  - 保存先候補: `logs/news_update.log`
  - 推奨設定: `maxBytes=1MB`、`backupCount=3`
  - 最大でも `news_update.log`、`news_update.log.1`、`news_update.log.2`、`news_update.log.3` 程度に収める。
- INFOログは更新処理の要約のみ残す。
  - 残してよい情報: refresh started、refresh skipped because cache is fresh、refresh succeeded、refresh failed、generated_at、fetched_at、news_count、heatmap_cell_count、category_lane_count、elapsed_ms、error type。
  - 残さない情報: ニュース本文全文、provider raw response、HTML全文、API key、認証情報、個人情報、巨大JSON、stack trace の過剰な重複。
- ERRORログも肥大化させない。
  - 連続失敗回数を status に持つ。
  - 同一エラーの連続出力を抑制できる構造にする。
  - stack trace は必要最小限にし、大量リトライをしない。
  - リトライ回数には上限を設ける。

キャッシュサイズ上限:

- `NewsDashboardSnapshot` は保存前に軽量化し、件数・文字数上限を適用する。
- MVP 目安:
  - `MAX_NEWS_ITEMS = 100`
  - `MAX_STREAM_HEADLINES = 20`
  - `MAX_HEADLINES_PER_CATEGORY = 5`
  - `MAX_HEATMAP_CELLS = 30`
  - `MAX_CHECKPOINTS_PER_NEWS = 3`
  - `MAX_SUMMARY_CHARS = 300`
  - `MAX_AI_COMMENT_CHARS = 240`
- 保存前の正規化では、件数上限、summary truncate、ai_comment truncate、investment_checkpoints 最大3件、related_symbols 重複除去、None / 空文字整理、raw field 排除を必ず行う。
- URLなしカードは必要以上に保存しない。ただし dashboard 表示上の警告や資料不足表示に必要な最小カードは許容する。

一時ファイル / Atomic Save:

- 更新中に一時ファイルを使う場合は `data/cache/news_dashboard_snapshot.tmp.json` に書く。
- tmp に書き込み、JSONとして読み直せることを確認し、既存 snapshot を `.prev` に退避してから tmp を本ファイルへ atomic replace する。
- 保存成功後は tmp を削除する。
- 起動時に古い tmp が残っていたら削除する。
- tmp ファイルを履歴化しない。
- 更新失敗時は既存キャッシュを壊さない。

Cache Cleanup:

- 起動時または更新後に軽量な `cleanup_news_cache_files()` を実行する。
- 削除対象は `data/cache` 配下の news dashboard 関連ファイルに限定する。
- 削除対象候補: 古い `.tmp` ファイル、2世代以上の古い backup、debug dump、想定外に増えた snapshot copy、一定日数以上前の一時ファイル。
- MVPでは aggressive に削除しすぎず、想定外ファイルの削除範囲は名前 prefix / suffix で明確に限定する。

更新頻度制御:

- fresh 状態では自動更新しない。
- 起動時も TTL 内なら更新を skip する。
- 手動更新は `force=True` で許可する。
- 連続失敗時に短時間で再試行し続けない。
- 初期候補:
  - `MIN_REFRESH_INTERVAL_MINUTES = 30`
  - `NEWS_CACHE_FRESH_HOURS = 3`
  - `NEWS_CACHE_EXPIRED_HOURS = 24`
  - `MAX_REFRESH_RETRY = 1`

状態ファイル:

- 必要であれば、更新状態だけを軽量に保存する。
  - 保存先候補: `data/cache/news_update_status.json`
  - 保持内容: last_attempt_at、last_success_at、last_error_at、last_error_type、consecutive_failures、is_refreshing、cache_file_size_bytes。
  - 履歴配列は持たず、最新状態のみ保存する。

UI表示:

- `投資レーダー` 画面には、肥大化防止に関係する状態を簡潔に表示できるようにする。
  - 通常表示はタイトル右上の `情報鮮度` とJST取得時刻に絞る。キャッシュサイズや更新履歴は初期画面に常時カード表示しない。
  - エラー時: `ニュース更新に失敗しました。前回キャッシュを表示しています。`
  - 詳細な stack trace や巨大ログは UI に出さない。

実装候補:

- `backend/news/contracts.py`
- `backend/news/dashboard_service.py`
- `backend/news/cache.py`
- `backend/news/update_manager.py`
- `backend/news/logging_utils.py`

関数候補:

```python
def cleanup_news_cache_files() -> None:
    ...

def get_news_cache_file_size() -> int | None:
    ...

def normalize_snapshot_for_cache(
    snapshot: NewsDashboardSnapshot,
) -> NewsDashboardSnapshot:
    ...

def save_cached_news_dashboard_snapshot(
    snapshot: NewsDashboardSnapshot,
) -> None:
    ...

def load_cached_news_dashboard_snapshot() -> NewsDashboardSnapshot | None:
    ...

def rotate_previous_snapshot() -> None:
    ...

def configure_news_update_logger() -> logging.Logger:
    ...
```

テスト方針:

- 追加候補: `tests/test_news_cache_cleanup.py`、`tests/test_news_cache_limits.py`、`tests/test_news_update_logging.py`
- 確認観点:
  - snapshot 保存時に件数上限が適用される。
  - category_lanes が1カテゴリ最大5件に制限される。
  - stream_headlines が最大20件に制限される。
  - summary / ai_comment が最大文字数で truncate される。
  - investment_checkpoints が最大3件に制限される。
  - related_symbols が重複除去される。
  - raw response field が保存されない。
  - `.prev` が1世代以上増えない。
  - `.tmp` が保存成功後に削除される。
  - 起動時 cleanup で古い tmp が削除される。
  - 更新失敗時に既存 cache が破壊されない。
  - ログファイルが `RotatingFileHandler` で設定される。
  - ログに巨大JSONや本文全文が出力されない。
  - TTL 内では自動更新が skip される。
  - 連続失敗時に過剰リトライしない。

Phase 22.y 完了条件:

- 最新 snapshot 1件と最大1世代 backup のみを保持する。
- raw provider response / HTML本文全文 / debug dump を通常運用で保存しない。
- snapshot 保存前に件数上限・文字数上限・重複除去・raw field 排除が適用される。
- atomic save により、更新失敗時も既存 cache が壊れない。
- cache cleanup が news dashboard 関連ファイルだけを対象に安全に動く。
- 更新ログはローテーションされ、本文全文・巨大JSON・秘密情報を出さない。
- TTL / 最小更新間隔 / retry 上限により、background refresh が走りすぎない。
- UI に最終更新、freshness、cache size、fallback 状態を簡潔に表示できる。
- network-free tests で cache limit、cleanup、logging、TTL skip、failure fallback を確認する。

Phase 22.z: 銘柄データベース自動リフレッシュ基盤

状態: 実装完了

目的: 銘柄データベースを、画面操作時に都度取得するだけの構成から、アプリ起動中にバックグラウンドで順次リフレッシュされる構成へ拡張する。アプリ起動直後は前回保存済みデータを即利用し、裏側で古い銘柄、重要銘柄、使用頻度の高い銘柄、直近閲覧銘柄から順次更新する。ランキング画面や銘柄コックピットで古すぎるデータに依存し続けることを避けつつ、画面表示を重くしない設計を目指す。

実装メモ（2026-06-03）:

- 22.z-1: `backend/symbols/contracts.py` と `backend/symbols/refresh_priority.py` を追加し、`data_freshness_status`、usage / importance / stale / recent view / ranking / manual refresh bonus、`refresh_priority_score`、更新キュー作成・ソートを deterministic に実装。
- 22.z-2: `backend/symbols/cache.py` を追加し、`symbol_refresh_queue.json`、`symbol_refresh_status.json`、`symbol_refresh.lock` の atomic save / bounded persistence / in_progress 復旧 / stale lock / cleanup を実装。
- 22.z-3: `backend/symbols/repository.py`、`backend/symbols/refresh_manager.py`、`backend/symbols/logging_utils.py` を追加し、正規化済み latest-only `SymbolRecord` 保存、raw/debug field 除外、1銘柄単位の保存、provider失敗時の既存データ維持、`RotatingFileHandler` ログを実装。
- 22.z-4 follow-up: `backend/symbols/startup.py` と `ui/app.py` startup hook を追加し、その後 visible startup path から daemon background worker へ切り替え済み。現在の short-session plan は `data/marketdata/symbol_universe.csv` から 150 symbols immediately、75 after 3 minutes、75 after 8 minutes、then 50 every 5 minutes を local-first に `symbols_cache.json` へ正規化保存し、fresh records を skip しつつ 1000 symbols per session で止める。`symbol_refresh_queue.json` は成功 batch 後に空へ戻し、`pending` / `retryable` / `in_progress` を残さない。
- 22.z-5 follow-up: Cockpit の選択銘柄と Ranking の比較対象銘柄を、ユーザー操作を増やさず background refresh の priority hint として登録する。`currently_visible_symbols` / `ranking_candidates` を既存 priority queue に渡し、missing / stale records を通常候補より先に更新する。visible UI は変更しない。
- 22.z-6 follow-up: ユーザーに明示操作を増やさず、Cockpit の `データを取得` 実行時は対象1銘柄を、Ranking の `最新データを取得して更新` 実行時はランキング作成前に比較候補を lightweight preflight refresh する。ランキングは性能劣化を避けるため、比較候補30件までは全件、31件以上は最大50件、対象スキャンは最大300件までに制限し、残りは既存の background priority refresh に任せる。visible UI は変更しない。
- 通常確認は network-free tests のみで完結する。visible UI freshness 表示は、Cockpit の選択銘柄行と Ranking / Cockpit 共通の `銘柄データ` モーダルへ初期接続済み。実provider refresh wiring は後続Phaseの接続作業として扱う。

基本UX:

1. アプリ起動時に保存済み銘柄DBを即利用する。
2. 銘柄ごとの freshness を確認する。
3. 使用頻度、重要度、古さ、直近閲覧情報から refresh priority を算出する。
4. `missing` / `expired` / `stale` 銘柄を更新キューに追加する。
5. 優先度が高い銘柄から順次更新する。
6. 1銘柄ごとに正規化、保存、状態更新を確定する。
7. 途中でアプリが閉じられても、次回起動時に未完了分を再評価する。

対象データ:

- MVPでは現在ランキング画面・銘柄コックピットで利用している主要フィールドを優先する。
- 対象候補は、株価、終値、出来高、PER、PBR、ROE、配当利回り、時価総額、業種 / セクター、市場区分、通貨、ETF基本情報、provider source、provider confidence、最終取得日時、freshness status。
- MVPではすべての field を完全更新しなくてよい。まず既存 UI の候補抽出、symbol detail、investment memo、ranking score 補助に使う field を対象にする。

必須機能:

- アプリ起動時に銘柄DBの鮮度を確認する。
- 保存済み銘柄データを即表示できる。
- 銘柄ごとに `data_freshness_status` を持つ。
- 使用頻度、重要度、古さから `refresh_priority_score` を算出する。
- `missing` / `expired` / `stale` 銘柄を更新候補に入れる。
- 直近閲覧銘柄、重要銘柄、主要銘柄を優先更新する。
- 更新キューを作成し、軽量に永続化する。
- 一度に更新する銘柄数と provider access rate に上限を設ける。
- provider 失敗時も既存データを壊さない。
- 更新成功時に正規化済み銘柄データを保存する。
- 1銘柄ごと、または小さなバッチ単位で更新結果を確定する。
- アプリ終了、強制終了、スリープ、例外発生で中断されても次回起動時に安全に復旧できる。
- 手動更新は `force=True` として許可する。
- ランキング画面 / 銘柄コックピットでデータ鮮度を小さく表示する。
- 外部 provider へ過剰アクセスしない。
- ログ、キャッシュ、更新履歴が無制限に肥大化しないようにする。

Refresh Priority Score:

- 単純な古い順ではなく、使用頻度、重要度、データの古さ、直近閲覧、ランキング利用有無、手動更新要求を組み合わせて優先度を決める。
- 初期案:

```text
refresh_priority_score =
    usage_score
  + importance_score
  + stale_score
  + recent_view_bonus
  + ranking_candidate_bonus
  + manual_refresh_bonus
```

- `usage_score`: Cockpitで開かれた回数、ランキングで表示された回数、詳細確認された回数、手動更新された回数を候補にする。MVPでは `usage_score = min(view_count_last_30_days, 20)` 程度でよい。
- `importance_score`: 国内主要銘柄、米国主要銘柄、ETF主要銘柄、大型株、ランキング対象銘柄、標準ウォッチ対象を候補にする。MVPでは固定リストまたは既存 CSV から `major_symbol: +30`、`ranking_base_symbol: +20`、`etf_core_symbol: +15` 程度でよい。
- `stale_score`: `missing: +100`、`expired: +60`、`stale: +30`、`fresh: +0` を初期案にする。
- `recent_view_bonus`: 1時間以内 `+40`、24時間以内 `+25`、7日以内 `+10` を初期案にする。
- `ranking_candidate_bonus`: 現在表示中のランキング候補 `+30`、ランキング候補群 `+15` を初期案にする。
- `manual_refresh_bonus`: 手動更新要求は `+100` として最優先に近づける。

更新キューの並び順:

1. `refresh_priority_score` の高い順。
2. `data_freshness_status` が `missing` / `expired` / `stale` の順。
3. `last_refreshed_at` が古い順。
4. `symbol` 昇順。

鮮度管理 / TTL:

- MVPでは `data_freshness_status` だけでもよい。
- 初期目安:
  - `fresh`: 24時間以内
  - `stale`: 1〜7日以内
  - `expired`: 7日超
  - `missing`: 未取得
- 将来的には `price_freshness_status`、`fundamental_freshness_status`、`data_freshness_status` に分離できる構造にする。

使用頻度 / 重要度メタデータ:

- 使用頻度は軽量な集計済みデータだけを保持する。
  - 保存先候補: `data/cache/symbol_usage_stats.json`
  - 候補 field: `symbol`、`view_count_total`、`view_count_last_30_days`、`last_viewed_at`、`last_opened_from`
  - 全閲覧履歴、クリック履歴の詳細ログ、無制限の操作ログは保存しない。
- 重要度 metadata は、MVPでは固定リストまたは既存 CSV から判定してよい。
  - 候補 field: `symbol`、`importance_rank`、`is_major_symbol`、`is_core_etf`、`is_ranking_base_symbol`

更新キュー設計:

- 更新キューや更新状態は軽量に保存する。
  - 保存先候補: `data/cache/symbol_refresh_queue.json`、`data/cache/symbol_refresh_status.json`
- `SymbolRefreshTask` 候補 field:
  - `symbol`
  - `market`
  - `priority`
  - `refresh_priority_score`
  - `reason`
  - `status`
  - `requested_at`
  - `started_at`
  - `finished_at`
  - `last_error_type`
  - `retry_count`
  - `last_refreshed_at`
- `reason` 候補: `opened_in_cockpit`、`ranking_candidate`、`expired_data`、`manual_refresh`、`startup_refresh`、`major_symbol`、`high_usage_symbol`
- `status` 候補: `pending`、`in_progress`、`succeeded`、`failed`、`skipped`、`retryable`
- 保持するのは現在の pending / retryable task と直近の lightweight status だけにし、全更新履歴や provider raw response は保存しない。

中断耐性 / 復旧設計:

- 銘柄DB更新は全件一括更新ではなく、1銘柄単位または小さなバッチ単位で安全に確定する。
- 1銘柄取得、正規化、atomic save / transaction commit、task status 更新、次の銘柄へ、という流れを基本にする。
- 次回起動時は、前回 `in_progress` の task を中断扱いにする。
  - 既にDB保存済みで fresh になっていれば skip。
  - 保存されていなければ pending または retryable に戻す。
  - `retry_count` が上限を超えていれば failed として扱う。
  - failed でも既存銘柄データは削除しない。
- 完了済み銘柄まで巻き戻さず、未完了分だけ再評価する。

Atomic Save / Transaction:

- SQLite等のDBを使う場合:
  - 1銘柄更新ごとに transaction を張る。
  - 正規化済みデータを upsert する。
  - commit 成功後に task を `succeeded` にする。
  - commit 失敗時は rollback し、既存データを保持する。
- JSON / CSV cache を使う場合:
  - 直接上書きしない。
  - `.tmp` に保存し、読み直して検証し、問題なければ `os.replace()` で atomic replace する。
  - 失敗時は既存ファイルを維持する。

Lock / stale lock:

- 同時に複数の更新処理が走らないようにする。
  - lock 候補: `data/cache/symbol_refresh.lock`
- 更新開始時に lock を取得し、更新完了時に解放する。
- 強制終了で lock が残る可能性を考慮し、lock には作成時刻を持たせる。
- 作成から30分以上経過した lock は stale lock として起動時に破棄する初期案にする。

更新頻度 / レート制限:

- MVP推奨値:
  - `MAX_SYMBOL_REFRESH_PER_RUN = 20`
  - `MAX_SYMBOL_REFRESH_PER_MINUTE = 5`
  - `MIN_SYMBOL_REFRESH_INTERVAL_HOURS = 12`
  - `SYMBOL_PRICE_FRESH_HOURS = 24`
  - `SYMBOL_EXPIRED_DAYS = 7`
  - `MAX_REFRESH_RETRY = 1`
  - `MAX_TASK_RETRY = 1`
  - `STALE_LOCK_MINUTES = 30`
- アプリ起動時は最大20銘柄まで更新する。
- 将来の定期更新は30〜60分ごとに最大10銘柄程度を候補にする。
- 銘柄コックピット表示時は対象銘柄が `expired` / `missing` の場合のみ優先更新する。
- `fresh` の場合は自動更新しない。
- 手動更新は `force=True` で許可する。
- provider 失敗は `retry_count` を増やし、上限以下なら `retryable`、上限超過なら `failed` にする。
- `failed` でも既存データは維持する。

データ肥大化防止:

- 保存するもの:
  - 最新の正規化済み銘柄データ
  - 最終更新日時
  - provider名
  - freshness status
  - 直近の軽量更新ステータス
  - 集計済みの軽量な使用頻度データ
  - 現在の pending / retryable task
- 保存しないもの:
  - provider raw response 全文
  - HTML全文
  - 巨大JSON
  - debug dump
  - 無制限の更新履歴
  - 過去 snapshot の無制限保存
  - 全閲覧履歴
  - クリック履歴の詳細ログ
  - API key / 認証情報 / 個人情報
- 価格履歴や過去データを保持する場合は別機能として明示的に扱う。MVPの銘柄DB自動リフレッシュでは、原則として最新値を上書きする。

Cleanup / logging:

- 起動時または更新前に `cleanup_symbol_refresh_artifacts(now)` を実行する。
- 削除対象候補: 古い `.tmp` ファイル、stale lock、古すぎる一時 queue、想定外に増えた backup、debug dump。
- 削除対象は銘柄DB更新関連ファイルに限定する。
- 銘柄DB更新ログは必ず `logging.handlers.RotatingFileHandler` でローテーションする。
  - 保存先候補: `logs/symbol_refresh.log`
  - 推奨設定: `maxBytes=1MB`、`backupCount=3`
- ログに残してよい情報: refresh started / skipped / succeeded / failed、symbol、provider、elapsed_ms、updated_field_count、freshness_status、error type。
- ログに残さない情報: raw response、巨大JSON、HTML全文、API key、認証情報、個人情報、詳細なイベント履歴。

UI表示:

- ランキング画面や銘柄コックピットに、データ鮮度を小さく表示する。
  - `データ最終更新: 2026-06-03 21:15`
  - `状態: fresh`
  - `バックグラウンド更新中`
- 古い場合: `一部データが古い可能性があります。バックグラウンドで更新中です。`
- 更新中: `銘柄データをバックグラウンド更新中。一部データは前回保存値を表示しています。`
- 更新失敗時: `最新データ取得に失敗しました。前回保存データを表示しています。`
- 通常は内部状態を出しすぎず、UIに stack trace や詳細ログは出さない。

実装候補:

- `backend/symbols/contracts.py`
- `backend/symbols/repository.py`
- `backend/symbols/cache.py`
- `backend/symbols/refresh_manager.py`
- `backend/symbols/logging_utils.py`
- 既存構成に寄せる場合は、`backend/marketdata/security_master/` または `backend/marketdata/symbol_refresh/` への配置も候補にする。

関数候補:

```python
def evaluate_symbol_freshness(symbol_record, now: datetime) -> str:
    ...

def calculate_symbol_refresh_priority(
    symbol_record,
    usage_stats,
    importance_meta,
    now: datetime,
    reason: str | None = None,
) -> SymbolRefreshPriority:
    ...

def build_symbol_refresh_queue(
    symbols: list[str],
    usage_context: dict,
    now: datetime,
) -> list[SymbolRefreshTask]:
    ...

def sort_symbol_refresh_queue(
    tasks: list[SymbolRefreshTask],
) -> list[SymbolRefreshTask]:
    ...

def refresh_symbols_if_needed(
    force: bool = False,
    max_items: int = 20,
) -> SymbolRefreshResult:
    ...

def refresh_single_symbol(
    task: SymbolRefreshTask,
) -> SymbolRefreshItemResult:
    ...

def save_symbol_record(record) -> None:
    ...

def cleanup_symbol_refresh_artifacts(now: datetime) -> None:
    ...
```

データ構造案:

```python
class SymbolRefreshPriority(BaseModel):
    symbol: str
    usage_score: int = 0
    importance_score: int = 0
    stale_score: int = 0
    recent_view_bonus: int = 0
    ranking_candidate_bonus: int = 0
    manual_refresh_bonus: int = 0
    refresh_priority_score: int
    reason: str | None = None

class SymbolRefreshTask(BaseModel):
    symbol: str
    market: str | None = None
    priority: int
    refresh_priority_score: int = 0
    reason: str
    status: str = "pending"
    requested_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error_type: str | None = None
    retry_count: int = 0
    last_refreshed_at: datetime | None = None

class SymbolRefreshItemResult(BaseModel):
    symbol: str
    success: bool
    provider: str | None = None
    updated_fields: list[str] = []
    skipped_reason: str | None = None
    error_type: str | None = None
    elapsed_ms: int | None = None

class SymbolRefreshResult(BaseModel):
    started_at: datetime
    finished_at: datetime
    attempted_count: int
    succeeded_count: int
    failed_count: int
    skipped_count: int
    items: list[SymbolRefreshItemResult]

class SymbolDataFreshness(BaseModel):
    symbol: str
    last_price_updated_at: datetime | None = None
    last_fundamental_updated_at: datetime | None = None
    data_freshness_status: str
    should_refresh: bool
    reason: str | None = None

class SymbolUsageStats(BaseModel):
    symbol: str
    view_count_total: int = 0
    view_count_last_30_days: int = 0
    last_viewed_at: datetime | None = None
    last_opened_from: str | None = None

class SymbolImportanceMeta(BaseModel):
    symbol: str
    importance_rank: int | None = None
    is_major_symbol: bool = False
    is_core_etf: bool = False
    is_ranking_base_symbol: bool = False
```

画面連携:

- 銘柄コックピット
  - 表示時に対象銘柄の freshness を確認する。
  - `expired` / `missing` の場合は高優先度で refresh queue に入れる。
  - 画面は前回保存データを即表示する。
  - 更新完了後、次回再描画時に新データを表示する。
  - `fresh` の場合は provider 取得を skip する。
  - 開いた回数や最終閲覧日時を usage stats として軽量に記録する。
- ランキング画面
  - ランキング表示に必要な銘柄群の freshness を確認する。
  - 古い銘柄を低〜中優先度で refresh queue に入れる。
  - 画面表示をブロックしない。
  - 一部データが古い場合は小さく注意表示する。
  - 表示対象になりやすい銘柄は `ranking_candidate_bonus` の対象にする。

テスト方針:

- 追加候補:
  - `tests/test_symbol_refresh_manager.py`
  - `tests/test_symbol_freshness.py`
  - `tests/test_symbol_refresh_priority.py`
  - `tests/test_symbol_refresh_limits.py`
  - `tests/test_symbol_refresh_logging.py`
  - `tests/test_symbol_refresh_resume.py`
  - `tests/test_symbol_refresh_atomic_save.py`
  - `tests/test_symbol_refresh_lock.py`
- 確認観点:
  - fresh 銘柄は自動更新対象にならない。
  - expired / missing 銘柄は更新対象になる。
  - stale / usage / importance / recent view / manual refresh bonus が優先度に反映される。
  - `refresh_priority_score` の高い順に queue が並び、同一優先度の場合は古い銘柄から更新される。
  - `MAX_SYMBOL_REFRESH_PER_RUN` と `MAX_SYMBOL_REFRESH_PER_MINUTE` を超えて provider access しない。
  - provider 取得失敗時に既存データを壊さない。
  - 更新成功時に normalized record が保存され、raw response を保存しない。
  - ログが `RotatingFileHandler` で設定される。
  - TTL内では自動更新が skip され、手動更新時は `force=True` で更新できる。
  - 連続失敗時に過剰リトライしない。
  - 1銘柄更新成功ごとに保存される。
  - 更新途中で例外が発生しても既存データが壊れない。
  - `in_progress` task が次回起動時に pending / retryable へ復旧される。
  - 既に更新済みの銘柄は次回起動時に再更新されない。
  - `.tmp` file cleanup、stale lock cleanup、二重更新防止、atomic replace / transaction rollback を確認する。
  - `retry_count` 上限超過時は failed になり、failed でも既存銘柄データが維持される。

対象外:

- Watchlist通知、自動売買、売買推奨。
- 価格履歴の長期蓄積。
- 詳細なクリック履歴の永続保存。
- OS常駐サービス化。
- 大量銘柄の高速並列更新。

完了条件:

- 最新ロードマップに、銘柄データベース自動リフレッシュ基盤が追記されている。
- 既存 Phase 番号と衝突していない。
- 目的、基本UX、対象データ、必須機能が記載されている。
- 使用頻度、重要度、古さを組み合わせた refresh priority score の考え方が記載されている。
- 更新キュー、TTL、レート制限が記載されている。
- アプリ終了・中断に強い復旧設計が記載されている。
- atomic save / transaction の方針が記載されている。
- lock / stale lock / cleanup の方針が記載されている。
- ログ・キャッシュ肥大化防止設計が記載されている。
- テスト方針が記載されている。
- 既存ロードマップの文体・章立てに合わせて自然に統合されている。


Phase 22 完了条件:

- Research Score は evidence と紐づいて説明できる。
- Cockpit / Decision Report で Research Score の内訳、根拠、confidence、warnings を確認できる。
- evidence 不足時は score 欠損または低信頼として表示される。
- 高度予測は Ranking の上昇気配 / 下降警戒へ25%までブレンドし、`AI総合` で控えめに加味する。Research / News など他の外部情報は既定ランキング順位を変更しない。
- external source adapter は通常 checks に入れない。

### 5.9 Phase 23: Optional Adapter と高度分析

状態: Advanced Forecast Slice 1 `advanced_linear`、Slice 2 `advanced_quantile` / adapter registry、Slice 3 `advanced_tree_sklearn`、Slice 4 `advanced_gbdt_sklearn`、Slice 5 advanced forecast consensus、Slice 5 closeout-1 の Cockpit chart 主導線整理、Slice 5 closeout-2 の AI総合 Ranking 統合、Cockpit chart / card polish、Ranking / Decision Report wording closeout まで接続済み。Cockpit / API は 1〜60日の共通 horizon に対応し、Cockpit では `AI予測インサイト` と高度予測モデルを取得期間由来の同じ予測日数で比較する。予測日数の初期値は取得期間のおよそ 1/12 を使い、60日を上限にする。Ranking では `AI予測インサイト` から派生した上昇 / 下振れ警戒を通常の上昇気配 / 下降警戒へ25%までブレンドし、`AI総合` では派生した上昇 / 下振れ警戒 / 信頼スコアを低信頼時に中立寄せしながら控えめに加味する。Ranking の理由表示、深掘り候補、score detail、Cockpit / Ranking Decision Report は `AI予測インサイト` が方向シグナルへどう効いたかを同じ文脈で説明する。

目的: default path を deterministic に保ったまま、追加 provider、advanced forecast / research model、news / sentiment、将来の LLM adapter を optional layer として追加する。次の実装優先度は、銘柄コックピット / 銘柄ランキングで使う高度予測モデル adapter を複数そろえ、比較表示の土台を作ること。

範囲:

- advanced forecast model adapter を追加し、既存の Forecast consensus / direction signal / Investment Score 入力へ安全に接続する。
- `polygon` など追加 live provider adapter は、必要になった時点で明示 opt-in として追加する。
- news / sentiment local CSV provider と optional external provider は、投資レーダー / Research RAG の後続拡張として扱う。
- LLM 連携は Phase 24 Assistant で外部 LLM Gateway API client / schema として扱い、provider 個別実装は Gateway 側に寄せる。
- LLM Gateway / news / external provider はすべて明示 opt-in とし、失敗時は deterministic fallback に戻す。

高度予測モデル first slice の方針:

- 既存の naive / moving-average / momentum baseline と consensus は backend baseline / fallback / 詳細確認用として維持する。Cockpit の初期チャートと主要カードでは、実績価格、`AI予測インサイト`、予測レンジ帯を主導線にし、個別高度予測モデルは詳細確認に回す。
- scikit-learn は `advanced_tree_sklearn` / `advanced_gbdt_sklearn` のため runtime dependency として導入済み。より重い LightGBM / XGBoost / Prophet / deep learning 系は optional adapter とし、未導入でもアプリ・通常 tests・CI が動くようにする。
- 最初は 1 銘柄または小さい銘柄集合で、walk-forward evaluation、モデル別予測、予測レンジ、方向シグナルへの反映を確認する。
- 高度予測 consensus は、予測統合で単純平均が強い benchmark になりやすいことを前提に、信頼度・誤差改善・モデル合意度・検証サンプル数による重みを保守的に 0.70〜1.30 に制限する。重みは「保証」ではなく比較補助として扱う。
- Cockpit の helper / tooltip では、Consensus の重み付き平均式と各予測モデルの基本ロジックを初心者向けの短い計算式で示し、「将来保証」ではなく比較補助として読める表現にする。
- ランキング順位への反映は、`advanced_linear` 単体では行わず、tree / GBDT / quantile / consensus をそろえた後の `AI総合` で控えめに開始する。個別モデルの強い加点ではなく、上昇気配 / 下降警戒への25%ブレンドと、上昇 / 下振れ警戒 / 信頼スコアの中立寄せで使う。
- UI では「将来保証」ではなく「モデル別の見方 / 不確実性 / 確認材料」として表示する。

#### Phase 23.a: Advanced Forecast Slice 1 - `advanced_linear`

状態: backend adapter / forecast service / API / Streamlit Cockpit / Ranking auxiliary display 接続済み。後続 closeout で、追加高度予測モデルと consensus をそろえたうえで Ranking 上昇気配 / 下降警戒への25%ブレンドと `AI総合` への控えめ統合まで実装済み。

目的: 派手な深層学習モデルより先に、軽量・deterministic・説明可能な高度予測 adapter の骨格を追加する。既存 FeatureBuilder / Forecast service / Cockpit / Ranking の構造を壊さず、将来の tree / GBDT / quantile / deep-learning adapter を足せる境界を作る。

実装方針:

- `backend/forecast/adapters/advanced_linear.py` を追加済み。
- default model は `Ridge`、optional model は `ElasticNet` とする。現行 backend first slice は sklearn 非依存の deterministic Ridge 互換実装を使い、ElasticNet は adapter contract 予約として warning 付きで扱う。
- 追加依存は最小にする。現行 slice は既存依存の `numpy` のみを使い、scikit-learn は追加していない。
- 価格そのものではなく forward return を予測する。
- 対応 horizon は Cockpit / API では `1`〜`60` trading days とし、取得期間から決まる通常予測 horizon と同じ予測日数で高度予測を表示する。
- `future_return_h = close[t+h] / close[t] - 1` を target とする。`h` は request / Cockpit の共通 horizon。
- target 作成後、未来値がない末尾行は学習対象から除外する。target 列、日付、銘柄名、未来由来の列は feature に混ぜない。
- FeatureBuilder / ranking feature / DailySnapshot など既存生成済み特徴量を優先し、存在しない特徴量を無理に新規実装しない。
- 使用候補 feature は、既存値があるものに限って `return_1d`、`return_5d`、`return_20d`、momentum、volatility、drawdown、volume / rolling volume、moving-average gap、利用可能なら RSI / PER / PBR / ROE / dividend yield / market cap / Research Score 系を扱う。
- 前処理は数値 feature 抽出、`SimpleImputer(strategy="median")`、`StandardScaler`、`Ridge` / `ElasticNet` を基本にする。
- sklearn adapter へ拡張する場合は、`Pipeline` で imputer / scaler / model をひとまとまりにする。
- deterministic のため、random state を持つ処理では `random_state = 42` を固定する。

評価方針:

- ランダム split は禁止し、`TimeSeriesSplit` または同等の walk-forward validation を使う。
- 最小評価指標は `MAE`、`RMSE`、`direction_accuracy`、`fold_count`、`sample_count`。
- `direction_accuracy` は predicted return と actual return の符号が一致した割合とする。
- 可能なら baseline 比較として `baseline_zero_return` を入れ、`baseline_zero_rmse` と `rmse_improvement` を返す。
- `rank_correlation` / `top_k_hit_rate` は Ranking 接続を意識した拡張候補として設計余地を残すが、初期 slice で重ければ TODO として残す。

出力候補:

- `adapter_name`: `advanced_linear`
- `model_name`: `Ridge` または `ElasticNet`
- `horizon_days`: `1`〜`60`
- `predicted_return`
- `direction_score`
- `confidence`: `low` / `medium` / `high`
- `validation_metrics`
- `feature_contribution_summary`
- `warnings`

confidence 方針:

- `high`: sample_count と fold_count が十分で、direction accuracy が baseline より明確に良く、RMSE が極端に悪くない。
- `medium`: sample_count が十分で、最低限の評価指標が計算できる。
- `low`: sample_count / fold_count が不足、欠損が多い、validation metrics が不安定。
- 初期実装では simple rule でよい。過度に賢く見せない。

feature contribution 方針:

- Ridge / ElasticNet の標準化後係数から、絶対値上位 feature を抽出する。
- 正の係数は `positive`、負の係数は `negative` と表示する。
- これは因果ではなく、モデル上の寄与傾向であることを warning / UI 文言で明示する。

API / service 接続方針:

- 既存 forecast API / service の default 挙動は壊さない。
- adapter 未指定時は既存 baseline consensus のままにする。
- `advanced_linear` 指定時だけ新 adapter を使う。
- horizon は `1`〜`60` をサポートし、不正 horizon は validation error にする。
- データ不足時は graceful error または low-confidence warning として扱う。

Streamlit / Ranking 接続方針:

- 銘柄コックピットの予測表示エリアに、通常予測と同じ horizon の高度予測を表示する。
- 表示候補は、高度予測モデル名、horizon、予測リターン、direction score、confidence、MAE / RMSE / direction accuracy、主な寄与 feature、非助言 note。
- まずは expander `高度予測モデル詳細` でもよい。
- Ranking では取得期間から決まる共通 horizon の `advanced_forecast_horizon_days`、`advanced_forecast_predicted_return`、`advanced_forecast_score`、`advanced_forecast_confidence` を保持し、表示テーブル / 選択候補 breakdown / score detail / CSV export で補助情報として確認できる。
- 初期 slice では Ranking 本体順位を変更せず、補助列 / optional score として扱う。追加高度予測モデルを一通りそろえた後の closeout で、上昇気配 / 下降警戒への25%ブレンドと `AI総合` の中立寄せ統合を実装済み。

実装済み / 将来 adapter 候補:

- 実装済み: `advanced_linear`: lightweight deterministic Ridge-style model
- 実装済み: `advanced_quantile`: historical forward-return quantile / prediction range
- 実装済み: `advanced_tree_sklearn`: scikit-learn ExtraTreesRegressor default / RandomForestRegressor option
- 実装済み: `advanced_gbdt_sklearn`: scikit-learn HistGradientBoostingRegressor
- 実装済み: advanced forecast consensus: registered advanced adapters の共通 horizon 出力を、信頼度・誤差改善・モデル合意度・検証サンプルで保守的に統合
- `advanced_gbdt_optional`: LightGBM / XGBoost
- LightGBM / XGBoost / Prophet / deep learning 系は今回追加しない。

#### Phase 23.b: Advanced Forecast Slice 2 - adapter registry / `advanced_quantile`

状態: 実装済み。backend adapter registry / service / API / Streamlit Cockpit chart-card-detail 接続済み。この slice 単体では Ranking 順位と既定 Investment Score は変更していない。

目的: 高度予測 adapter を model-by-model に直結せず、registry 経由で増やせる境界を作る。2本目の adapter として、単一予測値だけでなく下振れ / 中央 / 上振れレンジを確認できる deterministic quantile model を追加する。

実装方針:

- `backend/forecast/advanced_registry.py` で advanced adapter の key、表示名、説明、対応 horizon、factory を管理する。
- `evaluate_advanced_forecast(adapter_name=...)` を追加し、既存 `evaluate_advanced_linear_forecast` は互換 wrapper として残す。
- `advanced_quantile` は過去の forward return 分布から中央値、20% quantile、80% quantile を返す。
- 対応 horizon は `advanced_linear` と同じ `1`〜`60` trading days とする。
- 通常 forecast baseline、Ranking 順位、既定 Investment Score はこの slice 単体では変更しない。
- Streamlit Cockpit では登録済み高度予測 adapter を同じ高度予測セクションに表示し、通常予測と同じ共通 horizon で比較する。価格・予測チャートでは `advanced_quantile` の中央予測を線、下振れ〜上振れを薄い帯として表示し、全体チャートの右側に予測開始前数日と予測部分を自動抽出した `予測スコープ` を並べる。高度予測モデル / 単純予測モデルはグループチェックで追加し、表示後の個別系列の濃淡は固定色のチャート内凡例クリックで扱う。チェック切替はブラウザ内で完結し、Streamlit rerun / 予測再計算を避ける。全体チャートは `価格チャート` として線中心で小さな点マーカーを使う。
- Ranking auxiliary fields は登録済み adapter の共通 horizon consensus を補助値として保持する。後続 closeout 前は順位や既定 score に混ぜない。

完了条件:

- `POST /forecast/evaluate` で `adapter=advanced_quantile` を指定でき、1〜60日の中央値予測、予測価格、下振れ / 上振れレンジ、検証指標、信頼度、注意点を返す。
- Cockpit の価格・予測チャートと予測カード / 詳細表で `advanced_quantile` が `高度予測: レンジモデル` として確認でき、チャート上では薄い帯で下振れ〜上振れの参考幅と右側の予測拡大図を確認できる。
- adapter registry により、今後の tree / GBDT adapter 追加時の接続箇所が限定される。
- 通常 tests は network / cloud API / live provider に依存しない。

#### Phase 23.c: Advanced Forecast Slice 3 - `advanced_tree_sklearn`

状態: 実装済み。scikit-learn dependency / backend adapter / registry / service / API / Streamlit Cockpit chart-card-detail / Ranking auxiliary display 接続済み。この slice 単体では Ranking 順位と既定 Investment Score は変更していない。

目的: 線形モデルでは拾いにくい特徴量の非線形な組み合わせを、実績ある scikit-learn tree ensemble で検証できるようにする。精度比較を後続の ranking logic finalization に回すため、まずは Cockpit / Ranking 補助情報に同じ horizon で並べる。

実装方針:

- `setup/requirements.txt` に `scikit-learn==1.5.2` を追加済み。
- `backend/forecast/adapters/advanced_tree_sklearn.py` を追加済み。
- default model は `ExtraTreesRegressor`、constructor option として `RandomForestRegressor` を扱う。
- `SimpleImputer(strategy="median", keep_empty_features=True)` と tree estimator を `Pipeline` でまとめる。
- 対応 horizon は `advanced_linear` / `advanced_quantile` と同じ `1`〜`60` trading days とする。
- target は既存高度予測 adapter と同じ `future_return_h = close[t+h] / close[t] - 1` とする。
- 評価は random split を使わず、既存の walk-forward validation と同じ `MAE`、`RMSE`、`direction_accuracy`、`fold_count`、`sample_count`、`baseline_zero_rmse`、`rmse_improvement` を返す。
- feature summary は tree `feature_importances_` の上位を返し、符号は当該特徴量と target の相関から参考表示する。因果説明ではないことを warning / UI 文言で明示する。
- deterministic のため `random_state = 42`、`n_jobs = 1` を既定にする。

完了条件:

- `POST /forecast/evaluate` で `adapter=advanced_tree_sklearn` を指定でき、1〜60日の予測変化率、予測価格、検証指標、信頼度、特徴量重要度、注意点を返す。
- Cockpit の価格・予測チャート、カード、詳細表で `高度予測: ツリーモデル` として確認できる。
- Ranking の高度予測補助欄は登録済み adapter の共通 horizon consensus を参考値として保持する。後続 closeout 前はランキング順位を変更しない。
- 通常 tests は network / cloud API に依存しない。

#### Phase 23.d: Advanced Forecast Slice 4 - `advanced_gbdt_sklearn`

状態: 実装済み。scikit-learn `HistGradientBoostingRegressor` adapter / registry / service / API / Streamlit Cockpit chart-card-detail / Ranking auxiliary display 接続済み。この slice 単体では Ranking 順位と既定 Investment Score は変更していない。

目的: 線形、tree ensemble、quantile range に続き、boosting 系の非線形モデルを追加して、後続の advanced forecast consensus / ranking finalization で比較できる材料をそろえる。LightGBM / XGBoost へ進む前に、追加依存なしの scikit-learn 標準実装で費用対効果を確認する。

実装方針:

- `backend/forecast/adapters/advanced_gbdt_sklearn.py` を追加済み。
- default model は `HistGradientBoostingRegressor` とする。
- `SimpleImputer(strategy="median", keep_empty_features=True)` と estimator を `Pipeline` でまとめる。
- 対応 horizon は既存高度予測 adapter と同じ `1`〜`60` trading days とする。
- target は既存高度予測 adapter と同じ `future_return_h = close[t+h] / close[t] - 1` とする。
- 評価は random split を使わず、既存の walk-forward validation と同じ `MAE`、`RMSE`、`direction_accuracy`、`fold_count`、`sample_count`、`baseline_zero_rmse`、`rmse_improvement` を返す。
- feature summary は、各特徴量を中央値に置き換えたときの RMSE 悪化幅を簡易的な model sensitivity として上位表示する。因果説明ではないことを warning / UI 文言で明示する。
- deterministic のため `random_state = 42`、`early_stopping = False` を既定にする。

完了条件:

- `POST /forecast/evaluate` で `adapter=advanced_gbdt_sklearn` を指定でき、1〜60日の予測変化率、予測価格、検証指標、信頼度、特徴量感度、注意点を返す。
- Cockpit の価格・予測チャート、カード、詳細表で `高度予測: ブースティングモデル` として確認できる。
- Ranking の高度予測補助欄は登録済み adapter の共通 horizon consensus を参考値として保持する。後続 closeout 前はランキング順位を変更しない。
- 通常 tests は network / cloud API に依存しない。

#### Phase 23.e: Advanced Forecast Slice 5 - advanced forecast consensus

状態: 実装済み。`AdvancedForecastConsensus` / `summarize_advanced_forecast_evaluations` を backend forecast service に追加し、Cockpit の `AI予測インサイト` カード / 詳細表、Ranking の高度予測補助列に接続済み。後続 closeout で Ranking 上昇気配 / 下降警戒への25%ブレンドと `AI総合` への控えめ統合まで接続した。既定 Investment Score は変更していない。

目的: 個別の高度予測 adapter を増やす段階から、モデル群をどう読むかの段階へ進める。Ranking logic finalization の前に、Cockpit と Ranking が同じ consensus 計算を使い、信頼度・検証指標・モデル合意度・予測レンジを一貫して扱えるようにする。

実装方針:

- 入力は登録済み高度予測 adapter の共通 horizon `AdvancedForecastEvaluation` とする。
- 予測統合は、単純平均を強い baseline と見なし、過度な最適化を避ける。
- 個別モデル重みは `confidence`、`rmse_improvement / baseline_zero_rmse`、`direction_accuracy`、`sample_count / fold_count` で調整するが、0.70〜1.30 に制限する。
- `direction_accuracy` は 50% を chance-like benchmark と見なし、50% 超は軽い加点、50% 未満は軽い減点にとどめる。
- `advanced_quantile` の下振れ / 上振れは consensus の想定レンジに反映する。
- `agreement` はモデル間の予測変化率レンジで `HIGH` / `MEDIUM` / `LOW` を返す。
- `confidence` は個別モデル信頼度、モデル数、予測レンジ、モデル合意度、過去検証の方向一致率から `low` / `medium` / `high` を返す。
- `best_adapter_name` / `best_model_name` は RMSE 改善、方向一致率、検証サンプル数から相対的に安定したモデルを示す。
- warning では、consensus が投資助言ではないこと、重みは保守的で将来精度保証ではないこと、モデル間の開きや方向割れを明示する。

UI / Ranking 接続:

- Cockpit では個別モデルカードの前に `AI予測インサイト` カードを表示し、価格・予測チャートの初期表示は実績価格、`AI予測インサイト` 線、想定レンジ帯を中心にする。
- 初期カードでは、結論、中心予測（高度予測モデルの統合結果）、下振れ予測 / 上振れ予測、予測価格、予測レンジ、信頼度理由、モデル合意度、予測ばらつき、注意点、予測期間を表示する。中心予測はシナリオ行ではなく結論直下の主表示に置く。信頼度が低い、または判断保留に近い状態では amber accent を使う。個別高度モデルカードは常時表示し、平均 RMSE、誤差改善、過去検証の方向一致率、相対的に安定したモデル、単純予測比較は `高度予測モデルの詳細を見る` / `検証指標を見る` / `単純予測との比較を見る` に折りたたむ。
- Ranking 補助列 `advanced_forecast_predicted_return` / `advanced_forecast_score` / `advanced_forecast_confidence` は、個別モデル平均ではなく consensus rows を優先する。
- Ranking では consensus 由来の高度予測上昇 / 下振れ警戒を通常の上昇気配 / 下降警戒へ25%までブレンドし、`AI総合` では高度予測上昇 / 下振れ警戒 / 信頼スコアを控えめに加味する。その他の評価方針への拡張は後続で個別に検討する。
- Cockpit の初期チャートでは実績価格、`AI予測インサイト`、予測レンジ帯を表示する。高度予測モデル / 単純予測モデルはグループチェックでチャートに追加できるようにし、表示後は固定色のチャート内凡例クリックで個別系列を薄くできる。naive / moving-average / momentum は初期表示から外し、単純予測モデルは backend baseline / fallback / 技術詳細として残す。

完了条件:

- backend service が advanced consensus contract と計算関数を提供する。
- Cockpit が `AI予測インサイト` を表示し、個別モデル rows と読み分けられる。
- Ranking 補助列が consensus 値を使い、上昇気配 / 下降警戒への25%ブレンドと `AI総合` の derived advanced forecast scores が中立寄せで加味される。
- 通常 tests は network / cloud API に依存しない。

Ranking logic finalization 方針:

- 個別 adapter 追加のたびにランキング順位を変えず、まず Cockpit / Ranking の補助表示と CSV export にモデル別の予測・信頼度・検証指標を蓄積する。
- 一通りの高度予測モデルと advanced forecast consensus を追加した後、モデル間の重複、検証安定性、horizon 別の用途、計算時間、データ不足時の扱いを比較して、Ranking 用の統合指標を設計する。
- Ranking 統合は既定順位の丸ごと差し替えではなく、通常方向シグナルへの小さなブレンドと `AI総合` の一部として入れる。その他の opt-in sort profile / evaluation profile は後続で検討する。
- Phase 23 closeout-1 では、naive / moving-average / momentum の単純予測モデルを Cockpit chart の初期表示と主要モデルカードから外し、高度予測 consensus / 信頼度 / レンジ / 検証指標を主表示にした。Phase 23 closeout-2 では、AI総合が高度予測 consensus 由来の上昇 / 下振れ警戒 / 信頼スコアを控えめに加味し、通常の上昇気配 / 下降警戒にも25%までブレンドする。Cockpit chart polish では consensus 表示名を `AI予測インサイト` に改め、初期カードを結論、中心予測（高度予測モデルの統合結果）、下振れ予測 / 上振れ予測、予測価格、予測レンジ、信頼度理由、モデル合意度、予測ばらつき、主な理由、注意点、予測期間へ絞り込んだ。中心予測は結論直下の主表示とし、下段は下振れ / 上振れケースの比較に絞る。個別高度モデルカードは常時表示し、方向一致率、平均 RMSE、誤差改善、相対的に安定したモデル、単純予測比較は折りたたみ配下へ移す。初期チャートは実績価格、`AI予測インサイト`、予測レンジ帯を中心にし、高度予測モデル / 単純予測モデルはグループチェックで追加、表示後は固定色のチャート内凡例クリックで個別系列を薄くする。Ranking / Decision Report wording closeout では、Ranking の並べ替え理由、確認ポイント、深掘り候補、score detail、Cockpit / Ranking Decision Report のスコア分解・候補文脈・分布・ファクター上位・チェックポイントに `AI予測インサイト` の25%ブレンドと低信頼時の控えめな読み方を反映した。単純予測は削除せず、回帰 baseline / fallback / 技術詳細として残す。
- 完了条件には、Research Score と同様に「投資助言ではない」「既定の Ranking / Investment Score は急に変えない」「通常 checks は deterministic / network-free」を含める。

テスト方針:

- `advanced_linear` adapter を import できる。
- 小さな時系列 fixture で学習・予測できる。
- horizon 別の forward return target が生成される。
- 未来データが特徴量へ混ざらない。
- TimeSeriesSplit / walk-forward が使われ、random split が使われない。
- 欠損があっても落ちにくい。
- データ不足時に graceful error または low-confidence warning になる。
- prediction result schema が期待どおり。
- 既存 forecast API / default 挙動が壊れない。
- validation metrics、confidence、feature contribution summary が返る。

完了条件:

- adapter 未設定でも既存機能が壊れない。
- provider / model の使用状態と fallback 状態が UI/API で分かる。
- 通常 tests は network / cloud API / live provider に依存しない。
- 高度予測モデルの出力は、銘柄コックピットとランキングで既存 Forecast / direction signal と読み分けられる。
- 予測は売買判断の主体にせず、スコアやリスクと合わせて確認する材料として扱う。
- `advanced_linear` adapter が追加され、Ridge / ElasticNet の少なくとも Ridge が使える。
- 1〜60 trading day forward return の予測、walk-forward validation、validation metrics、confidence、feature contribution summary が返る。
- backend adapter / advanced forecast consensus は実装済み。`POST /forecast/evaluate` では `adapter=advanced_linear` / `advanced_tree_sklearn` / `advanced_gbdt_sklearn` / `advanced_quantile` 指定時に 1〜60日の高度予測、予測変化率、予測価格、信頼度、検証指標、特徴量要約またはレンジ、注意点を返す。Streamlit 銘柄コックピットでは共通 horizon の `AI予測インサイト` を価格・予測チャートの主役にし、初期表示は実績価格、統合予測線、予測レンジ帯、右側の `予測スコープ`、結論カードに絞る。カードは中心予測（高度予測モデルの統合結果）を結論直下に主表示し、下振れ予測 / 上振れ予測、予測価格、予測レンジ、モデル合意度、予測ばらつき、信頼度理由、注意点、予測期間を出す。個別高度モデルカードは常時表示し、検証指標と単純予測 baseline 比較は折りたたみ配下で確認する。高度予測モデル / 単純予測モデル線はグループチェックでチャートに追加でき、表示後は固定色のチャート内凡例クリックで個別系列を薄くできる。初期チャートと主要モデルカードから naive / moving-average / momentum は外し、単純予測は詳細確認用の baseline として残す。Ranking では取得期間から決まる同じ horizon の高度予測 consensus を補助列として保持し、表示テーブル / 選択候補 breakdown / score detail / CSV export で確認できる。`AI予測インサイト` から派生した上昇 / 下振れ警戒は通常の上昇気配 / 下降警戒へ25%までブレンドし、AI総合では上昇 / 下振れ警戒 / 信頼スコアを低信頼時に中立寄せしながら控えめに加味する。
- Phase 23 closeout では、単純予測モデルが Cockpit の通常チャート初期表示から外れ、高度予測モデル群 / `forecast_consensus` / 信頼度 / レンジ / 検証指標が主表示になっている。Ranking 主要評価への反映は、上昇気配 / 下降警戒の小さなブレンドとAI総合に組み込み済み。Ranking UI には `今回のランキング条件` カードを追加し、評価方針、共通予測日数、AI総合の重みグループ、下降警戒系は低いほど良いこと、AI予測は順位を直接支配しないことを明示する。その他の評価方針や専用 opt-in profile は後続検討する。
- README または roadmap に Advanced Forecast Slice 1 として記録されている。

Research資料保存方針の移行:

- `data/research_docs/` は local fixture / demo seed / user-saved archive / private-note path として残し、live product の主データ源にはしない。
- External live fetch is not a replacement for local storage and should not auto-populate `data/research_docs/` by default.
- If users need persistence later, add an explicit `資料を保存する` / archive action with clear retention wording, source attribution, and cleanup behavior. This must be separate from the default live reference flow.
- 長期目標: external source adapters が選択銘柄のfresh on-demand evidenceを提供し、local storage は fetched documents の暗黙cacheとして増やすのではなく、user-controlledな保存場所として扱う。

### 5.10 Phase 24: 低コストAssistant体験

状態: 初期backend slice と Cockpit / Ranking 向け floating `SMAI Copilot` UI slice 実装済み。LLM 実装後の `SMAI Copilot` チャット画面、限定自由入力、外部 LLM Gateway API 連携は後続範囲。

目的: Decision Report context と Research Summary を入力にし、初心者向けの質問応答・説明を deterministic template または opt-in `LLM Gateway API` で提供する。SMAI マスコットのフローティングAssistant UI として、アプリ機能の使い方、銘柄の確認観点、投資レーダーの読み方を案内する。

範囲:

- `backend/assistant/` の request / response contract を維持する。
- template-based response service を deterministic fallback として維持する。
- cockpit / ranking / rebalance / report / research context から assistant context を組み立てる。
- Streamlit に SMAI マスコットのフローティングAssistant UI、将来の `SMAI Copilot` チャット画面、固定質問 / 限定自由入力を追加する。
- LLM 基盤は SMAI 本体に密結合させず、外部 `LLM Gateway API` 経由で呼び出す。SMAI 側は context bundle、API client、schema validation、deterministic fallback を持ち、provider routing / prompt tuning / rate limit / model switching は Gateway 側に寄せる。
- 応答は理由、注意点、次に確認する観点、参照セクション、非助言文言を含める。

現在の実装メモ:

- `backend/assistant` に `AssistantRequest` / `AssistantResponse` と `TemplateAssistantService` の初期 slice を追加済み。LLM / network なしで、`DecisionReportContext` から質問意図、関連 section、理由、注意点、次の確認観点、引用 section を deterministic に整理する。
- Assistant は買う / 売る / 保有などの指示には答えず、スコア、リスク、根拠資料、未確認項目を確認するための説明に限定する。
- Cockpit / Ranking には fixed floating `SMAI Copilot` を追加済み。画面・セクションに応じた context を登録し、質問チップから deterministic `TemplateAssistantService` に渡す。Cockpit はデータ取得前、`AI予測インサイト`、`上昇気配・下降警戒`、Decision Report、Ranking は作成前、ランキング結果、深掘り候補を説明対象にする。
- チップ操作はブラウザ内の native `details` / `summary` と CSS 表示切替で完結し、query parameter navigation、価格取得、予測計算、ランキング作成を走らせない。回答は理由、注意点、次の確認、参照 section を返す。
- LLM 実装後の `SMAI Copilot` チャット画面、限定自由入力、外部 `LLM Gateway API` client、Gateway request / response schema、mock gateway provider は Phase 24 の後続 slice として扱う。
- `SMAI Copilot` チャット画面は、右下 floating Copilot の置き換えではなく、銘柄コックピット、ランキング、投資レーダー、Decision Report を横断して相談する専用ワークスペースとして扱う。floating Copilot は画面・セクション内のクイック補助、チャット画面は自由入力と会話履歴を持つ深掘り補助に分ける。

Pre-LLM closeout 方針:

- LLM 導入前に、現在の deterministic Assistant を基準線として固定する。対象画面、セクション、質問タイプ、`見る材料` / `注意点` / `次に確認すること` の出力形、非助言境界を仕様化する。
- SMAI から Gateway へ渡す `AssistantContextBundle` を定義し、Decision Report context、Research Summary、Ranking score breakdown、`AI予測インサイト`、データ品質、根拠不足などの共有可能な文脈だけを含める。内部 raw logs、不要な provider raw fields、保存対象でない外部本文全文は通常 request に含めない。
- Gateway request には task、language、user_question、context、constraints を含め、constraints で `no_investment_advice`、`do_not_change_scores`、`do_not_rank_symbols`、`answer_format=materials_cautions_checkpoints` を明示する。
- Gateway response は `answer`、`materials`、`cautions`、`next_checkpoints`、`referenced_sections`、`confidence`、`safety_notes` のような UI 互換 schema に固定し、schema validation に失敗した場合は deterministic fallback に戻す。
- 将来のチャット画面に備え、Gateway request / response は `conversation_id`、`message_history`、`active_context_id`、`referenced_context_ids` を後から追加できる形にする。初期実装では固定質問・単発質問でも、`AssistantContextBundle` は floating UI と chat UI の共通文脈として設計する。
- 通常テストは `MockAssistantGatewayClient` で network-free に保つ。実 Gateway / external LLM 呼び出しは明示 opt-in の live smoke として分離する。
- LLM は説明、要約、確認観点の提示だけを担当し、スコア計算、ランキング順位、予測値、売買判断、ポートフォリオ配分案の決定主体にしない。

Phase 24 closeout 後の `smai-ai-gateway` 構想:

- Phase 24 closeout 後、SMAI リポジトリ配下に `smai-ai-gateway/` を新設する。ただし将来的に独立リポジトリまたは Git submodule へ切り出せる前提で、SMAI 本体からの import 依存や内部 contract 共有を避ける。
- `smai-ai-gateway` は SMAI 専用ではなく、会議要約アプリ、AI テスト基盤、その他ローカルツールからも使える汎用 AI Gateway として扱う。SMAI との接続は HTTP API と request / response schema に限定する。
- 既存の SMAI RAG / News RAG / Research Evidence 機能は現時点では移動しない。まずは LLM 通信、API、prompt 実行、設定、ドキュメント体系、network-free test の土台を整備する。
- 初期構成は FastAPI ベースとし、`GET /health`、`POST /api/v1/chat`、`POST /api/v1/summarize` を提供する。chat / summarize は SMAI 固有名を使わず、`answer`、`model`、`provider`、`elapsed_ms` などの汎用 response を返す。
- 初期 LLM provider は Ollama とする。`OLLAMA_BASE_URL` は `.env` から読み、既定値は `http://localhost:11434`、既定 model は `DEFAULT_LLM_MODEL` とする。request model 指定があれば優先し、timeout と分かりやすい error response を備える。将来 OpenAI compatible API、vLLM、llama.cpp server へ差し替えられる client 境界にする。
- 設定は `APP_NAME`、`APP_ENV`、`OLLAMA_BASE_URL`、`DEFAULT_LLM_MODEL`、`REQUEST_TIMEOUT_SECONDS`、`ENABLE_DEBUG_LOG` を最小構成とし、`.env.example` と `SETUP.md` で起動手順を明示する。
- サービス層は `chat_service.py`、`summarize_service.py`、`prompt_service.py` に分け、API 層へ prompt 生成や provider 呼び出しを直接書かない。prompt template は後から外部化できる形を保つ。
- 初期ディレクトリ案:

```text
smai-ai-gateway/
  README.md
  SETUP.md
  .env.example
  pyproject.toml
  run_server.bat
  docs/
    architecture.md
    api_spec.md
    prompt_policy.md
    roadmap.md
  app/
    __init__.py
    main.py
    config.py
    clients/
      __init__.py
      ollama_client.py
    services/
      __init__.py
      chat_service.py
      summarize_service.py
      prompt_service.py
    schemas/
      __init__.py
      common.py
      chat.py
      summarize.py
  tests/
    test_health.py
    test_chat_schema.py
```

- Gateway 側 docs では、`README.md` に目的、SMAI 本体から LLM 通信を分離する理由、submodule 化前提、汎用用途、起動概要を書く。`SETUP.md` に Python 環境、依存関係、Ollama、`ollama pull qwen3:8b` 例、`.env` 作成、`run_server.bat`、`/health` と `/api/v1/chat` の確認を書く。
- `docs/architecture.md` には SMAI 本体、`smai-ai-gateway`、Ollama、将来 RAG / スマホ / PWA / cloud client の関係を書く。`docs/api_spec.md` には `/health`、`/api/v1/chat`、`/api/v1/summarize` の request / response 例を書く。`docs/prompt_policy.md` には LLM が数値予測やランキング決定ではなく説明、要約、判断補助を担当すること、投資助言ではないこと、根拠データを明示的に渡して hallucination を抑えること、将来 SMAI RAG context を入力として渡す方針を書く。
- Gateway 側 roadmap は、Phase 1 local Ollama 接続、Phase 2 SMAI の投資コメント生成、Phase 3 会議要約 / AI テスト基盤への展開、Phase 4 認証 / ログ / API key / rate limit、Phase 5 別リポジトリ化 / Git submodule 化、Phase 6 スマホ / PWA / cloud 対応とする。
- 初期 test は `/health` が 200 を返すこと、chat request schema、summarize request schema が validate できることに絞る。通常確認は Ollama や network に依存させず、live LLM smoke は明示 opt-in として分離する。
- 初期実装時は既存 SMAI の画面、RAG、Ranking、Forecast、News fetch、Decision Report を変更しない。SMAI から呼び出す統合 slice と `SMAI Copilot` チャット画面は、Gateway 単体の scaffold / schema / local smoke が安定した後に別タスクとして扱う。

完了条件:

- LLM なしでも assistant UI が deterministic fallback で動作する。
- LLM Gateway API を使う場合も明示 opt-in で、失敗時、timeout、schema validation failure 時は deterministic fallback に戻る。
- 同じ deterministic input / context では同じ応答になる。
- 通常 tests は network 非依存で通る。
- Assistant の説明は UI / report と同じ指標名・制約を使う。
- LLM は説明・要約・観点提示に限定し、スコア計算や売買判断の主体にしない。

Phase 24+ の高度ニュース活用候補:

- 関連銘柄の自動抽出
- `投資レーダー` 画面から `銘柄コックピット` への遷移
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

Phase 24+ のニュース機能で守る線:

- ニュース RAG は売買推奨を行わず、buy / sell / hold を直接出さない。
- ニュースだけで Investment Score やランキング順位を変更しない。
- source URL がない内容を断定しない。
- 古いニュースは warning または `freshness_status` で明示する。
- 外部ニュース取得は adapter 化し、`AI調査を更新` の標準 source として扱う。
- CI / 通常テストは外部ネットワークに依存させない。
- 外部 LLM は必須にせず、template / deterministic fallback を維持する。

### 5.11 Phase 25: 高度ExportとExecution Gate

状態: 将来範囲 / 低優先度

目的: Decision Report が安定した後に、PDF / Excel export や broker execution の再開可否を判断する。

範囲:

- UI リッチな PDF report / Excel report。
- report archive / saved watchlist / ranking scenario。
- broker 連携の再評価。
- order sending は、risk / report / audit / user confirmation が揃うまで実装しない。

完了条件:

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
- 高度ニュース活用
- `smai-ai-gateway` scaffold inside SMAI repo, with future independent repo / Git submodule boundary
- Generic FastAPI LLM Gateway endpoints: `/health`, `/api/v1/chat`, `/api/v1/summarize`
- Ollama client boundary with `.env` settings and future OpenAI compatible / vLLM / llama.cpp replacement path
- LLM Gateway API request / response protocol
- MockAssistantGatewayClient / schema validation
- Opt-in live LLM Gateway smoke
- `SMAI Copilot` dedicated chat workspace with conversation history and shared `AssistantContextBundle`
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
- Phase 22.x `投資レーダー` dashboard の追加ニュースprovider、詳細フィルタ、Watchlist連動をどの順に進めるか
- `投資レーダー` 画面の初期表示は、詳細な news cache status / cache size カードを置かず、タイトル右上の `情報鮮度` と必要時の警告に絞った。今後は詳細フィルタ / Watchlist 連動と合わせて継続調整するか
- Symbol DB background refresh の live provider refresh wiring をどの provider / opt-in 条件で接続するか
- Research Score をランキング順位へ統合する必要性を再確認するか。既定では統合しない
- Assistant が参照できる context の範囲、privacy boundary、API / Streamlit 質問パネルの位置
- PDF / Excel export をいつ入れるか
- Execution / broker order をどの段階で再開するか
