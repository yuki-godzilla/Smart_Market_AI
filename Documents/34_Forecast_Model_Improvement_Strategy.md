# 34 既存予測モデル改善 戦略

## 1. 目的と方針

モデル数を増やすのではなく、`advanced_linear`、`advanced_tree_sklearn`、`advanced_gbdt_sklearn`、`advanced_quantile`、forecast consensusとupside/downside/risk signalの予測確度、安定性、説明性、ランキング貢献度を高める。

性能測定、walk-forward強化、特徴量拡充、consensus weighting見直し、上向き兆候への寄与整理の順で進める。時系列Foundation Model、TFT、GNN、追加GBDTライブラリは本線に入れず、既存改善後の実験枠とする。

## 2. 評価設計

重点horizonは20・60営業日、補助は5営業日、120日はバックテストで確認する。direction accuracy、RMSE、MAE、単純予測比RMSE improvement、calibration、ranking貢献度、false positive削減、上向き兆候への寄与、下降警戒との整合、model disagreement、confidence calibrationをmodel、horizon、market、asset type、regime、symbol、期間別に集計する。

評価日後のデータを特徴量に使わず、scaler、imputer、model fittingをfold内に閉じる。horizon相当のpurge windowを検討し、上昇・横ばい・下落相場を含め、static splitだけで採用判断しない。

## 3. モデル別改善候補

- `advanced_linear`: Ridge/ElasticNet alpha、標準化、外れ値clip、market/sector pooling、feature contribution安定性。軽量で説明可能な基準として維持。
- `advanced_tree_sklearn`: ExtraTreesのestimators/depth/min leaf、小標本の過学習、高ボラへの過剰反応、市場・asset type差。
- `advanced_gbdt_sklearn`: learning rate、iterations、leaf nodes、L2をhorizonや市場別に軽量調整し、方向一致とconfidenceを重視。
- `advanced_quantile`: regime/volatility別forward return分布、下振れrangeの下降警戒・安全性接続、extreme outlier抑制。

## 4. Consensus weighting

horizon、market、asset type、validation direction accuracy、RMSE improvementで重みを調整し、model disagreementが大きい場合はconfidenceを下げる。上向き兆候では予測値より方向一致と下振れ安全性を重視する。

出力候補は`consensus_predicted_return`、`consensus_direction_agreement`、`consensus_confidence`、`model_disagreement_warning`、`horizon_specific_weight`、`model_weighting_reason`。

## 5. 特徴量候補

- Chart: RSI、Bollinger、MA gap/slope、recent low break、higher low、60日range、volatility compression、volume spike/dry-up
- Relative strength: market/sector比20・60日return、sector momentum/reversal、peer group、market regime
- Fundamentals: dividend yield、payout、ROE、EPS growth、operating CF、FCF、debt/equity、dividend safety/trap
- Data quality: price/fundamental completeness、material freshness、source reliability

## 6. 上向き兆候への接続

forecast return、up/down model count、consensus confidence、model disagreement、quantile downside rangeを使う。方向一致、下降警戒、下振れrange、上昇済みcapを優先し、単純な高予測return順にしない。

## 7. 評価成果物

- `forecast_model_evaluation_summary.md`
- `forecast_model_evaluation_by_horizon.csv`
- `forecast_model_evaluation_by_market.csv`
- `forecast_model_evaluation_by_asset_type.csv`
- `forecast_model_evaluation_by_regime.csv`
- `forecast_model_error_cases.md`
- `forecast_model_weighting_adjustments.md`

## 8. 新規モデルの採用条件と完了条件

既存評価で明確な弱点があり、特徴量やweightingで改善できず、walk-forwardで安定して上回り、推論時間・配布負荷・保守性が許容され、UIで説明できる場合だけ新規モデルを検討する。

モデルごとの得意・不得意、consensus weight、confidence低下ルール、上向き兆候への寄与を説明でき、新規モデルが必要か既存改善で十分か判断できれば完了とする。

## 9. 実装済み評価・改善gate

- 20/60営業日の外側rolling-originで、各起点時点までのbarsだけからmodelとconsensusを再予測する。
- adapter内部validationにはhorizon相当のpurge windowを適用する。
- horizon、market、asset type、regime別の実測指標と最新予測を分離して出力する。
- 過去foldのdirection accuracyとzero-return baseline比RMSE improvementから保守的な候補weightを作る。
- 前半rolling originsで候補weightを作り、後半originを時系列holdoutとして現行consensusと比較する。holdoutでRMSE改善かつ方向一致率維持の場合だけ採用候補にする。
- gate未通過weightは通常Rankingや通常Forecastへ適用できない。

## 10. 2026-07-19 広範比較後の選定

非重複133symbol、20日・60日、各最大3 rolling originsの比較では、単一modelがRMSEと方向一致率を
全horizon・全cohortで同時に支配しなかった。中心価格は`moving_average_3`または
`advanced_quantile`の保守的予測、方向はadvanced consensus、rangeは`advanced_quantile`へ分ける。
長期ほどzero-return近傍へ縮める`horizon-conditioned conservative calibration`をevaluation-onlyで
実装した。tuningは20日をconsensus 30% + `moving_average_3` 70%、60日を
`moving_average_3` 100%として固定した。overall RMSEはvalidation / auditの両horizonで改善したが、
validationの20日downtrend群で10.92%悪化してsubgroup gateを通過しなかった。結果を見た再調整は
行わず、runtimeへ接続しない。固定profileを過去3評価群と重複しない60symbolへ適用した直近再現は
20日14.96%、60日7.42%のoverall RMSE改善でgateを通過した。一方、2021年末cutoffの履歴再現は
overallで20日15.13%、60日12.55%改善しても、ETF・60日が19.08%悪化してsubgroup gate未通過と
なった。2023年末cutoffもoverallで20日13.59%、60日2.80%改善した一方、ETF・60日27.18%、
downtrend・60日36.70%悪化でgate未通過だった。3期間、重複なし1,074評価点、2019〜2026年へ
拡張してもasset type / regimeをまたぐ安定性が証明できないため、Cockpit、Ranking、Forecast consensusへ
接続しない。後付けでETF weightを調整せず、次は後日の新暦期間をsealed auditとして使う。

LLM material scoreはprice headへ直接加えず、point-in-timeのevent / adverse risk / freshness /
evidence qualityによるconfidence上限・range調整候補として実ニュース履歴で別評価する。
synthetic/static fixtureの高指標はruntime採用根拠にしない。詳細は
`Documents/40_Forecast_Model_Selection_Report.md`を参照する。
