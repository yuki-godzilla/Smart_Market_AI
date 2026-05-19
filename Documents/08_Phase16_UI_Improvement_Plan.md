# Phase 16 UI Improvement Plan

#### [BACK TO README](../README.md)

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
