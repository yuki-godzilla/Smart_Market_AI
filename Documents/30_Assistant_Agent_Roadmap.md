# 30_Assistant_Agent_Roadmap

SMAI Assistant のエージェント化ロードマップです。

## Safety Boundary

- SMAI Assistant は投資判断や売買を自動実行しません。
- Assistant は、確認すべき材料と SMAI 上で可能な操作を整理します。
- 外部取得、ランキング作成、確認レポート作成、保存はユーザー確認後に実行します。
- 通常テストは network-free を維持します。

## Phase 30-A: Tool Plan MVP

- 現在画面 context builder
- available action registry
- deterministic Tool Plan
- plan validation
- Assistant UI の `次にできること` 表示
- 実行は原則しない

## Phase 30-B: Confirmable Navigation Actions

- Plan から Ranking / Cockpit / News への安全な navigation
- 実行前確認 UI
- action result 表示

## Phase 30-C: Confirmable Safe Actions

- AI調査更新
- ニュース更新
- 確認レポート作成
- ランキング作成
- action audit log

## Phase 30-D: Multi-step Guided Workflow

- `上がりそうな株を探す` の guided workflow
- Ranking -> Cockpit -> Research -> Report
- 各ステップで確認
- 中断・再開可能

## Phase 30-E: LLM Tool Planner

- Gateway 経由の Plan 生成
- available actions 限定
- schema validation
- deterministic fallback
- Plan quality evaluation

## Phase 30-F: Agent Evaluation Harness

- fixture による Plan 評価
- unsafe action 検出
- hallucinated action 検出
- missing material handling
- regression tests

## Phase 30-G: Limited Semi-automatic Workflow

- ユーザー承認済み範囲内で連続実行
- 外部取得や重い処理は明示確認
- 投資判断・売買は実行しない
