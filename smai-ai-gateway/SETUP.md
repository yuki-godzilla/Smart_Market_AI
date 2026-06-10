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
