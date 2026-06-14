# SETUP

## 1. Python 環境

Python 3.11 以上を想定します。

```powershell
cd smai-ai-gateway
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

既存の SMAI 開発環境から試す場合は、リポジトリ直下の `venv_SMAI` を使っても構いません。

## 2. Ollama

Ollama を起動し、利用するモデルを取得します。

```powershell
ollama pull qwen3:8b
```

## 3. .env

`.env.example` を `.env` にコピーし、必要に応じて値を変更します。

```powershell
copy .env.example .env
```

主な設定:

- `OLLAMA_BASE_URL`: 既定 `http://localhost:11434`
- `DEFAULT_LLM_MODEL`: 既定 `qwen3:8b`
- `REQUEST_TIMEOUT_SECONDS`: 既定 `30`

## 4. 起動

```bat
run_server.bat
```

手動で起動する場合:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8088
```

## 5. 動作確認

### Ollama なしでできる確認

通常のテストは Ollama や network に依存しません。schema と `/health` の土台確認だけを行います。

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

既存の SMAI 開発環境から確認する場合:

```powershell
..\venv_SMAI\Scripts\python.exe -m pytest tests -q
```

### Gateway 起動確認

```powershell
curl http://127.0.0.1:8088/health
```

期待例:

```json
{
  "status": "ok",
  "service": "smai-ai-gateway"
}
```

チャット確認例:

```powershell
curl -X POST http://127.0.0.1:8088/api/v1/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"こんにちは\",\"system_prompt\":\"You are a helpful assistant.\",\"model\":\"qwen3:8b\"}"
```

要約確認例:

```powershell
curl -X POST http://127.0.0.1:8088/api/v1/summarize ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"確認したい文章の要点を短く整理してください。\",\"purpose\":\"general_summary\",\"model\":\"qwen3:8b\"}"
```

context answer 確認例:

```powershell
curl -X POST http://127.0.0.1:8088/api/v1/context-answer ^
  -H "Content-Type: application/json" ^
  -d "{\"user_question\":\"AI予測インサイトでは何を見る？\",\"model\":\"qwen3:8b\",\"context\":{\"bundle_id\":\"bundle-1\",\"title\":\"銘柄コックピット\",\"sections\":[{\"section_id\":\"forecast-1\",\"title\":\"AI予測インサイト\",\"source_kind\":\"forecast\",\"summary\":{\"中心予測\":\"+1.2%\",\"予測レンジ\":\"-3.0%〜+4.5%\"},\"included_fields\":[\"中心予測\",\"予測レンジ\",\"信頼度\"],\"warnings\":[\"予測レンジが広めです。\"],\"notes\":[\"根拠資料とデータ品質も確認します。\"]}]}}"
```

SMAI 親アプリから試す場合は、Gateway を起動したまま、SMAI 側の `SMAI_CONFIG_FILE` に次のような設定を指定します。通常確認では使わず、既定の `enabled: false` を維持します。

```yaml
assistant:
  gateway:
    enabled: true
    base_url: "http://127.0.0.1:8088"
    context_answer_path: "/api/v1/context-answer"
    timeout_seconds: 10
    execution_mode: "auto"
    environment_profile: "notebook"
```

SMAI 親は通常 `model` を固定指定せず、会話 intent から `task_type` を渡します。Gateway は `notebook` 環境では `qwen3:8b` を基本にし、`assistant_fast` / `assistant_standard` / `assistant_quality` / `report_quality` / `fallback` の profile を選んで timeout と token budget を決めます。高性能環境で `environment_profile: "desktop"` や `"server"` を使う場合は、quality profile を将来の大型モデルへ差し替えられます。

SMAI 親アプリから Gateway へ接続する opt-in live smoke 確認例:

```powershell
$env:SMAI_ASSISTANT_GATEWAY_LIVE_SMOKE = "1"
$env:SMAI_ASSISTANT_GATEWAY_BASE_URL = "http://127.0.0.1:8088"
$env:SMAI_ASSISTANT_GATEWAY_MODEL = "qwen3:8b"
..\venv_SMAI\Scripts\python.exe -m pytest ..\tests\test_assistant_gateway_live_smoke.py -q
Remove-Item Env:SMAI_ASSISTANT_GATEWAY_LIVE_SMOKE
Remove-Item Env:SMAI_ASSISTANT_GATEWAY_BASE_URL
Remove-Item Env:SMAI_ASSISTANT_GATEWAY_MODEL
```

`SMAIアシスタント` 画面の通常チャット送信は、UIにON/OFFを出さずに Gateway 接続を既定で試します。Gateway が未起動、timeout、schema validation failure、LLM JSON不正、空応答の場合は SMAI 側の deterministic fallback に戻ります。

SMAI 親側の context-answer 呼び出しは、SMAI Assistant intent と read-only Tool結果の要約を `user_question` 内に含めることがあります。Gateway は SMAI 固有moduleを importせず、`app_help`、`stock_summary`、`forecast_risk_compare`、`news_materials`、`decision_report_draft`、`free_chat` などの intent marker をプロンプト指示として読み、同じJSON response contractに沿って `materials` / `cautions` / `next_checkpoints` を返します。`answer` はSMAIナビの自然な会話応答から始め、構造化整理は必要に応じて各配列へ分けます。Gateway 側もスコア、ランキング、予測値、売買判断は変更しません。
`qwen3:8b` は thinking 出力が長くなりやすいため、Gateway は Ollama chat API に `think: false` を指定します。LLM の構造化JSONに文字化け、`????`、不正JSON、空項目がある場合も、画面には文脈由来の安全な回答を返します。

### Ollama ありの opt-in live smoke

Ollama を起動し、モデル取得後にだけ実行します。通常 CI / 通常確認には含めません。

```powershell
ollama pull qwen3:8b
$env:SMAI_AI_GATEWAY_LIVE_SMOKE = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_live_ollama_smoke.py -q
Remove-Item Env:SMAI_AI_GATEWAY_LIVE_SMOKE
```

SMAI の既存仮想環境から実行する場合:

```powershell
$env:SMAI_AI_GATEWAY_LIVE_SMOKE = "1"
..\venv_SMAI\Scripts\python.exe -m pytest tests/test_live_ollama_smoke.py -q
Remove-Item Env:SMAI_AI_GATEWAY_LIVE_SMOKE
```

Ollama 未起動、base URL 誤り、model 未取得、timeout の場合は、`code` と `retryable` を含むエラー detail を返します。
