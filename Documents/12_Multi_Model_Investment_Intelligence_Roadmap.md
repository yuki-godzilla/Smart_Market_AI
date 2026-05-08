# Multi-Model Investment Intelligence Roadmap

#### [BACK TO README](../README.md)

## 1. 目的

この文書は、Phase 9 までの MVP 実装を踏まえた次期ロードマップを定義します。

次期重点は、注文執行そのものではなく、外部プロバイダーから得た市場情報を使い、複数の予測モデルとスコアリングを比較しながら投資判断を補助することです。

このロードマップでは、次の状態を目指します。

- 外部データを明示的な opt-in で取得できる
- 銘柄ごとの特徴量を再利用しやすい形で保存・比較できる
- 複数の予測モデルを同じインターフェースで実行できる
- 予測結果、リスク、スクリーニング条件を合わせて銘柄スコアを出せる
- UI とレポートで、判断材料・不確実性・モデル間の違いを確認できる

本機能は投資判断を補助するための情報整理ツールであり、売買を推奨または保証するものではありません。

## 2. 基本方針

### 2.1 ローカル再現性を残す

既定経路は引き続き `mock` / `csv` provider を使う deterministic なローカル挙動にします。
外部 API、重い ML ライブラリ、ネットワーク接続を CI や通常 MVP 経路の必須条件にしません。

### 2.2 外部プロバイダーは明示 opt-in

外部プロバイダーは `dataaccess.allow_external_providers: true` のような明示設定を前提にします。
API 制限、タイムアウト、欠損、スキーマ差分はドメインエラーとして扱い、ユーザーに原因が分かる形で返します。

### 2.3 予測モデルは差し替え可能にする

単一モデルに固定せず、`ForecastModel` のような共通インターフェースを用意します。
最初は naive / moving average / momentum など軽量な baseline から始め、後から tree model、deep learning、Transformer、時系列 foundation model、ニュース・センチメントモデルを追加できる構造にします。

### 2.4 単一スコアを過信しない

画面やレポートでは、最終スコアだけでなく、スコアの内訳、モデル間の一致・不一致、予測 horizon、信頼度、主なリスク要因を表示します。
投資判断の補助では「なぜ高い/低いのか」を追えることを優先します。

### 2.5 研究知見は optional adapter として取り込む

最新論文や外部モデルを参考にする場合も、まずは抽象化と評価手順を整えます。
重い依存や実験的なモデルは、既定経路ではなく optional adapter として追加します。

## 3. 次期フェーズ

### Phase 10: External Data Ingestion MVP

目的: 外部プロバイダーから実データを取得するための最小経路を作る。

主な作業:

- live provider adapter の共通インターフェースを整理する
- `yahoo` など最初の候補 provider を opt-in 実装する
- 取得データを既存の `Bar` / `Quote` / `FxRate` 契約へ正規化する
- rate limit、timeout、provider unavailable、schema mismatch を一貫したエラーにする
- CI は mock で固定し、live smoke check は手動確認に分ける

完了条件:

- 設定で明示した場合だけ live provider を呼び出せる
- live provider なしでも既存テストが通る
- 失敗時の API 応答とドキュメントが揃っている

### Phase 11: Feature Store Lite

目的: 銘柄評価と予測で再利用する特徴量 snapshot を定義する。

主な作業:

- feature snapshot のデータ契約を追加する
- return、volatility、momentum、ADV、drawdown、欠損率などを計算する
- `dividend_yield`、`market_cap_jpy` など外部データ由来項目の扱いを決める
- feature version、as-of date、provider metadata を保持する

完了条件:

- 銘柄ごとに同じ形式の特徴量を取得できる
- 欠損や算出不能の理由を追跡できる
- screening / forecast / report から再利用できる

### Phase 12: Screening Score MVP

目的: 銘柄をランキングし、スコアの内訳を説明できるようにする。

主な作業:

- `ScreeningService.rank()` のような service を追加する
- momentum、quality、liquidity、risk、data completeness などのサブスコアを定義する
- `ScoreBreakdown` を返し、UI/レポートで説明できるようにする
- API と Streamlit にランキング確認経路を追加する

完了条件:

- 複数銘柄を deterministic に順位付けできる
- 最終スコアとサブスコアがテストで検証されている
- ユーザーが「なぜこの順位か」を確認できる

### Phase 13: Forecast Lab Baseline

目的: 予測モデルを比較するための最小実験基盤を作る。

主な作業:

- `ForecastModel` protocol / base class を定義する
- naive、moving average、momentum baseline を実装する
- time split、walk-forward など、未来情報を使わない評価手順を用意する
- MAE、RMSE、direction accuracy、hit rate などの基本 metrics を返す

完了条件:

- 複数 baseline を同じ形式で実行できる
- 評価時に data leakage を避ける設計になっている
- 予測値、信頼度、評価指標を保存・表示できる

### Phase 14: Multi-Model Forecasting

目的: 複数モデルの予測を並べ、合意度と不確実性を扱えるようにする。

主な作業:

- forecast model registry を追加する
- model ごとの horizon、入力特徴量、出力形式を揃える
- ensemble、median forecast、model agreement / disagreement を計算する
- 銘柄ごとの forecast summary を返す

完了条件:

- 複数モデルの予測結果を比較できる
- モデル間で意見が割れている銘柄を見つけられる
- forecast が screening score に接続できる

### Phase 15: Model-Informed Scoring

目的: スクリーニングと予測を統合した投資判断補助スコアを作る。

主な作業:

- screening score、forecast score、risk penalty、data quality penalty を統合する
- horizon 別スコアを定義する
- モデル信頼度や不一致をスコアへ反映する
- スコア計算の設定を YAML で調整できるようにする

完了条件:

- 銘柄ごとに総合スコアと内訳を返せる
- forecast が弱い場合やデータ品質が低い場合に過大評価しない
- 設定変更で重みを調整できる

### Phase 16: Visualization Cockpit

目的: 銘柄比較、予測、スコア内訳を UI で確認しやすくする。

主な作業:

- ranking table を追加する
- score breakdown chart を追加する
- forecast horizon chart を追加する
- model comparison / agreement view を追加する
- scenario 比較やフィルタを段階的に追加する

完了条件:

- ユーザーが銘柄ランキングから詳細へ進める
- 予測結果とスコア理由を同じ画面で確認できる
- UI は注文送信を行わず、判断補助に限定されている

### Phase 17: Research Model Adapters

目的: 最新研究や高度なモデルを安全に試せる拡張口を用意する。

主な作業:

- tree model、sequence model、Transformer、foundation model、sentiment model の adapter 方針を整理する
- model card を用意し、入力、出力、制約、検証結果を記録する
- 依存が重いモデルは optional dependency にする
- offline fixture で最低限の adapter 契約テストを行う

完了条件:

- 実験モデルを既定経路から分離して追加できる
- モデルごとの役割と限界がドキュメント化されている
- production-like 経路へ入れる前に評価できる

### Phase 18: Decision Report

目的: 人が読める判断補助レポートを出力する。

主な作業:

- 銘柄ごとの score、forecast、risk、data quality をまとめる
- モデル間の一致・不一致と注意点を文章化する
- Markdown / JSON / CSV / ZIP export を拡張する
- 将来の PDF / Excel export へ接続しやすい report context を整理する

完了条件:

- ユーザーがレポートだけで主要な判断材料を確認できる
- 予測の限界と注意点が明記されている
- 既存の deterministic export 方針を保っている

## 4. 今回は優先しないこと

- broker への live order 送信
- execution workflow の本格化
- 外部 provider の既定化
- 重い ML 依存の既定導入
- 単一モデルの予測を売買推奨として扱うこと

Execution は重要な将来領域ですが、今回のロードマップでは優先順位を下げ、情報取得・予測・スコアリング・可視化を先に固めます。

## 5. 成功指標

- local checks が外部 API なしで通る
- live provider は opt-in でのみ動く
- 銘柄ランキングにスコア内訳がある
- 複数モデルの予測を横並びで比較できる
- モデル間の一致・不一致を UI/レポートで確認できる
- 予測モデルの入力、出力、制約、評価結果が追跡できる
- ユーザーが「候補銘柄」「根拠」「不確実性」「次に確認すべき点」を理解できる
