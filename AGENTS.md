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

The current implementation is still MVP-oriented and intentionally favors deterministic local behavior over external integrations.
現在の実装はまだ MVP 指向であり、外部連携よりもローカルで再現性の高い挙動を優先しています。

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

## Current Development Focus / 現在の開発フォーカス

The repository appears to be at:
現時点のリポジトリの状態は次の通りです。

- Core contracts/config/errors: implemented / Core の契約・設定・エラーは実装済み
- MarketData MVP: implemented with `mock` provider / MarketData MVP は `mock` プロバイダで実装済み
- API bootstrap: implemented with `/health` and `POST /risk/pre-trade-check` / API の起点は `/health` と `POST /risk/pre-trade-check` 付きで実装済み
- Risk MVP: initial service and API implemented; next likely work is API contract/error hardening / Risk MVP は初期サービスと API が実装済み、次は API 契約とエラー応答の強化

Unless a task says otherwise, optimize changes for this progression.
特別な指示がない限り、この進行順を前提に変更を最適化します。

## Source Of Truth / 判断の優先順位

When deciding what to build next, consult these in order:
次に何を作るか判断する際は、次の順で参照します。

1. User request / ユーザー要求
2. Actual code in `backend/` and `tests/` / `backend/` と `tests/` の実コード
3. `PROJECT_CONTEXT.md`
4. `Documents/06_Implementation_Roadmap.md`
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
- future modules should follow the roadmap names where practical: `backend/risk`, `backend/portfolio`, `backend/execution`
  今後のモジュールは、可能な範囲でロードマップ上の命名 `backend/risk`、`backend/portfolio`、`backend/execution` に合わせます。

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
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend tests --no-cache
```

## Documentation Maintenance / ドキュメント更新方針

Update `PROJECT_CONTEXT.md` when any of the following change:
次の内容が変わったら `PROJECT_CONTEXT.md` を更新します。

- implemented modules or package layout / 実装済みモジュールやパッケージ構成
- active roadmap phase / 現在のロードマップ段階
- test/verification commands / テスト・確認コマンド
- known risks, blockers, or temporary assumptions / 既知のリスク、ブロッカー、一時的な前提
- each meaningful unit of work / 意味のある作業単位ごと

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
