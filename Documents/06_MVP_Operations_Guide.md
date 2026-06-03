# MVP Operations Guide

#### [BACK TO README](../README.md)

## 1. 目的

この文書は、現在の Smart Market AI MVP をローカルで起動、確認、説明するための運用ガイドです。
API 仕様、CSV provider、Streamlit UI、手動確認、外部 provider の扱いをこの 1 ファイルに集約します。

## 2. 現在の MVP 範囲

実装済み:

- FastAPI backend
- `GET /health`
- `POST /risk/pre-trade-check`
- `POST /portfolio/rebalance-check`
- `POST /screening/score`
- `POST /forecast/evaluate`
- `POST /scoring/investment-score`
- deterministic な `mock` / `csv` MarketData provider
- 明示 opt-in の `yahoo` live provider adapter 経路
- Feature Snapshot / Screening Score / Forecast Evaluation / Investment Score
- Portfolio-to-Risk rebalance-check workflow
- Decision Report context / Markdown / JSON / manifest / ZIP export for cockpit, ranking, and rebalance
- Research RAG Phase 20 local evidence slice
  - local UTF-8 document registration, chunking, keyword evidence search, Research Summary / ResearchBrief
  - Settings upload, Cockpit `AI調査を更新`, Ranking modal `AI Research`, Cockpit Decision Report Research Evidence / Research Score
- Streamlit UI
  - Market Data: `銘柄コックピット` / `銘柄ランキング`
  - Rebalance: summary flow / allocation comparison / risk confirmation
- JSON / CSV / Markdown / manifest / ZIP export
- file-backed rebalance scenarios

未実装または将来範囲:

- `polygon` などの追加 live provider adapter 本体
- 追加 provider adapter / fund metadata source
- 追加 Research RAG external source adapters / vector search の運用UI
- Research Score によるランキング順位統合は現時点では見送り。Cockpit / Ranking Research Summary と Cockpit Decision Report への参考表示、Investment Score optional numeric input、disabled-by-default weight は対応済み
- Assistant / LLM / news integration
- broker への live order 送信
- Execution workflow
- PDF / Excel export

現在の MVP は、ローカル検証と説明用です。
外部 API へ接続する場合は明示 opt-in が必要で、broker や execution provider へ注文を送りません。
Research RAG / News RAG は実運用では情報鮮度が重要です。標準導線では、`AI調査を更新` が EDINET securities-report metadata/link（`EDINET_API_KEY` 設定時のみ live call、未設定時 no-op）、TDnet 適時開示、企業IRサイト、Google News RSS headline search、Yahoo Finance profile / news を取得/参照し、source URL、provider、published_at、fetched_at、freshness warning を確認材料として表示します。Yahoo Finance を使う Research 側 adapter は MarketData 側と同じ yfinance cache / shared session 設定を使います。Google News RSS は一般ニュースのヘッドライン幅を広げる補助sourceで、検索語は会社名・関連キーワード・銘柄コードに決算/業績/株価/配当などの投資文脈語を添えます。ニュースURL表示自体は `外部参照ソース` と詳細データに実装済みです。Cockpit Research Summary では、`最新ニュース・開示サマリー` の直後に `投資ヒントとなるニュース` と `ニュース・開示の出典を表示（URL付きN件）` を置きます。サマリと注目材料は `Market Intelligence` の主表示カードとして扱い、出典は初期折りたたみの小さな citation list としてURL付きニュース・TDnet・企業IR・EDINET・Google News・Yahoo Finance を確認できるようにします。ニュース専用URLが無い場合も、外部参照ソース側に公式資料・provider URLがある可能性を案内します。取得本文は既定では保持せず、session-local の一時参照として扱います。通常検証は fake adapter / fixture / RSS fixture を使い、network 非依存を維持します。

## 3. API 起動と確認

FastAPI を起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

確認 URL:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

主な API:

| API | 役割 |
| --- | --- |
| `GET /health` | API 起動確認 |
| `POST /risk/pre-trade-check` | trade intent を deterministic risk rule で評価 |
| `POST /portfolio/rebalance-check` | 現在 portfolio と target allocation から配分見直し候補を作り Risk check へ接続 |
| `POST /screening/score` | Feature Snapshot から Screening Score / ranking / reason を返す |
| `POST /forecast/evaluate` | OHLCV から baseline forecast と walk-forward metrics を返す |
| `POST /scoring/investment-score` | Screening / Direction signal / Forecast agreement compatibility / Data quality / Risk signal を統合した Investment Score を返す。`research_scores_by_symbol` は任意入力で、既定 weight は 0.0 |

エラー応答は JSON です。

```json
{
  "code": "APP-2002",
  "message": "Target weights must not exceed 1",
  "details": {
    "target_weight_sum": "1.1"
  }
}
```

主な status code:

- `422`: request validation、domain validation、provider schema mismatch
- `429`: provider rate limit
- `502`: data source error
- `503`: provider unavailable
- `504`: provider timeout

## 4. 手動確認 workflow

サーバーを起動せずに rebalance-check flow を確認する場合は、demo script を使います。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_rebalance_check_demo.py
```

期待される結果:

- `proposal.trades` に `AAPL` の `BUY` trade が 1 件含まれる
- `risk_decision.status` が `BLOCK` になる
- `risk_decision.breaches` に dividend-yield data 欠損と concentration が含まれる

FastAPI 経由で確認する場合:

```powershell
$body = Get-Content .\examples\portfolio_rebalance_check.json -Raw
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/portfolio/rebalance-check `
  -ContentType "application/json" `
  -Body $body
```

Investment Score:

```powershell
$body = @{
  symbols = @("AAPL", "7203.T")
  as_of = "2026-04-09"
  horizon_days = 1
  # 任意: Research Score を既に別経路で計算済みの場合だけ渡す。既定 weight は 0.0。
  research_scores_by_symbol = @{ AAPL = "60" }
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/scoring/investment-score `
  -ContentType "application/json" `
  -Body $body
```

主な確認項目:

- `rank`
- `total_score`
- `score_band`
- `breakdown`
- `research_score` は任意入力の保持値です。既定設定では総合点や順位には寄与しません。
- `warnings`
- `reasons`
- `decision_support_note`

## 5. CSV MarketData provider

設定上の既定 provider は deterministic な `mock` です。
Streamlit の Market Data 画面では provider 選択の初期表示と表示順先頭が `yahoo` です。通常の API / local checks は `mock` / `csv` を基準にしつつ、UI では生きた株価データを主導線として扱います。
ローカル CSV を使う場合は、`SMAI_CONFIG_FILE` で設定ファイルを指定します。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe .\tools\run_rebalance_check_demo.py
```

API / UI 起動時も同じ設定を使えます。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

CSV sample は `data/marketdata/` 配下にあります。

- `symbols.csv`
- `ohlcv.csv`
- `fx_rates.csv`
- `fundamentals.csv`

`fx_rates.csv` の対応 pair は現在 `USDJPY` のみです。

## 6. Streamlit UI

起動:

```powershell
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

### プレ配布EXE

Windows向けプレ配布は PyInstaller の `onedir` 形式で作成します。
開発環境がないPCでの起動確認用であり、onefile化、インストーラー化、署名、自動アップデートは対象外です。

```powershell
.\venv_SMAI\Scripts\python.exe -m pip install -r setup\requirements-build.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\build_exe.ps1
```

成果物:

```text
dist\SMAI\SMAI.exe
dist\SMAI\README_PRE_RELEASE.txt
```

`SMAI.exe` は `ui/app.py` を Streamlit headless で起動し、実行時キャッシュ、出力、ログ、ユーザー設定を `%LOCALAPPDATA%\SmartMarketAI` に保存します。配布物には `backend/`, `ui/`, `config/`, 必要最小限の `data/marketdata/`, `data/research_docs/`, `examples/rebalance_scenarios/` を同梱し、`.git/`, `venv_SMAI/`, cache、`outputs/`, live/raw取得物、秘密情報は含めません。

### Side menu

Streamlit UI は左サイドメニューで画面を切り替えます。
サイドメニューは画面選択と実行環境の簡易表示だけにし、各 workflow の入力はそれぞれの画面内に置きます。
配色・文字階層・カード・テーブル・ボタン・チャートの共通テーマは `ui/styles.py` の `THEME_COLORS` / CSS custom properties を正とします。AI分析、Research Summary、Decision Report などの生成・整理結果は cyan / blue 系の AI text / accent、投資判断やリスクは positive / warning / negative / info / neutral の semantic text / signal token を使います。

| screen | 役割 |
| --- | --- |
| `銘柄コックピット` | 1 銘柄の価格、予測、Investment Score、注意点を深掘りする |
| `銘柄ランキング` | 複数銘柄を条件で絞り、Investment Score で比較する |
| `リバランス` | 現在資産、目標配分、配分見直し候補、Risk 判定を確認する |
| `設定 / データ情報` | Runtime、config、scenario directory、銘柄候補を確認する |

### 銘柄コックピット

確認できるもの:

- provider / symbol / company name / period
- collapsible `銘柄候補フィルター` narrows the Symbol select list by preference: region, product, NISA, market cap, theme/sector, beta band, dividend/category, currency, PER/PBR/ROE/dividend yield ranges. Product defaults to `指定なし`, which does not narrow by stock / ETF. The separate candidate-list expander is intentionally omitted; the filtered count and Symbol select are the source of truth.
- cockpit period preset: `カスタム`, `短期: 1週間`, `短期: 1か月`, `中期: 3か月`, `中期: 6か月`, `年初来`, `長期: 1年`, `長期: 3年`, `長期: 5年`
- default cockpit period is `カスタム`; preset選択時は Start / End を自動表示し、`カスタム` の時だけ手入力する
- period preset help explains the intended review basis: short-term material reaction, medium-term trend, long-term drawdown resilience / structural change, and custom event windows
- collapsed sample symbol reference
- 価格・予測チャート: モデル数、平均予測の変化率、予測の開きを先に確認し、方向シグナルの数値重複を避ける
- `Signal Reading / シグナル読み取り`: Analysis KPI と同じ `上昇気配` / `下降警戒` を、予測変化率、モデル方向一致、予測のばらつきと合わせて解釈する。売買推奨ではなく比較・確認材料として扱う。
- forecast agreement compatibility、forecast spread、best RMSE model
- Investment Score summary
- score breakdown chart
- post-fetch confirmation summary lifts key closed-detail items into the main view: latest price, OHLCV period/volume, forecast range, screening components, short-term features, data quality, and forecast evaluation
- period-aware evaluation summarizes the fetched window as short-term reaction, medium-term trend, annual trend, or long-term resilience, with return, range position, drawdown, and volatility checks
- warnings / reasons
- Forecast metrics / Screening Score / provider detail
- Research Summary: `最新ニュース・開示サマリー` の近くに `投資ヒントとなるニュース` と `ニュース・開示の出典を表示（URL付きN件）` が出ます。`最新ニュース・開示サマリー` と `投資ヒントとなるニュース` は `Market Intelligence` の主表示カードとして扱い、`ニュース・開示の出典` は初期折りたたみの小さな citation list として元記事・TDnet・企業IR・EDINET・Yahoo Finance を開けます。`投資ヒントとなるニュース` はURL付きの一般ニュースだけを `注目材料 Top 3` として表示し、タイトル、公開日、鮮度、出典、材料分類、確認観点、短い要約、種別アクセントを優先します。raw URLはカード本文に出さず、hrefは維持します。TDnet、企業IR、EDINET、provider source、URL不足ニュースはこの専用カードに混ぜず、下部の `ニュース・開示の出典` と `詳細情報・開発者向け` で確認します。
- JSON / CSV downloads

### 銘柄ランキング

確認できるもの:

- provider
- 地域 / 商品 / 評価方針
  - 地域: `国内` / `米国` / `全体`
  - 商品: `株式` / `ETF` / `指定なし`
  - 評価方針: `AI総合` / `上昇気配重視` / `モメンタム・トレンド` / `成長クオリティ` / `割安クオリティ` / `高配当の持続性` / `低ボラ・安定` / `リスク調整パフォーマンス` / `小型・成長探索` / `NISA長期適合` / `データ信頼度優先` / `ETF低コスト・コア` / `ETFインカム・分散`
- `評価方針` はSMAIの複合評価プロファイルを選ぶ主導線です（画面上では `最新データを取得して更新` ボタンの横で選択）。
  - AI総合: `総合マルチファクター`。Screening、上昇気配・下降警戒、Risk、Data Quality、条件適合度、DB信頼度を総合評価する既定条件。
  - 上昇気配重視: 上昇気配と下降警戒の差し引き、Screening、Data Qualityを重視する。買い推奨ではなく、短期的な深掘り候補の整理に使う。
  - モメンタム・トレンド: 取得期間の価格評価、上昇気配・下降警戒、Screeningを重視し、追随リスクも確認する。
  - 成長クオリティ: ROE、上昇気配、Screening、Data Qualityを重視し、PER/PBRは成長期待との釣り合い確認に使う。
  - 割安クオリティ: PER/PBRの低さに加え、ROE、Risk、Data Qualityを確認し、割安に見える理由を確認しやすくする。
  - 高配当の持続性: 配当利回り、配当カテゴリ、Risk、PBR、Data Qualityを組み合わせ、極端な高配当は減配リスク確認対象にする。
  - 低ボラ・安定: Risk signal、β分類、Data Quality、銘柄規模を重視し、値動きの落ち着きを優先する。
  - リスク調整パフォーマンス: リターンだけでなくRisk signal、Data Quality、条件適合度を合わせて見る。
  - 小型・成長探索: 小型/中型、ROE、Screening、上昇気配を重視し、RiskとDB信頼度も確認する。
  - NISA長期適合: NISA適合、投資スタイル、Risk、Data Quality、ROEを重視する。
  - データ信頼度優先: metadata source、更新日、Data Quality、欠損の少なさを最優先する。
  - ETF低コスト・コア: 経費率、連動指数、複雑性、NISA適合、DB信頼度を重視する。
  - ETFインカム・分散: ETFの利回り、経費率、指数、通貨、複雑性、Data Qualityを重視する。
  - 旧来の `配当重視` / `成長重視` / `割安重視` / `安定重視` / `トレンド重視` は内部互換として残すが、上部UIでは代表プロファイルへ統合して重複表示しない。
- ランキング結果画面では、`評価方針` で候補を採点し、そのスコア順に上位カード / Top 10棒グラフ / 確認メモを表示する。単一指標ソートは上部ドロップダウンには置かず、詳細テーブルの列ヘッダークリックで表示中データをローカルに並べ替える。詳細テーブルは `順位` / `銘柄` / `銘柄名` / `総合スコア` / `配当利回り` / `PER` / `PBR` / `ROE` / `見方` を常時表示する。`総合スコア` / `配当利回り` / `ROE` / `時価総額` / `出来高` / `データ品質` / `スクリーニング` / `上昇気配` は高い順、`PER` / `PBR` / `ボラティリティ` / `リスク` / `下降警戒` は低い順を最初に確認する。メインチャートは選択中の `評価方針` で使う代表指標の比較であり、詳細テーブルの列ソートでは自動切替しない。欠損値は `N/A` として表示し、ソート時は末尾に置く。データ品質 / 条件適合度 / DB信頼度 / 根拠状態は必要に応じて `信頼度/根拠` にまとめる。長い評価理由、確認ポイント、スコア内訳、取得状態は tooltip / 行クリック後の銘柄データで確認する。
- `上昇気配` / `下降警戒` は、予測エッジ、モデル別方向エッジ、価格モメンタム、トレンド確認を組み合わせる。予測変化率とモメンタムはボラティリティ調整し、モデル間の開きは直接加点せず、スコアを中立へ寄せる信頼度調整として扱う。ランキングは売買推奨ではなく、深掘り候補の比較優先度として扱う。
- `作成対象` は、外部 provider 取得前の件数上限です。既定は `標準: 上位300件` で、候補が多い場合は総合マルチファクター基準の条件適合度とDB信頼度で事前に上位候補を選んでから価格データを取得します。`評価方針` の変更、詳細テーブルの列ソート、検索、絞り込みは取得対象を変えず、取得済みデータの再評価・再ソートとして扱います。外部取得は `最新データを取得して更新` を押した場合のみ実行します。全件取得も選べますが、Yahoo live data では時間がかかります。
- ランキング結果の総合スコアには、取得期間の市場評価に加えて、条件適合度とDB信頼度を反映する。
  - 条件適合度: NISA、時価総額、配当、PER/PBR/ROE、ETF経費率、複雑性などを評価方針別に評価する。投資魅力度を直接保証するものではありません。
  - DB信頼度: `metadata_source`、`metadata_as_of` / `metadata_updated_at`、ランキング判断に使う主要項目の登録状況を評価する。
- 基本条件
  - period preset: `短期: 1か月` / `標準: 3か月` / `中期: 6か月` / `長期: 1年`
  - currency
  - 配当/分配金カテゴリ
  - 配当/分配金利回り
  - market-cap tier
  - ETF index family
  - max expense ratio
  - theme
  - keyword
- 常設の詳細条件パネル
  - `属性条件` / `数値条件` / `キーワード検索` に分けて表示
  - 地域 × 商品に応じて、現在の銘柄マスタで判定できる詳細条件だけを表示
  - 株式: 業種/テーマ、時価総額、市場感応度（β）、配当利回り、PER、PBR、ROE、NISA
  - ETF: 連動指数、信託報酬/経費率、分配金利回り、複雑さ
  - `取得期間` の `?` help では、標準3か月は20日/60日系の予測材料、1か月は直近反応、6か月は中期トレンド、1年は安定性確認に使うことを説明
  - 時価総額は、日本株では 10兆円 / 1兆円 / 1,000億円 / 100億円、米国株では $200B / $10B / $2B / $300M を目安に表示
  - 配当/分配金カテゴリは、0%、0%超〜3%未満、3%以上の利回り帯を選択肢に表示。ただし連続増配候補は curated metadata 由来
  - 配当/分配金カテゴリと数値条件の `配当/分配金利回り(%)` は同じ軸の条件なので、片方を指定した場合はもう片方を非活性にする
  - 各条件の `?` help で、指標の意味、目安値、注意点を確認可能
  - 条件のクリア
  - 条件変更後の候補数表示
- 比較する銘柄
  - 初期状態では候補をすべて選択
  - 取得期間、候補数、選択数は銘柄リストの上に1行で表示
  - 銘柄リストは折りたたみ内で確認・変更
- ranking result with ticker / company name / score / warnings
- ranking result は AgGrid で表示し、銘柄行をクリックするとローカル銘柄マスタ `symbol_universe.csv` の登録値をモーダルで確認できます
- 銘柄データモーダルの `AI Research` タブでは、`AIで資料を確認` を押した場合だけ登録済みResearch資料を検索し、Research Summary、根拠資料名、資料日、根拠数、詳細 evidence を確認できます
- 選択銘柄をコックピットへ渡す deep-dive flow

注意:

- ranking の候補条件は、provider fetch 前に使える `data/marketdata/symbol_universe.csv` の curated metadata を中心にしています。
- 地域 / 商品 / 詳細条件は provider fetch 前の候補 universe を絞ります。`重視して並べ替え` は Investment Score の表示順の重み付けに使い、候補 universe そのものは絞りません。
- `市場感応度（β）` は metadata の `risk_band` を使う provider fetch 前の条件です。β 0.8未満を低変動、0.8〜1.2を市場並み、1.2超を高変動として扱います。
- Ranking result の Risk / リスクスコアは取得期間の価格データを見た後の確認材料です。候補条件の `市場感応度（β）` とは別の指標として確認します。
- 投資信託は MVP のランキング / スクリーニング / チャート対象外です。source seed や metadata schema は将来対応として残しますが、default ranking universe と UI の主要導線には出しません。
- 配当/分配金カテゴリや theme は現在 curated metadata / source import / opt-in metadata refresh で管理します。live provider 由来の更新は明示 opt-in です。配当テーマは業種/テーマの選択肢には出さず、配当/分配金カテゴリまたは配当/分配金利回り条件で扱います。
- 株式の `業種/テーマ` は `theme`, `sector`, `tags` を見ます。JPX 東証上場銘柄一覧の `規模区分` は `market_cap_tier` へ変換し、`時価総額` 条件で使います。
- 株式の `investment_style` は、国内株・米国株とも一括投資向きの候補として `lump_sum` に機械バックフィルしています。ETF の積立可否は source 確認が必要なため、未確認の `investment_style=unknown` は残します。
- ETF の `nisa_category` は、JPX / IMAJ / SBI のローカル公式 source CSV と照合し、現在の ETF 1,046件では `growth` または `none` に確定済みです。未確認の `unknown` は ETF には残していません。
- Ranking UI の NISA 条件は `指定なし（NISAで絞らない）` / `NISA対象のみ（成長投資枠）` / `NISA対象外のみ` です。現在の株式候補は国内株・米国株とも成長投資枠対象として整理済みのため、株式で `NISA対象のみ（成長投資枠）` を選んでも候補数が変わらない場合があります。ETF は対象/対象外が混在するため、この条件で候補数が変わります。
- ranking universe の MVP 方針は、SBI証券で取り扱いがあり、現物・NISA・長期投資で検討しやすい株式・ETFを初期対象にすることです。詳細は [09_SBI_Symbol_Universe_Policy.md](./09_SBI_Symbol_Universe_Policy.md) を参照してください。
- `broker`, `tradability`, `nisa_category`, `investment_style`, `is_sbi_supported`, `is_active`, `is_leveraged`, `is_inverse` は Phase 18 policy columns として `symbol_universe.csv` に保持します。既存候補は local curated / source-import seed であり、SBI取扱確認済み master ではないため、`tradability=unknown` は初期 ranking で通します。
- ranking 候補抽出前に default SBI ranking universe policy を適用します。MVP の対象は `stock` / `etf` です。`mutual_fund` / `fund` / `investment_trust` / `adr` / `reit` / FX / CFD / 先物 / option / crypto / bond / MMF / commodity、レバレッジ、インバース、`not_tradable`、`is_sbi_supported=false`、`is_active=false` は初期候補から除外します。
- `symbol_universe.csv` は Phase 16/18 UI 用の銘柄候補マスタです。必須列は `symbol`, `name`, `market`, `asset_type`, `currency`, `broker`, `tradability`, `nisa_category`, `investment_style`, `is_sbi_supported`, `is_active`, `is_leveraged`, `is_inverse`, `theme`, `dividend_category`, `dividend_yield_pct`, `market_cap_tier`, `index_family`, `expense_ratio_pct`, `complexity`, `tags`, `aliases`, `per`, `pbr`, `roe_pct`, `sector`, `consensus_rating`, `forecast_agreement`, `data_quality`, `risk_band` です。任意列 `yahoo_symbol` は、表示用 symbol と Yahoo 取得用 symbol が異なる ETF で使います。
- Phase 18 metadata columns は `metadata_source`, `metadata_as_of`, `metadata_updated_at` です。現在の master は `curated_csv`, `yahoo`, `jpx`, `imaj`, `jpx_nisa_growth`, `sbi_us_stock`, `sbi_us_etf`, `sbi_us_stock_removed`, `sbi_us_etf_removed`, `manual`, `mutual_fund_seed` などの metadata source を行ごとに保持します。
- Metadata fields are governed by `backend/marketdata/symbol_metadata_schema.py`.
  - `core`: symbol, name, market, asset type, currency, sector/theme, aliases.
  - `ranking_filter`: dividend, PER/PBR/ROE, expense ratio, risk, complexity, quality fields. Source/freshness is tracked before live provider updates are trusted.
- `fund_extended`: trust fee, AUM, NISA eligibility, installment availability, management style, and distribution policy. Mutual-fund seed/source import rows can store these fields in `symbol_universe.csv`, but these fields are future extension metadata and are not MVP ranking filters.
- `設定 / データ情報` の `ランキング銘柄候補` では、候補数、metadata 出所、metadata 基準日、形式確認 status を確認できます。CSV の列形式 / 選択値 / 数値 / 重複 ticker / metadata 欠損に問題がある場合は一覧に表示されます。
- 常設パネルで条件を変えると、候補数と「比較する銘柄」の選択候補が同じ画面内で確認できます。

Symbol universe metadata refresh:

- `tools/refresh_symbol_universe_metadata.py` は provider-neutral な metadata refresh command です。
- 現在実装済みの provider は network 非依存の `curated_csv` と、明示 opt-in の `yahoo` です。
- 既定は dry-run で、CSV / manifest は書き換えません。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\refresh_symbol_universe_metadata.py --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

- Yahoo live metadata は外部通信のため `--provider yahoo --allow-live` を明示した場合だけ実行します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\refresh_symbol_universe_metadata.py --provider yahoo --allow-live --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

- `--write` を付けた場合だけ `symbol_universe.csv` と `data/marketdata/symbol_universe_manifest.json` を更新します。write 前に validation error が残る場合は書き込みを拒否します。
- Yahoo provider は取得できた `sector`, `dividend_yield_pct`, `dividend_category`, `per`, `pbr`, `roe_pct`, `market_cap_tier`, `risk_band`, ETF の `expense_ratio_pct`, metadata source/as-of/update fields を正規化して返します。`dividendYield` は yfinance が返す percentage value として扱い、`trailingAnnualDividendYield` は ratio から percentage に変換します。ETFの `annualReportExpenseRatio` は ratio から percentage に変換し、`netExpenseRatio` は percentage value として扱います。非数値、無限大、負の PER/PBR/配当/分配金利回り/経費率など schema に入れられない値は空欄のままにします。失敗銘柄は manifest の `failed_symbols` / `failures` に残します。
- live metadata refresh は対象を絞って実行できます。`--symbols`, `--asset-type`, `--market`, `--metadata-source`, `--missing-any`, `--limit` を使い、いきなり全件取得しない運用を推奨します。manifest の `selection` に対象件数と対象銘柄sampleを残します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\refresh_symbol_universe_metadata.py --provider yahoo --allow-live --asset-type stock --market jp --metadata-source jpx_listed_stock --missing-any per,pbr,roe_pct,dividend_yield_pct --limit 20 --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00
```

- 問題なければ `--write` を付けて同じ条件を反映します。live取得は通信状態やprovider応答に依存するため、失敗銘柄は manifest で確認し、必要に応じて小さい単位で再実行します。

Symbol universe source import:

- `tools/build_symbol_universe_source.py` は、公式 raw file を SMAI 用 source CSV へ変換する command です。現在は JPX の東証上場銘柄一覧から国内株 source を作る `--source-kind jpx_listed_stock`、JPX 国内 ETF / ETN source を作る `--source-kind jpx_etf`、JPX listed REIT source を作る `--source-kind jpx_reit`、SBI米国株 / 米国ETF・海外ETF のローカル raw file から source を作る `--source-kind sbi_us_stock` / `sbi_us_etf`、NISA制度 metadata 更新 source を作る `--source-kind nisa_eligibility` に対応しています。raw file は CSV、Excel (`.xls` / `.xlsx`)、JPX ETF/ETN / REIT 公式一覧の HTML、SBI の CP932 HTML を扱えます。PDF は通常 import 対象外です。既定は dry-run で、`--write` を付けた場合だけ source CSV / manifest を書き込みます。
- `tools/import_symbol_universe_source.py` は、JPX などのローカル source CSV を `symbol_universe.csv` 形式へ取り込む command です。
- 既定は dry-run で、`--write` を付けた場合だけ CSV / manifest を更新します。write 前に validation error が残る場合は書き込みを拒否します。
- 初期 source として `data/marketdata/symbol_universe_sources/jpx_etf_seed.csv` と `data/marketdata/symbol_universe_sources/jpx_stock_seed.csv` を置いています。2026-05-20 時点では JPX 東証上場銘柄一覧から国内株 3,645件を追加し、JPX seed と合わせて `symbol_universe.csv` に取り込み済みです。国内株 3,747件と米国株 4,334件は NISA 成長投資枠対象として `nisa_category=growth`, `nisa_growth_eligible=true`, `nisa_tsumitate_eligible=false` に整理済みです。2026-05-26 時点では JPX ETF/ETN 公式一覧 HTML 402件、JPX NISA ETF/ETN Excel 28件、IMAJ NISA listed-fund Excel 294件、SBI公式米国株 HTML 4,330行、SBI公式米国ETF HTML 612件を source 化しています。candidate master は 9,197件です。IMAJ source に含まれるインフラファンド等 5件は現行 MVP の候補マスタには未登録のため、`nisa_eligibility` の update-only failure として manifest に残します。
- MVP 向け source profile として `jpx_listed_stock`, `jpx_stock`, `jpx_etf`, `jpx_reit`, `sbi_us_stock`, `sbi_us_etf`, `sbi_availability`, `nisa_eligibility`, `quality_review`, `ranking_metadata` を使えます。`mutual_fund_seed` は将来対応用 profile として残します。
- 追加 seed として `sbi_us_stock_seed.csv`, `sbi_us_etf_seed.csv`, `mutual_fund_seed.csv` を置いています。SBI US stock / ETF は 2026-05-21 の公式 HTML source に置き換えて拡張済みです。投信 4件は future extension seed として保持し、default ranking universe から除外します。
- `nisa_eligibility_seed.csv` は既存の株式・ETF 31件へ NISA metadata を付与する local seed です。2026-05-19 時点で `symbol_universe.csv` に反映済みです。国内株と米国株は stock profile 側で成長投資枠対象として扱い、ETF / REIT / 投信など個別判定が必要な商品は `nisa_eligibility` source で更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_seed.csv --source-profile jpx_etf --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

JPX 東証上場銘柄一覧を使う場合は、先に公式 Excel (`.xls` / `.xlsx`) / CSV を `data/marketdata/raw/` などに保存し、SMAI 用 source CSV に変換します。ETF / ETN / REIT はこの builder では除外し、国内株だけを `jpx_listed_stock` source として作ります。JPX の `規模区分` は `TOPIX Core30 -> mega`, `TOPIX Large70 -> large`, `TOPIX Mid400 -> mid`, `TOPIX Small 1/2 -> small` として `market_cap_tier` に変換します。国内株 import profile は、NISA 成長投資枠が上場株式等を対象にする制度であることを前提に `growth / true / false` を既定値にします。整理・監理銘柄などの例外が確認できた場合は、後続の `nisa_eligibility` source で `none` などへ明示更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_listed_stock --raw-file .\data\marketdata\raw\jpx_listed_stock_20260520.xls --output-csv .\data\marketdata\symbol_universe_sources\jpx_listed_stock_20260520.csv --as-of 2026-05-20 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_listed_stock_20260520.csv --source-profile jpx_listed_stock --as-of 2026-05-20 --updated-at 2026-05-20T00:00:00+09:00 --write
```

JPX 国内 ETF / ETN を使う場合は、JPX ETF raw file を `jpx_etf` source として変換します。公式 ETF/ETN 一覧 HTML も扱えます。builder は `.T` 付き symbol、指数 family、信託報酬、商品系 theme、ETN / レバレッジ / インバース判定を保持します。商品系ETF、レバレッジ、インバースは ranking universe policy 側で除外できます。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_etf --raw-file .\data\marketdata\raw\jpx_etf_2026-05.xlsx --output-csv .\data\marketdata\symbol_universe_sources\jpx_etf_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_2026-05.csv --source-profile jpx_etf --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_etf --raw-file .\data\marketdata\raw\jpx_etf_20260520.html --output-csv .\data\marketdata\symbol_universe_sources\jpx_etf_20260520.csv --as-of 2026-05-20 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_20260520.csv --source-profile jpx_etf --as-of 2026-05-20 --updated-at 2026-05-20T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_20260520.csv --source-profile jpx_etf --as-of 2026-05-20 --updated-at 2026-05-20T00:00:00+09:00 --update-existing --write
```

JPX の「NISA 成長投資枠対象銘柄一覧」のように、列名にふりがなが含まれる Excel も `jpx_etf` / `nisa_eligibility` source として扱えます。銘柄本体を追加してから制度 metadata を更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_etf --raw-file .\data\marketdata\raw\jpx_etf_20260521_NISA.xlsx --output-csv .\data\marketdata\symbol_universe_sources\jpx_etf_nisa_growth_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_nisa_growth_20260521.csv --source-profile jpx_etf --source-name jpx_nisa_growth --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind nisa_eligibility --raw-file .\data\marketdata\raw\jpx_etf_20260521_NISA.xlsx --output-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_jpx_etf_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_jpx_etf_20260521.csv --source-profile nisa_eligibility --source-name jpx_nisa_growth --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --update-existing --write
```

JPX REIT を保持する場合は、JPX REIT 公式 HTML を `jpx_reit` source として変換します。REIT は master に保持しますが、MVP ranking universe では `reit` を初期対象外にしているため、ランキング候補には出ません。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_reit --raw-file .\data\marketdata\raw\jpx_reit_20260521.html --output-csv .\data\marketdata\symbol_universe_sources\jpx_reit_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_reit_20260521.csv --source-profile jpx_reit --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --write
```

IMAJ の「NISA成長投資枠対象の対象銘柄（国内ETF、REIT等）」Excel は、複数シート構成でも対象シートを自動検出します。5桁で末尾 `0` が付く国内コードは4桁 `.T` symbol に正規化します。REIT を追加した後に再適用すると REIT の NISA metadata も更新できます。インフラファンドなど未登録 symbol は update-only failure として manifest に残します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind nisa_eligibility --raw-file .\data\marketdata\raw\imaj_nisa_growth_listed_fund_20260519.xlsx --output-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_imaj_listed_fund_20260519.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_imaj_listed_fund_20260519.csv --source-profile nisa_eligibility --source-name imaj --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --update-existing --write
```

SBI米国株 / 米国ETF・海外ETF の取扱一覧を使う場合も、まずローカル raw CSV / Excel / HTML を source CSV に変換します。SBI公式HTMLは CP932 を扱えます。`sbi_us_stock` builder は米国株ページ内に混在するETF表を stock として取り込まないようにスキップします。`sbi_us_stock` builder は既知のクラス株式表記として `BRKB` / `UHALB` を Yahoo-compatible な `BRK-B` / `UHAL-B` に正規化します。米国株 import profile は NISA 成長投資枠を既定で `growth / true / false` にします。`sbi_us_etf` builder は、名称や明示フラグからレバレッジ / インバース ETF を判定し、後段の ranking universe policy で除外できるように `is_leveraged` / `is_inverse` を保持します。現在取り込んだ SBI 公式 ETF HTML は米国形式 ticker が中心です。将来 raw に香港・韓国・シンガポールなどの市場別コードが含まれる場合は、Yahoo symbol suffix / 通貨 / exchange mapping を決めてから追加します。
SBI source は公式ページ内に同一 ticker の重複・旧表記が混在する場合があります。既存銘柄の名称を一括上書きせず、通常は新規追加だけを `sbi_us_stock` / `sbi_us_etf` で行い、最新一覧から消えた銘柄は `sbi_availability` profile で `tradability=not_tradable`, `is_sbi_supported=false` に更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind sbi_us_stock --raw-file .\data\marketdata\raw\sbi_us_stock_2026-05.csv --output-csv .\data\marketdata\symbol_universe_sources\sbi_us_stock_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind sbi_us_etf --raw-file .\data\marketdata\raw\sbi_us_etf_2026-05.csv --output-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_stock_2026-05.csv --source-profile sbi_us_stock --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_2026-05.csv --source-profile sbi_us_etf --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind sbi_us_stock --raw-file .\data\marketdata\raw\sbi_us_stock_20260521.html --output-csv .\data\marketdata\symbol_universe_sources\sbi_us_stock_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind sbi_us_etf --raw-file .\data\marketdata\raw\sbi_us_etf_20260521.html --output-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_stock_20260521.csv --source-profile sbi_us_stock --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_20260521.csv --source-profile sbi_us_etf --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --write
```

JPX のように source 側が4桁コードで、SMAI 側では yfinance-compatible な `.T` suffix が必要な場合は、`jpx_stock` profile を使います。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_stock_seed.csv --source-profile jpx_stock --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

SBI profile の dry-run 例:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_seed.csv --source-profile sbi_us_etf --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

NISA eligibility のように既存銘柄の制度 metadata だけを更新する場合は `--source-profile nisa_eligibility --update-existing` を使います。この profile は `nisa_category`, `nisa_growth_eligible`, `nisa_tsumitate_eligible`, metadata source/as-of/update fields だけを更新し、既存の市場や商品分類は上書きしません。公式または確認済み raw file から source CSV を作る場合は、先に `--source-kind nisa_eligibility` で 4桁国内コードを `.T` 付き symbol に変換し、成長投資枠 / つみたて投資枠 / 対象外を canonical fields に正規化します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind nisa_eligibility --raw-file .\data\marketdata\raw\nisa_eligibility_2026-05.csv --output-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_2026-05.csv --source-profile nisa_eligibility --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --update-existing
```

Ranking metadata のように既存銘柄の条件列だけを更新する場合は `--source-profile ranking_metadata --update-existing` を使います。テンプレートは `data/marketdata/symbol_universe_sources/ranking_metadata_template.csv` です。この profile は `PER`, `PBR`, `ROE`, `配当利回り`, `時価総額`, `リスク`, ETF の `信託報酬/経費率` など ranking filter 用 metadata だけを更新し、名称・市場・商品分類は上書きしません。source CSV には `per` / `pe_ratio`, `pbr` / `price_to_book`, `roe_pct` / `roe`, `dividend_yield_pct` / `dividend_yield` などの列名を使えます。未確認値は空欄のままにし、推定値で埋めません。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\ranking_metadata_2026-05.csv --source-profile ranking_metadata --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --update-existing --write
```

provider 再取得後も極端な値が残るなど、数値を修正せず注意フラグだけ付けたい場合は `quality_review` profile を使います。この profile は `data_quality` と metadata fields だけを更新し、PER/PBR/ROE や商品分類は上書きしません。

Ranking metadata coverage:

- `tools/check_symbol_universe_metadata_coverage.py` は、`symbol_universe.csv` の ranking filter 用 metadata がどの程度埋まっているかを network なしで集計します。
- 2026-06-01 時点の出力は `data/marketdata/symbol_universe_metadata_coverage.json` です。candidate master 9,197件は、明示 opt-in の Yahoo metadata refresh 後に全行 `metadata_source=yahoo`, `metadata_as_of=2026-06-01` になっています。全体では `配当利回り` 9,091件、`PER` 7,222件、`PBR` 7,716件、`ROE` 7,532件、`信託報酬/経費率` 1,027件が埋まっています。取得不可の値は `0` で埋めず空欄のままにし、UI では `N/A` として扱います。
- Yahoo provider / yfinance の書き込み値を `symbol_universe.csv` の運用上の source-of-record とします。Yahoo Japan などのWeb画面や ETF 情報サイトは sanity check の参照に使いますが、trailing / forward / 会社予想 / TTM / 更新タイミングの違いがあるため完全一致は受け入れ条件にしません。正確な監査済み財務値が必要な場合は、将来の公式IR / 有価証券報告書 / 追加 verified provider の取り込み対象として扱います。
- DB書き込み時は `dividend_yield_pct > 20`, `PER <= 0 or > 200`, `PBR <= 0 or > 50`, `ROE < -100 or > 100` をランキング用の異常値として空欄化します。これらは詳細テーブル、カード、確認メモで `N/A` / 要確認相当として扱い、総合スコアやランキング計算には混入させません。
- Phase 18 の実装完了後は、NISA / ETF / stock metadata source の継続更新、上記の provider/source 欠損補完、海外ETF `yahoo_symbol` mapping の追加 live smoke は運用タスクとして扱います。これらは通常のリリース完了条件ではなく、確認済み source や network 利用可能時に更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\enrich_symbol_universe_etf_metadata.py --write
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_metadata_coverage.py --checked-at 2026-06-01T14:55:00+09:00 --write
```

- `tools/enrich_symbol_universe_etf_metadata.py` は、ETF の `index_family` 補完に加え、`data/marketdata/symbol_universe_sources/` 配下の JPX / IMAJ / SBI 公式 source CSV を使って ETF の NISA 対象 / 対象外を照合します。名称だけで NISA を推定しません。

SBI ranking universe policy:

- MVP対象: 国内株式、米国株式、国内ETF、米国ETF/海外ETF。
- 初期除外: 投資信託、ADR、REIT、FX、CFD、先物・オプション、暗号資産、債券、外貨建MMF、貴金属・コモディティ系ETF、レバレッジ、インバース、非tradable、非SBI対応。
- `symbol_universe.csv` / schema に SBI policy columns を追加済みです。local curated / source-import seed は conservative default として `broker=sbi_securities`, `tradability=unknown`, `is_sbi_supported=true`, `is_active=true`, `is_leveraged=false`, `is_inverse=false` を持てます。JPX 国内株と SBI 米国株 profile は `nisa_category=growth`, `investment_style=lump_sum` を既定値にし、ETF / REIT / 投信など個別判定が必要な商品では source 更新します。
- `tradability=unknown` は stock / ETF の初期 seed として通し、`not_tradable` だけを除外します。NISA metadata は国内株・米国株の成長投資枠 backfill と ETF / REIT source import まで反映済みです。ETF は公式 source 照合により `nisa_category=unknown` を解消済みです。投信公式 source import は Future Phase です。
- SBI証券サイトへのログインや画面スクレイピングは通常 workflow に含めません。SBI / JPX / NISA 一覧などを手動または curated source CSV に整形し、source import command で local master へ反映します。投信協会 / 投信CSV / 基準価額は Future Phase で扱います。
- Ranking / Screening は source site を直接参照せず、`symbol_universe.csv` と default policy helper だけを参照します。
- 投信向け metadata として `trust_fee_pct`, `aum`, `nisa_tsumitate_eligible`, `nisa_growth_eligible`, `installment_available`, `management_style`, `distribution_policy` を source CSV から取り込めます。ただし MVP ではランキング対象外です。
- 現在の候補マスタは 9,197件です。内訳は stock 8,087件、ETF 1,046件、REIT 58件、投信 4件、ADR 2件です。default ranking universe では stock / ETF のみを対象にします。2026-05-26 更新では、SBI最新一覧から消えた米国株19件・米国ETF5件を削除せず、履歴確認できるよう `not_tradable` / `is_sbi_supported=false` として保持しています。

Yahoo coverage check:

- `tools/check_symbol_universe_yahoo_coverage.py` は、`symbol_universe.csv` の対象行について Yahoo OHLCV（日足価格）を取得できるか確認する live smoke command です。外部通信を使うため、通常の local checks / CI には含めません。
- 国内株の確認例。metadata refresh 後は `metadata_source` が `yahoo` になるため、通常は `--asset-type stock --market jp` を主条件にします。refresh 前の raw/source 単位で確認する場合だけ `--metadata-source jpx_listed_stock` などを明示します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_yahoo_coverage.py --asset-type stock --market jp --sample-size 30 --batch-size 10 --timeout-ms 15000 --start 2026-05-12 --end 2026-05-20 --label yahoo_coverage_jp_stock_sample30_20260520
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_yahoo_coverage.py --asset-type stock --market jp --batch-size 25 --timeout-ms 20000 --start 2026-05-12 --end 2026-05-20 --label yahoo_coverage_jp_stock_full_20260520
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_yahoo_coverage.py --asset-type stock --market us --metadata-source sbi_us_stock --batch-size 50 --timeout-ms 25000 --start 2026-05-12 --end 2026-05-20 --label yahoo_coverage_sbi_us_stock_full_20260520
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_yahoo_coverage.py --asset-type etf --market us --metadata-source sbi_us_etf --batch-size 50 --timeout-ms 25000 --start 2026-05-12 --end 2026-05-20 --label yahoo_coverage_sbi_us_etf_full_20260520
```

- 2026-05-21 に実行した JPX 追加国内株の Yahoo coverage check では、サンプル 30件は 30/30 件成功。全数 3,645件は 3,641件成功、4件は短期期間で `YAHOO-NO-BARS` でした。失敗4件の個別再試行では、`9237.T` は同じ短期期間で取得成功し、`2344.T` / `4530.T` / `6565.T` は 2026-04-01 からの長め期間では取得できるものの、2026-05-12 〜 2026-05-20 ではバーがありませんでした。
- 2026-05-21 に実行した SBI 米国株 / 米国ETF の Yahoo coverage check では、米国株サンプル 30/30、米国株全数 4,240/4,293、米国ETFサンプル 29/30、米国ETF全数 593/607 が成功しました。失敗はすべて短期期間での `YAHOO-NO-BARS` です。クラス株式表記を正規化した `BRK-B` / `UHAL-B` の個別再確認は 2/2 成功しました。
- `--symbols` を使うと、失敗銘柄や表記修正後の銘柄だけを小さく再確認できます。
- `tools/analyze_yahoo_coverage_failures.py` は保存済みの coverage CSV を、銘柄マスタと照合して原因別に棚卸しします。2026-05-22 時点では、SBI米国株の失敗53件は `no_bars_short_window_or_yahoo_unsupported` 51件、旧表記 alias 解決済み2件です。SBI米国ETFの失敗14件は、レバレッジ除外3件、`yahoo_symbol` mapping 済み11件です。mapping 済み行は ranking / rebalance の Yahoo 取得時に provider symbol へ変換します。
- 結果は `data/marketdata/live_checks/` に JSON / CSV で保存します。

Phase 16 ranking implementation notes:

- `data/marketdata/symbol_universe.csv` is the ranking candidate master used before provider fetch. It is intentionally curated/local-first and currently carries display/search/filter metadata such as `symbol`, `name`, `market`, `asset_type`, `currency`, `theme`, `dividend_category`, `dividend_yield_pct`, `market_cap_tier`, `index_family`, `expense_ratio_pct`, `complexity`, `tags`, `aliases`, `per`, `pbr`, `roe_pct`, `sector`, `consensus_rating`, `forecast_agreement`, `data_quality`, and `risk_band`. Optional `yahoo_symbol` is used only when Yahoo needs a different ticker than the display/source symbol.
- Streamlit startup starts a daemon background symbol DB refresh worker instead of blocking the UI. The worker reads `symbol_universe.csv`, writes latest-only normalized records to `data/cache/symbols_cache.json`, keeps `symbol_refresh_queue.json` empty after successful batches, and updates `symbol_refresh_status.json`. The current network-free maintenance plan is: immediate startup batch 150 symbols, 75 symbols after 3 minutes, 75 symbols after 8 minutes, then 50 symbols every 5 minutes, with fresh records skipped and a 1000-symbol per-session safety cap.
- To check whether any symbol is stuck in the refresh queue, inspect `symbol_refresh_queue.json` or run `backend.symbols.startup.find_pending_symbol_refresh_tasks()`. A healthy post-startup state has no `pending`, `retryable`, or `in_progress` tasks left after the local batch completes.
- The Phase 18 schema helper validates required columns, allowed enum values, decimal fields, duplicate tickers, and metadata freshness/source columns without requiring live provider access.
- The in-page screening condition panel filters comparison candidates by metadata, NISA eligibility, and metric ranges. `取得期間` and `重視して並べ替え` are not screening filters; they control ranking calculation and display ordering.
- Ranking build uses a fast batch path first: it fetches OHLCV in chunks, builds feature snapshots from already-fetched market data, then reuses existing Screening / Investment Score services. If the batch path fails with a provider/domain error, local/deterministic providers can fall back to the existing per-symbol preview path; live Yahoo failures are reported once without retrying every symbol to avoid repeated network failures.
- Yahoo OHLCV uses the same non-threaded yfinance download path for single-symbol cockpit and multi-symbol ranking requests. The cockpit reuses one fetched OHLCV range for quote display and feature construction instead of fetching the same symbol again. Yahoo cockpit fetch prioritizes price data: initial fetch skips live FX and fundamentals so price / forecast / score rows can render without waiting on nonessential live requests. SMAI shares one curl_cffi-backed yfinance session across `Search`, `download`, and `Ticker` calls so Yahoo cookie / crumb state stays attached to the same session. If yfinance returns an empty batch response, the provider retries once after a short delay to absorb first-call warm-up / transient empty responses. Because live Yahoo requests are network-dependent and can be slow or noisy, Streamlit ranking warns when selected symbols exceed 30, uses smaller non-threaded download chunks, and suppresses yfinance's raw console noise in favor of structured UI error rows.
- Ranking rows are cached in Streamlit session state by `provider + symbols + start + end`. Re-running the same request or changing only the ranking weight preset reuses fetched rows and only re-sorts the display.
- Ranking display rows reuse a single symbol-master lookup map when building notes and modal guidance. This avoids repeated `symbol_universe.csv` scans during long-period ranking reruns and keeps row-click symbol-detail modal opening responsive.
- The ranking progress indicator reports batch fetch, feature construction, direction signal calculation, and final sorting so large candidate sets do not look frozen.
- Ranking deep-dive controls are rendered before the Decision Report block. The ranking Decision Report is generated lazily by `投資判断レポートを作成`, then reused for the same ranking source / evaluation policy so resorting and cockpit handoff remain responsive. Ranking report は上位候補メモとスコア詳細を分け、明細には symbol、銘柄名、評価方針、確認観点を並べて出力する。
- Ranking remains decision support only. Click a ranking row to open the shared `銘柄データ` modal with short ranking context plus local master details. Use the cockpit for detailed price / forecast / score-reason review.
- In `銘柄コックピット`, `銘柄データを見る` sits beside symbol selection and opens the same local-master modal for the selected symbol. Start / End inputs wrap to the next row. After fetch, the cockpit shows `投資判断メモ` combining score, warnings, valuation, income, price trend, and next-check wording. Research Evidence starts with an operation card that says `AI調査で確認すること` / `確認方針` before fetch, labels the button area as `調査アクション`, and shows `企業リサーチレポートを更新しました` after fetch. When AI Research has a report, the result panel begins with `企業リサーチサマリー`, followed by `定量情報サマリー`, `IR情報サマリー`, and `最新ニュース・開示サマリー`. These sections explain the company overview, main businesses, products/services, regions, scale, key metrics, IR availability, news/disclosures, and missing critical items as a company-understanding report. Normal UI keeps `企業理解の確認ポイント` as the main follow-up, while `詳細情報・開発者向け` is limited to distinct verification data such as Research Score, data-quality warnings, documents/source rows, grounded answers, retrieval quality, extracted claims, evidence detail, and external-source fetch status.
- `銘柄コックピット` と `銘柄ランキング` のresult areaには、Markdown / JSON / manifest / ZIP downloadsを持つ目立つ `Decision Report` blockを表示する。Markdownは人が読むmemo、JSONはstructured reproduction context、manifestはpackage contentsの説明、ZIPはfull package保存用。Cockpit reportsは、overall judgement card、3-line summary、main evidence block、sectioned detail expandersを持つstructured UIとして先に表示する。Cockpit / Ranking Research Summary panels は、AI Research reportがある場合にResearch Score summary、component、warning rowsを参考contextとして表示する。Cockpit では `Research Score（根拠資料の確認材料）` の折りたたみ内に読み方、要約、観点別内訳、注意点をまとめ、詳細データ側は検索品質や根拠詳細を中心にする。Ranking selected-candidate breakdownはreport-derived Research Score / confidenceを確認材料として表示できるが、ランキング順位は変えない。Cockpit `AI調査を更新` でResearch reportが作成され、documentsまたはevidenceがある場合、exported contextには `Research Evidence` と `Research Score` sectionsが入り、component rows、confidence、supporting evidence、warnings、non-advice notesを保存する。Ranking reportsは単一top-symbol reportではなく、comparison context、score distribution、factor leaders、group-level deep-dive checkpointsを中心にする。Ranking Markdown bodyは `レポート本文を表示` 内に置く。これはpoint-in-time analysis memoであり、buy/sell/hold instructionではない。
- In `リバランス`, the result area shows a prominent `投資判断レポート` block with Markdown / JSON / manifest / ZIP downloads. The report organizes current holdings, target allocation, allocation drift, rebalance review candidates, Risk breaches, and confirmation checkpoints. The Markdown body remains inside `レポート本文を表示`. It is a review aid, not an order instruction.
- UI リッチな PDF report / Excel report は将来の Advanced Export 範囲です。現行の Decision Report export は Markdown / JSON / manifest / ZIP を正とします。

Phase 16 final UI smoke checklist:

- Change screening conditions and confirm candidate count / comparison symbols update coherently.
- Build a ranking and confirm progress messages are shown.
- Run the same ranking again and confirm cached rows are reused.
- Change only `重視して並べ替え` and confirm rows are re-sorted without a provider refetch.
- Click a ranking row and confirm the symbol-detail modal opens quickly, including `判断補助` guidance when ranking context exists.
- Open `銘柄データを見る` in `銘柄コックピット` and confirm the selected symbol's local-master data appears in the same modal.
- Fetch cockpit data and confirm `投資判断メモ` appears without presenting buy/sell advice.
- Confirm Rebalance labels continue to describe decision support rather than buy/sell advice.

### リバランス

Rebalance は `Rebalance Cockpit` として、次の順に確認します。

1. 現在資産
2. 目標配分
3. 配分見直し候補
4. Risk 判定

確認できるもの:

- sample / account / as-of / cash / target weight input
- summary flow
- target allocation percentage input
- current positions
- target allocations
- allocation comparison chart
- rebalance review candidates
- risk decision
- beginner-friendly risk breach confirmation points
- `投資判断レポート` Markdown / JSON / manifest / ZIP download for current holdings, targets, drift, rebalance review candidates, Risk breaches, and confirmation checkpoints
- JSON / CSV / Markdown / ZIP export

## 7. 外部 MarketData provider

現在使える provider:

| provider | 状態 | opt-in | 主な用途 |
| --- | --- | --- | --- |
| `mock` | 実装済み | 不要 | 既定の MVP 確認 |
| `csv` | 実装済み | 不要 | ローカル CSV 確認 |
| `yahoo` | 実装済み経路あり | 必要 | yfinance による live data 確認 |
| `polygon` | metadata のみ | 将来必要 | live provider 候補 |

`yahoo` を使う場合は、設定で `allow_external_providers: true` を明示します。
通常の自動テストと local checks は外部 API に依存させません。

## 8. ローカル検証

まとめて確認:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
```

個別確認:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check . --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy .
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

Markdown UTF-8 check:

```powershell
.\venv_SMAI\Scripts\python.exe -c "from pathlib import Path; [p.read_text(encoding='utf-8') for p in Path('.').rglob('*.md') if '.git' not in p.parts]; print('markdown utf-8 ok')"
```

## 9. 更新ルール

- 実装状態が変わったら README / PROJECT_CONTEXT / Roadmap / Operations Guide を同期する。
- UI に見える変更は `07_UI_Wording_Policy.md` と `08_Phase16_UI_Improvement_Plan.md` も確認する。
- 作業履歴は `Documents/99_Work_Log.md` の先頭へ追加する。
- Research RAG は Phase 20 local evidence slice を deterministic foundation として開始済み。`backend/research` の local UTF-8 document ingestion / chunk / keyword search / deterministic Research Summary、`設定 / データ情報` での session-local資料登録は、通常 tests / demo seed / user archive / fallback として維持する。今後の標準ユーザー導線では、`銘柄コックピット` の `AI調査を更新` が外部の最新IR・開示・ニュース・provider evidence を取得/参照し、Research Evidence / Research Score / Cockpit Decision Report に反映する。価格データ取得時にはResearch RAGを自動実行しない。Ranking evidence-status display は軽量表示に留め、Research Score によるランキング順位変更は現時点では行わない。
- Stock News RAG は Phase 21.5 の first local deterministic slice として、`source_type=news` で登録されたローカル資料から URL 付きニュースだけを `銘柄コックピット` の Research Evidence card に統合表示する。これはテスト/fixtureの土台であり、通常ユーザー導線では外部ニュース adapter に置き換える方向。news 資料には `url:` または `source_url:` 行、任意で `source:` / `summary:` 行を含める。Investment Score / ランキング順位は変更しない。
- External Research / News fetch は Phase 21.6 / 21.7 の first UI slice として、`ExternalResearchSourceAdapter` protocol と backend `allow_network` gate を持つ。独立した `外部資料取得（明示許可）` UI は廃止し、`AI調査を更新` の標準処理へ統合済み。既定 adapter は EDINET（`EDINET_API_KEY` 設定時のみ live call、未設定時 no-op）、TDnet timely disclosure、企業IR site、Google News RSS headline search、Yahoo Finance profile / news を順に取得する。Phase 21.7 backend では `ExternalStockNewsAdapter` / `ExternalStockNewsFetchService` が URL 付き外部ニュースを `StockNewsEvidence` に正規化し、viewpoint、sentiment、freshness、dedupe、network opt-in gate を扱う。Google News RSS は取得したRSS itemを `source_type=news` の `ExternalResearchSourcePayload` に変換し、通常 checks はRSS文字列fixtureで確認する。取得本文・変換Markdown・manifest JSON は既定では保持しない。取得結果は session-local RAG store でその場の summary / Research Score / News 表示に一時参照し、画面やReportには provider / fetched_at / published_at / source URL / freshness_status / freshness warning / 短い要約だけを残す。Cockpit Decision Report には `外部参照ソース` section として trace row だけを含め、本文・local path・document hash は含めない。通常 checks は fake adapter / fixture を使い、network 非依存を維持する。
- `tools/fetch_research_yfinance_profile.py --symbol 7203.T --write` は、確認用の実データResearch資料を Yahoo Finance / yfinance から取得して `data/research_docs/` に保存する。外部通信を使うため通常 checks には含めない。
- EDINET / TDnet / IR site などの外部 source adapter が安定しても、外部取得本文を自動保存しない。`data/research_docs/` は開発 fixture、demo seed、private note、ユーザーが明示保存した資料、または fallback として扱う。永続化が必要な場合は、既定取得とは別の `資料を保存する` / archive action として実装する。
- Research Summary は、外部LLMを使わず、local rule-based `CompanyResearchSummary`、`ResearchBrief`、`InvestmentInsight`、`InvestmentQuestionSummary` へ変換してから表示する。通常表示では provider profile の生フィールド羅列を出さず、`CompanyResearchEvidence` で company profile / IR / TDnet / news / market data の役割を正規化する。最初に `企業リサーチサマリー` として企業概要、主な事業、製品・サービス、地域展開、規模感、直近の注目ポイントを表示する。続けて `定量情報サマリー` に売上高、営業利益、純利益、EPS、PER、PBR、ROE、配当利回り、時価総額、従業員数、`IR情報サマリー` に決算短信、決算説明資料、有価証券報告書、適時開示、中期経営計画、配当・自社株買い、業績予想修正、`最新ニュース・開示サマリー` に直近ニュース/開示と影響カテゴリ、公式IR確認要否を表示する。ニュース/開示は `Market Intelligence` パネルとして通常カードから分け、URL付き項目は初期折りたたみの citation list から開く。その直後の `投資ヒントとなるニュース` はURL付き一般ニュースだけの `注目材料 Top 3` 表示で、TDnetやprovider sourceを混ぜない。IR / news / metric では found / missing / unparsed / unverified を区別する。`詳細情報・開発者向け` は通常表示と用途が重なるAI整理メモ、読み方サマリー、出典カード再掲を省き、Research Score、データ品質、検索品質、抽出主張、根拠資料詳細、外部source取得状況などの検証用データに絞る。上部の operation card は fetch 前の `確認方針` と fetch 後の `企業リサーチレポートを更新しました` / `追加確認` に分け、抽出指標数、出典カード数、Research Score は詳細側に下げる。
- Research Summary maturity slice として、`ResearchBrief` の前段に `ResearchFactSummary` を追加済み。運用上の表示目標は、取得状態や件数ではなく、事業概要、主要事業、地域・収益源、確認済みのIR / 公式資料 / TDnet / ニュース、主要定量指標、業績見通し、配当・株主還元方針、直近イベント、良材料候補、注意材料候補、未確認項目を source-backed fact として提示すること。provider-only の情報は公式資料と同列に扱わず、`外部データ由来では` と明示する。
- ResearchBrief の確認ポイントは、provider profile や検索根拠の英語断片をそのまま出さず、`会社概要`、`確認できた事実`、`公式資料で未確認` の3ブロックに言い換える。良材料候補 / 注意材料候補は詳細側の確認材料とし、主表示では件数よりも、事業・数値・業績見通し・株主還元・未確認項目の中身を優先する。ニュース取得警告などの「根拠不足」は注意材料ではなく確認不足として扱う。
- `ResearchBrief` の定量評価では、取得できた PER / PBR / ROE / 売上高 / 営業利益 / 純利益 / EPS / 配当 / 時価総額などを source type と confidence 付きの小カードで表示する。取得できない主要指標は missing metrics として警告パネルに明示する。
- `ResearchBrief` の確認不足は、`未確認の定量指標` のような内部表現をそのまま見せず、`まだ確認できていない数値` として表示する。これは悪材料ではなく、公式資料で追加確認する項目であることを併記する。
- `ResearchBrief` の confidence は情報源の信頼度であり、投資判断の正しさではない。公式IR / TDnet / EDINET / 企業IRは high、Yahoo Finance / provider profile / news は medium、キーワード抽出のみは low として説明する。Research Score は調査メモの後ろに表示し、ランキング順位は既定では変更しない。
