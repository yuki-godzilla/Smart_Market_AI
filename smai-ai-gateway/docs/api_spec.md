# API Spec

## GET /health

Gateway の起動確認です。

Response:

```json
{
  "status": "ok",
  "service": "smai-ai-gateway"
}
```

## POST /api/v1/chat

汎用チャット API です。SMAI 専用の naming は使いません。

Request:

```json
{
  "message": "こんにちは",
  "system_prompt": "You are a helpful assistant.",
  "model": "qwen3:8b"
}
```

Response:

```json
{
  "answer": "こんにちは。どのようなお手伝いをしましょうか。",
  "model": "qwen3:8b",
  "provider": "ollama",
  "elapsed_ms": 120
}
```

## POST /api/v1/summarize

汎用要約 API です。会議要約、ニュース要約、技術文書要約などに使う想定です。

Request:

```json
{
  "text": "...",
  "purpose": "meeting_notes",
  "model": "qwen3:8b"
}
```

Response:

```json
{
  "answer": "要約本文...",
  "model": "qwen3:8b",
  "provider": "ollama",
  "elapsed_ms": 180
}
```

## Error

provider 呼び出しに失敗した場合は、HTTP 502 として分かりやすい detail を返します。

```json
{
  "detail": {
    "error": "Ollama request timed out.",
    "provider": "ollama"
  }
}
```
