# 06_Implementation_Roadmap

#### [BACK TO README](../README.md)

## 1. Purpose

このドキュメントは、既存の要件定義・設計書を実装作業に接続するためのロードマップです。
実装を進めるたびに、対象範囲・成果物・完了条件をここへ反映し、プロジェクトの現在地を追えるようにします。

## 2. Current State

- 実装は FastAPI の最小スケルトンから始まり、現在は Risk / Portfolio の MVP API と最小 Streamlit UI まで公開済み。
- 現在ある API は `/health`、`POST /risk/pre-trade-check`、`POST /portfolio/rebalance-check`。
- テストは core、MarketData、Risk、Portfolio、API、OpenAPI schema を対象に追加済み。
- Execution と live market-data provider はまだ実装前。UI は Portfolio-to-Risk workflow 向けの最小 Streamlit 画面から着手済み。
- 依存関係は FastAPI / Pydantic / SQLAlchemy / httpx / pandas / numpy などの基盤寄りが中心。
- Streamlit は最小 UI 用に導入済み。yfinance、最適化ライブラリ、ML ライブラリはまだ導入前。

Current implementation sync note:
- Done: Core Foundation MVP.
- Done: MarketData MVP with deterministic `mock` and `csv` providers.
- Done: Risk MVP initial service at `backend/risk/service.py`.
- Done: FastAPI endpoints `/health` and `POST /risk/pre-trade-check`.
- Done: Portfolio MVP initial service at `backend/portfolio/service.py`.
- Done: Portfolio-to-Risk workflow for generated rebalance trades.
- Done: Portfolio-to-Risk API endpoint `POST /portfolio/rebalance-check`.
- Done: Swagger/OpenAPI metadata and Japanese API specification notes.
- Done: Optional YAML settings loading through `SMAI_CONFIG_FILE`.
- Done: Deterministic manual workflow docs and example request for Portfolio-to-Risk checks.
- Done: Local sample CSV market-data files and `config/csv_example.yaml`.
- Done: Minimal Streamlit UI for the Portfolio-to-Risk rebalance-check workflow.
- Done: Streamlit UI runtime settings display and deterministic sample selector.
- Remaining: live market data providers, Execution, broader UI workflows, and broader environment settings loading.

## 3. Implementation Policy

- 最初は外部 API や重い ML 処理に入らず、ローカルで再現できる土台から作る。
- 共通型、設定、例外、MarketData の mock/csv 実装を先に整える。
- 各実装ステップでテストを追加し、後続の Risk / Portfolio / Screening / Forecast が同じ入力を使えるようにする。
- ドキュメントとコードの差分が広がらないよう、完了したこと・未決事項をこの文書へ反映する。

## 4. Recommended Order

### Phase 1: Core Foundation

Status: MVP complete

Design diagram: [04-7_Implementation_Class_Diagram.md](./04_Detail_Design/04-7_Implementation_Class_Diagram.md)

目的: 後続機能が共有する基盤を作る。

成果物:
- Done: `backend/core/data_contracts.py`
- Done: `backend/core/errors.py`
- Done: `backend/core/config.py`
- Done: core 向けユニットテスト

主な内容:
- Done: `Symbol`, `FxRate`, `TradeIntent`, `Position`, `DailySnapshot` などの Pydantic モデル
- Done: `Bar`, `Quote` など MarketData MVP で使う基本データ型
- Done: `AppError`, `DataSourceError`, `RateLimitError`, `SchemaMismatchError` などの共通例外
- Done: `base_currency`, `dataaccess.provider`, cache TTL などの最小設定モデル

完了条件:
- Done: core のユニットテストが通る
- Done: 後続フェーズから import できる型と例外が揃っている
- Done: `SMAI_CONFIG_FILE` で YAML 設定を読み込める
- Remaining: `.env` や個別環境変数による設定上書き

### Phase 2: MarketData MVP

Status: MVP complete

Design diagrams:
- [04-2_Onepager_marketdata_dataaccess.md](./04_Detail_Design/04-2_Onepager_marketdata_dataaccess.md)
- [04-5_Onepager_Feature_Builder.md](./04_Detail_Design/04-5_Onepager_Feature_Builder.md)
- [04-7_Implementation_Class_Diagram.md](./04_Detail_Design/04-7_Implementation_Class_Diagram.md)

目的: 外部 API に依存しない形で価格・為替・スナップショットの入力を作る。

成果物:
- Done: `backend/marketdata/data_access.py`
- Done: `backend/marketdata/feature_builder.py`
- Done: MarketData 向けユニットテスト

主な内容:
- Done: `mock` provider による `fetch_ohlcv`, `fetch_quotes`, `get_fx_rates`
- Done: `csv` provider によるローカル CSV からの `fetch_ohlcv`, `fetch_quotes`, `get_fx_rates`
- Done: `compute_adv`
- Done: `compute_vol`
- Done: `build_daily_snapshot`
- Remaining: `yahoo` provider
- Remaining: 配当利回り、発行株式数、営業日カレンダーの正式データ源

完了条件:
- Done: ネットワークなしで MarketData のテストが通る
- Done: `DailySnapshot` を生成できる
- Done: Risk / Portfolio の入力として使える最小項目が揃っている

### Phase 3: Risk MVP

Status: MVP initial service and API complete

目的: 取引前チェックの最小ルールエンジンを作る。

成果物:
- Done: `backend/risk/service.py`
- Done: Risk 向けユニットテスト
- Done: `POST /risk/pre-trade-check` FastAPI endpoint and deterministic API tests

主な内容:
- `ALLOW`, `REVIEW`, `BLOCK` の判定
- 1銘柄上限、バスケット上限、集中度、最低配当利回りなどのしきい値評価

完了条件:
- `TradeIntent` と `DailySnapshot` から判定できる
- 判定理由をテストで検証できる

### Phase 4: Portfolio MVP

Status: MVP initial service complete

目的: シンプルな制約付きリバランス案を作る。

成果物:
- Done: `backend/portfolio/service.py`
- Done: Portfolio 向けユニットテスト

主な内容:
- 現在ポジションの JPY 評価
- 集中度・配当利回りなどの制約評価
- まずは最適化ソルバなしの単純提案から開始し、後で pulp / ortools に拡張

完了条件:
- サンプルポートフォリオを評価できる
- Risk に渡せる `TradeIntent` を生成できる

### Phase 5: API and UI Integration

目的: バックエンド機能を API / UI から呼び出せるようにする。

成果物:
- FastAPI ルーター
- Streamlit UI の初期画面
- API / UI の簡易テスト

主な内容:
- 銘柄リスト入力
- スナップショット生成
- リスク判定
- レポート出力への接続準備

完了条件:
- ローカルで主要フローを手動確認できる
- `/health` 以外の最小 API が動作する

## 5. Near-Term Decision

次に着手する推奨範囲は **expand UI workflow or richer CSV data conventions**。

理由:
- Phase 1 の最小 core 基盤は追加済み。
- Phase 2 の mock MarketData で `DailySnapshot` を生成できる。
- Phase 3 の最小 RiskService と API は追加済み。
- Phase 4 の最小 PortfolioService は追加済み。
- Portfolio が生成した `TradeIntent` は service-level workflow で Risk 判定へ接続済み。
- Done: Portfolio-to-Risk workflow can now be called through `POST /portfolio/rebalance-check`.
- Done: Swagger UI now has tags, summaries, descriptions, and request examples for current MVP APIs.
- Done: YAML settings can be loaded through `SMAI_CONFIG_FILE`.
- Done: `POST /portfolio/rebalance-check` can be manually checked with an example request and demo script.
- Done: CSV provider can be smoke-checked through `config/csv_example.yaml` and `data/marketdata`.
- Done: A minimal Streamlit UI can run the Portfolio-to-Risk rebalance-check workflow.
- 次は UI workflow の拡張、または csv provider のデータ規約拡張に進む。

## 6. Verification Notes

重い全体チェックは避け、当面は対象を絞って実行する。

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend tests --no-cache
```

`black` と `mypy` は実行対象や除外設定を整えてから再確認する。

## 7. Open Items

- README と詳細設計 README のリンク整合性を確認する。
- CI が `.venv` / `venv_*` を走査しないよう、必要なら設定を追加する。
- `setup/SETUP.md` 内の仮想環境名表記を `venv_SMAI` に統一する。
- `yfinance` / Streamlit / 最適化ライブラリの導入タイミングを決める。
