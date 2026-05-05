# PROJECT_CONTEXT.md

## Overview / 概要

This document captures the current repository state so future work can start from a shared understanding instead of rediscovering context each time.
この文書は、毎回コンテキストを掘り直さなくても将来の作業を共通認識から始められるように、現在のリポジトリ状況を記録するものです。

Last updated: 2026-05-05
最終更新日: 2026-05-05

## Project Summary / プロジェクト概要

Smart Market AI is a Python backend project for investment-support workflows.
Smart Market AI は、投資支援ワークフロー向けの Python バックエンドプロジェクトです。

The current codebase provides:
現在のコードベースには以下が含まれます。

- a minimal FastAPI app / 最小構成の FastAPI アプリ
- shared domain contracts and configuration models / 共通ドメイン契約と設定モデル
- a deterministic MarketData MVP based on mock and csv providers / mock provider と csv provider ベースの再現性ある MarketData MVP
- tests for core models, config, errors, marketdata, portfolio, API health, Risk API, and Portfolio API / core モデル、config、errors、marketdata、portfolio、API health、Risk API、Portfolio API のテスト
- Swagger/OpenAPI metadata and Japanese API specification notes / Swagger/OpenAPI メタデータと日本語 API 仕様メモ
- deterministic manual workflow docs and example request for Portfolio-to-Risk checks / Portfolio-to-Risk チェック向けの決定的な手動確認手順とサンプル request
- local sample CSV market-data files under `data/marketdata` / `data/marketdata` 配下のローカル CSV market-data サンプル
- minimal Streamlit UI for the Portfolio-to-Risk workflow / Portfolio-to-Risk workflow 向けの最小 Streamlit UI

The implementation is still MVP-oriented and pre-integration. Risk has a minimal service and API endpoint, Portfolio has a minimal service, and external providers, UI, and execution flows are mostly planned rather than fully built.
実装はまだ統合前段階であり、外部プロバイダ、UI、risk、portfolio、execution の各フローは多くが計画段階です。

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
- pytest suite for current MVP modules / 現在の MVP モジュールを対象とした pytest 群

## Not Yet Implemented Or Partial / 未実装または部分実装

- non-local market data providers such as `yahoo` / `yahoo` などの非ローカル市場データプロバイダ
- `.env` driven settings loading beyond `SMAI_CONFIG_FILE` / `SMAI_CONFIG_FILE` 以外の `.env` ベース設定読み込み
- `backend/execution/`
- broader UI workflows beyond the initial Streamlit rebalance-check screen / 初期 Streamlit rebalance-check 画面以外の UI workflow
- report/export pipelines / レポート・出力パイプライン

## Behavioral Notes / 挙動メモ

- `DataAccess` currently supports deterministic `mock` and `csv` providers, and rejects live providers such as `yahoo`.
  `DataAccess` は現在 deterministic な `mock` / `csv` provider に対応し、`yahoo` などの live provider は拒否します。
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
- Phase 5 API and UI Integration: started with Portfolio-to-Risk API exposure / Phase 5 API and UI Integration: Portfolio-to-Risk API 公開から着手済み
- Next recommended work: expand the UI workflow or add richer CSV data conventions / 次の推奨作業: UI workflow の拡張、または CSV データ規約の拡張

## Test And Verification Baseline / テストと確認の基準

Known useful commands:
現時点で有用な確認コマンドです。

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend tests --no-cache
```

These commands are also referenced by the roadmap document.
これらのコマンドはロードマップ文書でも参照されています。

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

- add a local UI or manual workflow entry point for the rebalance-check flow
  rebalance-check フロー向けのローカル UI または手動確認用入口を追加する
- expand environment-variable settings support beyond `SMAI_CONFIG_FILE`
  `SMAI_CONFIG_FILE` 以外の環境変数ベース設定対応を拡張する
- expand csv market data coverage and document production-like file conventions
  csv 市場データのカバレッジを広げ、本番に近いファイル規約を文書化する
- improve documentation consistency, especially README encoding and status summaries
  特に README の文字化け問題や進捗サマリの整合性を改善する

## Maintenance Rule / 更新ルール

Update this file when:
次のような変更があったらこのファイルを更新します。

- a new top-level module is added / 新しい上位モジュールが追加されたとき
- the active roadmap phase changes / 現在のロードマップ段階が変わったとき
- verification commands change / 確認コマンドが変わったとき
- a notable mismatch between docs and code is discovered / ドキュメントとコードの目立つ差異を発見したとき

## Work Log / 作業ログ

- 2026-05-05: Checked recent Streamlit UI changes against design documents and synchronized the roadmap, UI guide, and contributor documentation policy. / 最近の Streamlit UI 変更を設計ドキュメントと照合し、roadmap、UI guide、contributor 向けドキュメント方針を同期。

- 2026-05-05: Added deterministic Streamlit rebalance sample selection with default and no-trades scenarios. / Streamlit の rebalance 入力に default と no-trades の決定的なサンプル切り替えを追加。

- 2026-05-05: Added Streamlit UI runtime settings display, shared default request helpers, and deterministic UI helper tests. / Streamlit UI に実行時設定表示、共通デフォルト request helper、決定的な UI helper テストを追加。

- 2026-05-05: Verified repository Markdown files are valid UTF-8 without BOM and documented the encoding check rule in `AGENTS.md`. / リポジトリ内 Markdown が UTF-8 without BOM として正常であることを確認し、文字コード確認ルールを `AGENTS.md` に追記。

- 2026-05-05: Aligned the Streamlit UI helper test expectations with current Risk MVP breach rules and fixed import ordering. / Streamlit UI helper テストの期待値を現在の Risk MVP 違反ルールに合わせ、import 順を修正。

- 2026-05-05: Exposed the Portfolio-to-Risk workflow through `POST /portfolio/rebalance-check` and added deterministic API tests. / `POST /portfolio/rebalance-check` で Portfolio-to-Risk workflow を公開し、決定的な API テストを追加。
- 2026-05-05: Improved Swagger/OpenAPI metadata and added Japanese API specification notes in `Documents/07_API_Specification.md`. / Swagger/OpenAPI メタデータを整備し、`Documents/07_API_Specification.md` に日本語 API 仕様メモを追加。
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
