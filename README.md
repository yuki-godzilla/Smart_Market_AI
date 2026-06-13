# Smart Market AI
![CI](https://github.com/yuki-godzilla/Smart_Market_AI/actions/workflows/ci.yml/badge.svg)

Smart Market AI（SMAI）は、投資判断に必要な情報を整理・可視化し、
市場データ取得、特徴量生成、スクリーニング、複数モデル予測、Investment Score、ポートフォリオ評価、Research RAG による外部最新情報・根拠整理を通じて、
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
- Decision Report context v1
  - cockpit / ranking / rebalance の判断材料を Markdown / JSON / manifest / ZIP として保存
  - data confidence、symbol metadata、decision checkpoints、Research Evidence / Research Score section の標準 builder
- Research RAG Phase 20 local evidence foundation
  - local UTF-8 Markdown / Text / CSV の登録、hash dedupe、chunking、keyword evidence search
  - deterministic Research Summary、data-quality warning、Cockpit / Ranking modal / Decision Report 連携
- Research RAG external fresh-source fetch first UI slice
  - TDnet 適時開示 + Yahoo Finance profile / news の first slice を `AI調査を更新` の標準処理へ統合済み
  - 方針として、取得本文は保持せず session-local に一時参照する。画面とDecision Reportには source URL / provider / fetched_at / published_at / freshness warning / 要約を表示する
- Research Summary local readability first slice
  - 外部LLMはいったん使わず、RAG evidence / provider profile / news / TDnet trace を表示専用 `ResearchBrief` に変換する
  - AI整理メモ、定量評価サマリー、企業概要、良材料候補、注意材料候補、不足根拠、次に確認すべき資料、出典カードの順に読める調査メモへ整理する
- Research Score first slices
  - `ResearchScoreService`、optional Investment Score input、disabled-by-default `scoring.weights.research`
  - Cockpit / Ranking Research Summary の Research Score 参考表示
  - Ranking selected-candidate breakdown の Research Score 確認材料表示
  - Cockpit Decision Report の Research Score section
- Investment News / News cache backend foundation
  - `backend/news` の dashboard snapshot / status contracts、latest snapshot cache、1世代 backup、atomic save、cleanup、TTL / retry / failure fallback、rotating log
  - 通常 tests は fake snapshot / fixture で network-free に維持
- Symbol Database background refresh foundation
  - `backend/symbols` の freshness 判定、priority queue、atomic queue/status persistence、latest-only normalized symbol cache、startup background worker
  - Streamlit 起動時に画面表示をブロックせず、local `symbol_universe.csv` から missing / stale 銘柄を順次更新
- Low-cost Assistant backend first slice
  - `backend/assistant` の `AssistantRequest` / `AssistantResponse` / `TemplateAssistantService`
  - LLM / network なしで Decision Report context から理由、注意点、次の確認観点を deterministic に返し、売買指示質問は助言境界として扱う
- LLM expansion direction
  - SMAI plans to use LLMs as an interpretation and reasoning support layer.
  - The LLM layer will first power SMAI Copilot, context-aware explanations, news/material summaries, and Decision Report drafting.
  - It will not directly change scores, rankings, forecasts, or investment decisions in the early phases.
  - Validated LLM-derived factors may later be tested and gradually integrated into ranking or forecast models.
  - SMAI では LLM を判断主体ではなく、解釈・理由付け・材料整理を支援する layer として扱う。
  - 初期段階の LLM は Copilot、画面文脈に沿った説明、ニュース / 材料要約、Decision Report 草案、LLM Factor 候補生成に使い、スコア、順位、予測値、投資判断は直接変更しない。
  - LLM 由来の特徴量を Ranking / Forecast に統合する場合は、backtest、leakage check、baseline 比較などの検証後に段階的に扱う。
- Streamlit UI
  - left side menu for `銘柄コックピット` / `銘柄ランキング` / `投資レーダー` / `SMAIアシスタント` / `リバランス` / `設定 / データ情報`
  - 銘柄コックピット: 価格・予測チャート、AI予測インサイト、Investment Score、投資判断メモ、Research Evidence、Decision Report、銘柄データ modal、warnings、downloads
  - 銘柄ランキング: curated symbol metadata、候補条件 modal、ランキング preset、今回のランキング条件カード、AI総合 / 予測シグナル説明、AI予測インサイト込みの並べ替え理由と深掘り候補、行クリックで開く銘柄データ modal、AI Research tab、Decision Report
  - 投資レーダー: network-free demo snapshot と手動更新時の Google News RSS Standard Mode による市場ニュースヘッドライン、企業名主表示＋シンボル補助タグのクリック可能な株式ヒートマップ風投資ヒートマップ、3列カテゴリ別ニュースカード、銘柄名付き関連銘柄から銘柄コックピットへの導線
  - Rebalance Cockpit: summary flow、percentage target、allocation comparison chart、risk breach confirmation points、Decision Report
- symbol universe metadata schema、source import、opt-in metadata refresh、SBI ranking universe policy columns / default exclusion helper
- JPX / SBI / NISA / IMAJ / REIT source builders and import profiles
- JSON / CSV / Markdown / manifest / ZIP export
- file-backed rebalance scenarios
- Windows 環境向け single-process Black check helper

未実装または将来範囲:

- `polygon` など追加 live provider adapter 本体
- 追加 provider / fund metadata source adapter
- 投信 metadata / 基準価額 / ranking 対応
- `投資レーダー` dashboard の外部ニュースsource接続、詳細フィルタ、Watchlist連動、通知
- EDINET / company IR site など追加 Research RAG external source adapter の拡張、vector / hybrid search の運用UI
- Research Score の ranking order 統合は現時点では見送り。必要性が再確認された場合のみ opt-in 後続機能として扱う
- Assistant API / Streamlit 質問パネル、optional LLM provider
- 銘柄DB freshness badge / live provider refresh wiring の visible UI 接続
- Execution / broker への注文送信
- PDF / Excel export

MVP の通常確認は引き続きネットワーク不要の `mock` / `csv` で維持します。一方、Streamlit の Market Data 画面は投資判断 UI として `yahoo` live data を初期表示・先頭表示にし、画面上で明示 opt-in した live provider として `yfinance` 経由で利用します。

## 現在のロードマップ上の位置

- Phase 1〜15: implementation complete
- Phase 16: UI / Visualization Cockpit implementation complete。銘柄データ modal、コックピット投資判断メモ、ランキング行クリック詳細表示まで実装済み。最終 Streamlit browser smoke は推奨確認
- Phase 16S: Stabilization / final Streamlit smoke に加え、Manual UX Review と Functional Spec Issues による成熟性レビューを実施
- Phase 17: UI Polish / ランキング条件 UI 再設計は implementation complete
- Phase 18: symbol universe / metadata refresh / source import / SBI ranking universe policy は implementation complete。継続的な NISA / ETF / stock metadata source 更新は運用タスクとして扱う
- Phase 19: Decision Report Context MVP は implementation complete
- Phase 20: Research RAG Evidence Layer は local evidence foundation が implementation complete
- Phase 21: 高度Research RAG / Stock News RAG / external fresh-source fetch の first slices は implementation complete。追加 provider と運用UIは後続
- Phase 22: Research Score / Cockpit deep-dive は first UI slices 実装済み。Phase 22.x `投資レーダー` (Investment News dashboard) は初期MVP実装済み、Phase 22.y news cache と Phase 22.z symbol DB background refresh は backend foundation 実装済み
- Phase 23: Optional Adapter / 高度分析を先に進める。Advanced Forecast は `advanced_linear` / `advanced_tree_sklearn` / `advanced_gbdt_sklearn` / `advanced_quantile` の registry、forecast service / API adapter selection、Cockpit `AI予測インサイト` chart/card/detail、Ranking auxiliary 表示、上昇気配 / 下降警戒への控えめブレンド、AI総合への軽量統合、Ranking理由表示 / 深掘り候補 / Decision Report 連携まで実装済み。Cockpit の AI予測インサイト初期表示は、結論、中心予測（高度予測モデルの統合結果）、下振れ / 上振れケース、予測価格、予測レンジ、信頼度、モデル合意度、予測ばらつき、注意点に整理し、個別高度モデルカードは常時表示、RMSE / 方向一致率 / 単純予測比較は折りたたみ配下で確認する
- Phase 24-25: Template Assistant backend slice、SMAI Copilot floating UI、専用 Copilot workspace、Gateway schema / client / deterministic fallback、`smai-ai-gateway/` scaffold、`SMAIアシスタント` 画面のセッション内 LLM Gateway 接続設定、親SMAI側の opt-in live smoke test path は実装済み
- Phase 24A: `SMAI LLM Factor` の schema、deterministic fake / cache、Cockpit / Ranking 参考表示、validation foundation は実装済み。実 LLM 生成とモデル統合は未実施
- Phase 26-30: context-aware Copilot、LLM Factor live generation、Cockpit / Ranking / Radar / News / Decision Report への LLM 解釈展開、LLM Factor validation and gradual model integration を段階的に扱う
- Phase 31: advanced export、Execution gate の順に整理
- Execution / broker order: Decision Report と risk/audit 境界が固まるまで低優先度

次の重点は Phase 26-30 の LLM 拡張を、既存の Copilot / LLM Factor / Decision Report 境界を壊さずに段階化することです。まず context-aware Copilot を進め、次に LLM Factor の実生成、各画面の解釈支援、Decision Report 草案、検証済み LLM-derived factor の段階的統合可否を扱います。早期段階では LLM が Ranking score、AI総合、Forecast、Investment Score、投資判断を直接変更しません。通常 checks は引き続き fake adapter / fixture で network 非依存を維持します。実 Gateway / Ollama smoke は明示 opt-in で分離します。
詳細は [実装ロードマップ](./Documents/05_Implementation_Roadmap.md) を参照してください。

## ドキュメント

- [プロジェクト現在地](./PROJECT_CONTEXT.md)
- [実装ロードマップ](./Documents/05_Implementation_Roadmap.md)
- [MVP 運用ガイド](./Documents/06_MVP_Operations_Guide.md)
- [UI 文言ポリシー](./Documents/07_UI_Wording_Policy.md)
- [Phase 16 UI 改善計画](./Documents/08_Phase16_UI_Improvement_Plan.md)
- [SBI 銘柄ユニバース方針](./Documents/09_SBI_Symbol_Universe_Policy.md)
- [手動 UX レビューチェックリスト](./Documents/96_Manual_UX_Review_Checklist.md)
- [機能仕様 issue 台帳](./Documents/97_Functional_Spec_Issues.md)
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
`リバランス` では、現在資産、目標配分、配分差分、見直し候補、Risk 判定を順に確認します。
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
.\venv_SMAI\Scripts\python.exe -m ruff check . --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy .
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

この Windows 環境では、直接の multi-file `python -m black --check .` が worker process を残す場合があるため、通常は `tools/run_black_check.py` を使います。
