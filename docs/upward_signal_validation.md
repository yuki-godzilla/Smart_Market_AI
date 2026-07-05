# 上向き兆候 実確認・バックテスト記録

## 現在の状態

- UI名称、形状分類、危険キャップ、ETF分岐、時点固定バックテスト契約を実装済み。
- 通常確認は fake / local fixture で実施し、外部通信を使わない。
- 下表の実銘柄確認は Yahoo live data を使う明示 opt-in 作業として分離する。
- 実確認前に成功扱いにはしない。違和感銘柄と調整内容はこの文書へ追記する。

## 共通記録項目

`Sprint / 銘柄 / 条件 / 上向き兆候 / ラベル / チャート印象 / 問題分類 / 原因仮説 / 修正内容 / 再確認結果`

## 10スプリント

| Sprint | 対象 | 主な確認 | 状態 |
| --- | --- | --- | --- |
| 1 | 日本大型株 | 押し目・横ばい・上昇気配との差 | live確認待ち |
| 2 | 日本高配当株 | 配当罠・長期下落・安全性未確認 | deterministic cap test済み / live確認待ち |
| 3 | 日本グロース・半導体 | 急落・高ボラ・上昇済み | deterministic cap test済み / live確認待ち |
| 4 | 米国大型グロース | 押し目と決算後急落 | live確認待ち |
| 5 | 米国高配当 | 横ばい上放れと長期低迷 | live確認待ち |
| 6 | ETF | 指数押し目・資産クラス差・個別株ロジック除外 | ETF分岐test済み / live確認待ち |
| 7 | 横ばい候補 | 上放れ・蓄積準備・無風横ばい | deterministic shape test済み / live確認待ち |
| 8 | 落ちるナイフ | 長期下落・急落・下降警戒cap | deterministic cap test済み / live確認待ち |
| 9 | 既知成功例 | 評価日後20/60/120営業日 | point-in-time test済み / live確認待ち |
| 10 | 自動抽出 | 成功/失敗差・勝率・市場超過率 | summary/output test済み / live確認待ち |

## 合格基準

- 上位10件のうち7件以上が、押し目反発待ち・底打ち接近・横ばい上放れ候補・蓄積上昇準備として説明可能。
- 明らかな落ちるナイフは上位10件に原則含めない。
- 高配当罠、上昇済み、データ不足には警告または上限を適用する。
- 成功例の平均上向き兆候スコアが失敗例より10点以上高い。
- Top10の60日勝率55%以上、市場平均超過率50%以上を目安とする。

## バックテスト成果物

`backend.scoring.upward_signal_backtest.write_upward_signal_backtest_outputs` は次を出力する。

- `backtest_upward_signal_cases.csv`
- `backtest_upward_signal_summary.md`
- `upward_signal_false_positive_cases.md`
- `upward_signal_logic_adjustments.md`

評価ロジックへ渡す履歴は `as_of` 以下に切られ、将来価格はリターン・最大下落・ベンチマーク超過の事後評価だけに使う。
