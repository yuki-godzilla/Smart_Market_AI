# Architecture

## 全体像

```text
SMAI / future local tools
        |
        | HTTP API
        v
smai-ai-gateway
        |
        | provider client boundary
        v
Ollama / OpenAI compatible API / vLLM / llama.cpp server
```

## 設計方針

- Gateway は SMAI 本体を主利用元としつつ、将来ほかのローカルツールにも展開できる汎用 AI API とする
- SMAI 本体とは HTTP request / response schema だけで接続する
- Gateway から SMAI 本体の Python module を import しない
- provider routing、prompt 実行、timeout、error normalization は Gateway 側に寄せる
- model routing も Gateway 側の責務とし、SMAI 親は `task_type` / `execution_mode` / `environment_profile` / optional `profile` / optional `model` を渡すだけにする。Gateway は `notebook_dev` / `notebook_standard` / `desktop_fast` / `desktop_analysis` / `desktop_heavy` を provider / model / timeout / token budget に解決する。
- Gateway response は `request_id`、`gateway_status`、`fallback_reason`、`elapsed_ms`、`provider`、`model`、`profile`、`timeout_sec`、`context_tokens_estimate`、`prompt_chars`、`response_chars`、`tool_execution_ms`、`llm_generation_ms`、`total_elapsed_ms` を返し、SMAI 親は valid LLM response を `response_source=llm`、失敗時の安全応答を `response_source=deterministic_fallback` としてUIへ渡す。親 UI ではこれらの runtime metadata を通常回答の主表示に出さず、折りたたみ技術情報として扱う。
- SMAI 側は context bundle 作成、schema validation、deterministic fallback を持つ
- SMAI 親側の opt-in HTTP client は `assistant.gateway.enabled=true` のときだけ `/api/v1/context-answer` を呼び、失敗時は deterministic fallback に戻る
- `free_chat` / `identity` / `app_help` / `capability_help` / `screen_guidance` は LLM-first のまま `llm_micro` として扱い、SMAI 親は tool / RAG / news / symbol-specific context / 長い履歴を送らない。Gateway は最小 context、`/no_think`、Ollama `think: false`、1 回だけの品質再生成を使い、fallback は provider / Gateway / validation failure の最後の保険に限定する。runtime は task_type を主軸にし、実際の Ollama model ごとの token policy で調整する。軽量会話は `qwen3:1.7b` で 280-300 tokens、`qwen3:4b` で 320 tokens、`qwen3:8b` で 360-450 tokens、`qwen3:14b` で 360-500 tokens を目安にする。画面固有の `report_context` がない場合も、SMAI 親は最小アシスタント文脈で Gateway を呼ぶ。
- `context-answer` では、LLM は回答本文を作り、`materials` / `cautions` / `next_checkpoints` は Gateway が渡された context から安定生成する
- `cockpit_interpretation` は `context-answer` の task_type で扱い、Gateway はSMAI親から渡された画面要約contextを読み解く。Cockpit context compression、response validation、cache、deterministic fallback、UI表示はSMAI親側の責務とする
- Gateway / SMAI parent は presentation sanitizer を通し、provider raw fields、debug logs、external source bodies、`privacy_notes` / `safety_notes` などの内部向け文言を通常回答、コピー、Markdown保存、Decision Report向け表示から除外する
- `SMAI LLM Factor` では、Gateway は `/api/v1/llm-factor/generate` による provider 呼び出しと prompt 実行の境界に留める。LLM factor の domain schema、source hash、file-backed cache、deterministic backtest evaluator、broader historical fixture / validation report、Cockpit / Ranking 参考表示、cache policy、UI 統合拡張は SMAI 本体側で扱う

## 現時点で移動しないもの

- SMAI の Research RAG
- News RAG
- Research Evidence
- Forecast / Ranking / Scoring
- Decision Report 生成
- SMAI LLM Factor の domain model / backtest / score integration
- Cockpit interpretation の validation / cache / UI panel

これらは当面 SMAI 本体側に残し、Gateway には必要な context だけを明示的に渡します。

## 将来拡張

- SMAI 親側の `SMAIアシスタント` チャットワークスペース first slice は実装済み。Gateway 側は汎用 `context-answer` 境界を保ち、SMAIナビ header、6つの相談カード、チャット幅の `新しい会話` action、擬似ストリーミングなどの UI は親側で扱う。長い会話履歴や複数文脈参照の本格拡張は後続で扱う
- `SMAI LLM Factor` 向けの構造化 JSON 生成補助を継続改善する。ただし最終予測、ランキング順位、Investment Score 統合は SMAI 側の backtest 後に判断する
- 他ローカルツールからの汎用 chat / summarize 利用
- スマホ / PWA からの共通 AI API 利用
- 認証、API key、rate limit、監査ログ
