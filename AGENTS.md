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
- MarketData / broker / execution external providers only by explicit opt-in; Research RAG external source search is a standard AI Research flow but still network-free in normal checks
- investment outputs are decision support, not buy/sell advice
- Research RAG / News RAG product behavior prioritizes current external sources because freshness matters; normal checks still use fake/local fixtures and must not depend on network. Treat `AI調査を更新` as the intended standard external-source search action, keep fetched source text transient by default, and require a separate explicit archive/save action for persistence.

既定経路:
- local / deterministic
- 通常確認は network 非依存
- MarketData / broker / execution の外部 provider は明示 opt-in のみ。Research RAG の外部 source 探索は AI調査の標準導線だが、通常確認は network 非依存
- 投資出力は売買推奨ではなく判断補助
- Research RAG / News RAG は鮮度が重要なため、プロダクト挙動では最新外部 source を優先する。通常確認は fake/local fixture で network 非依存を維持する。`AI調査を更新` は外部 source 探索の標準導線とし、取得本文は既定では保持せず、永続化は別の明示 archive/save action とする。

## Fast Start / 最初に見るもの

Use the smallest context set that can safely solve the task.
安全に解ける最小文脈だけを読む。

| Task type | Read first | Usually inspect | Avoid first |
| --- | --- | --- | --- |
| Small bug / test fix | failing test or error | target module + matching tests | all docs |
| API change | `backend/app/main.py` | request/response models + API tests + operations guide | UI docs unless UI changes |
| Streamlit UI change | `ui/app.py` | UI helpers/tests + operations guide | unrelated backend docs |
| MarketData/provider | `backend/marketdata/` | provider tests + config docs | live network smoke unless requested |
| Feature/Screening/Forecast/Scoring | target service | contracts + service tests + roadmap phase | Execution docs |
| Research RAG | `Documents/04_Detail_Design/04-8_Onepager_Research_RAG.md` | `backend/research` + fake adapters / fixtures + roadmap R phases | live scraping / external LLM smoke unless requested |
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
1. improve project maturity before feature expansion: clarify specs, UX wording, review checklists, and role boundaries
2. keep Phase 16 cockpit / ranking / rebalance flows stable and run final Streamlit browser smoke when available
3. keep Investment Score, Screening, Forecast, Risk, Research Evidence, and Portfolio explanations consistent across API/UI/docs
4. prepare or maintain Decision Report context from existing cockpit/ranking/rebalance outputs
5. move Research RAG external-source search into the standard AI Research flow while keeping normal checks network-free; keep Assistant as planned/future unless explicitly assigned

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
- For SMAI maturity work, avoid adding new features unless explicitly requested. Prefer clarifying specs, UX wording, and review checklists before changing implementation behavior.
- Treat Ranking, Investment Score, Research Evidence, Rebalance, Forecast, Risk, and Decision Report outputs as decision-support information, not investment advice.
- For Research Summary maturity work, prefer local rule-based `ResearchBrief` / readable memo shaping before external LLM integration; keep provider raw fields out of the normal UI and reserve them for detail data.
- Before changing behavior that affects Ranking / Cockpit / Rebalance / Decision Report / Research / scoring wording, check `Documents/96_Manual_UX_Review_Checklist.md` and `Documents/97_Functional_Spec_Issues.md`.
- Keep Execution / Broker integration deferred unless explicitly assigned.
- Treat Research RAG external evidence freshness as a product priority while preserving network-free normal checks. Keep Assistant as planned / future scope unless explicitly assigned.

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

## Command Hang Policy / コマンド停止時の扱い

If a verification command appears to hang:
- do not wait indefinitely
- report the command name and last visible output
- prefer stopping the command and running a narrower diagnostic
- never treat a hung command as success
- if the same command completes manually, trust the manual result and continue with `git status` / `git diff` verification

確認コマンドが停止しているように見える場合:
- 無期限に待ち続けない
- コマンド名と最後に見えている出力を報告する
- 停止して、より小さい確認コマンドに切り替える
- 停止したコマンドを成功扱いしない
- 同じコマンドが手動で完了した場合は、手動結果を優先し、`git status` / `git diff` で作業状態を確認する

## Handoff Summary Format / 作業完了サマリ

At handoff, report:
- changed files
- purpose of each change
- commands run and results
- commands not run and why
- remaining risks or TODOs
- suggested commit message

作業完了時は以下を報告します:
- 変更ファイル
- 各変更の目的
- 実行した確認コマンドと結果
- 実行しなかった確認と理由
- 残リスク / TODO
- 推奨コミットメッセージ

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
- `backend/risk`, `backend/portfolio`, `backend/screening`, `backend/forecast`, `backend/scoring`: implemented domain services
- `backend/research`: Research RAG/evidence/search service for external fresh sources, local fixtures/archives, and Research Score
- `backend/execution`: deferred future broker execution module; do not assume it exists

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
- use `Documents/07_UI_Wording_Policy.md` when changing user-facing UI/report wording
- use `Documents/04_Detail_Design/04-8_Onepager_Research_RAG.md` when adding research/RAG/evidence behavior
- use `Documents/04_Detail_Design/04-9_Onepager_Investment_Scoring_UI.md` when changing Investment Score or Phase 16 scoring UI behavior
- update `Documents/05_Implementation_Roadmap.md` for phase/scope/completion changes

Encoding:
- Markdown files should be UTF-8 without BOM
- if Japanese looks garbled in terminal output, verify bytes with strict UTF-8 before assuming corruption

## Windows Shell Note

If PowerShell fails with 8009001d:
- first try a direct Python UTF-8 read, then fallback to cmd.exe
- avoid relying on PowerShell-only commands
- prefer:
  - `python -c "from pathlib import Path; print(Path('AGENTS.md').read_text(encoding='utf-8'))"`
  - `py -3 -c "from pathlib import Path; print(Path('AGENTS.md').read_text(encoding='utf-8'))"`
  - `cmd /c type AGENTS.md`
  - `cmd /c dir`
  - `cmd /c findstr`
- Git Bash may not be installed; do not assume `bash` is available

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
- configured default provider remains safe/local; any UI live-provider selection must opt in explicitly and keep tests deterministic
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

Do not use direct multi-file `python -m black --check .` as a routine check in this Windows environment; use `tools/run_black_check.py` or `tools/run_local_checks.py` instead.
この Windows 環境では、通常確認として複数ファイル対象の `python -m black --check .` を直接使わず、`tools/run_black_check.py` または `tools/run_local_checks.py` を使います。

Black hang workaround:
- Do not run `python -m black ...` directly in this Windows workspace, even for a single file, unless the user explicitly asks for it.
- Known symptom: the command stops responding after printing little or no output, and child `python.exe` processes may remain active with high CPU.
- Likely cause: the Black CLI path can leave worker/subprocess state stuck in this local PowerShell/Windows environment; direct CLI behavior is less reliable than the project helper.
- Preferred check: `.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py`.
- If the helper reports `would reformat`, make the small formatting edit manually with `apply_patch`, then rerun the helper.
- If a direct Black command was accidentally started and appears hung, stop waiting, report the command, inspect lingering Python processes, and ask before stopping any suspected leftover process if it cannot be identified safely.

Black 停止回避:
- この Windows workspace では、単一ファイルでも `python -m black ...` を直接実行しない。明示依頼がある場合だけ例外。
- 既知症状: 出力がほぼないまま停止し、子 `python.exe` が高 CPU のまま残ることがある。
- 推定原因: この local PowerShell / Windows 環境では Black CLI 経路の worker/subprocess 状態が固まることがあり、project helper より不安定。
- 推奨確認: `.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py`
- helper が `would reformat` を出した場合は、`apply_patch` で小さく手動整形してから helper を再実行する。
- 誤って direct Black を起動して停止した場合は、待ち続けず、実行コマンドを報告し、残存 Python process を確認する。安全に特定できない process 停止はユーザー確認を取る。

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

Read `Documents/07_UI_Wording_Policy.md` when changing labels, chart legends, metric explanations, warnings, summaries, or report wording.
ラベル、チャート凡例、指標説明、警告、要約、レポート文言を変える場合に読む。

Read component detail docs only when touching that component.
該当コンポーネントを触る場合だけ個別詳細設計を読む。
