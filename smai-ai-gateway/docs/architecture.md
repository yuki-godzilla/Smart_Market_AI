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
- SMAI 側は context bundle 作成、schema validation、deterministic fallback を持つ
- `context-answer` では、LLM は回答本文を作り、`materials` / `cautions` / `next_checkpoints` は Gateway が渡された context から安定生成する
- 将来の `SMAI LLM Factor` では、Gateway は provider 呼び出しと prompt 実行の境界に留める。LLM factor の domain schema、source hash、file-backed cache、deterministic backtest evaluator は SMAI 本体側の初期 slice で実装済みで、Ranking 参考表示、broader historical backtest、cache policy expansion、UI 統合拡張も SMAI 本体側で扱う

## 現時点で移動しないもの

- SMAI の Research RAG
- News RAG
- Research Evidence
- Forecast / Ranking / Scoring
- Decision Report 生成
- SMAI LLM Factor の domain model / backtest / score integration

これらは当面 SMAI 本体側に残し、Gateway には必要な context だけを明示的に渡します。

## 将来拡張

- SMAI Copilot チャット画面
- `SMAI LLM Factor` 向けの構造化 JSON 生成補助。ただし最終予測、ランキング順位、Investment Score 統合は SMAI 側の backtest 後に判断する
- 他ローカルツールからの汎用 chat / summarize 利用
- スマホ / PWA からの共通 AI API 利用
- 認証、API key、rate limit、監査ログ
