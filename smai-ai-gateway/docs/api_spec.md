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
  "profile": "notebook_dev"
}
```

Response:

```json
{
  "answer": "こんにちは。どのようなお手伝いをしましょうか。",
  "model": "qwen3:4b",
  "provider": "ollama",
  "elapsed_ms": 120
}
```

## POST /api/v1/summarize

汎用要約 API です。入力テキストの要点整理に使う想定で、特定アプリ専用の field は持ちません。

Request:

```json
{
  "text": "...",
  "purpose": "general_summary",
  "profile": "desktop_fast"
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

## POST /api/v1/context-answer

context bundle をもとに、説明本文と `materials` / `cautions` / `next_checkpoints` を返す汎用 API です。
SMAI Copilot や Decision Report 連携では、画面やレポートの安全な要約 context だけを渡します。Gateway はスコア、予測値、ランキング順位を変更しません。
SMAI 親側では `assistant.gateway.enabled=true` のときだけこの endpoint を呼び、失敗時は deterministic fallback に戻します。

Request:

```json
{
  "schema_version": "assistant-gateway-request-v1",
  "task": "explain",
  "language": "ja",
  "user_question": "AI予測インサイトでは何を見ればよいですか？",
  "task_type": "forecast_risk_compare",
  "profile": "notebook_dev",
  "execution_mode": "auto",
  "environment_profile": "notebook",
  "request_id": "assistant-request-1",
  "timeout_sec": 90,
  "context_tokens_estimate": 380,
  "prompt_chars": 1200,
  "response_chars": 240,
  "tool_execution_ms": 0,
  "llm_generation_ms": 120,
  "total_elapsed_ms": 130,
  "context": {
    "schema_version": "assistant-context-bundle-v1",
    "bundle_id": "bundle-1",
    "title": "銘柄コックピット / AI予測インサイト",
    "source": "decision_report",
    "active_context_id": "forecast-1",
    "sections": [
      {
        "section_id": "forecast-1",
        "title": "AI予測インサイト",
        "source_kind": "forecast",
        "summary": {
          "中心予測": "+1.2%",
          "予測レンジ": "-3.0%〜+4.5%"
        },
        "included_fields": ["中心予測", "予測レンジ", "信頼度"],
        "warnings": ["予測レンジが広めです。"],
        "notes": ["根拠資料とデータ品質も確認します。"]
      }
    ],
    "privacy_notes": [
      "Provider raw fields, debug logs, and full external source bodies are excluded."
    ]
  },
  "constraints": {
    "no_investment_advice": true,
    "do_not_change_scores": true,
    "do_not_rank_symbols": true,
    "answer_format": "materials_cautions_checkpoints",
    "require_referenced_sections": true
  }
}
```

Response:

```json
{
  "schema_version": "assistant-gateway-response-v1",
  "answer": "中心予測、予測レンジ、信頼度の順に確認します。",
  "materials": ["AI予測インサイト", "中心予測", "予測レンジ", "信頼度"],
  "cautions": [
    "予測レンジが広めです。",
    "投資助言ではなく、確認材料の整理として扱ってください。"
  ],
  "next_checkpoints": ["根拠資料とデータ品質も確認します。"],
  "referenced_sections": [
    {
      "section_id": "forecast-1",
      "title": "AI予測インサイト",
      "source_kind": "forecast"
    }
  ],
  "confidence": "medium",
  "safety_notes": ["スコア、予測値、ランキング順位は変更していません。"],
  "provider": "ollama",
  "model": "qwen3:4b",
  "profile": "notebook_dev",
  "elapsed_ms": 120,
  "gateway_status": "ok",
  "fallback_reason": null,
  "request_id": "assistant-request-1",
  "decision_support_note": "この回答は判断材料の整理であり、投資助言ではありません。"
}
```

## Error

provider 呼び出しに失敗した場合は、分かりやすい detail を返します。Ollama 未起動や URL 誤りは `provider_unreachable`、timeout は `provider_timeout`、model 未取得は `model_not_found` として扱います。

```json
{
  "detail": {
    "error": "Ollama request failed. Check OLLAMA_BASE_URL and whether Ollama is running.",
    "provider": "ollama",
    "code": "provider_unreachable",
    "retryable": true
  }
}
```

model が未取得の場合:

```json
{
  "detail": {
    "error": "Ollama model 'qwen3:4b' was not found. Run `ollama pull qwen3:4b` or choose an installed model.",
    "provider": "ollama",
    "code": "model_not_found",
    "retryable": false
  }
}
```

## GET /models

Ollama が起動しているか、設定中 model が導入済みかを確認します。

```json
{
  "provider": "ollama",
  "base_url": "http://localhost:11434",
  "default_profile": "notebook_dev",
  "default_model": "qwen3:4b",
  "installed_models": ["qwen3:4b", "qwen3:8b"],
  "configured_model_installed": true,
  "install_hint": null
}
```
