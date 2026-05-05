# 10_UI_Guide

#### [BACK TO README](../README.md)

## Purpose / 目的

This document explains how to run and manually check the minimal Smart Market AI Streamlit UI locally.
この文書は、Smart Market AI の最小 Streamlit UI をローカルで起動し、手動確認する手順をまとめます。

The current UI is an MVP screen for the Portfolio-to-Risk rebalance-check workflow. It does not send orders to a broker or execution provider.
現在の UI は Portfolio-to-Risk rebalance-check workflow 向けの MVP 画面です。broker や execution provider に注文は送信しません。

## Run / 起動方法

Install dependencies if needed.
必要に応じて依存関係をインストールします。

```powershell
.\venv_SMAI\Scripts\python.exe -m pip install -r setup\requirements.txt -r setup\requirements-dev.txt
```

Run the Streamlit UI.
Streamlit UI を起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

To run with the deterministic CSV provider, set `SMAI_CONFIG_FILE` first.
決定的な CSV provider で確認する場合は、先に `SMAI_CONFIG_FILE` を指定します。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

## What You Can Check / 画面で確認できること

- Runtime settings: active provider, config source, and CSV data directory when using `csv`.
  Runtime 設定: 使用中の provider、設定ファイル、`csv` 利用時の CSV data directory。
- Sample input selection: `Default rebalance` and `No trades`.
  サンプル入力切り替え: `Default rebalance` と `No trades`。
- Sample-specific input state: switching samples refreshes the account, cash, positions, and targets fields for that sample.
  サンプル別入力状態: サンプルを切り替えると、そのサンプル用の account、cash、positions、targets 入力に切り替わります。
- Account, as-of date, JPY cash, positions JSON, and target allocations JSON.
  account、評価日、JPY cash、positions JSON、target allocations JSON。
- Rebalance result summary, current positions, target allocations, proposed trades, risk breaches, and raw JSON.
  リバランス結果 summary、現在ポジション、目標配分、提案取引、risk breach、raw JSON。

## Expected Manual Checks / 手動確認ポイント

With `Default rebalance`, the UI should generate an AAPL `BUY` proposal and show a `BLOCK` risk status with breach rows.
`Default rebalance` では、AAPL の `BUY` 提案が生成され、risk status は `BLOCK`、breach 行が表示されます。

With `No trades`, the UI should generate zero proposed trades and show `NO_TRADES`, because Risk is skipped when there are no generated trades.
`No trades` では、提案取引が 0 件になり、生成取引がないため Risk は実行されず `NO_TRADES` が表示されます。

If `Cash JPY` is not a decimal number, the UI should show a clear cash-input error.
`Cash JPY` が decimal number でない場合、cash 入力エラーが表示されます。

If positions or targets JSON is invalid, the UI should show a JSON validation error.
positions または targets JSON が不正な場合、JSON validation error が表示されます。

## MVP Constraints / MVP 制約

- The UI is for local manual verification.
  UI はローカル手動確認用です。
- The UI currently targets only the Portfolio-to-Risk workflow.
  現在は Portfolio-to-Risk workflow のみを対象にしています。
- The default provider is deterministic `mock`.
  デフォルト provider は deterministic な `mock` です。
- `SMAI_CONFIG_FILE` can switch the UI to the deterministic `csv` provider.
  `SMAI_CONFIG_FILE` で deterministic な `csv` provider に切り替えできます。
