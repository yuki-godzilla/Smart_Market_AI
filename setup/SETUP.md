# Setup Guide (Python) — Smart Market AI

このドキュメントは **Windows + PowerShell** 前提で、仮想環境名を **`venv_SMA`** として統一します。
ワンコマンド実行の **`setup.bat`** にも対応しました。

---

## 0) 事前準備
- Python 3.11 系（推奨）をインストールして PATH に通す
- リポジトリ直下で以下の操作を行う

---

## 1) かんたんセットアップ（バッチ推奨）
1. PowerShell を開き、リポジトリ直下で実行:
   ```powershell
   .\setup\setup.bat
   ```
2. 正常終了後、仮想環境は `venv_SMA/` に作成されます。

> **補足（PowerShell の実行ポリシー）**
> 実行時に *「スクリプトの実行が無効」* と出る場合:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```
> を実行してからやり直してください。

---

## 2) 手動セットアップ（バッチが使えない場合）

1) 仮想環境の作成
```powershell
python -m venv venv_SMAI
```

2) 仮想環境の有効化（PowerShell）
```powershell
.\venv_SMAI\Scripts\Activate.ps1
```

3) 依存インストール（本番＋開発）
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

4) 動作確認（主要ツールが表示されればOK）
```powershell
ruff --version
black --version
pytest --version
```

5) 品質チェック一括（lint/format/check/test）
```powershell
pytest
ruff check .
black --check .
mypy .
```

---

## 3) プロジェクトの起動確認（任意）
FastAPI の最小アプリを起動してヘルスチェック:
```powershell
uvicorn backend.app.main:app --reload
```
ブラウザで `http://127.0.0.1:8000/health` にアクセス → `{"status":"ok"}` が返ればOK。

---

## 4) よくあるトラブル
- **python が見つからない**
  → Python を再インストールし、 *「PATH を追加」* を有効化。新しい PowerShell を開き直す。
- **依存のビルドに失敗**
  → `pip install --upgrade pip setuptools wheel` を実行後、再インストール。
- **仮想環境が有効化できない**
  → 実行ポリシーを `RemoteSigned` に変更（上記参照）。

---

## 5) 便利コマンド（PowerShell）
```powershell
# venv 有効化
.\venv_SMA\Scripts\Activate.ps1

# venv 無効化
deactivate

# 依存を再インストール
pip install -r requirements.txt -r requirements-dev.txt
```
