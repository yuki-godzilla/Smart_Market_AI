# Smart Market AI

Smart Market AI は、投資支援ワークフロー向けの Python プロジェクトです。
現在のリポジトリは、Portfolio-to-Risk workflow をローカルで再現できる deterministic な MVP として整備しています。

![CI](https://github.com/yuki-godzilla/Smart_Market_AI/actions/workflows/ci.yml/badge.svg)

## 現在の MVP

実装済み:

- `/health`、`POST /risk/pre-trade-check`、`POST /portfolio/rebalance-check`、`POST /screening/score` を持つ FastAPI backend
- Pydantic v2 の共通データ契約、設定モデル、ドメインエラー
- deterministic な MarketData provider: `mock` と `csv`
- 日次 snapshot、ADV、volatility の feature building
- Feature Snapshot、単一銘柄 Screening Score、Forecast chart の preview
- deterministic な MVP ルールによる Risk pre-trade check
- Portfolio 評価と solver なしの rebalance proposal
- rebalance-check workflow 向け Streamlit UI
- rebalance-check 結果の JSON / CSV / Markdown / ZIP export
- ローカル sample CSV と deterministic な example request
- `examples/rebalance_scenarios/` の file-backed rebalance sample

未実装:

- `polygon` など追加 live market-data provider
- Execution / broker への注文送信
- forecast、高度な reporting workflow、AI assistant experience
- `SMAI_CONFIG_FILE` 以外の環境変数設定

`yahoo` / `polygon` は設定値として予約されています。`yahoo` は `allow_external_providers: true` の明示 opt-in 時だけ `yfinance` 経由の live adapter として利用できます。`polygon` はまだ未実装です。
MVP の既定経路は引き続きネットワーク不要の `mock` / `csv` です。

## 次期ロードマップ

次期重点は Multi-Model Investment Intelligence です。
注文執行の優先度を下げ、外部データ取得、特徴量管理、銘柄スコアリング、複数モデル予測、可視化、判断補助レポートを段階的に整備します。
詳細は [実装ロードマップ](./Documents/05_Implementation_Roadmap.md) を参照してください。

## ドキュメント

- [プロジェクト現在地](./PROJECT_CONTEXT.md)
- [実装ロードマップ](./Documents/05_Implementation_Roadmap.md)
- [MVP 運用ガイド](./Documents/06_MVP_Operations_Guide.md)

設計背景:

- [要件定義](./Documents/01_Define_requirements.md)
- [システム設計](./Documents/02_System_design.md)
- [機能設計](./Documents/03_Functional_design.md)
- [詳細設計](./Documents/04_Detail_Design/04_Detail_Design_README.md)
- 実装 checklist / stubs は、現在の実装ロードマップと実コードを正とします。

## セットアップ

リポジトリ直下で実行します。

```powershell
.\setup\setup.bat
```

既存の仮想環境を使う場合は、依存関係を直接インストールします。

```powershell
.\venv_SMAI\Scripts\python.exe -m pip install -r setup\requirements.txt -r setup\requirements-dev.txt
```

## API の起動

```powershell
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

ローカル確認用 URL:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

## Streamlit UI の起動

```powershell
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

現在の UI は Portfolio-to-Risk rebalance-check workflow と Market Data / Feature Snapshot / 単一銘柄 Screening Score / Forecast chart preview を対象にしています。
broker へ注文は送信しません。

## CSV MarketData で起動

デフォルト provider は deterministic な `mock` です。
ローカル CSV サンプルデータを使う場合は、次のように設定します。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

同じ設定は Streamlit UI でも使えます。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

## 手動 Smoke Check

サーバーを起動せずに rebalance-check flow を確認できます。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_rebalance_check_demo.py
```

期待される結果:

- `AAPL` の `BUY` proposal が 1 件出る
- `risk_decision.status` が `BLOCK` になる
- breach に dividend-yield data 欠損と concentration が含まれる

Streamlit UI の実行結果は JSON に加えて、summary、current positions、target allocations、allocation comparison、proposed trades、risk breaches を CSV としてダウンロードできます。入力 request、Markdown summary、JSON、CSV 一式、内容説明用 manifest をまとめた ZIP も保存できます。現在の MVP export は JSON、CSV、Markdown、manifest、ZIP までを対象とし、PDF / Excel は将来の拡張範囲です。

## Rebalance Scenario

Streamlit UI の sample は次のディレクトリの JSON から読み込みます。

```text
examples/rebalance_scenarios/
```

新しい sample を追加する場合は、同じ形式の JSON を追加します。
`description` を書くと、UI の Sample 選択欄の下にシナリオ説明として表示されます。

別のローカルディレクトリから sample を読み込む場合は、`SMAI_REBALANCE_SCENARIO_DIR` を指定します。

```powershell
$env:SMAI_REBALANCE_SCENARIO_DIR = ".\my_rebalance_scenarios"
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

指定したパスが存在しない場合やディレクトリではない場合は、UI に scenario load error が表示されます。

## 検証

まずローカル MVP の基本確認をまとめて実行します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
```

個別に実行する場合:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend tests --no-cache
```

CI では現在、cache-free の `tools/run_black_check.py` と `mypy .` も実行します。

## 作業メモ

実装判断では次の順序を優先します。

1. ユーザー要求
2. `backend/` と `tests/` の実コード
3. `PROJECT_CONTEXT.md`
4. `Documents/05_Implementation_Roadmap.md`
5. `Documents/` 配下のその他設計資料

明示的に必要な作業でない限り、MVP の主要経路は offline かつ deterministic に保ちます。
