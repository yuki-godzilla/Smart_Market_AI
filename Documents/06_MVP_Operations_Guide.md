# MVP Operations Guide

#### [BACK TO README](../README.md)

## 1. 目的

この文書は、現在の Smart Market AI MVP をローカルで起動、確認、説明するための運用ガイドです。

以前は API 仕様、CSV 形式、手動確認手順、UI ガイド、外部 MarketData provider 準備を個別ファイルに分けていました。
内容が細かく分散して視認性が落ちていたため、MVP の運用に必要な情報をこの 1 ファイルへ統合しています。

## 2. 現在の MVP 範囲

実装済み:

- FastAPI backend
- `GET /health`
- `POST /risk/pre-trade-check`
- `POST /portfolio/rebalance-check`
- deterministic な `mock` / `csv` MarketData provider
- Portfolio-to-Risk rebalance-check workflow
- Streamlit UI
- JSON / CSV / Markdown / manifest / ZIP report export
- 外部 MarketData provider の opt-in 準備

未実装:

- `yahoo` / `polygon` などの live provider adapter 本体
- broker への live order 送信
- Execution workflow
- screening / forecasting / multi-model scoring の実装

現在の MVP は、ローカル検証と説明用です。
外部 API へ接続せず、broker や execution provider へ注文を送りません。

## 3. API 起動と確認

FastAPI を起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

確認 URL:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

主な API:

- `GET /health`
  - API が起動していることを確認します。
- `POST /risk/pre-trade-check`
  - trade intent を deterministic な MVP リスクルールで評価します。
- `POST /portfolio/rebalance-check`
  - 現在 portfolio と target allocation から rebalance proposal を作り、必要に応じて Risk check へ接続します。

エラー応答は JSON です。

```json
{
  "code": "APP-2002",
  "message": "Target weights must not exceed 1",
  "details": {
    "target_weight_sum": "1.1"
  }
}
```

主な status code:

- `422`: request validation、domain validation、provider schema mismatch
- `429`: provider rate limit
- `502`: data source error
- `503`: provider unavailable
- `504`: provider timeout

## 4. 手動確認 workflow

サーバーを起動せずに rebalance-check flow を確認する場合は、demo script を使います。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_rebalance_check_demo.py
```

期待される結果:

- `proposal.trades` に `AAPL` の `BUY` trade が 1 件含まれる
- `risk_decision.status` が `BLOCK` になる
- `risk_decision.breaches` に dividend-yield data 欠損と concentration が含まれる

FastAPI 経由で確認する場合:

```powershell
$body = Get-Content .\examples\portfolio_rebalance_check.json -Raw
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/portfolio/rebalance-check `
  -ContentType "application/json" `
  -Body $body
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

期待される response:

```json
{
  "status": "ok"
}
```

## 5. CSV MarketData provider

既定 provider は deterministic な `mock` です。
ローカル CSV を使う場合は、`SMAI_CONFIG_FILE` で設定ファイルを指定します。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe .\tools\run_rebalance_check_demo.py
```

API / UI 起動時も同じ設定を使えます。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

設定例:

```yaml
dataaccess:
  provider: csv
  csv_data_dir: data/marketdata
```

必要な CSV:

```text
symbols.csv
ohlcv.csv
fx_rates.csv
```

サンプル配置:

```text
config/csv_example.yaml
data/marketdata/symbols.csv
data/marketdata/ohlcv.csv
data/marketdata/fx_rates.csv
```

`symbols.csv`:

```csv
raw,exchange,code,currency
AAPL,NASDAQ,AAPL,USD
7203.T,TSE,7203,JPY
```

`ohlcv.csv`:

```csv
symbol,ts,open,high,low,close,volume
AAPL,2026-04-09T00:00:00+00:00,173.00,176.00,172.00,175.00,62000000
```

`fx_rates.csv`:

```csv
pair,rate,ts,source
USDJPY,150.00,2026-04-09T00:00:00+00:00,csv
```

MVP 制約:

- `fx_rates.csv` の対応 pair は現在 `USDJPY` のみ
- `ohlcv.csv` は日次データを想定
- 必須列がない場合はエラー
- 余分な列は無視される

## 6. Streamlit UI

Streamlit UI を起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

UI で確認できる主な内容:

- Market Data tab での provider metadata、quote、OHLCV summary、FX、error details
- runtime settings
- sample symbol reference
- `Default rebalance` / `No trades` sample selector
- `examples/rebalance_scenarios/` の file-backed sample
- account、as-of date、cash、positions JSON、target allocations JSON
- AAPL target-weight slider
- rebalance summary
- current positions
- target allocations
- allocation comparison
- proposed trades
- risk breaches
- raw JSON result
- JSON / CSV / Markdown / ZIP download
- validated request JSON download
- report manifest

別ディレクトリの scenario JSON を使う場合:

```powershell
$env:SMAI_REBALANCE_SCENARIO_DIR = ".\my_rebalance_scenarios"
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

指定パスが存在しない、またはディレクトリでない場合は、UI に scenario load error が表示されます。

MVP export は JSON、CSV、Markdown、manifest、ZIP までです。
PDF / Excel は将来の reporting 拡張で扱います。

## 7. 外部 MarketData provider 準備

現在使える provider:

| provider | 実装状態 | network | 用途 |
| --- | --- | --- | --- |
| `mock` | 実装済み | 不要 | 既定の MVP 確認 |
| `csv` | 実装済み | 不要 | ローカル CSV 確認 |
| `yahoo` | 未実装 | 将来必要 | live provider 候補 |
| `polygon` | 未実装 | 将来必要 | live provider 候補 |

live provider を指定するには、設定ファイルで `dataaccess.allow_external_providers: true` を明示する必要があります。

```yaml
dataaccess:
  provider: yahoo
  allow_external_providers: true
```

ただし、現時点では live provider adapter 本体が未実装です。
opt-in しても外部 API へは接続せず、未実装であることを示す domain error を返します。
Phase 10 の完了時点では、明示 opt-in した live provider から実データを取得し、Streamlit UI 上で取得結果と provider 状態を確認できることを目標にします。

通常のローカル確認では、次のどちらかを使います。

```yaml
dataaccess:
  provider: mock
  allow_external_providers: false
```

```yaml
dataaccess:
  provider: csv
  csv_data_dir: data/marketdata
  allow_external_providers: false
```

provider capability は `backend/marketdata/provider_registry.py` で管理します。
将来の live provider adapter の依存や module 予定は `backend/marketdata/live_provider_adapters.py` で管理します。
provider adapter の共通 interface は `backend/marketdata/provider_adapters.py` の `MarketDataProviderAdapter` protocol です。
設定から provider adapter を作る入口は `backend/marketdata/provider_factory.py` の `create_market_data_provider_adapter()` です。

## 8. ローカル検証

基本確認:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
```

個別確認:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend tests --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy .
```

Markdown の UTF-8 確認:

```powershell
.\venv_SMAI\Scripts\python.exe -c "from pathlib import Path; [p.read_text(encoding='utf-8') for p in Path('.').rglob('*.md') if '.git' not in p.parts]; print('markdown utf-8 ok')"
```

## 9. 更新ルール

API、CSV provider、manual workflow、UI、外部 provider 準備、検証コマンドが変わる場合は、この文書を更新します。
実装状態や次の作業方針が変わる場合は、あわせて `PROJECT_CONTEXT.md` と `Documents/05_Implementation_Roadmap.md` も更新します。
