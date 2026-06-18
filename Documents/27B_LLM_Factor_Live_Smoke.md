# Phase 27-B LLM Factor Live Smoke / Cockpit UX確認

## 目的

Phase 27-A で追加した `SMAI LLM Factor` の live generation を、実 Gateway / Ollama で確認するための opt-in 手順です。通常の pytest / CI は引き続き network-free で、ここにある live smoke は手動確認用です。

LLM Factor は Cockpit の `AI材料分析` に参考表示するだけです。Ranking score、AI総合、Forecast、Investment Score、投資判断、Assistant自動実行には反映しません。

## 設定例

live 接続用の最小設定は [config/llm_factor_live_example.yaml](../config/llm_factor_live_example.yaml) です。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\llm_factor_live_example.yaml"
```

通常確認や CI ではこの設定を使わず、既定の `llm_factor.live.enabled=false` を維持します。

## Gateway / Ollama 起動

別ターミナルで Gateway を起動します。

```powershell
cd .\smai-ai-gateway
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8088
```

Ollama model が未導入の場合は、Gateway の設定に合わせて導入します。

```powershell
ollama pull qwen3:14b
```

接続確認:

```powershell
curl.exe http://127.0.0.1:8088/health
curl.exe http://127.0.0.1:8088/health/ready
```

## 親 SMAI の live smoke

実 Gateway / Ollama まで到達させる確認は、明示 opt-in の pytest で実行します。

```powershell
$env:SMAI_LLM_FACTOR_GATEWAY_LIVE_SMOKE = "1"
$env:SMAI_LLM_FACTOR_GATEWAY_BASE_URL = "http://127.0.0.1:8088"
$env:SMAI_LLM_FACTOR_GATEWAY_PROFILE = "desktop_analysis"
.\venv_SMAI\Scripts\python.exe -m pytest tests\test_llm_factor_gateway_live_smoke.py -q --basetemp outputs\work\pytest_tmp_phase27b_live -p no:cacheprovider
```

任意で model を固定する場合:

```powershell
$env:SMAI_LLM_FACTOR_GATEWAY_MODEL = "qwen3:14b"
```

成功時の期待値:

- `gateway_status == "ok"`
- `fallback_reason is None`
- `provider` が `deterministic` ではない
- `model_name` と `gateway_profile` が表示される
- 出典が残る

失敗時は Cockpit で fallback 表示に戻ります。標準化した理由は `disabled`、`gateway_unavailable`、`gateway_timeout`、`gateway_http_error`、`malformed_json`、`validation_error`、`wrong_symbol`、`unknown_evidence`、`stale_source`、`cache_miss`、`cache_corrupt`、`provider_error` です。

## Cockpit UX 確認

`銘柄コックピット` の `AI材料分析` パネルで、次の状態を確認します。

- disabled: `LLM接続: disabled`、理由は `設定で無効`
- fallback: `LLM接続: fallback`、理由は `LLM Gatewayに接続できません` など
- live: `LLM接続: live`、`provider`、`model`、`profile`、生成時刻が表示される
- validation warning: 古い出典、version mismatch、強弱材料の矛盾、長すぎる応答、不足項目が確認メモに表示される
- reference note: `Ranking・予測・Investment Scoreには反映していません` が表示される

Playwright の network-free 表示確認:

```powershell
.\venv_SMAI\Scripts\python.exe tools\playwright_llm_factor_panel_smoke.py
```

この確認は実 Cockpit パネルの HTML helper を使って disabled / fallback / live の3状態を描画し、スクリーンショットを `outputs/work/playwright_llm_factor_panel_smoke/` に保存します。Streamlit 全体の手動確認では、上記 live 設定を有効にして Cockpit を開き、`AI材料分析` のステータス表示を目視確認します。

## Validation / fallback 観点

親 SMAI は Gateway 応答をそのまま採用せず、次の条件で fallback または confidence cap / warning にします。

- wrong symbol: fallback `wrong_symbol`
- unknown evidence id: fallback `unknown_evidence`
- high confidence without evidence: fallback `validation_error`
- malformed / empty JSON: fallback `malformed_json` または `validation_error`
- confidence out of range: fallback `validation_error`
- stale / future source date: warning と confidence cap
- contradictory positive / negative materials: warning と confidence cap
- schema / prompt version mismatch: warning と confidence cap
- overlong output: 表示用に truncate し warning

## Cache 確認

live cache key は `symbol`、`as_of`、context hash、model、prompt version、schema version、Gateway profile を含みます。prompt / model / schema / profile を変えると cache miss になり、同一条件では cache hit になります。cache が壊れている場合は deterministic fallback または再生成に戻し、通常テストでは network に依存しません。

## CI 境界

通常 CI に含めるのは deterministic tests、mock transport tests、Playwright panel smoke までです。`SMAI_LLM_FACTOR_GATEWAY_LIVE_SMOKE=1` を必要とする実 Gateway / Ollama smoke は手動確認専用です。
