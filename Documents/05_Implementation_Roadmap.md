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
- Research RAG の `ResearchFactSummary` 抽出対象拡張、追加 external source adapter、Research Score の銘柄コックピット深掘り導線 / Decision Report 表示 polish
- cockpit / report の Research Summary 表示 polish と source-backed fact 表示
- Research Score によるランキング順位統合は、現時点では見送り。必要性が再確認された場合のみ後続の opt-in 機能として扱う
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
- Assistant / LLM / external source / Execution は、判断材料の構造化が安定してから追加する。

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

- 新しい `投資ニュース` 画面の実装
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

Phase 22.x: 投資ニュースダッシュボード MVP

状態: 方針整理済み / 実装候補

目的: 新画面 `投資ニュース` を、単なるニュース一覧ではなく、市場全体の温度感、注目テーマ、関連銘柄への深掘り導線を提供する市場ニュースコックピットとして設計する。ニュースだけで判断を完結させず、気になる材料を `銘柄コックピット` で確認する入口にする。

現在の前提:

- 既存実装では、Cockpit Research Summary 内に `Market Intelligence`、URL付き `投資ヒントとなるニュース`、`ニュース・開示の出典` citation list がある。
- 独立した `投資ニュース` 画面、ニュース横断ランキング、News Score 化、Watchlist 連動、通知は未実装。
- Phase 22 本体の Research Score 方針は維持し、投資ニュース dashboard は Phase 22.x の UI / backend snapshot slice として扱う。

MVP 必須機能:

- 上部: 流れるマーケット概況ニュース
  - 固定サマリーではなく、ニュースティッカー / 速報カード / 重要ニュースの自動ローテーション風 UI を配置する。
  - 表示項目は title、source_name、source_type、published_at、freshness_status、material_type、related_symbols、短いAIコメント、元記事URL。
  - MVP では realtime 通信は不要。fake fixture / snapshot 内のニュースを一定間隔で切り替える UI でよい。
  - ユーザー操作による一時停止、hover 時停止、URLクリックを将来拡張しやすい構造にする。
- 中央上: 加熱テーマ・ヒートマップ
  - 価格変動ではなくニュース加熱度ヒートマップにする。
  - `heat = news_count * freshness_weight * material_weight` を初期案とし、カテゴリ、news_count、risk_count、positive_count、official_source_count、freshness_ratio を表示する。
  - heat が高いセルは強調、リスク材料が多いセルは警戒色、ポジティブ材料が多いセルはポジティブ色、公式開示が多いセルは badge 表示にする。
  - セルクリックで下部カテゴリレーンへフォーカスできるとよい。
- 中央下: 投資カテゴリ別ニュースレーン
  - 国内株、米国株、ETF、半導体・AI、金融、エネルギー、為替・金利、決算・業績修正、配当・株主還元、政策・規制、地政学・マクロリスクを初期カテゴリ候補にする。
  - 各カテゴリに 3〜5 件程度のコンパクトニュースカードを表示する。
  - カード項目は title、source_name、source_type、url、published_at、fetched_at、freshness_status、summary、material_type、related_symbols、official_source badge、AI分析コメント、投資確認観点。
- AI分析コメント / 投資確認観点
  - MVP では LLM 生成は不要。material_type / category / source_type に応じた deterministic template comment でよい。
  - `ai_comment: str | None` と `investment_checkpoints: list[str]` を保持し、将来 LLM / RAG 生成へ差し替えやすい関数境界にする。
  - コメントは売買推奨に見えないようにし、買い / 売り / 今すぐ投資 / 必ず上がる / 確実に儲かる等の断定表現を避ける。
- 銘柄コックピットで確認 導線
  - `related_symbols` が1件以上あるニュースカードには、銘柄チップと `銘柄コックピットで確認` 導線を表示する。
  - ニュースだけで銘柄評価、Investment Score、Research Score、ランキング順位を変更しない。

MVP で見送る機能:

- 右側フィルタ、詳細なニュース一覧、高度な検索、ソース別の細かい絞り込み。
- Watchlist 連動、通知、SNS sentiment、高度なクラスタリング。
- News Score、ニュースによる Investment Score / Ranking 順位への統合。
- 売買推奨、自動売買、buy / sell / hold 判断。

実装候補:

- `backend/news/contracts.py`: `NewsHeadlineCard`、`NewsHeatmapCell`、`NewsCategoryLane`、`NewsDashboardSnapshot`。
- `backend/news/dashboard_service.py`: `build_news_dashboard_snapshot`、`classify_news_category`、`classify_material_type`、`build_news_stream`、`build_heatmap_cells`、`build_category_lanes`、`build_ai_comment`、`build_investment_checkpoints`。
- `ui/views/news.py`: `投資ニュース` 画面。ニュースストリーム、加熱テーマヒートマップ、カテゴリ別ニュースレーンを表示する。
- `ui/components/sidemenu.py` / `ui/app.py`: `投資ニュース` を side menu と routing に追加する。

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
- stream_headlines、heatmap_cells、category_lanes、source URL 保持、related_symbols ありの場合の Cockpit 導線対象、ai_comment、investment_checkpoints を確認する。
- published_at / fetched_at 欠落時も壊れないことを確認する。
- 禁止表現テストとして、買い、売り、今すぐ投資、必ず上がる、確実に儲かる等を含まないことを確認する。

Phase 22.x 完了条件:

- サイドメニューから `投資ニュース` 画面を開ける。
- 上部に流れるマーケットニュースストリームが表示される。
- ニュースカードが自動ローテーション風に表示される。
- 加熱テーマ・ヒートマップが表示される。
- 投資カテゴリ別ニュースレーンが表示される。
- ニュースカードにAI分析コメント / 投資確認観点が表示される。
- 関連銘柄があるニュースカードに `銘柄コックピットで確認` 導線が表示される。
- 元記事URLがクリック可能。
- 右側フィルタ / 詳細一覧は未実装でよい。
- fake fixture による network-free regression test が通る。
- 既存の Research Summary / ニュースURL表示仕様を壊さない。

Phase 22.y: News Background Refresh & Cache Layer

状態: 実装完了

目的: 投資ニュースダッシュボードのニュース取得、分類、AIコメント生成、ヒートマップ生成を、起動時、手動更新、将来の定期更新で繰り返しても、ニュースキャッシュ、更新履歴、取得ログ、エラーログ、一時ファイル、古い snapshot、source raw data、debug dump が無制限に増えないようにする。ローカルアプリとして長期利用してもストレージを圧迫しない設計を MVP 時点から入れる。

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

- `投資ニュース` 画面には、肥大化防止に関係する状態を簡潔に表示できるようにする。
  - 例: `最終更新: 21:15`、`状態: fresh`、`キャッシュ: 182KB`、`バックグラウンド更新中`
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

完了条件:

- Research Score は evidence と紐づいて説明できる。
- Cockpit / Decision Report で Research Score の内訳、根拠、confidence、warnings を確認できる。
- evidence 不足時は score 欠損または低信頼として表示される。
- ランキング順位は既定では変更しない。
- external source adapter は通常 checks に入れない。

### 5.9 Phase 23: 低コストAssistant体験

状態: 初期backend slice 実装中

目的: Decision Report context と Research Summary を入力にし、初心者向けの質問応答・説明を deterministic template で提供する。

範囲:

- `backend/assistant/` の request / response contract を定義する。
- template-based response service を default provider として実装する。
- cockpit / ranking / rebalance / report / research context から assistant context を組み立てる。
- Streamlit に質問パネルまたは assistant view を追加する。
- 応答は理由、注意点、次に確認する観点、非助言文言を含める。

現在の実装メモ:

- `backend/assistant` に `AssistantRequest` / `AssistantResponse` と `TemplateAssistantService` の初期 slice を追加済み。LLM / network なしで、`DecisionReportContext` から質問意図、関連 section、理由、注意点、次の確認観点、引用 section を deterministic に整理する。
- Assistant は買う / 売る / 保有などの指示には答えず、スコア、リスク、根拠資料、未確認項目を確認するための説明に限定する。
- 初期 slice は backend service / unit tests まで。API / Streamlit 質問パネルは次の slice として扱う。

完了条件:

- LLM なしで assistant API/UI が動作する。
- 同じ input / context では同じ応答になる。
- 通常 tests は network 非依存で通る。
- Assistant の説明は UI / report と同じ指標名・制約を使う。

Phase 23+ の高度ニュース活用候補:

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

Phase 23+ のニュース機能で守る線:

- ニュース RAG は売買推奨を行わず、buy / sell / hold を直接出さない。
- ニュースだけで Investment Score やランキング順位を変更しない。
- source URL がない内容を断定しない。
- 古いニュースは warning または `freshness_status` で明示する。
- 外部ニュース取得は adapter 化し、`AI調査を更新` の標準 source として扱う。
- CI / 通常テストは外部ネットワークに依存させない。
- 外部 LLM は必須にせず、template / deterministic fallback を維持する。

### 5.10 Phase 24: Optional Adapter と高度分析

状態: 計画中

目的: default path を deterministic に保ったまま、追加 provider、advanced forecast / research model、LLM adapter、news / sentiment を optional layer として追加する。

範囲:

- `polygon` など追加 live provider adapter。
- advanced forecast model adapter。
- local LLM / cloud LLM assistant provider。
- news / sentiment local CSV provider と optional external provider。
- LLM / news / external provider はすべて明示 opt-in とし、失敗時は deterministic fallback に戻す。

完了条件:

- adapter 未設定でも既存機能が壊れない。
- provider / model / LLM の使用状態と fallback 状態が UI/API で分かる。
- 通常 tests は network / cloud API / heavy ML library に依存しない。
- LLM は説明・要約・観点提示に限定し、スコア計算や売買判断の主体にしない。

Research資料保存方針の移行:

- `data/research_docs/` は local fixture / demo seed / user-saved archive / private-note path として残し、live product の主データ源にはしない。
- External live fetch is not a replacement for local storage and should not auto-populate `data/research_docs/` by default.
- If users need persistence later, add an explicit `資料を保存する` / archive action with clear retention wording, source attribution, and cleanup behavior. This must be separate from the default live reference flow.
- 長期目標: external source adapters が選択銘柄のfresh on-demand evidenceを提供し、local storage は fetched documents の暗黙cacheとして増やすのではなく、user-controlledな保存場所として扱う。

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
