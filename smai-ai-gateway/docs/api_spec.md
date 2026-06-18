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

## GET /health/ready

Gateway process、Ollama API、設定中 model の導入状態をまとめて確認します。Ollama 未起動や model 未取得でも診断しやすいよう、endpoint 自体は JSON を返します。

Response:

```json
{
  "status": "ok",
  "service": "smai-ai-gateway",
  "gateway": "ok",
  "ollama": "ok",
  "provider": "ollama",
  "ollama_base_url": "http://localhost:11434",
  "default_profile": "notebook_dev",
  "default_model": "qwen3:1.7b",
  "installed_models": ["qwen3:1.7b"],
  "configured_model_installed": true,
  "error_code": null,
  "error_message": null,
  "install_hint": null
}
```

Ollama 未起動や model 未取得時は `status: degraded` になり、`error_code` に `provider_unreachable` または `model_not_found`、`install_hint` に `ollama pull qwen3:1.7b` などの次アクションを返します。

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
  "model": "qwen3:1.7b",
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
SMAIアシスタント や Decision Report 連携では、画面やレポートの安全な要約 context だけを渡します。Gateway はスコア、予測値、ランキング順位を変更しません。
SMAI 親側では `assistant.gateway.enabled=true` のときだけこの endpoint を呼び、失敗時は deterministic fallback に戻します。

主な `task_type`:

- `free_chat` / `identity` / `app_help` / `capability_help` / `screen_guidance`: 軽量会話。
- `stock_summary` / `forecast_risk_compare` / `news_materials` / `decision_report_draft`: SMAIアシスタントの材料整理。
- `cockpit_interpretation`: Cockpit `AI解釈メモ`。価格、Forecast、Investment Score、Research Evidence、AI材料分析の要約contextを読み解く。SMAI側は別途 validation / cache / fallback を持ち、Gateway はスコア、順位、予測値、Decision Report本文を変更しない。

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
  "model": "qwen3:1.7b",
  "profile": "notebook_dev",
  "elapsed_ms": 120,
  "gateway_status": "ok",
  "fallback_reason": null,
  "request_id": "assistant-request-1",
  "decision_support_note": "この回答は判断材料の整理であり、投資助言ではありません。"
}
```

## POST /api/v1/llm-factor/generate

1銘柄の compact context から `llm_factor.v1` の構造化材料を返す API です。SMAI 親側では Cockpit `AI材料分析` の参考表示に使い、スコア、予測値、ランキング順位は変更しません。Provider failure、timeout、invalid JSON、schema validation failure は fallback JSON に変換され、親側でも追加 validation / cache / fallback を行います。親側の標準 fallback reason は `disabled`、`gateway_unavailable`、`gateway_timeout`、`gateway_http_error`、`malformed_json`、`validation_error`、`wrong_symbol`、`unknown_evidence`、`stale_source`、`cache_miss`、`cache_corrupt`、`provider_error` です。

Request:

```json
{
  "schema_version": "llm-factor-gateway-request-v1",
  "symbol": "7203.T",
  "company_name": "Toyota Motor",
  "as_of": "2026-06-12",
  "language": "ja",
  "prompt_version": "llm_factor_live_mvp.v1",
  "response_schema_version": "llm_factor.v1",
  "preferred_profile": "desktop_analysis",
  "execution_mode": "auto",
  "environment_profile": "notebook",
  "context": {
    "symbol_profile": {
      "company_name": "Toyota Motor",
      "symbol": "7203.T"
    },
    "research_summary": ["増配と自社株買いが確認できます。"],
    "news_summary": [],
    "forecast_summary": {
      "中心予測": "+1.2%"
    },
    "evidence": [
      {
        "evidence_id": "evidence_001",
        "title": "増配と自社株買いを発表",
        "source_type": "company_ir",
        "source_url": "https://example.com/ir/7203",
        "source_date": "2026-06-12",
        "provider": "fixture",
        "summary": "増配と自社株買いが確認できます。",
        "reliability_score": 82
      }
    ]
  },
  "constraints": {
    "no_investment_advice": true,
    "use_only_supplied_context": true,
    "do_not_change_scores": true,
    "do_not_rank_symbols": true,
    "require_evidence_ids": true
  }
}
```

Response:

```json
{
  "schema_version": "llm_factor.v1",
  "symbol": "7203.T",
  "overall_summary": "出典付き材料では株主還元が確認できます。",
  "sentiment_label": "positive",
  "confidence": 0.78,
  "factors": [
    {
      "title": "株主還元",
      "direction": "positive",
      "summary": "増配と自社株買いが確認できます。",
      "strength": 0.82,
      "evidence_ids": ["evidence_001"]
    }
  ],
  "risks": [],
  "opportunities": [],
  "evidence": [
    {
      "evidence_id": "evidence_001",
      "title": "増配と自社株買いを発表",
      "source_type": "company_ir",
      "source_url": "https://example.com/ir/7203",
      "source_date": "2026-06-12",
      "summary": "増配と自社株買いが確認できます。"
    }
  ],
  "missing_fields": [],
  "warnings": [],
  "prompt_version": "llm_factor_live_mvp.v1",
  "provider": "ollama",
  "model": "qwen3:14b",
  "profile": "desktop_analysis",
  "generated_at": "2026-06-12T10:00:00Z",
  "elapsed_ms": 120,
  "gateway_status": "ok",
  "fallback_reason": null,
  "decision_support_note": "この結果は判断材料の整理であり、投資助言ではありません。"
}
```

## Error

provider 呼び出しに失敗した場合は、分かりやすい detail を返します。Ollama 未起動や URL 誤りは `provider_unreachable`、timeout は `provider_timeout`、model 未取得は `model_not_found` として扱います。`/api/v1/context-answer` の `task_type=free_chat` だけは、timeout 時も通常会話を崩さないため `local_conversation_fallback` として自然な fallback answer を返します。`/api/v1/llm-factor/generate` は provider / validation failure を原則 fallback JSON に変換します。

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
    "error": "Ollama model 'qwen3:1.7b' was not found. Run `ollama pull qwen3:1.7b` or choose an installed model.",
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
  "default_model": "qwen3:1.7b",
  "installed_models": ["qwen3:1.7b", "qwen3:8b"],
  "configured_model_installed": true,
  "install_hint": null
}
```
