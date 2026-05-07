# 10_UI_Guide

#### [BACK TO README](../README.md)

## 目的

この文書は、現在の Streamlit UI をローカルで起動し、手動確認する方法をまとめます。

UI は Portfolio-to-Risk rebalance-check workflow 向けの MVP 画面です。
broker や execution provider へ注文を送信しません。

## 起動

必要に応じて依存関係をインストールします。

```powershell
.\venv_SMAI\Scripts\python.exe -m pip install -r setup\requirements.txt -r setup\requirements-dev.txt
```

Streamlit を起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

## CSV MarketData で起動

UI はデフォルトで deterministic な `mock` provider を使います。
ローカル CSV provider を使う場合:

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

## UI で確認できること

- Runtime settings: 使用中の provider、config source、CSV data directory
- `7203.T` と `AAPL` の sample symbol reference
- `Default rebalance` と `No trades` の sample selector
- `examples/rebalance_scenarios/` から読み込まれる file-backed sample
- 壊れた scenario JSON がある場合の読み込みエラーメッセージ
- account、as-of date、JPY cash、positions JSON、target allocations JSON
- 現在の 2 銘柄 target allocation JSON を再生成する AAPL target-weight slider
- rebalance summary、current positions、target allocations、allocation comparison、proposed trades、risk breaches
- raw JSON result と local JSON download

## 手動確認ポイント

`Default rebalance` を使う場合:

- UI は `AAPL` の `BUY` proposal を 1 件生成します。
- Risk status は `BLOCK` になります。
- breach rows には dividend-yield data 欠損と concentration が含まれます。

`No trades` を使う場合:

- proposed trades は 0 件になります。
- Risk status は `NO_TRADES` になります。
- 生成された trade がないため、Risk は実行されません。

不正入力の確認:

- Decimal ではない `Cash JPY` は cash-input error になります。
- 不正な positions JSON は JSON validation error になります。
- 不正な targets JSON は JSON validation error になります。
- `examples/rebalance_scenarios/` 配下の scenario JSON が壊れている場合は、対象ファイル名と原因をまとめた scenario load error になります。

## MVP 制約

- UI はローカル手動確認用です。
- 現在の UI は Portfolio-to-Risk workflow のみを対象にしています。
- デフォルト provider は deterministic な `mock` です。
- `SMAI_CONFIG_FILE` で deterministic な `csv` に切り替えられます。
- broker や execution provider は呼び出しません。
