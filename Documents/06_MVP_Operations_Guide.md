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

- `polygon` などの追加 live provider adapter 本体
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
- `POST /screening/score`
  - 指定した銘柄の Feature Snapshot を作り、ranking と score breakdown を返します。
- `POST /forecast/evaluate`
  - 指定した銘柄の OHLCV から baseline forecast と walk-forward metrics を返します。

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

Screening score:

```powershell
$body = @{
  symbols = @("AAPL", "7203.T")
  as_of = "2026-04-09"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/screening/score `
  -ContentType "application/json" `
  -Body $body
```

期待される response:

- `rank`
- `total_score`
- `momentum_score`
- `liquidity_score`
- `risk_score`
- `data_quality_score`
- `reasons`

Forecast evaluate:

```powershell
$body = @{
  symbol = "AAPL"
  start = "2026-04-07"
  end = "2026-04-09"
  horizon_days = 1
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/forecast/evaluate `
  -ContentType "application/json" `
  -Body $body
```

期待される response:

- `model_name`
- `latest_forecast.forecast_close`
- `metrics.mae`
- `metrics.rmse`
- `metrics.direction_accuracy`
- `metrics.sample_count`

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
fundamentals.csv
```

サンプル配置:

```text
config/csv_example.yaml
data/marketdata/symbols.csv
data/marketdata/ohlcv.csv
data/marketdata/fx_rates.csv
data/marketdata/fundamentals.csv
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

`fundamentals.csv`:

```csv
symbol,as_of,dividend_yield,market_cap_jpy
AAPL,2026-04-09,0.005,450000000000000
```

MVP 制約:

- `fx_rates.csv` の対応 pair は現在 `USDJPY` のみ
- `ohlcv.csv` は日次データを想定
- `fundamentals.csv` は `as_of` 以前の最新行を使い、`dividend_yield` と `market_cap_jpy` を Feature Snapshot に反映する
- 必須列がない場合はエラー
- 余分な列は無視される

## 6. Streamlit UI

Market Data tab の各結果 section には、見出しとは別に評価中の symbol / 銘柄名が小さく表示されます。

Streamlit UI を起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

UI で確認できる主な内容:

- Market Data tab での forecast chart / metrics、screening score、provider metadata、quote、OHLCV summary、FX、feature snapshot、error details
- Market Data tab では、取得後の chart 付近にある `Forecast days` で 1〜30 日先の forecast horizon を選択
- `Forecast days` の初期値は表示期間から自動設定され、変更時は取得済みデータから chart / metrics だけを再計算
- forecast model の参照期間は取得期間と forecast horizon から自動計算され、UI には `自動計算された参照期間` として表示
- forecast chart の凡例では、各系列をクリックして表示 / 非表示を切り替え可能
- forecast chart では実績価格とモデル別予測線を分け、将来予測の開始位置を確認
- Forecast Summary では ensemble、median forecast、予測レンジ、model agreement / disagreement を確認できる
- forecast metrics は JSON / CSV として保存できる
- Screening Score では forecast agreement を補助的な score / reason として確認できる
- provider の UI 既定値は `yahoo`
- symbol は `Symbol search` と `Symbol` プルダウンで指定し、国内・米国の代表候補を ticker / company name の部分一致で検索して選択できる
- `Symbol search` に入力がある場合は、代表候補に加えて yfinance `Search` の候補も補助的に表示する
- yfinance 検索候補はネットワークや Yahoo 側の応答に依存するため、失敗時は代表候補だけで動作する
- 既知の銘柄は名称を横に表示する
- provider metadata、quote、OHLCV summary、FX、feature snapshot は補助情報として折りたたみ表示

UI のラベル、凡例、指標説明などの文言方針は [07_UI_Wording_Policy.md](./07_UI_Wording_Policy.md) を参照します。
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
Market Data tab の forecast metrics と screening score は、それぞれ JSON / CSV として保存できます。
PDF / Excel は将来の reporting 拡張で扱います。

## 7. 外部 MarketData provider 準備

現在使える provider:

| provider | 実装状態 | network | 用途 |
| --- | --- | --- | --- |
| `mock` | 実装済み | 不要 | 既定の MVP 確認 |
| `csv` | 実装済み | 不要 | ローカル CSV 確認 |
| `yahoo` | opt-in live adapter | 必要 | 最初の live provider |
| `polygon` | 未実装 | 将来必要 | live provider 候補 |

live provider を指定するには、設定ファイルで `dataaccess.allow_external_providers: true` を明示する必要があります。

```yaml
dataaccess:
  provider: yahoo
  allow_external_providers: true
```

`yahoo` は `yfinance` を使う opt-in live adapter として factory から呼ばれます。
`yfinance` が未インストール、provider が応答しない、または取得データが空の場合は domain error として UI に表示されます。
Phase 10 の確認では、明示 opt-in した `yahoo` provider から実データを取得し、Streamlit UI 上で取得結果と provider 状態を確認します。

live provider を UI で確認する例:

```powershell
.\venv_SMAI\Scripts\python.exe -m pip install -r .\setup\requirements.txt
$env:SMAI_CONFIG_FILE = ".\tests\fixtures\config\live_provider_yahoo_opt_in.yaml"
$env:SMAI_YFINANCE_CACHE_DIR = ".\.yfinance_cache"
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

Streamlit の `Market Data` tab で `AAPL` などの symbol と date range を指定し、quote、OHLCV summary、USDJPY FX、provider metadata を確認します。
`unable to open database file` が出る場合は、`SMAI_YFINANCE_CACHE_DIR` に書き込み可能なディレクトリを指定してください。

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
.\venv_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy .
```

Markdown の UTF-8 確認:

```powershell
.\venv_SMAI\Scripts\python.exe -c "from pathlib import Path; [p.read_text(encoding='utf-8') for p in Path('.').rglob('*.md') if '.git' not in p.parts]; print('markdown utf-8 ok')"
```

## 9. 更新ルール

API、CSV provider、manual workflow、UI、外部 provider 準備、検証コマンドが変わる場合は、この文書を更新します。
実装状態や次の作業方針が変わる場合は、あわせて `PROJECT_CONTEXT.md` と `Documents/05_Implementation_Roadmap.md` も更新します。
