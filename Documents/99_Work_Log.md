# 99_Work_Log

#### [BACK TO README](../README.md)

## Purpose / ??

This file stores historical work-log entries for Smart Market AI.
??????? Smart Market AI ??????????????

`PROJECT_CONTEXT.md` should stay compact and focused on the current project state.
`PROJECT_CONTEXT.md` ???????????????????????????

Read this file only when historical investigation is needed.
???????????????????????????

When adding a new work-log entry, append it to the top of the Work Log section.
????????????????Work Log ???????????????

## Work Log / 作業ログ

- 2026-05-10: Added a `Symbol search` text filter to the Streamlit Market Data symbol selector so yfinance-compatible candidate tickers can be narrowed by ticker or company-name partial matches while preserving Custom input. / Streamlit Market Data の symbol selector に `Symbol search` テキスト絞り込みを追加し、yfinance 形式の候補 ticker を ticker / company name の部分一致で絞り込めるようにしつつ Custom 入力を維持した。
- 2026-05-10: Added a yfinance-compatible representative symbol selector and adjacent company-name display to the Streamlit Market Data form while keeping custom symbol input available. / Streamlit Market Data form に yfinance 形式の代表銘柄候補 selector と横並びの会社名表示を追加しつつ、custom symbol 入力も維持した。
- 2026-05-10: Improved the Streamlit Forecast / Market Data UI by moving Market Data to the left tab, adding legend-click series visibility for the forecast chart, and deriving forecast reference periods automatically from the fetched period and horizon. / Streamlit Forecast / Market Data UI を改善し、Market Data tab を左側へ移動、forecast chart の凡例クリックによる系列表示切替、取得期間と horizon からの参照期間自動算出を追加した。
- 2026-05-10: Added symbol resolver and market-selection requirements to the beginner-friendly UI roadmap so Japanese equity codes, Yahoo suffixes, and provider-specific symbol normalization are handled deliberately later. / 日本株コード、Yahoo suffix、provider 固有の symbol 正規化を後で意図的に扱えるよう、初心者向け UI roadmap に symbol resolver と市場選択の要件を追加した。
- 2026-05-10: Moved Streamlit `Forecast days` out of the Market Data fetch header and into the forecast result area so changing the horizon recalculates only chart and metric rows from already fetched bars. / Streamlit の `Forecast days` を Market Data 取得ヘッダーから forecast 結果エリアへ移し、horizon 変更時は取得済み bars から chart / metric 行だけを再計算するようにした。
- 2026-05-10: Added `Documents/07_UI_Wording_Policy.md` to define concise Japanese UI wording, chart legend labels, metric explanation tone, and investment-support phrasing for future UI/report work. / 今後の UI / report 作業に向けて、簡潔な日本語 UI 文言、チャート凡例、指標説明の温度感、投資判断補助としての表現方針を定義する `Documents/07_UI_Wording_Policy.md` を追加した。
- 2026-05-10: Replaced the pre-commit Black hook with the local single-process `tools/run_black_check.py` helper and documented that direct multi-file `python -m black --check .` is not the routine check path in this Windows environment. / pre-commit の Black hook を単一プロセスの `tools/run_black_check.py` helper に置き換え、この Windows 環境では複数ファイル対象の `python -m black --check .` を通常確認経路にしないことを明記した。
- 2026-05-10: Improved the Streamlit Market Data forecast view by making the forecast chart primary, adding beginner-friendly model labels and metric summaries, marking the future forecast boundary, and folding provider/feature details into expanders. / Streamlit Market Data の forecast 表示を主役化し、初心者向けのモデル名・指標要約、将来予測の境界表示、provider/feature 補助情報の折りたたみを追加した。
- 2026-05-10: Split the historical work log out of `PROJECT_CONTEXT.md` into `Documents/99_Work_Log.md`, rewrote `PROJECT_CONTEXT.md` as a compact current-state summary, and added a Codex task template. / `PROJECT_CONTEXT.md` から過去作業ログを `Documents/99_Work_Log.md` へ分離し、`PROJECT_CONTEXT.md` を軽量な現在地サマリへ整理し、Codex 用タスクテンプレートを追加した。
- 2026-05-08: Added a `yahoo` opt-in live-provider stub and connected it through the market-data provider factory without importing external provider libraries. / external provider library を import せずに `yahoo` opt-in live-provider stub を追加し、market-data provider factory へ接続した。
- 2026-05-08: Added a Streamlit Market Data preview tab that shows provider metadata, quote rows, OHLCV summary, FX rates, and provider error details for the configured provider. / 設定中 provider の provider metadata、quote rows、OHLCV summary、FX rates、provider error details を表示する Streamlit Market Data preview tab を追加した。
- 2026-05-08: Expanded the Phase 10 completion target to include Streamlit UI confirmation of live-provider data and provider status. / Phase 10 の完了目標を拡張し、live provider の取得データと provider 状態を Streamlit UI で確認できることを含めた。
- 2026-05-08: Added `create_market_data_provider_adapter()` as the configured factory entrypoint for deterministic and future live market-data adapters. / deterministic provider と将来の live market-data adapter の設定済み factory 入口として `create_market_data_provider_adapter()` を追加した。
- 2026-05-08: Added the shared `MarketDataProviderAdapter` protocol and linked planned live-provider adapter metadata to that interface. / 共通 `MarketDataProviderAdapter` protocol を追加し、planned live-provider adapter metadata をその interface に紐づけた。
- 2026-05-08: Started Phase 10 by adding planned live-provider adapter metadata for `yahoo` and `polygon` without importing network-dependent libraries. / network-dependent library を import せずに、`yahoo` と `polygon` の planned live-provider adapter metadata を追加して Phase 10 に着手した。
- 2026-05-08: Checked project-wide consistency after document consolidation and aligned current context/agent guidance with the new roadmap and operations-guide files. / 文書統合後にプロジェクト全体の整合性を確認し、現在地コンテキストと agent 向け方針を新しい roadmap / operations guide 構成に合わせた。
- 2026-05-08: Reorganized `Documents/05_Implementation_Roadmap.md` into a cleaner Japanese structure with current state, completed phases, next roadmap, verification commands, and open items. / `Documents/05_Implementation_Roadmap.md` を、現在地、完了済みフェーズ、次期ロードマップ、検証コマンド、未決事項が見やすい日本語構成へ整理した。
- 2026-05-08: Consolidated post-05 documents by merging API, CSV, manual workflow, UI, external provider, and next-roadmap notes into `Documents/05_Implementation_Roadmap.md` and `Documents/06_MVP_Operations_Guide.md`. / 05 以降の文書を整理し、API、CSV、manual workflow、UI、external provider、次期 roadmap の説明を `Documents/05_Implementation_Roadmap.md` と `Documents/06_MVP_Operations_Guide.md` に統合した。
- 2026-05-08: Documented the next Multi-Model Investment Intelligence roadmap across requirements, system design, functional design, roadmap, README, AGENTS, and project context. / 次期 Multi-Model Investment Intelligence roadmap を、要件定義、システム設計、機能設計、ロードマップ、README、AGENTS、project context に反映した。
- 2026-05-08: Added local CSV downloads for Streamlit rebalance result tables. / Streamlit rebalance 結果テーブル向けのローカル CSV ダウンロードを追加した。
- 2026-05-08: Added a deterministic local ZIP download for Streamlit rebalance JSON and CSV report files. / Streamlit rebalance の JSON と CSV レポートファイルをまとめる deterministic なローカル ZIP ダウンロードを追加した。
- 2026-05-08: Added a deterministic report manifest to the Streamlit rebalance ZIP export. / Streamlit rebalance の ZIP export に deterministic な report manifest を追加した。
- 2026-05-08: Added validated request JSON to the Streamlit rebalance downloads and report ZIP. / Streamlit rebalance の download と report ZIP に validated request JSON を追加した。
- 2026-05-08: Added a human-readable Markdown report summary to Streamlit rebalance downloads and report ZIP. / Streamlit rebalance の download と report ZIP に人が読みやすい Markdown report summary を追加した。
- 2026-05-08: Added allocation-comparison and proposed-trade tables to the Streamlit rebalance Markdown report. / Streamlit rebalance Markdown report に allocation comparison と proposed trade の表を追加した。
- 2026-05-08: Added current-position and target-allocation tables to the Streamlit rebalance Markdown report. / Streamlit rebalance Markdown report に current position と target allocation の表を追加した。
- 2026-05-08: Completed Reporting MVP scope by sharing report rows through `RebalanceReportContext` and documenting the JSON/CSV/Markdown/manifest/ZIP boundary for MVP exports. / `RebalanceReportContext` で report rows を共有し、MVP export の範囲を JSON/CSV/Markdown/manifest/ZIP として文書化して Reporting MVP の範囲を完了扱いにした。
- 2026-05-08: Clarified planned live market-data provider failures with explicit `DataSourceError` details for future opt-in support. / 将来の opt-in 対応に向けて、予定されている live market-data provider の失敗を明示的な `DataSourceError` details で分かるようにした。
- 2026-05-08: Added provider unavailable and timeout domain errors for future live market-data API mapping. / 将来の live market-data API mapping に向けて、provider unavailable と timeout のドメインエラーを追加した。
- 2026-05-08: Added `dataaccess.allow_external_providers` as an explicit opt-in gate before future live provider implementation paths. / 将来の live provider 実装経路へ進む前の明示 opt-in gate として `dataaccess.allow_external_providers` を追加した。
- 2026-05-08: Added structured API response coverage and OpenAPI metadata for live-provider opt-in, unavailable, and timeout failures. / live provider の opt-in、unavailable、timeout 失敗に対する構造化 API レスポンスのカバレッジと OpenAPI metadata を追加した。
- 2026-05-08: Added structured API response tests for provider rate-limit and schema-mismatch failures. / provider rate limit と schema mismatch 失敗に対する構造化 API レスポンステストを追加した。
- 2026-05-08: Centralized market-data provider capability metadata in a registry for future live adapter implementation. / 将来の live adapter 実装に向けて、market-data provider の capability metadata を registry に集約した。
- 2026-05-08: Completed Phase 9 preparation by documenting external provider setup, limitations, failure modes, and offline default behavior. / external provider の setup、制約、failure mode、offline default behavior を文書化して Phase 9 の準備作業を完了扱いにした。
- 2026-05-08: Checked project-wide documentation consistency after Phase 9 and corrected stale status wording. / Phase 9 後にプロジェクト全体のドキュメント整合性を確認し、古い状態表現を修正した。
- 2026-05-07: Added explicit `RebalanceScenarioError` handling for malformed file-backed rebalance scenarios and covered invalid JSON, invalid request schema, and duplicate scenario names with tests. / 壊れた file-backed rebalance scenario 向けに明示的な `RebalanceScenarioError` 処理を追加し、不正 JSON、不正 request schema、重複 scenario 名をテストでカバーした。
- 2026-05-07: Added file-backed rebalance scenarios under `examples/rebalance_scenarios/` and made the Streamlit UI sample selector load them. / `examples/rebalance_scenarios/` に file-backed rebalance scenario を追加し、Streamlit UI の sample selector から読み込むようにした。

- 2026-05-07: Added Black exclude settings for local virtualenv and cache directories, then moved routine local checks to `tools/run_black_check.py` to avoid direct `black --check .` scans. / ローカル仮想環境と cache ディレクトリの Black 除外設定を追加し、その後の通常ローカル確認は `black --check .` 直接実行ではなく `tools/run_black_check.py` に寄せた。

- 2026-05-07: Added cache-free local Black and MVP verification helpers, then covered command construction and file discovery with tests. / cache-free のローカル Black 確認 helper と MVP 確認 helper を追加し、コマンド生成とファイル探索をテストでカバー。

- 2026-05-07: Updated `AGENTS.md` to clarify that diff review and verification are checkpoints, not automatic stopping points, when the implementation direction is already approved. / 実装方針が承認済みの場合、差分確認と検証は自動停止地点ではなくチェックポイントとして扱うよう `AGENTS.md` に明記。

- 2026-05-07: Clarified documentation language policy in `AGENTS.md`: human-facing docs are Japanese-first, while AI-facing operating/context docs are bilingual English/Japanese. / `AGENTS.md` のドキュメント言語方針を明確化し、人向け文書は日本語中心、AI 向け運用・文脈文書は英日併記と定義。

- 2026-05-07: Synchronized README, manual workflow docs, and UI guide with the current deterministic Portfolio-to-Risk MVP. / README、手動確認手順、UI ガイドを現在の deterministic な Portfolio-to-Risk MVP に合わせて同期。

- 2026-05-05: Extended the implementation roadmap through MVP stabilization, CSV/scenario expansion, configurable scenarios, reporting MVP, and explicit opt-in external data provider preparation. / 実装ロードマップを MVP stabilization、CSV/scenario expansion、configurable scenarios、reporting MVP、明示 opt-in の外部データ provider 準備まで拡張。

- 2026-05-05: Rechecked project-wide implementation direction against roadmap and context documents, then removed stale Streamlit/UI next-step wording. / プロジェクト全体の実装方針を roadmap と context 文書に照らして再確認し、古い Streamlit/UI の次ステップ表現を削除。

- 2026-05-05: Added Streamlit sample-symbol explanations and human-readable symbol labels in rebalance result tables. / Streamlit にサンプル銘柄の説明と rebalance 結果テーブル向けの読みやすい銘柄ラベルを追加。

- 2026-05-05: Added Streamlit allocation comparison rows showing current weights, target weights, and drift by symbol. / 銘柄ごとの current weight、target weight、drift を表示する Streamlit allocation comparison 行を追加。

- 2026-05-05: Added a Streamlit AAPL target-weight slider that regenerates deterministic MVP target-allocation JSON. / deterministic な MVP target-allocation JSON を再生成する Streamlit の AAPL target-weight slider を追加。

- 2026-05-05: Added a Streamlit local JSON download for rebalance-check results and covered the payload helper with tests. / Streamlit に rebalance-check 結果のローカル JSON ダウンロードを追加し、payload helper をテストでカバー。

- 2026-05-05: Made Streamlit rebalance sample inputs use sample-specific widget keys so sample switching refreshes form values reliably. / Streamlit rebalance サンプル入力にサンプル別 widget key を使い、サンプル切り替え時にフォーム値が確実に切り替わるようにした。

- 2026-05-05: Checked recent Streamlit UI changes against design documents and synchronized the roadmap, UI guide, and contributor documentation policy. / 最近の Streamlit UI 変更を設計ドキュメントと照合し、roadmap、UI guide、contributor 向けドキュメント方針を同期。

- 2026-05-05: Added deterministic Streamlit rebalance sample selection with default and no-trades scenarios. / Streamlit の rebalance 入力に default と no-trades の決定的なサンプル切り替えを追加。

- 2026-05-05: Added Streamlit UI runtime settings display, shared default request helpers, and deterministic UI helper tests. / Streamlit UI に実行時設定表示、共通デフォルト request helper、決定的な UI helper テストを追加。

- 2026-05-05: Verified repository Markdown files are valid UTF-8 without BOM and documented the encoding check rule in `AGENTS.md`. / リポジトリ内 Markdown が UTF-8 without BOM として正常であることを確認し、文字コード確認ルールを `AGENTS.md` に追記。

- 2026-05-05: Aligned the Streamlit UI helper test expectations with current Risk MVP breach rules and fixed import ordering. / Streamlit UI helper テストの期待値を現在の Risk MVP 違反ルールに合わせ、import 順を修正。

- 2026-05-05: Exposed the Portfolio-to-Risk workflow through `POST /portfolio/rebalance-check` and added deterministic API tests. / `POST /portfolio/rebalance-check` で Portfolio-to-Risk workflow を公開し、決定的な API テストを追加。
- 2026-05-05: Improved Swagger/OpenAPI metadata and added Japanese API specification notes, now consolidated into `Documents/06_MVP_Operations_Guide.md`. / Swagger/OpenAPI メタデータを整備し、日本語 API 仕様メモを追加した。現在は `Documents/06_MVP_Operations_Guide.md` に統合済み。
- 2026-05-05: Added optional YAML settings loading via `SMAI_CONFIG_FILE`, PyYAML dependency, example config, and deterministic config tests. / `SMAI_CONFIG_FILE` による任意の YAML 設定読み込み、PyYAML 依存、設定例、決定的な config テストを追加。
- 2026-05-05: Updated `AGENTS.md` to require beginner-friendly implementation explanations after each work unit. / 各作業単位の完了後に初学者向け説明を行うルールを `AGENTS.md` に追記。
- 2026-05-05: Added `types-PyYAML` to development and pre-commit mypy dependencies so YAML imports have type stubs. / YAML import の型スタブを使えるように、開発依存と pre-commit mypy 依存へ `types-PyYAML` を追加。
- 2026-05-05: Added deterministic CSV market-data provider support for symbols, OHLCV bars, quotes, and USDJPY FX rates. / symbols、OHLCV、quotes、USDJPY FX rates に対応する決定的な CSV market-data provider を追加。
- 2026-05-05: Synchronized current-state documents with implemented APIs/providers and added CSV required-column validation. / 実装済み API/provider に合わせて現在地ドキュメントを同期し、CSV 必須列検証を追加。
- 2026-05-05: Updated `AGENTS.md` to require commit message suggestions after each completed work unit. / 各作業単位の完了後にコミットメッセージ案を提示するルールを `AGENTS.md` に追記。
- 2026-05-05: Added deterministic manual workflow docs, example request, and serverless demo script for `POST /portfolio/rebalance-check`. / `POST /portfolio/rebalance-check` 向けの決定的な手動確認手順、サンプル request、サーバー不要の demo script を追加。
- 2026-05-05: Fixed CI mypy issues for PyYAML imports, FastAPI response metadata typing, and CSV currency parsing. / PyYAML import、FastAPI response metadata の型、CSV currency parsing に関する CI mypy 問題を修正。
- 2026-05-05: Added local sample CSV market-data files, `config/csv_example.yaml`, and CSV-provider manual workflow coverage. / ローカル CSV market-data サンプル、`config/csv_example.yaml`、CSV provider 手動確認フローのカバレッジを追加。
- 2026-05-05: Added a minimal Streamlit UI for the Portfolio-to-Risk rebalance-check workflow and UI helper tests. / Portfolio-to-Risk rebalance-check workflow 向けの最小 Streamlit UI と UI helper テストを追加。
- 2026-04-29: Added `AGENTS.md` and `PROJECT_CONTEXT.md` as root-level shared context documents. / ルート共有文書として `AGENTS.md` と `PROJECT_CONTEXT.md` を追加。
- 2026-04-29: Updated both root documents to bilingual English/Japanese format. / ルート文書2点を英日併記に更新。
- 2026-04-29: Updated `AGENTS.md` to require diff-first review and work-log updates per task unit. / `AGENTS.md` に差分先出しレビューと作業単位ごとのログ更新ルールを追記。
- 2026-04-29: Started Phase 3 Risk MVP by adding `backend/risk/` with minimal `RiskService` and decision tests. / `backend/risk/` の最小 `RiskService` と判定テストを追加し、Phase 3 Risk MVP に着手。
- 2026-04-29: Exposed Risk MVP through `POST /risk/pre-trade-check` with deterministic API tests. / `POST /risk/pre-trade-check` で Risk MVP を公開し、決定的な API テストを追加。
- 2026-04-29: Synchronized project documents with the implemented Risk service and API state. / 実装済みの Risk サービスと API の状態に合わせてドキュメントを同期。
- 2026-04-29: Hardened Risk API error-response tests for data-source and computation failures. / データソース失敗と計算失敗に対する Risk API エラー応答テストを強化。
- 2026-04-29: Started Phase 4 Portfolio MVP with deterministic snapshot valuation and no-solver rebalance proposals. / deterministic な評価スナップショットと solver なしのリバランス提案で Phase 4 Portfolio MVP に着手。
- 2026-04-29: Connected Portfolio rebalance proposals to Risk pre-trade checks through a service-level workflow. / service-level workflow で Portfolio リバランス提案を Risk 取引前判定へ接続。
- 2026-05-08: Added `SMAI_REBALANCE_SCENARIO_DIR` so the Streamlit rebalance UI can load file-backed scenarios from a configured local directory. / `SMAI_REBALANCE_SCENARIO_DIR` を追加し、Streamlit rebalance UI が設定されたローカルディレクトリから file-backed scenario を読み込めるようにした。
- 2026-05-08: Added explicit errors for missing or non-directory `SMAI_REBALANCE_SCENARIO_DIR` paths while preserving the default fallback scenarios. / `SMAI_REBALANCE_SCENARIO_DIR` の指定先が存在しない場合やディレクトリでない場合の明示エラーを追加しつつ、既定 scenario の fallback は維持した。
- 2026-05-08: Added optional rebalance scenario descriptions and displayed them under the Streamlit sample selector. / 任意の rebalance scenario 説明を追加できるようにし、Streamlit の sample selector 下に表示するようにした。
- 2026-05-08: Localized the default user-facing rebalance scenario descriptions to Japanese. / 既定のユーザー向け rebalance scenario 説明を日本語化した。
- 2026-05-08: Clarified that future roadmap phases affecting UI behavior must include UI-level completion criteria, and that external-provider features should prefer live-data UI confirmation when available. / 今後のロードマップで UI に影響するフェーズは UI 上の確認を完了条件に含め、外部 provider 機能では可能な限り live data による UI 確認を優先する方針を明確化した。
- 2026-05-08: Expanded the Yahoo market-data provider from an opt-in stub to a `yfinance`-backed live adapter for OHLCV, quotes, and USDJPY FX, with deterministic fake-provider tests and Streamlit Market Data preview coverage. / Yahoo market-data provider を opt-in stub から `yfinance` を使う live adapter へ拡張し、OHLCV、quote、USDJPY FX の取得、deterministic fake-provider test、Streamlit Market Data preview の検証を追加した。
- 2026-05-09: Updated Streamlit date input defaults so rebalance `As of` and Market Data `End` use the current date, while Market Data `Start` defaults to seven days before today. / Streamlit の日付入力初期値を更新し、rebalance の `As of` と Market Data の `End` は現在日付、Market Data の `Start` は現在日付の 7 日前を使うようにした。
- 2026-05-09: Started Feature Store Lite by adding a `FeatureSnapshot` contract, `FeatureBuilder.build_feature_snapshot()`, and Streamlit Market Data feature snapshot rows with provider/version/missing metadata. / `FeatureSnapshot` contract、`FeatureBuilder.build_feature_snapshot()`、provider/version/missing metadata 付きの Streamlit Market Data feature snapshot 行を追加し、Feature Store Lite に着手した。
- 2026-05-09: Added rolling recent OHLCV rows to the mock market-data provider so current-date Streamlit defaults can show an OHLCV summary without losing fixed historical fixture rows. / Streamlit の現在日付デフォルトでも OHLCV summary を表示できるように、固定の historical fixture 行を残したまま mock market-data provider に直近日付の rolling OHLCV 行を追加した。
- 2026-05-09: Extended Feature Store Lite snapshots with return, momentum, drawdown, volatility, ADV, and data-completeness fields, and exposed those values in the Streamlit Market Data feature snapshot table. / Feature Store Lite snapshot に return、momentum、drawdown、volatility、ADV、data completeness を追加し、Streamlit Market Data の feature snapshot table で確認できるようにした。
- 2026-05-09: Formatted Streamlit Feature Snapshot ratio fields as percentages for easier UI inspection. / Streamlit Feature Snapshot の比率系項目を UI で読みやすい percentage 表示に整えた。
- 2026-05-09: Updated `AGENTS.md` current-state wording so deterministic local defaults and explicit opt-in live-provider support are both represented accurately. / deterministic な local default と明示 opt-in の live-provider support の両方が正確に伝わるように、`AGENTS.md` の現在地表現を更新した。
- 2026-05-10: Added Feature Store Lite data-quality judgement to `DailySnapshot` / `FeatureSnapshot`, computed `OK` / `WARN` / `BLOCK` from missing features and data completeness, and exposed the result in the Streamlit Market Data Feature Snapshot table. / `DailySnapshot` / `FeatureSnapshot` に Feature Store Lite の data quality 判定を追加し、欠損特徴量と data completeness から `OK` / `WARN` / `BLOCK` を計算して Streamlit Market Data の Feature Snapshot 表で確認できるようにした。
- 2026-05-10: Confirmed that direct multi-file `python -m black` can leave worker processes stuck in the current local PowerShell environment, stopped the leftover processes, and aligned CI/setup docs with the cache-free `tools/run_black_check.py` helper. / 現在のローカル PowerShell 環境では複数ファイル指定の `python -m black` が worker process を残して固まる場合があることを確認し、残存 process を停止したうえで、CI と setup docs を cache-free の `tools/run_black_check.py` helper に合わせた。
- 2026-05-10: Added provider-level fundamentals through `FundamentalSnapshot` and `fetch_fundamentals()`, wired `dividend_yield` and `market_cap_jpy` into Feature Store Lite, and exposed those fields in the Streamlit Market Data Feature Snapshot table. / `FundamentalSnapshot` と `fetch_fundamentals()` で provider-level fundamentals を追加し、Feature Store Lite に `dividend_yield` と `market_cap_jpy` を接続して Streamlit Market Data の Feature Snapshot 表で確認できるようにした。
- 2026-05-10: Started Screening Score MVP by adding `ScreeningService`, explainable score breakdowns for momentum, liquidity, risk, and data quality, and Streamlit Market Data ranking rows. / `ScreeningService`、momentum、liquidity、risk、data quality の説明可能な score breakdown、Streamlit Market Data の ranking 行を追加して Screening Score MVP に着手した。
- 2026-05-10: Exposed Screening Score MVP through `POST /screening/score` with deterministic API coverage for ranked score breakdowns. / `POST /screening/score` で Screening Score MVP を公開し、ranking と score breakdown の deterministic API テストを追加した。
- 2026-05-10: Added Streamlit Screening Score JSON / CSV downloads so ranking, sub-scores, and reasons can be saved from the UI. / Streamlit Screening Score に JSON / CSV download を追加し、ranking、sub score、理由を UI から保存できるようにした。
- 2026-05-10: Added beginner-friendly Screening Score summaries and Japanese reason labels to the service, API, Streamlit preview, and JSON / CSV exports. / Screening Score の summary と日本語 reason label を初心者向けに追加し、service、API、Streamlit preview、JSON / CSV export で確認できるようにした。
- 2026-05-10: Changed the Streamlit Market Data Screening Score preview to score only the input symbol, while keeping multi-symbol ranking available through `POST /screening/score`. / Streamlit Market Data の Screening Score preview は入力銘柄だけを score 表示するように変更し、複数銘柄 ranking は `POST /screening/score` 側に残した。
- 2026-05-10: Documented that multi-symbol ranking UI should be designed in the beginner-friendly UI phase instead of the current Market Data preview. / 複数銘柄 ranking UI は現在の Market Data preview ではなく、初心者向け UI phase で設計する方針として文書化した。
- 2026-05-10: Started Forecast Lab Baseline by adding deterministic naive, moving-average, and momentum forecast models with walk-forward MAE, RMSE, and direction-accuracy metrics. / deterministic な naive、moving-average、momentum forecast model と walk-forward の MAE、RMSE、direction accuracy metrics を追加して Forecast Lab Baseline に着手した。
- 2026-05-10: Added Streamlit Market Data chart rows for selected-symbol close prices, baseline forecast lines, and model-level forecast metrics. / Streamlit Market Data に、選択銘柄の終値 chart、baseline forecast line、model 別 forecast metrics を表示する行を追加した。
- 2026-05-10: Improved the Forecast chart UI by rendering actual closes as solid lines and forecast models as dashed lines, added Market Data provider selection, and made recent mock OHLCV rows less linear. / Forecast chart UI を改善し、実績終値を実線、forecast model を破線で表示するようにした。Market Data provider 選択を追加し、直近 mock OHLCV 行を単調すぎない系列にした。
- 2026-05-10: Made Yahoo live-provider failures easier to diagnose in the Streamlit Market Data tab by showing the error code, message, and JSON details immediately after a failed fetch. / Yahoo live-provider の取得失敗を Streamlit Market Data tab で診断しやすくするため、失敗直後に error code、message、JSON details を表示するようにした。
- 2026-05-10: Added `POST /forecast/evaluate` for deterministic baseline forecast evaluations and aligned local Ruff checks with `backend ui tests`. / deterministic な baseline forecast evaluation を返す `POST /forecast/evaluate` を追加し、local Ruff check の対象を `backend ui tests` に揃えた。
- 2026-05-10: Added Streamlit forecast horizon selection for 1-30 days, aligned chart forecast dates and walk-forward metrics with the selected horizon, and documented the UI workflow. / Streamlit で forecast horizon を 1〜30 日から選べるようにし、chart の予測日付と walk-forward metrics を選択 horizon に合わせ、UI workflow を文書化した。
- 2026-05-10: Added a dedicated roadmap phase for beginner-friendly UI design, including watchlists, symbol search, Japanese score explanations, comparison flows, and UI verification criteria. / watchlist、銘柄検索、日本語の score 説明、比較 flow、UI 確認観点を含む初心者向け UI design の専用 roadmap phase を追加した。
- 2026-05-10: Added a dedicated roadmap phase for a low-cost AI assistant experience that starts with deterministic rule-based explanations and leaves optional LLM adapters for later. / deterministic な rule-based 説明から始め、optional LLM adapter は後から差し替えられる形にする低コスト AI assistant 体験の専用 roadmap phase を追加した。
- 2026-05-10: Adjusted the Streamlit Forecast chart so clicking a price/model legend item greys out only that legend item and its matching series, clicking it again restores it, and the chart body is about 1.5x taller for easier inspection. / Streamlit Forecast chart で価格・モデル凡例をクリックしたとき、その凡例項目と対応する系列だけを薄くし、再クリックで戻るように調整し、チャート本体を約 1.5 倍の高さにして確認しやすくした。
- 2026-05-10: Changed the Forecast chart legend selection to support multiple inactive price/model series at the same time instead of reactivating the previously inactive series when another legend item is clicked. / Forecast chart の凡例選択を、別の凡例項目をクリックしても以前の非活性系列が勝手に戻らず、複数の価格・モデル系列を同時に非活性にできる挙動へ変更した。
- 2026-05-10: Consolidated the Streamlit Market Data symbol picker from separate search and candidate widgets into one searchable `Symbol` dropdown, keeping adjacent company-name display for the selected candidate. / Streamlit Market Data の symbol picker を search と candidate の2要素から、検索可能な1つの `Symbol` プルダウンへ統合し、選択候補の会社名表示は横に残した。
- 2026-05-10: Improved Forecast chart readability by changing successful Market Data fetch feedback to a transient toast, reducing persistent explanatory banners, grouping forecast controls with the chart header, and applying explicit dark chart / legend styling. / Market Data 取得成功の表示を一時的な toast に変更し、常設の説明帯を減らし、予測期間コントロールをチャート見出し付近へ整理し、チャートと凡例に明示的なダーク背景スタイルを適用して Forecast chart の視認性を改善した。
- 2026-05-10: Moved the Forecast chart legend into a right-side panel with explicit dark styling, kept the main chart responsive, and included a compact actual/forecast line-style legend in the same panel. / Forecast chart の凡例を右側パネルへ移動し、明示的なダーク背景スタイルを付け、チャート本体は横幅に追従するよう維持し、実績/予測の線種凡例も同じパネル内にまとめた。
- 2026-05-10: Changed the Streamlit Market Data provider UI default to `yahoo` and made `Symbol` a free text input again while keeping partial-match candidate completion as an optional helper. / Streamlit Market Data の provider UI 既定値を `yahoo` に変更し、`Symbol` は候補にない ticker も指定できる自由入力へ戻しつつ、部分一致する候補補完を補助として残した。
- 2026-05-10: Reverted the Streamlit Market Data `Symbol` control from free text plus matching candidates back to the single searchable candidate dropdown, while keeping the `yahoo` provider UI default. / Streamlit Market Data の `Symbol` control を自由入力 + 候補補完から、検索可能な単一候補プルダウンへ戻し、provider UI 既定値 `yahoo` は維持した。
- 2026-05-10: Expanded representative Streamlit Market Data symbol candidates across Japanese and US equities / ETFs, and added optional yfinance `Search` completion for the user's `Symbol search` query with deterministic fallback to representative candidates. / Streamlit Market Data の代表 symbol 候補を日本株・米国株・ETF で拡充し、ユーザーの `Symbol search` 入力に対して任意の yfinance `Search` 補完を追加しつつ、失敗時は代表候補だけで動く deterministic fallback を維持した。
- 2026-05-10: Added currency-aware y-axis labeling to the Forecast chart and tightened the chart / legend widths so the right-side legend remains visible within the Streamlit page. / Forecast chart の縦軸に通貨を含む価格ラベルを追加し、右側凡例が Streamlit 画面内に収まりやすいようチャート本体と凡例の横幅を調整した。

## 2026-05-15

- `Documents/future_roadmap/` の将来構想を、`Documents/05_Implementation_Roadmap.md` に実装可能な粒度の Future Implementation Candidates として追記。
- Chat AI Assistant MVP、News & Sentiment Intelligence MVP、Assistant x News Integration を、Goal / Scope / Non-goals / Implementation slices / Acceptance criteria の形に整理。
- LLM 活用を Optional LLM Adapter と LLM-assisted Report Generation に分離し、deterministic/local-first を維持した実装順として `Documents/05_Implementation_Roadmap.md` に追記。
- Forecast Metrics の JSON / CSV download helper と Streamlit Market Data tab の download button を追加し、Phase 13 の forecast result export を完了扱いに更新。
- Phase 14 の入口として、複数 forecast model の median forecast、予測レンジ、model agreement を計算する Forecast Summary を追加し、Streamlit Market Data tab で確認できるようにした。
- Forecast Model Registry Lite を追加し、API / UI の forecast model 選択と表示ラベルを registry 経由に寄せた。
- Streamlit Market Data tab の各結果 section で、見出しとは別に評価中の symbol / 銘柄名を小さく表示するようにした。
- Forecast Summary に複数 baseline model の平均予測である ensemble forecast を追加した。
- Forecast Summary の model agreement を Screening Score の forecast_score / forecast_reason として接続し、Phase 14 の scoring 接続を完了扱いにした。

## 2026-05-16

- Phase 14 を implementation complete として整理し、Phase 15 の最初の実装スライスを `backend/scoring` の Investment Score contract と deterministic tests に定義した。
