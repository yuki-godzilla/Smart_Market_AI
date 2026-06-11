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
