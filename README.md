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
  - left side menu for `銘柄コックピット` / `銘柄ランキング` / `リバランス` / `設定 / データ情報`
  - 銘柄コックピット: 価格・予測チャート、Investment Score、score breakdown、warnings、downloads
  - 銘柄ランキング: curated symbol metadata、候補条件 modal、ランキング preset、コックピットへの深掘り導線
  - Rebalance Cockpit: summary flow、percentage target、allocation comparison chart、risk breach confirmation points
- symbol universe metadata schema、source import、opt-in metadata refresh、SBI ranking universe policy columns / default exclusion helper
- JSON / CSV / Markdown / manifest / ZIP export
- file-backed rebalance scenarios
- Windows 環境向け single-process Black check helper

未実装または将来範囲:

- `polygon` など追加 live provider adapter 本体
- SBI / NISA metadata の公式 source import（NISA seed import は実装済み）
- 投信 metadata / 基準価額 / ranking 対応は Future Phase
- Research RAG の ingestion / chunk store / retrieval / Research Score
- Decision Report の本格化
- Execution / broker への注文送信
- AI assistant experience
- PDF / Excel export

MVP の通常確認は引き続きネットワーク不要の `mock` / `csv` で維持します。一方、Streamlit の Market Data 画面は投資判断 UI として `yahoo` live data を初期表示・先頭表示にし、画面上で明示 opt-in した live provider として `yfinance` 経由で利用します。

## 現在のロードマップ上の位置

- Phase 1〜15: implementation complete
- Phase 16: UI / Visualization Cockpit implementation complete、最終 Streamlit browser smoke は推奨確認
- Phase 16S: Stabilization / final Streamlit smoke は必要に応じて実施
- Phase 17: UI Polish / ランキング条件 UI 再設計は implementation complete
- Phase 18: symbol universe / metadata refresh / source import / SBI ranking universe policy が進行中。次は SBI / ETF metadata source の拡張
- Phase 19〜24: Decision Report、Research RAG、Research Score、Assistant、optional adapter、Execution gate の順に整理
- Execution / broker order: Decision Report と risk/audit 境界が固まるまで低優先度

次の重点は、Phase 18 の SBI / ETF metadata source 拡張、Phase 19 の Decision Report context です。
詳細は [実装ロードマップ](./Documents/05_Implementation_Roadmap.md) を参照してください。

## ドキュメント

- [プロジェクト現在地](./PROJECT_CONTEXT.md)
- [実装ロードマップ](./Documents/05_Implementation_Roadmap.md)
- [MVP 運用ガイド](./Documents/06_MVP_Operations_Guide.md)
- [UI 文言ポリシー](./Documents/07_UI_Wording_Policy.md)
- [Phase 16 UI 改善計画](./Documents/08_Phase16_UI_Improvement_Plan.md)
- [SBI 銘柄ユニバース方針](./Documents/09_SBI_Symbol_Universe_Policy.md)
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

`setup\setup.bat` は Python 3.11 を前提に仮想環境を作成します。
Python 3.12 など 3.11 以外の環境では、下の手動インストール手順で `venv_SMAI` を作成してください。

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

現在の UI は左サイドメニューで画面を切り替えます。
`銘柄コックピット` では 1 銘柄を深掘りし、`銘柄ランキング` では複数銘柄を比較します。
`リバランス` では、現在資産、目標配分、必要な売買、Risk 判定を順に確認します。
`設定 / データ情報` では、実行環境とローカルの銘柄候補を確認できます。

## CSV MarketData で起動

設定上のデフォルト provider は deterministic な `mock` です。
Streamlit の Market Data 画面では provider 選択の初期表示と表示順先頭が `yahoo` です。通常の API / local checks は `mock` / `csv` を基準にしつつ、UI では生きた株価データを主導線として扱います。
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
