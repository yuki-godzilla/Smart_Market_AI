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

Ollama を起動し、ノートPC開発用の軽量モデルを取得します。

```powershell
ollama pull qwen3:1.7b
```

デスクトップ環境では必要に応じて `qwen3:8b`、`qwen3:14b`、`qwen3:30b` も取得します。

## 3. .env

`.env.example` を `.env` にコピーし、必要に応じて値を変更します。

```powershell
copy .env.example .env
```

主な設定:

- `SMAI_OLLAMA_BASE_URL`: 既定 `http://localhost:11434`
- `SMAI_LLM_PROFILE`: 既定 `notebook_dev`
- `SMAI_OLLAMA_MODEL`: 既定 `qwen3:1.7b`
- `OLLAMA_BASE_URL` / `DEFAULT_LLM_MODEL`: legacy alias
- `REQUEST_TIMEOUT_SECONDS`: 既定 `30`

推奨モデル:

| 環境 | profile | 推奨モデル | 用途 |
| --- | --- | --- | --- |
| ノートPC | `notebook_dev` | `qwen3:1.7b` | 軽量開発・疎通確認 |
| ノートPC標準 | `notebook_standard` | `qwen3:4b` | 標準開発・短めの整理 |
| デスクトップ通常 | `desktop_fast` | `qwen3:8b` | Copilot・要約 |
| デスクトップ高精度 | `desktop_analysis` | `qwen3:14b` | 銘柄分析・RAG統合 |
| 高負荷分析 | `desktop_heavy` | `qwen3:30b` | 週次/月次レポート |

## 4. 起動

```bat
run_server.bat
```

手動で起動する場合:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8088
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

Ollama / model まで含めた readiness 確認:

```powershell
curl http://127.0.0.1:8088/health/ready
```

期待例:

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

モデル確認:

```powershell
curl http://127.0.0.1:8088/models
```

設定中 model が未導入の場合は `Please run: ollama pull qwen3:1.7b` のような案内が返ります。

### 新PCで `gateway_unavailable` が出る場合の切り分け

`gateway_unavailable` は「SMAI本体から `smai-ai-gateway` に到達できない」状態です。Ollama生成の遅さや `provider_timeout` とは分けて確認します。

```powershell
ollama list
curl http://localhost:11434/api/tags
curl http://127.0.0.1:8088/health
curl http://127.0.0.1:8088/health/ready
curl http://127.0.0.1:8088/models
```

- `ollama list` / `/api/tags` に `qwen3:1.7b` が無い: `ollama pull qwen3:1.7b`
- `/api/tags` が応答しない: Ollama アプリ/サービス、`SMAI_OLLAMA_BASE_URL`、firewall を確認
- `/health` が応答しない: `smai-ai-gateway` が未起動、または SMAI 側 `base_url` / port が不一致。親SMAIの `HttpAssistantGatewayClient` は `http://127.0.0.1` / `localhost` の未起動 Gateway を画面遷移時の診断またはチャット送信時に自動起動します。自動起動を止める場合は `SMAI_ASSISTANT_GATEWAY_AUTOSTART=0` を指定します。
- `/health` はOKで `/health/ready` が `degraded`: Gateway は起動済み、Ollama未接続または model 未取得
- SMAI画面だけ `gateway_unavailable`: SMAI 側 `assistant.gateway.base_url` が Gateway 起動URLと一致しているか確認

チャット確認例:

```powershell
curl -X POST http://127.0.0.1:8088/api/v1/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"こんにちは\",\"system_prompt\":\"You are a helpful assistant.\",\"profile\":\"notebook_dev\"}"
```

要約確認例:

```powershell
curl -X POST http://127.0.0.1:8088/api/v1/summarize ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"確認したい文章の要点を短く整理してください。\",\"purpose\":\"general_summary\",\"profile\":\"desktop_fast\"}"
```

context answer 確認例:

```powershell
curl -X POST http://127.0.0.1:8088/api/v1/context-answer ^
  -H "Content-Type: application/json" ^
  -d "{\"user_question\":\"AI予測インサイトでは何を見る？\",\"profile\":\"notebook_dev\",\"context\":{\"bundle_id\":\"bundle-1\",\"title\":\"銘柄コックピット\",\"sections\":[{\"section_id\":\"forecast-1\",\"title\":\"AI予測インサイト\",\"source_kind\":\"forecast\",\"summary\":{\"中心予測\":\"+1.2%\",\"予測レンジ\":\"-3.0%〜+4.5%\"},\"included_fields\":[\"中心予測\",\"予測レンジ\",\"信頼度\"],\"warnings\":[\"予測レンジが広めです。\"],\"notes\":[\"根拠資料とデータ品質も確認します。\"]}]}}"
```

Assistant Tool Planner 確認例:

```powershell
curl -X POST http://127.0.0.1:8088/api/v1/assistant/tool-plan ^
  -H "Content-Type: application/json" ^
  -d "{\"user_question\":\"この銘柄の根拠を確認したい\",\"current_page\":\"cockpit\",\"context_summary\":\"現在画面: 銘柄コックピット / AI調査: missing\",\"available_actions\":[{\"action_id\":\"open_research_section\",\"label\":\"根拠資料を見る\",\"description\":\"Research Evidenceを確認します。\",\"action_type\":\"navigation\",\"requires_confirmation\":false,\"is_external_fetch\":false,\"enabled\":true},{\"action_id\":\"update_research\",\"label\":\"AI調査を更新\",\"description\":\"外部ソース候補を確認します。\",\"action_type\":\"data_fetch\",\"requires_confirmation\":true,\"is_external_fetch\":true,\"enabled\":true}],\"constraints\":{\"allowed_action_ids\":[\"open_research_section\",\"update_research\"],\"max_steps\":5},\"preferred_profile\":\"assistant_fast\"}"
```

親SMAIの汎用 Assistant service から試す場合は、Gateway を起動したまま、SMAI 側の `SMAI_CONFIG_FILE` に次のような設定を指定します。通常確認では使わず、既定の `enabled: false` を維持します。専用 `SMAIアシスタント` workspace は画面内で Gateway 接続を既定で試し、失敗時は deterministic fallback に戻ります。

```yaml
assistant:
  gateway:
    enabled: true
    base_url: "http://127.0.0.1:8088"
    context_answer_path: "/api/v1/context-answer"
    timeout_seconds: 90
    execution_mode: "auto"
    environment_profile: "notebook"
```

optional LLM Tool Planner を親SMAIから試す場合は、別設定として明示ONにします。通常確認では `assistant.llm_planner.enabled=false` の既定値を維持します。Gateway は action 案を返すだけで、親SMAIが validation / fallback / UI採用を行います。

```yaml
assistant:
  llm_planner:
    enabled: true
    gateway_url: "http://127.0.0.1:8088"
    endpoint_path: "/api/v1/assistant/tool-plan"
    timeout_seconds: 15
    max_steps: 5
    fallback_to_deterministic: true
    preferred_profile: "assistant_fast"
```

SMAI 親は通常 `model` を固定指定せず、会話 intent から `task_type` を渡します。Gateway は `SMAI_LLM_PROFILE` または request の `profile` から `notebook_dev` / `notebook_standard` / `desktop_fast` / `desktop_analysis` / `desktop_heavy` を選び、timeout と token budget を決めます。request の `model` は最優先で model 名を上書きします。

Cockpit `AI解釈メモ` を試す場合は、親SMAI側で次のように明示 opt-in します。通常確認では `enabled: false` の既定値を維持し、Gateway未起動やvalidation failure時はSMAI側のdeterministic fallback表示に戻します。

```yaml
llm_interpretation:
  cockpit:
    enabled: true
    base_url: "http://127.0.0.1:8088"
    context_answer_path: "/api/v1/context-answer"
    timeout_seconds: 45
    execution_mode: "auto"
    environment_profile: "desktop"
    preferred_profile: "desktop_fast"
```

SMAI 親アプリから Gateway へ接続する opt-in live smoke 確認例:

```powershell
$env:SMAI_ASSISTANT_GATEWAY_LIVE_SMOKE = "1"
$env:SMAI_ASSISTANT_GATEWAY_BASE_URL = "http://127.0.0.1:8088"
$env:SMAI_ASSISTANT_GATEWAY_MODEL = "qwen3:1.7b"
..\venv_SMAI\Scripts\python.exe -m pytest ..\tests\test_assistant_gateway_live_smoke.py -q
Remove-Item Env:SMAI_ASSISTANT_GATEWAY_LIVE_SMOKE
Remove-Item Env:SMAI_ASSISTANT_GATEWAY_BASE_URL
Remove-Item Env:SMAI_ASSISTANT_GATEWAY_MODEL
```

`SMAIアシスタント` 画面の通常チャット送信は、UIにON/OFFを出さずに Gateway 接続を既定で試します。Gateway が未起動、timeout、schema validation failure、LLM JSON不正、空応答の場合は SMAI 側の deterministic fallback に戻ります。

Phase 30-H以降は、親SMAIがAssistant初回描画時にbackgroundで `GET /models` を確認します。この確認はStreamlit初期表示を待たせず、失敗しても通常UIとdeterministic fallbackを利用できます。chat completionを使う追加warmupは親設定で既定OFFです。
画面上部は SMAIナビ header、チャット幅に揃えた `新しい会話` action、参照中の材料 chips、6つの相談カード、下部 composer の構成です。初回のSMAIナビ発話は、ユーザー送信またはカード選択後にだけ表示します。

`free_chat` / `identity` / `app_help` / `capability_help` / `screen_guidance` は短い通常会話用の `llm_micro` 経路です。SMAI 親は Tool Layer / RAG / news / symbol-specific context / 長い履歴を送らず、Gateway 側は最小 context、`/no_think`、Ollama `think: false` で応答を軽量化します。runtime は task_type を主軸にしつつ、実際の Ollama model ごとに token budget を調整します。軽量会話の目安は `qwen3:1.7b` が 280-300 tokens、`qwen3:4b` が 320 tokens、`qwen3:8b` が 360-450 tokens、`qwen3:14b` が 360-500 tokens です。挨拶、名前質問、できること質問、使い方質問もまず LLM へ投げ、低品質な短文回答は 1 回だけ再生成し、provider timeout などの失敗時だけ自然な fallback に寄せます。SMAI 親に画面固有の report context がない場合も、即時 fallback せず最小のSMAIアシスタント文脈で Gateway を呼びます。

SMAI 親側の context-answer 呼び出しは、SMAI Assistant intent と read-only Tool結果の要約を `user_question` 内に含めることがあります。Gateway は SMAI 固有moduleを importせず、`app_help`、`stock_summary`、`forecast_risk_compare`、`news_materials`、`decision_report_draft`、`free_chat`、`cockpit_interpretation` などの intent marker をプロンプト指示として読み、同じJSON response contractに沿って `materials` / `cautions` / `next_checkpoints` を返します。`answer` はSMAIナビの自然な会話応答から始め、構造化整理は必要に応じて各配列へ分けます。Gateway 側もスコア、ランキング、予測値、売買判断は変更しません。
Qwen3 系は thinking 出力が長くなりやすいため、Gateway は Ollama chat API に `think: false` を指定します。LLM の構造化JSONに文字化け、`????`、不正JSON、空項目がある場合も、画面には文脈由来の安全な回答を返します。

### Ollama ありの opt-in live smoke

Ollama を起動し、モデル取得後にだけ実行します。通常 CI / 通常確認には含めません。

```powershell
ollama pull qwen3:1.7b
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
