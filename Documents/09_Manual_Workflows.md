# 09_Manual_Workflows

#### [BACK TO README](../README.md)

## 目的

この文書は、現在の Smart Market AI MVP をローカルで手動確認する手順をまとめます。

現在の workflow は deterministic です。

- デフォルトではローカルの `mock` market data を使います。
- `SMAI_CONFIG_FILE` により、ローカル CSV ファイルも使えます。
- 外部 market-data API には接続しません。
- broker や execution provider へ注文を送信しません。

## Portfolio Rebalance Check

`POST /portfolio/rebalance-check` は、現在ポジションと目標配分を受け取ります。

処理の流れ:

1. 現在の portfolio を JPY で評価します。
2. solver なしの rebalance proposal を生成します。
3. 生成された trade を Risk pre-trade check に渡します。
4. trade が生成されない場合、Risk は実行しません。

サンプル request:

```text
examples/portfolio_rebalance_check.json
```

## サーバーなしで確認

demo script は FastAPI app を `TestClient` 経由で呼び出すため、サーバー起動は不要です。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_rebalance_check_demo.py
```

期待される結果:

- `proposal.trades` に `AAPL` の `BUY` trade が 1 件含まれます。
- `risk_decision.status` は `BLOCK` です。
- `risk_decision.breaches` に `R5:min_dividend_yield:AAPL` と `R3:max_concentration` が含まれます。

## CSV Provider で確認

demo script を実行する前に `SMAI_CONFIG_FILE` を設定します。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe .\tools\run_rebalance_check_demo.py
```

使用されるファイル:

```text
config/csv_example.yaml
data/marketdata/symbols.csv
data/marketdata/ohlcv.csv
data/marketdata/fx_rates.csv
```

期待される結果は、デフォルトの mock provider 確認と同じです。

## API サーバーを起動して確認

FastAPI を起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

別の PowerShell から sample request を送ります。

```powershell
$body = Get-Content .\examples\portfolio_rebalance_check.json -Raw
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/portfolio/rebalance-check `
  -ContentType "application/json" `
  -Body $body
```

Swagger UI は次の URL で確認できます。

```text
http://127.0.0.1:8000/docs
```

## Health Check

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

期待される response:

```json
{
  "status": "ok"
}
```

## 注意

- デフォルト provider は `mock` です。
- CSV provider は deterministic で、ローカルファイルだけを読みます。
- Decimal 値は JSON 文字列として送れます。
- 現在の MVP はローカル確認と説明用であり、live trading 用ではありません。

## ローカル検証

ローカル MVP の基本確認は次の helper でまとめて実行できます。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
```

この helper は cache-free の Black check、`ruff`、`pytest` を順に実行します。
