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

Status: first MVP implemented. Navigation actions render same-app links using `smai_page` query params. They do not run external fetch, ranking creation, or report creation.

## Phase 30-C: Confirmable Safe Actions

- Action Execution Layer
- `AssistantActionResult`
- session-local action audit log
- confirmation UI
- action result card
- 確認レポート作成
- AI調査更新
- ニュース更新
- ランキング作成

Status: MVP implemented for `create_decision_report` and `update_research`. SMAIアシスタント now shows a confirmation panel before report creation or AI調査更新, executes only after user confirmation, displays success / partial_success / failure / cancelled result cards in the chat thread, and records minimal audit metadata in session state. `update_research` uses the existing session-local external Research fetch path after confirmation and returns only safe summary fields such as fetched count, source counts, warnings, and failed / timed-out sources. Ranking creation, score changes, forecast changes, broker actions, raw provider responses, and source body display remain out of scope. `refresh_news` and `create_ranking` remain follow-up actions.

## Phase 30-D: Multi-step Guided Workflow

- `上がりそうな株を探す` の guided workflow
- Ranking -> Cockpit -> Research -> Report
- 各ステップで確認
- 中断・再開可能

Status: MVP implemented with deterministic guided workflows. SMAIアシスタント can show a separate `確認フロー` card for Ranking -> Cockpit -> AI調査 -> 確認レポート, current-Cockpit deep dives, and report-creation intents. Workflow steps are guidance only: navigation links open SMAI pages, while `update_research` and `create_decision_report` still go through the existing confirmation card and action result flow. Ranking creation, price fetch, external fetch, report creation, score / forecast / AI総合 / Research Score changes, and broker actions are not auto-executed. LLM planning remains Phase 30-E scope.

## Phase 30-E: LLM Tool Planner

- Gateway 経由の Plan 生成
- available actions 限定
- schema validation
- deterministic fallback
- Plan quality evaluation

Status: MVP implemented as an optional, disabled-by-default planner. Parent SMAI can build an `assistant_tool_plan` request with redacted material state and allowed actions, call `smai-ai-gateway` `/api/v1/assistant/tool-plan`, validate schema / action allowlist / confirmation requirements / unsafe wording, and adopt only valid LLM plans into the existing `次にできること` or `確認フロー` UI. Invalid, unavailable, timeout, malformed, unsafe, unknown-action, `create_ranking` / `refresh_news`, or unconfirmed external-fetch plans are hidden and deterministic Tool Plan / Guided Workflow fallback is used. The Gateway remains generic and imports no SMAI modules; it proposes JSON only and never executes actions.

## Phase 30-F: Agent Evaluation Harness

- fixture による Plan 評価
- unsafe action 検出
- hallucinated action 検出
- missing material handling
- regression tests

Status: MVP implemented. `backend/assistant/agent_evaluation.py` can load fixture cases, evaluate raw planner responses, adopted planner states, deterministic Tool Plans, and deterministic Guided Workflows, and return structured pass / fail / warning summaries. The fixture pack covers safe Ranking -> Cockpit workflows, Cockpit research/report workflows, unknown actions, unconfirmed external fetches, broker/order wording, buy/sell/hold wording, malformed response fallback, Gateway timeout fallback, missing Research material handling, and unsupported `create_ranking` ready state. Regular evaluation is pytest / fixture based and network-free. Live LLM output evaluation remains a future opt-in path.

## Phase 30-G: Limited Semi-automatic Workflow

- ユーザー承認済み範囲内で連続実行
- 外部取得や重い処理は明示確認
- 投資判断・売買は実行しない
- Phase 30-F の evaluation gate を通した action / workflow だけを検討対象にする

Status: 30-G1 MVP implemented. 親SMAI側に session-local `AssistantWorkflowSession` と `workflow_runtime` state machine を追加し、validation gate を通った `AssistantGuidedWorkflow` だけを runtime session 化する。UI は既存の確認カード導線を維持しつつ、ターン内の `assistant_workflow_session` JSON に `planned` / `active` / `completed` / `cancelled` / `failed` と各stepの `planned` / `waiting_confirmation` / `running` / `done` / `failed` / `skipped` / `cancelled` / `blocked` を保持する。`update_research` 成功・一部成功後は `create_decision_report` を確認待ちとして見せるが自動実行せず、失敗時は session を failed にして Tool Plan への自動fallbackも止める。`create_decision_report` 成功時は workflow を完了にできる。確認必須actionは `confirmed=True` なしで running へ遷移できず、done/running step の重複実行は警告だけ返す。Gateway は引き続き plan JSON の提案のみで、workflow session / execution は親SMAI側の責務。

Status: 30-G2 MVP implemented. `workflow_runtime.retry_step()` を追加し、SMAIアシスタント UI に session-local workflow controls を接続する。active session では現在stepのスキップとフロー中止、failed session では失敗stepの再試行、`update_research` 失敗後の `今ある材料で確認`、フロー中止を表示する。再試行はstepを `waiting_confirmation` に戻すだけで自動実行せず、`今ある材料で確認` は失敗したAI調査更新を skipped にして次の確認待ちへ進める。confirmable actionの実行は引き続き既存確認カード経由のみ。

## Phase 30-H: Assistant Scenario QA / LLM Startup Warmup

- Assistant composerを画面下部へ常時固定し、環境取得model selectorとchat input / 送信を一体表示
- composer下の重複するmodel選択理由、LLM接続先、一般注意captionを削除
- 代表ユーザー発話をデータ駆動fixtureで回帰確認
- 国内株、米国株、ETF / 投信、曖昧銘柄、テーマ探索、レポート作成を横断
- LLM Startup Warmup と readiness status
- Assistant loading experience
- Main-area loading modal（sidebar操作は維持）と控えめなInvestment Radar animation
- Gateway / provider / model failure別のbounded auto retry、fallback、automatic recovery
- Gateway `/models` による動的モデル一覧、選択優先順位、missing model案内
- 新着メッセージ時だけのchat auto-scrollと状態保持回帰
- LLM model selector: chat composer横の単一selectboxにGateway取得済みmodelだけを性能順で表示し、初期値は最高性能model
- Loading Modal News Readability Polish: 市場ヘッドラインをカテゴリbadge・2行title・source metadata付きmini news cardへ変更し、no-cache案内を追加
- Investment Radar cache由来のloading headlines
- LLM準備中・失敗時のdeterministic fallback
- Assistant intent flexibility
- Concept explanation mode
- Broad discovery mode
- Action card restraint policy
- Explicit user intent driven navigation

Status: first slice implemented. `tests/fixtures/assistant_scenarios.json` に固定16シナリオを追加し、Intent Router / Conversation Mode / entity resolution / Action Card levelをnetwork-freeで回帰確認する。親SMAIはAssistant初回描画時に設定単位で重複しないbackground warmupを開始し、UIをブロックせず、準備中・準備完了・degraded・failed・timeoutを保持する。準備中は軽量なSMAIロードカードと既存ニュースキャッシュ（なければbundled sample）を最大5件表示する。同期ニュース取得、LLM必須化、自動売買、スコア・予測・ランキング変更は行わない。

Loading UI polish slice: 投資レーダー既存assetを56pxのヘッダーアイコンとして再利用し、asset欠損時はCSSミニレーダーへfallbackする。warming中は2秒間隔のStreamlit fragmentでprocess-local warmup状態だけを監視し、ready / failed / timeout検知時にattempt単位のガード付きで1回だけ通常画面を再描画する。ready後はloading panelを残さず、fallback時も入力欄・相談カード・deterministic回答を利用できる。再描画処理は入力widget、chat history、workflow sessionを変更しない。

Intent flexibility slice: 親SMAIのdeterministic policyでAction CardをLevel 0〜2に分け、雑談・自己紹介・用語説明ではカードを非表示、広いテーマ/セクター相談では文章内の軽い案内、明確な操作・調査・比較・作成依頼だけでTool Plan / Guided Workflowを表示する。銘柄未指定の広い相談は失敗ではなくBroad Discoveryとして扱い、特定銘柄の外部取得を開始しない。
