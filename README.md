# Smart Market AI
![CI](https://github.com/yuki-godzilla/Smart_Market_AI/actions/workflows/ci.yml/badge.svg)

Smart Market AI（SMAI）は、投資判断に必要な情報を整理・可視化し、
市場データ取得、特徴量生成、スクリーニング、複数モデル予測、Investment Score、ポートフォリオ評価、将来の Research RAG による根拠収集を通じて、
「売買を自動化する」のではなく「判断材料を説明可能にする」ためのローカルファーストな投資分析プラットフォームです。

SMAI は以下の思想を重視しています。

- deterministic（再現可能）な分析基盤
- explainable（説明可能）なスコアリング
- local-first な実行環境
- optional な外部 API 連携
- モジュール分離された拡張可能アーキテクチャ
- 売買推奨ではなく、根拠・不確実性・注意点を含む投資判断補助

<img src="Documents/img/01_system_diagram.png" width="1200">

## 現在の MVP / 実装状況

実装済み:

- FastAPI backend
  - `GET /health`
  - `POST /risk/pre-trade-check`
  - `POST /portfolio/rebalance-check`
  - `POST /screening/score`
  - `POST /forecast/evaluate`
  - `POST /scoring/investment-score`
- Pydantic v2 の共通データ契約、設定モデル、ドメインエラー
- deterministic な MarketData provider: `mock` / `csv`
- 明示 opt-in の `yahoo` live provider adapter 経路
- `polygon` provider の capability metadata / 将来予約
- 日次 snapshot、ADV、volatility、momentum、drawdown、data completeness の feature building
- Feature Snapshot を使った Screening Score
- naive / moving-average / momentum baseline による Forecast Evaluation
- Forecast Summary / model agreement / forecast range / best RMSE model の表示補助
- Screening、Forecast agreement、Data Quality、Risk signal を統合する Investment Score
- configurable `scoring.weights`
- deterministic な Risk pre-trade check
- Portfolio 評価と solver なしの rebalance proposal
- Portfolio-to-Risk workflow
- Streamlit UI
  - Market Data tab: `銘柄コックピット` / `銘柄ランキング`
  - 銘柄コックピット: 価格・予測チャート、Investment Score、score breakdown、warnings、downloads
  - 銘柄ランキング: curated symbol metadata、候補条件 modal、ランキング preset、コックピットへの深掘り導線
  - Rebalance Cockpit: summary flow、percentage target、allocation comparison chart、risk breach confirmation points
- JSON / CSV / Markdown / manifest / ZIP export
- file-backed rebalance scenarios
- Windows 環境向け single-process Black check helper

未実装または将来範囲:

- `polygon` など追加 live provider adapter 本体
- provider 由来 metadata を定期更新する symbol metadata refresh command
- Research RAG の ingestion / chunk store / retrieval / Research Score
- Decision Report の本格化
- Execution / broker への注文送信
- AI assistant experience
- PDF / Excel export

MVP の既定経路は引き続きネットワーク不要の `mock` / `csv` です。`yahoo` は `allow_external_providers: true` の明示 opt-in 時だけ `yfinance` 経由で利用します。

## 現在のロードマップ上の位置

- Phase 1〜15: implementation complete
- Phase 16: UI / Visualization Cockpit 改善中
- Research RAG: 設計済み、実装は planned
- Execution / broker order: 優先度を下げた将来領域

次の重点は、Phase 16 の Rebalance Cockpit / Ranking-to-Cockpit 導線の磨き込みと、Research RAG 実装に入る前の document / roadmap 同期です。
詳細は [実装ロードマップ](./Documents/05_Implementation_Roadmap.md) を参照してください。

## ドキュメント

- [プロジェクト現在地](./PROJECT_CONTEXT.md)
- [実装ロードマップ](./Documents/05_Implementation_Roadmap.md)
- [MVP 運用ガイド](./Documents/06_MVP_Operations_Guide.md)
- [UI 文言ポリシー](./Documents/07_UI_Wording_Policy.md)
- [Phase 16 UI 改善計画](./Documents/08_Phase16_UI_Improvement_Plan.md)
- [Research RAG 詳細設計](./Documents/04_Detail_Design/04-8_Onepager_Research_RAG.md)
- [Investment Scoring / UI 詳細設計](./Documents/04_Detail_Design/04-9_Onepager_Investment_Scoring_UI.md)
- [Codex タスクテンプレート](./Documents/98_Codex_Task_Template.md)
- [作業ログ](./Documents/99_Work_Log.md)

設計背景:

- [要件定義](./Documents/01_Define_requirements.md)
- [システム設計](./Documents/02_System_design.md)
- [機能設計](./Documents/03_Functional_design.md)
- [詳細設計](./Documents/04_Detail_Design/04_Detail_Design_README.md)

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

現在の UI は Market Data / Rebalance の 2 tab 構成です。
Market Data では、1銘柄を深掘りする `銘柄コックピット` と、複数銘柄を比較する `銘柄ランキング` を切り替えます。
Rebalance では、現在資産、目標配分、必要な売買、Risk 判定を順に確認します。

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

## 検証

まずローカル MVP の基本確認をまとめて実行します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
```

個別に実行する場合:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy backend
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

この Windows 環境では、直接の multi-file `python -m black --check .` が worker process を残す場合があるため、通常は `tools/run_black_check.py` を使います。
