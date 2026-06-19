# Roadmap

## Phase 1: ローカル Ollama 接続

- FastAPI Gateway
- `/health`
- `/api/v1/chat`
- `/api/v1/summarize`
- `/api/v1/context-answer`
- `/api/v1/assistant/tool-plan`
- Ollama client
- 基本 schema / tests
- provider error detail
- opt-in live Ollama smoke
- SMAI 本体側の `SMAI LLM Factor` 初期 schema / fake service / file-backed cache / deterministic backtest evaluator / broader validation report / Cockpit 参考表示 / Ranking 参考表示は親プロジェクト側で実装済み。Gateway 側も `/api/v1/llm-factor/generate` の構造化抽出 endpoint を提供済み。

## Phase 2: SMAI から投資コメント生成に利用

- SMAI 側 `AssistantContextBundle` から Gateway へ接続。親側 opt-in HTTP client wiring は実装済み
- SMAI floating Copilot の説明補助と、親側 `SMAIアシスタント` workspace / 質問候補 / 限定自由入力 / チャット幅の `新しい会話` / 擬似ストリーミング first slice は実装済み
- context answer response の `materials` / `cautions` / `next_checkpoints` を UI 互換 `AssistantResponse` へ接続済み
- deterministic fallback 維持。通常 tests は network-free、live smoke は後続の明示 opt-in 確認

## Phase 2.1: SMAI Assistant Command Center / Research Mode support

- 親SMAI側で `normal_chat` / `soft_research_suggestion` / `research_plan` を切り替える Conversation Mode Router、承認付きTool Planカード、approve / cached-only / cancel action、session-local Context Aggregator、Decision Report下書き導線、confirmable safe action executor の初期スライスは実装済み。`create_decision_report` と `update_research` は親SMAI側で確認後だけ実行する
- Gateway は Tool Planの判断・外部取得・SMAI内部機能実行を担当しない。Gateway 側は、親SMAIが承認後に集約したcontextを受け取り、自然な回答・材料整理・注意点・次の確認を返す汎用 `context-answer` 境界を維持する
- optional LLM Tool Planner MVP として `/api/v1/assistant/tool-plan` を追加済み。ただし Gateway は available actions から JSON plan 案を返すだけで、親SMAI側が schema / allowlist / safety validation、deterministic fallback、既存 UI 採用、確認付き action execution を担当する
- 親SMAI側 Phase 30-F で fixture-based Agent Evaluation Harness を追加済み。Phase 30-G1 では Workflow Session / runtime state machine も親SMAI側に追加済み。Gateway は引き続き action を実行せず、評価 / 採用 / fallback / session進行 / UI表示は親SMAI側の責務とする
- 外部取得や重いResearch RAG / news fetchは親SMAI側でユーザー承認を挟む。通常testsはfake adapter / fixtureでnetwork-freeに保つ
- Gateway prompt profileは `stock_forward_view`、`news_research`、`decision_report_request`、`cockpit_interpretation` などのtask_typeを受け取れるように段階拡張するが、スコア・ランキング順位・予測値・売買判断は変更しない

## Phase 2.5: 構造化特徴量生成の安全基盤

- `SMAI LLM Factor` 向けに、RAG / News / IR 由来の定性材料を JSON へ変換する `/api/v1/llm-factor/generate` を実装済み
- Gateway は provider 呼び出し、prompt 実行、timeout、error normalization を担当する
- `LLMFactorResult`、factor schema、source hash、file-backed cache、deterministic backtest evaluator、broader historical fixture / validation report、Cockpit / Ranking 参考表示は SMAI 本体側で実装済み。cache policy expansion、UI 統合拡張も SMAI 本体側で扱い、Gateway から SMAI module は import しない
- LLM は最終予測、ランキング順位、Investment Score、売買判断を決めない
- source URL、source date、model name、prompt version を request / response に保持する
- 通常 tests は network-free、live provider smoke は opt-in に分離する

## Phase 2.6: Cockpit LLM interpretation support

- 親SMAI側 Phase 28-A で Cockpit `AI解釈メモ` を実装済み。Gateway は `/api/v1/context-answer` の `task_type=cockpit_interpretation` として扱う
- Gateway は価格、Forecast、Investment Score、Research Evidence、AI材料分析の要約contextから、強い材料、注意点、矛盾・不確実性、次の確認を整理する
- context compression、Pydantic validation、cache、deterministic fallback、UI表示は親SMAI側の責務とする
- Ranking、Forecast、AI総合、Investment Score、Research Score、Decision Report本文、売買判断は変更しない

## Phase 3: 他ローカルツールへ展開

- SMAI 以外のローカルクライアントからの利用
- 汎用テキスト要約
- 汎用プロンプト実行
- 汎用チャット

## Phase 4: 運用機能

- 認証
- ログ
- API key
- rate limit
- provider 切替

## Phase 5: 別リポジトリ化 / Git submodule化

- SMAI 本体との境界を HTTP API に限定
- Gateway 単体 CI
- versioning

## Phase 6: スマホ / PWA / クラウド対応

- PWA / mobile client からの利用
- Cloud deploy option
- remote provider support
