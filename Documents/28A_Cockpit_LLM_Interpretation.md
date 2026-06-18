# Phase 28-A Cockpit LLM Interpretation MVP

## 目的

`AI解釈メモ` は、銘柄コックピットに集まった価格、予測、Investment Score、Research Evidence、AI材料分析を、ユーザーが読みやすい形に整理する参考パネルです。

LLM は説明と整理だけを担当します。Ranking score、Forecast、Advanced Forecast consensus、Investment Score、AI総合、Research Score、売買判断、Assistantの自動外部取得には反映しません。

## 設定

既定は disabled です。live 接続確認を行う場合だけ、次の設定例を使います。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\cockpit_interpretation_example.yaml"
```

通常テストや CI ではこの設定を使いません。

## Gateway 連携

親 SMAI は既存 `smai-ai-gateway` `/api/v1/context-answer` を使い、`task_type=cockpit_interpretation` を渡します。新しい endpoint は追加していません。

送信 context は `AssistantContextBundle` 形式で、以下の短い要約だけを含みます。

- 価格サマリー
- AI予測サマリー
- Investment Score の総合 / 内訳
- Research Evidence の短い出典行
- AI材料分析の要約
- warnings / missing fields

Provider raw fields、debug logs、外部source本文全文は送信しません。

## Validation / fallback

Gateway 応答はそのまま表示せず、次を検証します。

- Gateway status が `ok`
- referenced section / evidence id が context 内に存在する
- 売買推奨や断定的な禁止表現がない
- スコア、予測値、ランキングを変更したような表現がない
- 長すぎる文は表示用に短縮し warning を付ける

失敗時は deterministic fallback の簡易メモを表示します。fallback reason は `disabled`、`gateway_unavailable`、`gateway_timeout`、`gateway_http_error`、`malformed_json`、`validation_error`、`wrong_symbol`、`unknown_evidence`、`policy_violation`、`cache_miss`、`cache_corrupt`、`provider_error` を使います。

## Cache

cache key は `task_type=cockpit_interpretation`、symbol、as_of、context hash、prompt version、schema version、model、Gateway profile で作ります。同一 context は cache hit し、context / prompt / schema / model / profile が変わると miss します。

## UI

銘柄コックピットでは `AI材料分析` の次に `AI解釈メモ` を表示します。

表示項目:

- 全体の読み方
- 強材料
- 注意材料
- 矛盾・不確実性
- 次に確認すべき材料
- warnings / missing fields
- `LLM接続: disabled` / `fallback` / `live` / `validation error`
- provider / model / profile / generated_at / fallback_reason

必ず次の境界を表示します。

```text
このAI解釈メモは、価格・予測・Research Evidence・AI材料分析を読み解くための参考情報です。
売買推奨ではなく、Ranking・予測・Investment Scoreには反映していません。
```

## 確認

通常確認:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests\interpretation\test_cockpit_interpretation.py tests\test_ui_cockpit_interpretation.py -q --basetemp outputs\work\pytest_tmp_phase28a -p no:cacheprovider
.\venv_SMAI\Scripts\python.exe -m ruff check backend\interpretation ui\app.py tests\interpretation\test_cockpit_interpretation.py tests\test_ui_cockpit_interpretation.py --no-cache
```

Playwright panel smoke:

```powershell
.\venv_SMAI\Scripts\python.exe tools\playwright_cockpit_interpretation_panel_smoke.py
```

実 Gateway / Ollama smoke は任意です。通常 CI では要求しません。
