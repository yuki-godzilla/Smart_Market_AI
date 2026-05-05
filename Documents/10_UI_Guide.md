# 10_UI_Guide

#### [BACK TO README](../README.md)

## 目的

この文書は、Smart Market AI の最小 Streamlit UI をローカルで起動する手順をまとめます。

現在の UI は `POST /portfolio/rebalance-check` 相当の Portfolio-to-Risk workflow を画面から確認するための
MVP です。broker や execution provider に注文は送りません。

## 起動方法

依存関係をインストールします。

```powershell
.\venv_SMAI\Scripts\python.exe -m pip install -r setup\requirements.txt -r setup\requirements-dev.txt
```

Streamlit UI を起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

CSV provider のサンプルデータで確認する場合は、先に設定ファイルを指定します。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

## 画面でできること

- `account_id` を入力する
- 評価日を選ぶ
- JPY cash を入力する
- positions JSON を編集する
- target allocations JSON を編集する
- リバランス案と Risk 判定を JSON で確認する

## MVP 制約

- UI はローカル手動確認用です。
- 現在は Portfolio-to-Risk workflow のみを対象にしています。
- デフォルトでは `mock` provider を使います。
- `SMAI_CONFIG_FILE` で `csv` provider に切り替えできます。
