# 09_Manual_Workflows

#### [BACK TO README](../README.md)

## 目的

この文書は、Smart Market AI の MVP をローカルで手動確認するための手順をまとめます。

ここで扱う手順は外部 API に接続しません。現在の `mock` provider と固定サンプル request を使うため、
同じ入力から同じ結果を再現できます。

## Portfolio Rebalance Check

`POST /portfolio/rebalance-check` は、現在ポジションと目標配分を受け取り、リバランス案を作成します。
生成された取引案がある場合は、Risk の取引前判定にも接続します。

サンプル request は次のファイルです。

```text
examples/portfolio_rebalance_check.json
```

## サーバーを起動せずに確認する

FastAPI の `TestClient` を使うと、サーバーを起動せずに API と同じ処理を確認できます。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_rebalance_check_demo.py
```

期待する結果:

- `proposal.trades` に `AAPL` の `BUY` が1件出る
- `risk_decision.status` は `BLOCK`
- `risk_decision.breaches` に配当利回り不足と集中度の breach が出る

## サーバーを起動して確認する

FastAPI サーバーを起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

別の PowerShell から request を送ります。

```powershell
$body = Get-Content .\examples\portfolio_rebalance_check.json -Raw
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/portfolio/rebalance-check `
  -ContentType "application/json" `
  -Body $body
```

Swagger UI からも確認できます。

```text
http://127.0.0.1:8000/docs
```

## 注意

- この手順はローカル MVP の smoke check です。
- 現在の API は broker や execution provider に注文を送りません。
- データ取得はデフォルトでは `mock` provider を使います。
- `SMAI_CONFIG_FILE` を設定すれば `csv` provider の確認にも進められます。
