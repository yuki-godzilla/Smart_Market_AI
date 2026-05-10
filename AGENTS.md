# AGENTS.md

## Purpose / 目的

This file is the shared operating guide for contributors and coding agents working in this repository.
このファイルは、このリポジトリで作業する開発者およびコーディングエージェント向けの共通運用ガイドです。

Use it together with `PROJECT_CONTEXT.md`:
`PROJECT_CONTEXT.md` とあわせて利用します。

- `AGENTS.md`: how we work / 作業の進め方
- `PROJECT_CONTEXT.md`: what the project currently looks like / プロジェクトの現在地

## Project Goal / プロジェクト目標

Smart Market AI is a Python-based investment support project centered on:
Smart Market AI は、以下を中核とする Python ベースの投資支援プロジェクトです。

- FastAPI backend services / FastAPI ベースのバックエンド
- market data ingestion and feature building / マーケットデータ取得と特徴量生成
- future risk, portfolio, execution, and UI layers / 将来的なリスク、ポートフォリオ、執行、UI レイヤ

The current implementation is still MVP-oriented. The default path and automated checks intentionally remain deterministic and local, while external market-data providers are supported only through explicit opt-in adapters such as `yahoo`.
現在の実装はまだ MVP 指向です。既定経路と自動検証はローカルで再現性の高い挙動を維持しつつ、外部 market-data provider は `yahoo` などの明示 opt-in adapter 経由でのみ利用します。

## Working Principles / 作業原則

1. Preserve the project direction documented in `Documents/`.
   `Documents/` に記載されたプロジェクト方針を尊重すること。
2. Prefer small, verifiable changes over broad speculative refactors.
   広範囲な推測ベースのリファクタより、小さく検証可能な変更を優先すること。
3. Keep the backend import graph clean and explicit.
   バックエンドの import 関係は明示的で分かりやすく保つこと。
4. Avoid introducing network-dependent behavior into the MVP path unless the task specifically requires it.
   明示的に必要な作業でない限り、MVP の主要経路にネットワーク依存を持ち込まないこと。
5. Update `PROJECT_CONTEXT.md` when the implementation status or working assumptions materially change.
   実装状況や前提条件が大きく変わったら `PROJECT_CONTEXT.md` を更新すること。
6. Before applying code or document changes, present the expected diff for review and then make the change.
   コードやドキュメントを変更する前に、想定差分を提示してレビューしたうえで変更すること。
7. Append a work-log entry to `PROJECT_CONTEXT.md` for each unit of work.
   作業単位ごとに `PROJECT_CONTEXT.md` へ作業ログを追記すること。
8. After each implementation task, explain the result in beginner-friendly language.
   各実装作業の完了後は、初学者にも分かる言葉で結果を説明すること。
   Include what changed, why it changed, how to use it, and how it was verified.
   変更内容、変更理由、使い方、検証結果を含めること。
   Also suggest an appropriate commit message for the completed work.
   完了した作業に適したコミットメッセージも提案すること。
   When introducing a new concept or technology, briefly explain what role it plays.
   新しい概念や技術を導入した場合は、その役割も短く説明すること。
9. Treat diff review and verification as checkpoints, not as automatic stopping points.
   差分確認と検証はチェックポイントであり、自動的な停止地点ではありません。
   When the user has already approved the implementation direction, continue to the next logical small task after reporting the checkpoint unless a new decision or risk needs user review.
   ユーザーが実装方針を承認済みの場合、チェックポイントを報告した後も、新しい判断やリスク確認が必要でない限り、次の自然な小タスクへ進みます。
10. For roadmap phases that affect user-visible UI behavior, include UI-level confirmation in the phase completion criteria.
    UI 上で見える挙動に影響するロードマップフェーズでは、フェーズ完了条件に UI 上で変更を確認できることを含めます。
    For external-provider features, prefer confirmation with live provider data when available, while keeping deterministic local checks independent from external APIs.
    外部 provider に関する機能では、利用可能であれば live provider の生きたデータで確認することを優先しつつ、通常の local checks は外部 API に依存させません。

## Current Development Focus / 現在の開発フォーカス

The repository appears to be at:
現時点のリポジトリの状態は次の通りです。

- Core contracts/config/errors: implemented / Core の契約・設定・エラーは実装済み
- MarketData MVP: implemented with deterministic `mock` and `csv` providers / MarketData MVP は deterministic な `mock` / `csv` プロバイダで実装済み
- Yahoo MarketData live adapter: implemented as explicit opt-in through `create_market_data_provider_adapter()`; not the default path / Yahoo MarketData live adapter は `create_market_data_provider_adapter()` 経由の明示 opt-in として実装済みで、既定経路ではありません
- Feature Store Lite: started with reusable `FeatureSnapshot` rows and Streamlit preview for return, momentum, volatility, drawdown, ADV, data completeness, dividend yield, market cap, missing metadata, and data-quality judgement / Feature Store Lite は再利用可能な `FeatureSnapshot` 行と、return、momentum、volatility、drawdown、ADV、data completeness、dividend yield、market cap、missing metadata、data-quality judgement の Streamlit preview から着手済み
- Screening Score MVP: started with explainable score breakdown rows in the Streamlit Market Data preview and `POST /screening/score` / Screening Score MVP は Streamlit Market Data preview の説明可能な score breakdown 行と `POST /screening/score` から着手済み
- API bootstrap: implemented with `/health`, `POST /risk/pre-trade-check`, and `POST /portfolio/rebalance-check` / API の起点は `/health`、`POST /risk/pre-trade-check`、`POST /portfolio/rebalance-check` 付きで実装済み
- Portfolio-to-Risk workflow: implemented and exposed through FastAPI / Portfolio-to-Risk workflow は実装済みで FastAPI から公開済み
- Swagger/OpenAPI metadata and YAML settings loading via `SMAI_CONFIG_FILE`: implemented / Swagger/OpenAPI メタデータと `SMAI_CONFIG_FILE` による YAML 設定読み込みは実装済み
- Streamlit rebalance UI, file-backed scenarios, and local report exports: implemented for MVP / Streamlit rebalance UI、file-backed scenarios、local report exports は MVP として実装済み
- External MarketData provider preparation: implemented through explicit opt-in gates, provider registry, documented failure modes, and the initial `yahoo` live adapter / External MarketData provider preparation は明示 opt-in gate、provider registry、failure mode 文書化、初期 `yahoo` live adapter まで実装済み
- Additional live market-data provider adapters such as `polygon`, and Execution workflows: not implemented / `polygon` など追加 live market-data provider adapter と Execution workflow は未実装
- Next roadmap focus: Multi-Model Investment Intelligence, including external data ingestion, Feature Store Lite, screening scores, multi-model forecasts, visualization, decision reports, beginner-friendly UI design, and low-cost AI assistant experiences / 次期ロードマップの重点は Multi-Model Investment Intelligence で、外部データ取得、Feature Store Lite、screening score、multi-model forecast、可視化、decision report、初心者向け UI design、低コスト AI assistant 体験を含みます
- Execution and broker order sending are lower priority unless the user explicitly requests them / Execution と broker order 送信は、ユーザーが明示的に依頼しない限り優先度を下げます

Unless a task says otherwise, optimize changes for this progression.
特別な指示がない限り、この進行順を前提に変更を最適化します。

## Source Of Truth / 判断の優先順位

When deciding what to build next, consult these in order:
次に何を作るか判断する際は、次の順で参照します。

1. User request / ユーザー要求
2. Actual code in `backend/` and `tests/` / `backend/` と `tests/` の実コード
3. `PROJECT_CONTEXT.md`
4. `Documents/05_Implementation_Roadmap.md`
5. Other design docs under `Documents/` / `Documents/` 配下のその他設計資料

If docs and code disagree, trust the code for current behavior and record the mismatch in `PROJECT_CONTEXT.md`.
ドキュメントとコードに差異がある場合、現在の挙動についてはコードを優先し、その差分を `PROJECT_CONTEXT.md` に記録します。

## Repository Conventions / リポジトリ規約

## Python / Python 実装

- Keep code simple and typed.
  コードはシンプルに保ち、型を活用すること。
- Follow existing Pydantic v2 patterns.
  既存の Pydantic v2 パターンに従うこと。
- Reuse domain contracts from `backend/core/data_contracts.py`.
  ドメイン契約は `backend/core/data_contracts.py` を再利用すること。
- Reuse settings models from `backend/core/config.py`.
  設定モデルは `backend/core/config.py` を再利用すること。
- Raise domain-specific errors from `backend/core/errors.py` where appropriate.
  適切な箇所では `backend/core/errors.py` のドメインエラーを使うこと。

## Architecture / アーキテクチャ

- `backend/app`: FastAPI entrypoints and application wiring / FastAPI のエントリポイントとアプリ配線
- `backend/core`: shared contracts, config, and base errors / 共通契約、設定、基底エラー
- `backend/marketdata`: market data access and feature construction / マーケットデータ取得と特徴量構築
- future modules should follow the roadmap names where practical: `backend/risk`, `backend/portfolio`, `backend/screening`, `backend/forecast`, `backend/scoring`, `backend/execution`
  今後のモジュールは、可能な範囲でロードマップ上の命名 `backend/risk`、`backend/portfolio`、`backend/screening`、`backend/forecast`、`backend/scoring`、`backend/execution` に合わせます。

## Tests / テスト

- Add or update tests for behavior changes whenever practical.
  振る舞いを変える場合は、可能な限りテストを追加または更新します。
- Prefer deterministic tests that do not rely on external APIs.
  外部 API に依存しない再現性の高いテストを優先します。
- Keep MVP tests aligned with the mock-provider approach.
  MVP のテストは mock provider 前提に揃えます。

## Commands / 確認コマンド

Use the project virtual environment when available.
利用可能であれば、プロジェクトの仮想環境を使います。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend tests --no-cache
```

## Text Encoding / 文字コード

- Repository Markdown files are expected to be UTF-8 without BOM unless a task explicitly says otherwise.
  リポジトリ内の Markdown ファイルは、特別な指示がない限り UTF-8 without BOM を前提とします。
- If Japanese text appears garbled in a terminal or tool output, verify the file bytes with strict UTF-8 decoding before treating the document as corrupted.
  ターミナルやツール出力で日本語が文字化けして見える場合でも、文書が壊れていると判断する前に strict UTF-8 decode でファイル本体を確認します。

## Documentation Language / ドキュメント言語

- Human-facing documents should be written primarily in Japanese.
  人が読む通常ドキュメントは、日本語を主言語として書きます。
- AI-facing operating/context documents should be bilingual English/Japanese.
  AI や coding agent が作業判断に使う運用・文脈ドキュメントは、英日併記で書きます。
- `AGENTS.md` and `PROJECT_CONTEXT.md` are AI-facing documents.
  `AGENTS.md` と `PROJECT_CONTEXT.md` は AI-facing documents として扱います。
- `README.md`, `Documents/`, `setup/`, examples, and UI/manual guides are human-facing unless a task explicitly says otherwise.
  `README.md`、`Documents/`、`setup/`、examples、UI/manual guide は、明示的な指示がない限り human-facing documents として扱います。
- Technical identifiers such as endpoint paths, config keys, class names, and command names may remain in English.
  endpoint path、config key、class name、command name などの技術識別子は英語のままで構いません。

## Documentation Maintenance / ドキュメント更新方針

Update `PROJECT_CONTEXT.md` when any of the following change:
次の内容が変わったら `PROJECT_CONTEXT.md` を更新します。

- implemented modules or package layout / 実装済みモジュールやパッケージ構成
- active roadmap phase / 現在のロードマップ段階
- test/verification commands / テスト・確認コマンド
- known risks, blockers, or temporary assumptions / 既知のリスク、ブロッカー、一時的な前提
- each meaningful unit of work / 意味のある作業単位ごと

When an implementation changes API behavior, UI behavior, configuration behavior, workflows, or verification steps, check the relevant design/operation documents under `Documents/` and keep them synchronized in the same work unit when practical.
API 挙動、UI 挙動、設定挙動、workflow、確認手順が変わる実装では、`Documents/` 配下の関連する設計・運用ドキュメントを照合し、可能な限り同じ作業単位で同期します。

Update `AGENTS.md` when any of the following change:
次の内容が変わったら `AGENTS.md` を更新します。

- team working rules / チームの作業ルール
- contribution conventions / コントリビューション規約
- preferred decision order between code and docs / コードとドキュメントの判断優先順

## Non-Goals For Routine Tasks / 通常作業で暗黙にやらないこと

Avoid doing these implicitly during unrelated work:
無関係な作業のついでに、次のことを暗黙に進めないようにします。

- switching package managers or environment strategy / パッケージ管理や環境戦略の変更
- introducing live market-data providers as default behavior / 本番系マーケットデータプロバイダを既定化すること
- broad README rewrites unless requested / 依頼のない大規模な README 改訂
- large architectural moves that are not backed by tests and context updates / テストやコンテキスト更新を伴わない大きな構成変更

## First Step For New Work / 新しい作業の最初の手順

Before making substantial changes:
大きな変更に入る前に、次を確認します。

1. read `PROJECT_CONTEXT.md` / `PROJECT_CONTEXT.md` を読む
2. inspect the relevant code path / 対象コード経路を確認する
3. show the planned diff for review before editing / 編集前に想定差分を提示してレビューする
4. verify whether tests already cover the target behavior / 既存テストが対象挙動をカバーしているか確認する
5. keep the context documents in sync if the work changes project state / 状態が変わる作業なら文書も同期更新する
