# Architecture

## 全体像

```text
SMAI / meeting summary / AI test tools
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

- Gateway は SMAI 専用ではなく、複数アプリから使える汎用 AI API とする
- SMAI 本体とは HTTP request / response schema だけで接続する
- Gateway から SMAI 本体の Python module を import しない
- provider routing、prompt 実行、timeout、error normalization は Gateway 側に寄せる
- SMAI 側は context bundle 作成、schema validation、deterministic fallback を持つ

## 現時点で移動しないもの

- SMAI の Research RAG
- News RAG
- Research Evidence
- Forecast / Ranking / Scoring
- Decision Report 生成

これらは当面 SMAI 本体側に残し、Gateway には必要な context だけを明示的に渡します。

## 将来拡張

- SMAI Copilot チャット画面
- 会議要約アプリからの要約利用
- AI テスト基盤からのテスト観点生成
- スマホ / PWA からの共通 AI API 利用
- 認証、API key、rate limit、監査ログ
