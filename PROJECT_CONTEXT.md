# PROJECT_CONTEXT.md

## Overview / 概要

This document captures the current repository state so future work can start from a shared understanding instead of rediscovering context each time.
この文書は、毎回コンテキストを掘り直さなくても将来の作業を共通認識から始められるように、現在のリポジトリ状況を記録するものです。

Last updated: 2026-05-08
最終更新日: 2026-05-08

## Project Summary / プロジェクト概要

Smart Market AI is a Python backend project for investment-support workflows.
Smart Market AI は、投資支援ワークフロー向けの Python バックエンドプロジェクトです。

The current codebase provides:
現在のコードベースには以下が含まれます。

- a minimal FastAPI app / 最小構成の FastAPI アプリ
- shared domain contracts and configuration models / 共通ドメイン契約と設定モデル
- a deterministic MarketData MVP based on mock and csv providers / mock provider と csv provider ベースの再現性ある MarketData MVP
- tests for core models, config, errors, marketdata, portfolio, API health, Risk API, and Portfolio API / core モデル、config、errors、marketdata、portfolio、API health、Risk API、Portfolio API のテスト
- Swagger/OpenAPI metadata plus consolidated MVP operations notes / Swagger/OpenAPI メタデータと統合済み MVP 運用メモ
- deterministic manual workflow guide and example request for Portfolio-to-Risk checks / Portfolio-to-Risk チェック向けの決定的な手動確認ガイドとサンプル request
- local sample CSV market-data files under `data/marketdata` / `data/marketdata` 配下のローカル CSV market-data サンプル
- minimal Streamlit UI for the Portfolio-to-Risk workflow / Portfolio-to-Risk workflow 向けの最小 Streamlit UI
- Streamlit Market Data preview tab for provider metadata and deterministic market-data checks / provider metadata と deterministic market-data 確認向けの Streamlit Market Data preview tab
- file-backed deterministic rebalance scenarios under `examples/rebalance_scenarios` / `examples/rebalance_scenarios` 配下の file-backed deterministic rebalance scenario
- local JSON/CSV/Markdown/manifest/ZIP reporting exports for rebalance-check results / rebalance-check 結果向けのローカル JSON/CSV/Markdown/manifest/ZIP reporting export
- external market-data provider preparation with explicit opt-in gates / 明示 opt-in gate を持つ外部 market-data provider 準備
- next roadmap for Multi-Model Investment Intelligence / Multi-Model Investment Intelligence の次期ロードマップ

The implementation is still MVP-oriented. Risk, Portfolio, API, Streamlit UI, local reporting exports, and external-provider preparation are implemented for deterministic MVP use; the next focus is Multi-Model Investment Intelligence, while live broker execution remains lower priority.
実装はまだ MVP 指向です。Risk、Portfolio、API、Streamlit UI、ローカル reporting export、external-provider preparation は deterministic MVP 用に実装済みで、次の重点は Multi-Model Investment Intelligence です。live broker execution は優先度を下げています。

## Repository Layout / リポジトリ構成

- `backend/app/main.py`
  FastAPI entrypoint with `/health` / `/health` を持つ FastAPI のエントリポイント
- `backend/core/`
  shared Pydantic models, config models, and error types / 共通 Pydantic モデル、設定モデル、エラー型
- `backend/marketdata/`
  mock data access and feature building / mock データアクセスと特徴量構築
- `tests/`
  pytest coverage for current MVP behavior / 現在の MVP 挙動を対象にした pytest
- `Documents/`
  requirements, design, detail design, checklist, and roadmap / 要件、設計、詳細設計、チェックリスト、ロードマップ
- `setup/`
  local setup notes and requirements files / ローカルセットアップ資料と requirements 群

## Current Implementation Status / 現在の実装状況

## Implemented / 実装済み

- FastAPI application bootstrap / FastAPI アプリ起動基盤
- `/health` endpoint / `/health` エンドポイント
- strict domain contracts in `backend/core/data_contracts.py` / `backend/core/data_contracts.py` の厳格なドメイン契約
- strict settings models in `backend/core/config.py` / `backend/core/config.py` の厳格な設定モデル
- core error classes in `backend/core/errors.py` / `backend/core/errors.py` の基底エラー群
- MarketData `DataAccess` with deterministic `mock` and `csv` providers / deterministic な `mock` / `csv` provider 対応の MarketData `DataAccess`
- `FeatureBuilder` for ADV, volatility, and daily snapshot generation / ADV、ボラティリティ、日次スナップショットを生成する `FeatureBuilder`
- Risk `RiskService` and `POST /risk/pre-trade-check` API endpoint / Risk `RiskService` と `POST /risk/pre-trade-check` API エンドポイント
- Portfolio `PortfolioService` for deterministic snapshots and no-solver rebalance proposals / deterministic なスナップショットと solver なしのリバランス提案を行う Portfolio `PortfolioService`
- Portfolio-to-Risk workflow and `POST /portfolio/rebalance-check` API endpoint / Portfolio-to-Risk workflow と `POST /portfolio/rebalance-check` API エンドポイント
- Swagger UI / OpenAPI specification metadata for current MVP endpoints / 現在の MVP エンドポイント向け Swagger UI / OpenAPI 仕様メタデータ
- Manual workflow example for `POST /portfolio/rebalance-check` / `POST /portfolio/rebalance-check` の手動確認 example
- CSV provider sample config and data files for local smoke checks / ローカル smoke check 用の CSV provider 設定例とデータファイル
- Streamlit UI entrypoint at `ui/app.py` / `ui/app.py` の Streamlit UI エントリポイント
- Streamlit Market Data preview tab for provider metadata, quotes, OHLCV summary, FX, and provider errors / provider metadata、quotes、OHLCV summary、FX、provider error を表示する Streamlit Market Data preview tab
- `examples/rebalance_scenarios/`
  file-backed rebalance-check UI samples / file-backed rebalance-check UI sample
- pytest suite for current MVP modules / 現在の MVP モジュールを対象とした pytest 群

## Not Yet Implemented Or Partial / 未実装または部分実装

- non-local market data providers such as `yahoo` / `yahoo` などの非ローカル市場データプロバイダ
- `.env` driven settings loading beyond `SMAI_CONFIG_FILE` / `SMAI_CONFIG_FILE` 以外の `.env` ベース設定読み込み
- `backend/execution/`
- `backend/screening/`
- `backend/forecast/`
- `backend/scoring/`
- broader UI workflows beyond the initial Streamlit rebalance-check screen / 初期 Streamlit rebalance-check 画面以外の UI workflow
- advanced reporting beyond local JSON/CSV/Markdown/ZIP exports / ローカル JSON/CSV/Markdown/ZIP export を超える高度な reporting

## Behavioral Notes / 挙動メモ

- `DataAccess` currently supports deterministic `mock` and `csv` providers, and rejects live providers such as `yahoo`.
  `DataAccess` は現在 deterministic な `mock` / `csv` provider に対応し、`yahoo` などの live provider は拒否します。
- Rejected live providers return a `DataSourceError` that names supported providers and marks live-provider support as a future explicit opt-in path.
  拒否された live provider は、対応済み provider と live provider が将来の明示 opt-in 経路であることを示す `DataSourceError` を返します。
- Live providers require `dataaccess.allow_external_providers: true` before reaching future implementation paths, and remain unimplemented for now.
  live provider は将来の実装経路へ進む前に `dataaccess.allow_external_providers: true` を必要とし、現時点ではまだ未実装です。
- Market-data provider capabilities are centralized in `backend/marketdata/provider_registry.py`.
  market-data provider の capability は `backend/marketdata/provider_registry.py` に集約しています。
- Planned live-provider adapter metadata is centralized in `backend/marketdata/live_provider_adapters.py`.
  将来の live provider adapter metadata は `backend/marketdata/live_provider_adapters.py` に集約しています。
- Market-data provider adapters share the `MarketDataProviderAdapter` protocol in `backend/marketdata/provider_adapters.py`.
  market-data provider adapter は `backend/marketdata/provider_adapters.py` の `MarketDataProviderAdapter` protocol を共通契約にします。
- Configured market-data provider adapters can be created through `backend/marketdata/provider_factory.py`.
  設定済み market-data provider adapter は `backend/marketdata/provider_factory.py` から作成できます。
- Future live-provider failures can use dedicated domain errors for rate limits, provider unavailability, provider timeouts, and schema mismatches.
  将来の live provider 失敗は、rate limit、provider unavailable、provider timeout、schema mismatch 向けの専用ドメインエラーで表現できます。
- API metadata and tests cover structured provider failure responses for opt-in rejection, provider unavailability, and provider timeouts.
  API metadata とテストは、opt-in 拒否、provider unavailable、provider timeout の構造化 provider 失敗レスポンスをカバーしています。
- API tests also cover structured rate-limit and schema-mismatch provider failure responses.
  API テストは、rate limit と schema mismatch の構造化 provider 失敗レスポンスもカバーしています。
- API, CSV, manual workflow, UI, and external provider notes are consolidated in `Documents/06_MVP_Operations_Guide.md`.
  API、CSV、manual workflow、UI、external provider の説明は `Documents/06_MVP_Operations_Guide.md` に統合しています。
- Market data is deterministic and in-repo, which keeps tests offline and stable.
  市場データはリポジトリ内の固定データで、テストをオフラインかつ安定して実行できます。
- The `csv` provider reads local `symbols.csv`, `ohlcv.csv`, and `fx_rates.csv` files from `dataaccess.csv_data_dir`.
  `csv` provider は `dataaccess.csv_data_dir` 配下の `symbols.csv`、`ohlcv.csv`、`fx_rates.csv` を読み込みます。
- `FeatureBuilder.build_daily_snapshot()` currently leaves `dividend_yield` and `market_cap_jpy` as missing values.
  `FeatureBuilder.build_daily_snapshot()` は現在 `dividend_yield` と `market_cap_jpy` を欠損値扱いにしています。
- `get_settings()` returns defaults unless `SMAI_CONFIG_FILE` points to a YAML config file.
  `get_settings()` は `SMAI_CONFIG_FILE` が YAML 設定ファイルを指す場合のみ外部設定を読み込み、それ以外はデフォルトを返します。

## Likely Current Phase / 現在フェーズの見立て

Based on code and roadmap documents, the project is effectively here:
コードとロードマップ資料から見ると、プロジェクトは実質的に次の段階にあります。

- Phase 1 Core Foundation: complete for MVP / Phase 1 Core Foundation: MVP として完了
- Phase 2 MarketData MVP: complete for MVP / Phase 2 MarketData MVP: MVP として完了
- Phase 3 Risk MVP: initial service and API complete for MVP / Phase 3 Risk MVP: 初期サービスと API は MVP として完了
- Phase 4 Portfolio MVP: initial service complete for MVP / Phase 4 Portfolio MVP: 初期サービスは MVP として完了
- Phase 5 API and UI Integration: complete for the current Portfolio-to-Risk MVP / Phase 5 API and UI Integration: 現在の Portfolio-to-Risk MVP として完了
- Phase 6 CSV Data And Scenario Expansion: implemented for current local examples / Phase 6 CSV Data And Scenario Expansion: 現在のローカル example 向けに実装済み
- Phase 7 Config And Scenario Management: implemented for file-backed rebalance scenarios / Phase 7 Config And Scenario Management: file-backed rebalance scenario 向けに実装済み
- Phase 8 Reporting MVP: complete for JSON/CSV/Markdown/manifest/ZIP exports / Phase 8 Reporting MVP: JSON/CSV/Markdown/manifest/ZIP export として完了
- Phase 9 External Data Provider Preparation: complete before live adapter implementation / Phase 9 External Data Provider Preparation: live adapter 実装前の準備として完了
- Phase 10 External Data Ingestion MVP: started with planned live-provider adapter metadata, a shared `MarketDataProviderAdapter` protocol, a provider adapter factory, a Streamlit Market Data preview tab, and a `yahoo` opt-in stub; completion target still requires live-provider data retrieval. / Phase 10 External Data Ingestion MVP: planned live-provider adapter metadata、共通 `MarketDataProviderAdapter` protocol、provider adapter factory、Streamlit Market Data preview tab、`yahoo` opt-in stub から着手。完了にはまだ live-provider data retrieval が必要。
- Next recommended work: continue External Data Ingestion MVP by expanding the `yahoo` stub into a real data retrieval adapter, then verify provider data/status in the Streamlit UI before moving to Feature Store Lite. / 次の推奨作業: `yahoo` stub を実データ取得 adapter へ拡張し、その後 Feature Store Lite へ進む前に provider data / status を Streamlit UI で確認する。

## Test And Verification Baseline / テストと確認の基準

Known useful commands:
現時点で有用な確認コマンドです。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend tests --no-cache
```

These commands are also referenced by the roadmap document.
これらのコマンドはロードマップ文書と MVP 運用ガイドでも参照されています。

## Known Documentation Mismatches / 既知のドキュメント差分

- Some design documents describe future modules that do not yet exist in code.
  一部の設計資料には、まだコード上に存在しない将来モジュールが記載されています。
- `README.md` content appears to have encoding/display issues in the current environment, so it should not be treated as the cleanest operational summary until reviewed.
  `README.md` はこの環境で文字コードまたは表示上の問題が見えるため、見直し完了までは運用上の主要サマリとして扱わないほうが安全です。

## Working Assumptions / 現在の作業前提

- The project currently values deterministic local development over external API integration.
  現在のプロジェクトは、外部 API 統合よりもローカルで再現可能な開発を優先しています。
- New work should preserve the current package structure unless there is a strong reason to change it.
  強い理由がない限り、新しい作業でも現行のパッケージ構成を維持します。
- When adding new capabilities, prefer following the roadmap sequence: core -> marketdata -> risk -> portfolio -> API/UI integration.
  新機能追加時は、基本的に `core -> marketdata -> risk -> portfolio -> API/UI integration` の順序に沿います。

## Next Good Targets / 次の着手候補

- start External Data Ingestion MVP with explicit opt-in live provider behavior
  明示 opt-in の live provider 挙動を持つ External Data Ingestion MVP に着手する
- define Feature Store Lite contracts for screening and forecast reuse
  screening と forecast で再利用する Feature Store Lite の契約を定義する
- add Screening Score MVP with explainable score breakdowns
  説明可能な score breakdown を持つ Screening Score MVP を追加する
- add Forecast Lab Baseline before heavier research model adapters
  重い research model adapter の前に Forecast Lab Baseline を追加する
- expand environment-variable settings support beyond `SMAI_CONFIG_FILE`
  `SMAI_CONFIG_FILE` 以外の環境変数ベース設定対応を拡張する
- expand csv market data coverage and document production-like file conventions
  csv 市場データのカバレッジを広げ、本番に近いファイル規約を文書化する
- keep documentation status summaries aligned after phase transitions
  phase 移行後もドキュメントの進捗サマリを揃える

## Maintenance Rule / 更新ルール

Update this file when:
次のような変更があったらこのファイルを更新します。

- a new top-level module is added / 新しい上位モジュールが追加されたとき
- the active roadmap phase changes / 現在のロードマップ段階が変わったとき
- verification commands change / 確認コマンドが変わったとき
- a notable mismatch between docs and code is discovered / ドキュメントとコードの目立つ差異を発見したとき

## Work Log / 作業ログ

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

- 2026-05-07: Added Black exclude settings for local virtualenv and cache directories so `black --check .` does not scan `venv_SMAI`. / `black --check .` が `venv_SMAI` を走査しないよう、ローカル仮想環境と cache ディレクトリの Black 除外設定を追加。

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
