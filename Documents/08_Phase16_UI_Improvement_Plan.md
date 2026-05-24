# Phase 16 UI Improvement Plan

#### [BACK TO README](../README.md)

## Current Sync / 2026-05-23

Phase 16 UI is implementation-complete at the code level. The current Streamlit flows include:

- `銘柄ランキング`: ranking rows open the shared `銘柄データ` modal. The table keeps a short note; the modal carries richer decision-support guidance.
- `銘柄コックピット`: `銘柄データを見る` is placed beside symbol selection, Start / End inputs wrap to the next row, and fetched results show `投資判断メモ`.
- `銘柄データ` modal: local symbol-master metrics, ranking context, valuation, income, and next-check wording are shown without buy/sell recommendation language.
- Performance note: ranking display-row generation reuses a symbol lookup map to avoid repeated symbol-master scans when opening modals from long-period rankings.

Remaining confirmation is browser-level smoke, not a known implementation blocker: ranking cache/progress, ranking row modal, cockpit symbol-detail button, cockpit investment memo, and Rebalance wording.

## Maturity Review Addendum / 2026-05-24

Phase 16 polish の次の焦点は、新機能追加ではなく、既存UIの分かりにくさ、仕様の曖昧さ、投資助言に見えすぎる表現の棚卸しです。

- 手動確認は [96_Manual_UX_Review_Checklist.md](./96_Manual_UX_Review_Checklist.md) を使い、Symbol Cockpit、Ranking、Rebalance Cockpit、Decision Report、Research Summary / Evidence、Forecast、Risk、Market Data freshness、score explanation を横断して確認する。
- 仕様上の曖昧さは [97_Functional_Spec_Issues.md](./97_Functional_Spec_Issues.md) に記録し、実装修正前に期待方向を整理する。
- Ranking は候補探索、Symbol Cockpit は1銘柄の深掘り、Rebalance Cockpit は配分見直しシミュレーション、Decision Report は判断材料の保存・説明として扱う。
- Investment Score、Database Fit、Metadata Confidence、Research Evidence は役割が異なるため、画面やレポートで混同されないかを優先レビューする。
- Execution / Broker integration、Assistant、Research external adapters、distribution readiness は、仕様・UXレビューが進むまで future scope とする。

## Ranking Visualization Addendum / 2026-05-24

Ranking 画面は、既存ランキング結果の「見せ方」を改善し、候補探索・比較・深掘り対象の整理に使う金融ダッシュボード風 UI として磨き込む。

- 上部に対象銘柄数、表示候補数、平均 Investment Score、High Confidence 候補数、ランキング軸、対象範囲の summary cards を置く。
- 上位候補は `Top Screening Candidates` としてカード化し、「おすすめ」ではなく比較候補・深掘り候補として表現する。
- 常時表示する主要グラフは `Top 10 Score Comparison` と `Score x Evaluation Confidence` に絞り、スコア差と評価信頼度の違いを短い説明文で補足する。
- 選択中の1銘柄について、Investment Score、Screening、Forecast、Data Confidence、Risk の既存表示値を `Selected Candidate Breakdown` として整理する。
- Score distribution など補助分析は `Advanced Insights` に入れ、初期表示の情報量を抑える。
- backend ranking logic、score calculation、Investment Score / Database Fit / Metadata Confidence の意味は変更しない。

### Ranking chart profile update / 2026-05-24

Ranking のメインチャートは、並べ替え条件に応じた chart profile で選択する。UI本体に条件分岐を増やしすぎず、`ui/views/ranking_chart_profiles.py` の設定で拡張する。

- `multi_factor` / default: `Score x Risk Map`
- `dividend` / `sustainable_income` / `etf_income`: `Dividend x Stability Map`、列不足時は `Score x Risk Map`
- `growth` / `quality_growth` / `small_growth`: `Growth x Momentum Map`、列不足時は `Score x Forecast Map`
- `value` / `quality_value`: `Valuation x Risk Map`、列不足時は `Score x Risk Map`
- `stability` / `min_volatility` / `risk_adjusted`: `Stability x Risk Map`、列不足時は `Score x Risk Map`
- `trend` / `momentum`: `Momentum x Forecast Map`、列不足時は `Score x Forecast Map`
- `nisa_long_term`: `Long-term Fit x Confidence Map`、列不足時は `Score x Risk Map`
- `etf_core_cost`: `ETF Cost x Score Map`、列不足時は `Score x Evaluation Confidence`
- `data_confidence`: `Score x Evaluation Confidence`

Evaluation Confidence は通常の主Factorではなく、評価信頼度・データ充実度を示す補助指標として扱う。`data_confidence` 系の並べ替え条件では主グラフにし、それ以外では `Advanced Insights` の補助分析に置く。

### Ranking UI readability polish / 2026-05-24

Ranking 画面は、カードや表の文字切れを避け、重要情報を短く読める表示に寄せる。

- Top Screening Candidates は銘柄名や説明文を短縮し、Score、Symbol、badge を優先して見せる。
- Top 10 Score Comparison はY軸をsymbol中心にし、長いcompany nameはtooltipで確認する。
- 条件別メインチャートの詳しい読み方は `読み方` expander に逃がし、常時表示の説明文を短くする。
- Detailed Ranking Table は Rank、Symbol、Name、Score、Risk、Data Confidence、見方、Short Reason を優先表示し、長い理由やraw情報はReport / CSV / download側に残す。
- Decision Report はPreviewとRaw Markdownを分け、画面上ではレポートとして読みやすく確認できるようにする。

## Symbol Cockpit UI Maturity Addendum / 2026-05-24

Symbol Cockpit は、既存分析結果を「結論 → 根拠 → 詳細」の順に読みやすくし、1銘柄を深掘りする金融ダッシュボード風の分析ビューとして磨き込む。

- 価格・予測チャートの前に `Symbol Cockpit Summary` を置き、Symbol、Name、Provider、As of、Reference period、Asset / Region、Investment Score、Decision View、Data Confidence、Risk、Forecast horizon を整理する。
- `Analysis KPI` では Investment Score、Decision View、Forecast Agreement、Data Confidence、Risk を既存表示値からカード化し、Data Confidence を投資魅力度ではなく評価信頼度として説明する。
- `Score Breakdown` はKPI直下に配置し、総合スコアの構成観点を早い段階で確認できるようにする。
- 価格・予測チャート、期間別評価、投資判断メモ、確認サマリーには、売買推奨ではなく確認観点であることを短く補足する。
- `Research Evidence Summary` はResearch RAG実行後に表示し、Document Count、Evidence Count、Latest Source Date、Data Quality Status、Warnings を確認材料として見せる。Research RAGは自動実行しない。
- Forecast details、Screening Score、Provider / Quote / OHLCV、FX / Feature Snapshot は下部の詳細確認 Expander として維持する。
- backend logic、Investment Score calculation、Forecast / Research / Decision Report generation logic は変更しない。

### Symbol Cockpit hero chart update / 2026-05-24

Symbol Cockpit は、Summary / KPI の直後に `02 Price & Forecast` を置き、価格・予測チャートを1銘柄深掘りの主役として扱う。`03 Score Breakdown` はチャート直後に置き、値動きを見たあとに「なぜこの評価になっているか」を確認する位置づけにする。

- `01 Summary / Symbol Cockpit` で対象、Provider、期間、主要スコアを確認する。
- `Analysis KPI` でスコア、見方、予測一致、Data Confidence、Risk を把握する。
- `02 Price & Forecast` で実績価格と予測レンジを確認する。
- `03 Score Breakdown`、期間別評価、Review Memo、Confirmation Summary の順で根拠を読む。
- Research Evidence、Decision Report、Developer / Data Details は削除せず、下部で確認できる詳細・保存・検証用の領域として維持する。

## Global UI Tone Polish Addendum / 2026-05-24

SMAI の全体UIは `Professional but Friendly` を基本トーンとし、落ち着いた金融ダッシュボードとして見えるように整える。

- 背景は pure black ではなく dark navy / charcoal を使い、カードは背景より少し明るい面として見せる。
- Ranking Summary、Top Screening Candidates、Symbol Cockpit Summary、Analysis KPI、Research Evidence Summary は共通カード/バッジ表現に寄せる。
- blue は情報・分類、green は高信頼/良好なデータ状態、amber は確認・注意、gray は中立/不明として扱う。
- 数値表示は長すぎる小数を避け、主要スコアは読みやすい短い表示に整える。ただし計算値やロジックは変更しない。
- グラフの説明文は、仕様説明ではなく「何を見るか」「どう確認するか」を短く伝える。
- CSSと表示ヘルパーは `ui/styles.py` に寄せ、`ui/app.py` への長いHTML/CSS直書き追加を避ける。

## 目的

Phase 16 では、Smart Market AI を「表を読む分析ツール」から、個人投資家が候補を探し、理由を理解し、次に確認する観点を整理できる UI に近づける。

この資料は、これまで相談した銘柄コックピット、銘柄ランキング、チャート、条件検索の改善方針を実装用に整理する。

基本方針:

- 売買推奨ではなく、判断材料と注意点の整理として表示する。
- 初心者が最初に読む文は短く、具体的にする。
- 専門指標は詳細に残しつつ、上部では読み取り文に翻訳する。
- 銘柄を選ぶ前に使う条件と、データ取得後に評価する条件を分ける。
- 通常確認は deterministic / local-first を維持する。


## 現在の実装状態（2026-05-18）

実装済み:

- Streamlit UI を左サイドメニューで `銘柄コックピット` / `銘柄ランキング` / `リバランス` / `設定 / データ情報` に分割。
- 銘柄コックピットで、価格・予測チャート、Forecast Summary、Investment Score、score breakdown、warnings、downloads を表示。
- 銘柄ランキングで、ranking preset、候補条件 modal、static / curated metadata による fetch-before filtering、ticker + company name 表示を実装。
- ranking result から選択銘柄と provider を cockpit state へ渡す導線を実装。
- `リバランス` 画面で、JSON input を advanced input に移動し、summary flow、percentage target、allocation comparison chart、risk breach confirmation points、latest result persistence を追加。
- サイドメニューを画面選択と実行環境表示に絞り、Rebalance 入力と銘柄候補表を各画面側へ移動。

推奨確認 / 次フェーズ:

- 最終 Streamlit browser smoke で ranking 条件、cache/progress、preset resort、cockpit handoff、Rebalance 文言を確認する。
- Decision Report へ渡す cockpit / ranking / rebalance context の整理。
- provider fundamentals 由来の symbol metadata refresh 方針の具体化。

## 画面全体の考え方

Market Data 系画面は 2 つの役割に分ける。

- 銘柄ランキング: 目的や条件から候補銘柄を探す。
- 銘柄コックピット: 選んだ 1 銘柄を深掘りし、価格、予測、スコア、注意点を見る。

`リバランス` は、候補を保有に入れた場合の配分や risk を確認する画面として整理する。

想定ワークフロー:

1. 銘柄ランキングで候補を作る。
2. ranking result から銘柄コックピットへ進む。
3. 銘柄コックピットで価格・予測・Investment Score・注意点を確認する。
4. 必要に応じて Rebalance Cockpit で保有との関係を確認する。
5. 将来は Decision Report に残す。

## 銘柄コックピット

### 方針

チャートを先に見せ、その下で Investment Score と理由を読む構成にする。

ユーザーの自然な読み順:

1. 銘柄名、provider、期間、as-of、data quality
2. 価格・予測チャート
3. チャートの読み取り summary
4. Investment Score
5. Screening / Forecast / Risk / Data Quality の内訳
6. Forecast Metrics、Screening Score、provider / quote / OHLCV などの詳細

### チャート改善

初心者が迷いやすい点:

- 実績線と予測線の違いが分かりにくい。
- どこから予測なのか分かりにくい。
- model agreement や forecast range の意味が硬い。
- RMSE / MAE だけでは何を見ればよいか分かりにくい。

改善方針:

- チャートを Investment Score より上に置く。
- 実績価格、予測線、予測開始位置を短い文で説明する。
- chart summary は「モデルの見方が近い / 割れている」のように読む。
- 予測レンジは「予測の開き」として表現する。
- RMSE / MAE は詳細に残し、上部では「今回の比較で誤差が小さかったモデル」として説明する。

表示文の方向性:

- 赤い線はこれまでの実績価格です。
- 点線はモデルごとの予測です。
- 点線同士が近いほど、モデルの見方が近い状態です。
- 縦の点線は、実績価格から予測表示へ切り替わる位置です。
- 予測は売買判断ではなく、確認材料のひとつです。

### Investment Score

Investment Score は、チャートで値動きを見た後に読む判断材料として置く。

表示するもの:

- 総合スコア
- 見方
- 注意点
- Screening / Forecast / Risk / Data Quality の内訳
- 「なぜこのスコアか」の短い説明

詳細は expander に入れる:

- score breakdown
- raw score rows
- Forecast Metrics
- Screening Score
- provider metadata
- JSON / CSV downloads

## 銘柄ランキング

### 役割

銘柄ランキングは、買う銘柄を決める画面ではなく、深掘り候補を整理する画面。

ランキング前の目的:

- ユーザーの投資目的に合う候補 universe を作る。
- 銘柄を知らないユーザーでも、目的や条件から候補を選べるようにする。

ランキング後の目的:

- 取得した market data / scoring / forecast / risk で比較する。
- 気になる銘柄を銘柄コックピットへ渡す。

## 条件設計

### Fetch 前に使う条件

Fetch 前の条件は、static metadata、curated list、symbol reference だけで判断できるものに限定する。

使ってよい条件:

- 投資目的
- 投資期間
- 対象市場
- 銘柄タイプ
- 通貨
- 地域
- セクター
- テーマ
- 配当カテゴリ
- インデックス連動タイプ
- 投資商品のわかりやすさ
- 候補リスト
- キーワード検索
- 表示件数

Fetch 前には使わない条件:

- Investment Score
- Screening Score
- Forecast agreement
- Data quality
- Risk signal
- volatility
- drawdown
- momentum
- liquidity
- forecast RMSE / MAE
- provider error / missing data
- live provider 由来の dividend_yield
- 直近価格変動
- 予測レンジ

これらは Fetch 後に ranking / cockpit で評価する。

### 初期実装で優先する条件

#### 投資目的

ユーザーが最初に選ぶ軸。

候補:

- 配当を重視したい
- 積み立て候補を探したい
- 成長期待の銘柄を見たい
- リスク控えめに探したい
- 短期の値動きを確認したい
- 長期保有候補を探したい
- バランスよく探したい

使い方:

- static tags / curated list で候補 universe を作る。
- Fetch 後の ranking preset の初期値にも反映する。

#### 投資期間

日付入力より先に、用途に合う期間 preset を用意する。

候補:

- 短期: 1週間
- 中期: 1か月
- 長期: 1年

想定:

- 短期は値動き確認と短期 forecast に寄せる。
- 中期は直近トレンド確認に寄せる。
- 長期は安定性、data quality、長期傾向の確認に寄せる。

#### 対象市場

候補:

- 日本株
- 米国株
- ETF
- すべて

使い方:

- symbol suffix、currency、curated metadata から候補を絞る。
- ETF は市場ではなく asset type としても扱うため、UI 上では重複して見えないように整理する。

#### 銘柄タイプ

候補:

- 個別株
- ETF

注意:

- MVP は個別株 / ETF を中心にする。
- ADR / 投信 / REIT は Future Phase とし、default ranking universe から除外する。

#### 通貨

候補:

- JPY
- USD
- すべて

説明:

- 為替リスクを避けたいユーザーに意味がある。
- 初心者向けには「円建て中心 / 外貨建ても含める」という表現も検討する。

#### セクター / テーマ

候補:

- テクノロジー
- 半導体
- 金融
- 消費
- ヘルスケア
- エネルギー
- 自動車
- 商社
- インデックス
- 高配当
- REIT

注意:

- 最初は curated tags で十分。
- 正式な sector data は将来 provider / metadata 拡張で扱う。

#### 配当カテゴリ

候補:

- 高配当候補
- 配当あり
- 配当なし
- 連続増配候補
- 指定なし

注意:

- 最低配当利回りを Fetch 前に使う場合は、static metadata / curated fundamentals がある銘柄だけ対象にする。
- live provider で取得して初めて分かる dividend_yield は Fetch 後の評価条件に回す。

#### インデックス連動タイプ

ETF向けに重要。投信向けの活用は Future Phase。

候補:

- S&P 500
- NASDAQ 100
- 全世界
- 全米
- 日経平均
- TOPIX
- 指定なし

#### 投資商品のわかりやすさ

初心者保護のための条件。

候補:

- 初心者向け
- 標準
- 上級者向けも含める

例:

- レバレッジ ETF や複雑なテーマ型商品は上級者寄りに分類する。
- 初期候補では、主要 ETF、大型株、分散性のある商品を優先する。

## Fetch 後に使う条件

Fetch 後の条件は、既存の MarketData / Feature Store / Screening / Forecast / Risk / Investment Score の結果で評価する。

候補:

- 表示順: バランス重視、予測一致重視、データ品質重視、リスク控えめ
- Data quality: 注意ありを含める / 除外
- 予測一致度: 高いものだけ / 中くらい以上 / すべて
- 最低 Investment Score
- Risk warning を含める / 除外
- 表示件数

初期実装では、既存 Investment Score components を再加重する deterministic preset を使う。

## ランキング表からコックピットへ進む導線

理想:

- ranking table の行を選ぶと、そのまま銘柄コックピットへ進める。

段階的実装:

1. ranking table の下に「深掘りする銘柄」selectbox を置く。
2. 「銘柄コックピットで確認」ボタンで symbol / provider を引き継ぐ。
3. 将来、Streamlit の dataframe selection API が安定して使える場合は、表の行選択から直接遷移する。

## Rebalance Cockpit

現在の役割:

- 保有と目標配分の差を確認する。
- 必要な売買案を確認する。
- Risk 判定と主な理由を確認する。

改善方針:

- JSON 入力は advanced に下げる。
- 現在資産 -> 目標配分 -> 必要な売買 -> Risk 判定の流れを上部に置く。
- allocation drift が大きい銘柄を強調する。
- risk breach code は残しつつ、確認ポイントを日本語で表示する。

## 実装順

以下は設計時の実装順です。主要な Phase 16 UI 項目は実装済みで、残りは最終 smoke または次フェーズとして扱います。

短期:

1. 銘柄コックピットで chart を score より上に移動する。
2. chart の初心者向け説明を強める。
3. ランキングの期間を短期 / 中期 / 長期 preset にする。
4. ランキングの候補選択を Fetch 前条件と Fetch 後条件に分ける。
5. static metadata / curated tags を持つ `symbol_universe_rows()` を追加する。

中期:

1. 投資目的、対象市場、銘柄タイプ、通貨、テーマ、配当カテゴリで候補を作る。
2. ranking table から直接コックピットへ進める導線を改善する。
3. Rebalance Cockpit の drift 強調を入れる。
4. report context に cockpit summary / ranking result を渡す。

将来:

1. 投信 data schema / CSV取込 / 基準価額チャートを追加する。
2. NISA 適性、信託報酬、最低投資金額、分配金方針を扱う。
3. 保有 portfolio との相性で候補を絞る。
4. Assistant / Report で同じ context を自然文にする。

## Non-goals

Phase 16 では以下を行わない。

- broker order / live order 送信
- LLM による銘柄選定
- live provider 依存の通常確認
- Fetch 前条件に、Fetch 後でしか分からない指標を混ぜること
- 買い / 売りの推奨表現
