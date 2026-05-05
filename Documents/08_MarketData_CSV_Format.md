# 08_MarketData_CSV_Format

#### [BACK TO README](../README.md)

## 目的

この文書は、MarketData の `csv` provider が読むローカル CSV ファイルの形式を説明します。

`csv` provider は外部 API に接続せず、手元の CSV ファイルだけで価格、quote、為替レートを返します。
そのため、テストやローカル検証を deterministic に行えます。

## 設定方法

YAML 設定で `dataaccess.provider` を `csv` にし、`dataaccess.csv_data_dir` に CSV ファイルのある
ディレクトリを指定します。

```yaml
dataaccess:
  provider: csv
  csv_data_dir: data/marketdata
```

PowerShell では次のように設定ファイルを指定して起動します。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\example.yaml"
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

## 必要なファイル

`csv_data_dir` 配下に次の3ファイルを置きます。

```text
symbols.csv
ohlcv.csv
fx_rates.csv
```

リポジトリには手動確認用のサンプルとして、次のディレクトリを用意しています。

```text
data/marketdata
```

このサンプルを使う設定ファイルは次です。

```text
config/csv_example.yaml
```

## `symbols.csv`

銘柄の基本情報を定義します。

```csv
raw,exchange,code,currency
AAPL,NASDAQ,AAPL,USD
7203.T,TSE,7203,JPY
```

列:

- `raw`: API や内部処理で指定する銘柄文字列。
- `exchange`: 取引所名。
- `code`: 銘柄コード。
- `currency`: `JPY` または `USD`。

## `ohlcv.csv`

日次価格と出来高を定義します。

```csv
symbol,ts,open,high,low,close,volume
AAPL,2026-04-09T00:00:00+00:00,173.00,176.00,172.00,175.00,62000000
```

列:

- `symbol`: `symbols.csv` の `raw` と一致する銘柄。
- `ts`: ISO 8601 形式の日時。UTC 推奨。
- `open`: 始値。
- `high`: 高値。
- `low`: 安値。
- `close`: 終値。
- `volume`: 出来高。

`fetch_quotes()` は、指定時刻以前の最新 `ohlcv.csv` 行の `close` を `bid`、`ask`、`last` として返します。

## `fx_rates.csv`

為替レートを定義します。

```csv
pair,rate,ts,source
USDJPY,150.00,2026-04-09T00:00:00+00:00,csv
```

列:

- `pair`: 現在の MVP では `USDJPY` のみ対応。
- `rate`: 為替レート。
- `ts`: ISO 8601 形式の日時。UTC 推奨。
- `source`: データソース名。通常は `csv`。

## MVP 制約

- 現在の CSV provider はローカル検証用です。
- 対応 FX pair は `USDJPY` のみです。
- `ohlcv.csv` は日次データを想定しています。
- CSV の列名は固定です。未知の列は無視されますが、必要な列がない場合はエラーになります。
