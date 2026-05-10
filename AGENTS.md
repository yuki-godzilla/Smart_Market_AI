# AGENTS.md

## Purpose / 目的

Shared operating guide for contributors and coding agents.
開発者と coding agent 向けの共通作業ガイドです。

Keep this file short and action-oriented. Read long context only when needed.
このファイルは短く、作業判断に直結する内容だけにします。長い文脈は必要な場合だけ読みます。

- `AGENTS.md`: stable rules and fast paths / 安定ルールと最短手順
- `PROJECT_CONTEXT.md`: compact current-state summary / 軽量な現在地サマリ
- `Documents/99_Work_Log.md`: historical work log / 過去作業ログ
- `Documents/98_Codex_Task_Template.md`: reusable Codex task template / Codex 用タスクテンプレート
- `Documents/05_Implementation_Roadmap.md`: phase plan / フェーズ計画
- `Documents/06_MVP_Operations_Guide.md`: API, UI, CSV, provider, runbook / 運用ガイド

## Core Guardrails / 守る線

Smart Market AI is a local-first Python investment-support app using FastAPI, Streamlit, deterministic MarketData, Feature Store Lite, Screening Score, Forecast baseline, Risk, and Portfolio MVP modules.
Smart Market AI は、FastAPI、Streamlit、deterministic MarketData、Feature Store Lite、Screening Score、Forecast baseline、Risk、Portfolio MVP を持つ local-first な Python 投資判断支援アプリです。

Default path:
- local and deterministic
- no network dependency in normal checks
- external providers only by explicit opt-in
- investment outputs are decision support, not buy/sell advice

既定経路:
- local / deterministic
- 通常確認は network 非依存
- 外部 provider は明示 opt-in のみ
- 投資出力は売買推奨ではなく判断補助

## Fast Start / 最初に見るもの

Use the smallest context set that can safely solve the task.
安全に解ける最小文脈だけを読む。

| Task type | Read first | Usually inspect | Avoid first |
| --- | --- | --- | --- |
| Small bug / test fix | failing test or error | target module + matching tests | all docs |
| API change | `backend/app/main.py` | request/response models + API tests + operations guide | UI docs unless UI changes |
| Streamlit UI change | `ui/app.py` | UI helpers/tests + operations guide | unrelated backend docs |
| MarketData/provider | `backend/marketdata/` | provider tests + config docs | live network smoke unless requested |
| Feature/Screening/Forecast | target service | contracts + service tests + roadmap phase | Execution docs |
| Docs-only change | target doc | `PROJECT_CONTEXT.md` if status changes | code scan unless needed |
| New implementation task | `PROJECT_CONTEXT.md` + relevant doc | related service + tests | `Documents/99_Work_Log.md` unless history is needed |
| New phase work | roadmap current phase + `PROJECT_CONTEXT.md` | related service + tests | broad refactor |

## Source Of Truth / 判断優先順位

1. User request / ユーザー要求
2. Actual code in `backend/`, `ui/`, and `tests/` / 実コード
3. `PROJECT_CONTEXT.md`
4. `Documents/05_Implementation_Roadmap.md`
5. Other design docs / その他設計資料

If docs and code disagree, trust code for current behavior and record material current-state mismatches in `PROJECT_CONTEXT.md`.
ドキュメントとコードがズレる場合、現在挙動はコードを優先し、現在地に関わる重要な差分だけ `PROJECT_CONTEXT.md` に記録します。

## Current Direction / 現在の方向性

Follow the Multi-Model Investment Intelligence roadmap unless the user says otherwise.
通常は Multi-Model Investment Intelligence の流れに沿います。

Near-term priority:
1. connect Forecast Lab Baseline results to API / export
2. keep beginner-friendly UI design as a dedicated phase
3. build low-cost AI assistant as deterministic rule/template first; optional LLM adapter later

Execution and broker order sending stay lower priority unless explicitly requested.
Execution と broker order 送信は、明示依頼がない限り優先度を下げます。

## Speed Rules / 実装速度を上げるルール

- Prefer one narrow vertical slice: contract -> service -> API/UI -> test -> docs only if needed.
- Reuse existing models, helpers, fixtures, and error types before creating new ones.
- Add the smallest test that proves the changed behavior; do not overbuild test matrices early.
- Run targeted checks first; full local checks only after meaningful code changes or before handoff.
- Do not reread long docs after every step. Cache the relevant conclusion in your work summary.
- Do not update `PROJECT_CONTEXT.md` for typo-only or internal refactor-only changes with no status/assumption change.
- Append work-log entries to `Documents/99_Work_Log.md`, not to `PROJECT_CONTEXT.md`.
- Read `Documents/99_Work_Log.md` only when historical investigation is needed.
- Keep user-facing labels beginner-friendly Japanese when exposing scores, warnings, reasons, or reports.

実装速度の基本:
- 小さな縦切りで進める: contract -> service -> API/UI -> test -> 必要な文書
- 新規作成より既存 model/helper/fixture/error の再利用を優先
- 変更を証明する最小テストを追加
- まず対象を絞った確認、引き渡し前に必要なら全体確認
- 長い文書を毎回読み直さない
- 状態や前提が変わらない typo/refactor では `PROJECT_CONTEXT.md` を更新しない
- 作業ログは `PROJECT_CONTEXT.md` ではなく `Documents/99_Work_Log.md` に追記する
- 履歴調査が必要な場合だけ `Documents/99_Work_Log.md` を読む
- スコア・警告・理由・レポートは初心者向け日本語を意識する

## Work Loop / 作業手順

For implementation work:
1. Identify the task type from Fast Start.
2. Inspect the smallest relevant code/tests.
3. State intended diff when practical.
4. Make one small coherent change.
5. Run targeted verification.
6. Update docs/context only when behavior, API/UI, commands, assumptions, or phase status changed.
7. Report changed/why/how to use/verification/commit message.

Diff review and verification are checkpoints, not automatic stopping points. If direction is already approved, continue to the next logical small task unless a new decision or risk needs review.
差分確認と検証はチェックポイントであり、自動停止地点ではありません。方針承認済みなら、新しい判断やリスク確認が必要な場合を除き、次の自然な小タスクへ進みます。

## Implementation Conventions / 実装規約

Python:
- simple, explicit, typed
- follow existing Pydantic v2 patterns
- reuse `backend/core/data_contracts.py`, `backend/core/config.py`, `backend/core/errors.py`
- avoid hidden global state and implicit provider selection

Architecture:
- `backend/app`: FastAPI entrypoints and wiring only
- `backend/core`: shared contracts, config, errors
- `backend/marketdata`: providers, adapters, feature construction
- `backend/risk`, `backend/portfolio`, `backend/screening`, `backend/forecast`: domain services
- future modules should follow roadmap names: `backend/scoring`, `backend/execution`, etc.

Testing:
- add/update tests for behavior changes whenever practical
- prefer deterministic tests using `mock`, `csv`, fixtures, or fake providers
- keep live provider smoke separate from normal local/CI checks
- UI-impacting roadmap phases need UI-level confirmation criteria

Docs:
- human-facing docs: Japanese-first
- AI-facing docs (`AGENTS.md`, `PROJECT_CONTEXT.md`): concise bilingual where useful
- keep `AGENTS.md` stable; keep volatile history in `Documents/99_Work_Log.md`
- update `PROJECT_CONTEXT.md` only when current state, assumptions, phase, or verification baseline changes
- use `Documents/98_Codex_Task_Template.md` when a new implementation task needs a reusable prompt shape
- update `Documents/06_MVP_Operations_Guide.md` for API/UI/CSV/provider/runbook changes
- update `Documents/05_Implementation_Roadmap.md` for phase/scope/completion changes

Encoding:
- Markdown files should be UTF-8 without BOM
- if Japanese looks garbled in terminal output, verify bytes with strict UTF-8 before assuming corruption

## Task Checklists / タスク別チェックリスト

API endpoint:
- request/response contract is typed
- domain logic stays outside `backend/app`
- structured domain errors map to expected status codes
- API test covers success and at least one meaningful failure
- operations guide updated if usage changed

Service logic:
- uses existing contracts/config/errors
- deterministic fixture or fake provider test exists
- edge cases cover missing data, invalid input, or quality warning where relevant
- no network call in default path

Streamlit UI:
- helper logic is testable outside Streamlit when practical
- user-facing text explains reason/warning, not only raw numbers
- default provider remains safe/local unless explicit opt-in
- manual UI confirmation point is documented when phase completion depends on UI

Provider/live data:
- adapter is explicit opt-in
- provider failures become domain errors with useful details
- normal tests use fake provider or fixtures
- live smoke is documented separately and not required for CI

Forecast/scoring/report:
- output includes reason, metric, or breakdown where user-visible
- data quality and uncertainty are visible when relevant
- do not present model output as investment advice
- export/API/UI use consistent field names

## Verification Commands / 確認コマンド

Use the project virtual environment when available.
利用可能であればプロジェクト仮想環境を使います。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
```

Targeted examples:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests/test_health.py -q
.\venv_SMAI\Scripts\python.exe -m pytest tests -q -k forecast
.\venv_SMAI\Scripts\python.exe -m ruff check backend/forecast tests --no-cache
```

Use targeted checks for small changes. Avoid broad or network-dependent checks unless the task needs them.
小さな変更では対象を絞った確認を優先します。必要がない限り、広範囲・network 依存の確認は避けます。

## When To Read More / 詳細参照の目安

Read `PROJECT_CONTEXT.md` first for new implementation tasks, together with the relevant design or operation document.
新しい実装タスクでは、まず `PROJECT_CONTEXT.md` と該当する設計・運用ドキュメントを読む。

Read `Documents/99_Work_Log.md` only when historical investigation or past decision tracing is needed.
履歴調査や過去判断の追跡が必要な場合だけ `Documents/99_Work_Log.md` を読む。

Read `Documents/98_Codex_Task_Template.md` when shaping a new Codex task request.
新しい Codex 向けタスク依頼の形を整える場合に `Documents/98_Codex_Task_Template.md` を読む。

Read `Documents/05_Implementation_Roadmap.md` when choosing/changing phase work or completion criteria.
フェーズ作業や完了条件を選ぶ/変える場合に読む。

Read `Documents/06_MVP_Operations_Guide.md` when changing API behavior, CSV formats, provider setup, Streamlit workflow, exports, or verification commands.
API、CSV、provider、Streamlit、export、確認コマンドを変える場合に読む。

Read component detail docs only when touching that component.
該当コンポーネントを触る場合だけ個別詳細設計を読む。
