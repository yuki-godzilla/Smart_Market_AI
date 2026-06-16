# Setup Guide (Python) — Smart Market AI

このドキュメントは **Windows + PowerShell** 前提です。仮想環境名は **`venv_SMAI`** に統一します。
2026-05-17 時点の実装では、FastAPI API、Streamlit UI、local check helper、mock / csv market-data provider を利用できます。

---

## 0) 事前準備

- Python 3.11 または 3.12 系をインストールして PATH に通す
- Python 3.11 / 3.12 以外を使う場合は、下の手動セットアップを使う
- リポジトリ直下で以下の操作を行う
- 通常確認は外部ネットワーク非依存の `mock` / `csv` provider を使う

---

## 1) かんたんセットアップ（Python 3.11 / 3.12 / バッチ）

PowerShell を開き、リポジトリ直下で実行します。

```powershell
.\setup\setup.bat
```

正常終了後、仮想環境は `venv_SMAI/` に作成されます。
`BLACK_CACHE_DIR` はリポジトリ直下の `.black_cache/` に設定されます。

注意: 現在の `setup\setup.bat` は Python 3.11 または 3.12 を探します。
Python 3.11 / 3.12 以外のバージョンだけが入っている環境では、手動セットアップで `python -m venv venv_SMAI` を実行してください。

> 実行時に「スクリプトの実行が無効」と出る場合:
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

---

## 2) 手動セットアップ

```powershell
python -m venv venv_SMAI
.\venv_SMAI\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r setup\requirements.txt -r setup\requirements-dev.txt
```

Black キャッシュ先をプロジェクト配下に寄せます。

```powershell
$env:BLACK_CACHE_DIR = "$PWD\.black_cache"
[Environment]::SetEnvironmentVariable("BLACK_CACHE_DIR", "$PWD\.black_cache", "User")
```

ツール確認:

```powershell
ruff --version
black --version
pytest --version
```

---

## 3) FastAPI 起動

```powershell
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

確認:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

主な実装済みAPI:

| API | 用途 |
|---|---|
| `GET /health` | 起動確認 |
| `POST /risk/pre-trade-check` | 売買案のRisk判定 |
| `POST /portfolio/rebalance-check` | リバランス案 + Risk判定 |
| `POST /screening/score` | 複数銘柄のScreening Score |
| `POST /forecast/evaluate` | baseline forecast evaluation |
| `POST /scoring/investment-score` | Investment Score |

---

## 4) Streamlit UI 起動

メインUI:

```powershell
.\venv_SMAI\Scripts\python.exe -m streamlit run ui\app.py
```

Rebalance 専用UI:

```powershell
.\venv_SMAI\Scripts\python.exe -m streamlit run ui\rebalance_app.py
```

UIでは、銘柄コックピット、銘柄ランキング、Forecast / Screening / Investment Score、Rebalance Cockpit を確認できます。
出力は判断補助であり、売買推奨ではありません。

---

## 5) 設定ファイル

未指定の場合はコード内デフォルト設定で起動します。
YAML設定を使う場合は `SMAI_CONFIG_FILE` を指定します。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\example.yaml"
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

CSV provider を使う例:

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe -m streamlit run ui\app.py
```

`SMAI_CONFIG_FILE` は `backend/core/config.py` の `Settings` モデルに対応します。未知キーは設定ミスとして拒否されます。

---

## 6) 品質チェック

推奨の一括確認:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
.\venv_SMAI\Scripts\python.exe -m mypy .
```

対象を絞る例:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests/test_scoring_service.py tests/test_scoring_api.py -q
.\venv_SMAI\Scripts\python.exe -m pytest tests/test_ui_rebalance_app.py -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
```

Black は直接 `python -m black --check .` を使わず、helper を優先します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

---

## 7) よくあるトラブル

### python が見つからない

Python を再インストールし、「PATH を追加」を有効化してから新しい PowerShell を開き直します。

### 仮想環境が有効化できない

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 依存のビルドに失敗

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install -r setup\requirements.txt -r setup\requirements-dev.txt
```

### black が長時間終わらない

直接 Black を叩かず helper を使います。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

### 外部 provider が使えない

通常は外部 provider を使わない設計です。`allow_external_providers: true` を明示しない限り、live provider は通常経路に入りません。

---

## 8) 便利コマンド

```powershell
# venv 有効化
.\venv_SMAI\Scripts\Activate.ps1

# venv 無効化
deactivate

# 依存を再インストール
pip install -r setup\requirements.txt -r setup\requirements-dev.txt

# API 起動
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload

# UI 起動
.\venv_SMAI\Scripts\python.exe -m streamlit run ui\app.py

# Local checks
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
```
