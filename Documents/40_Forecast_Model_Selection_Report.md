# 40 将来価格予測モデル 広範比較・選定レポート

更新日: 2026-07-19

## 1. 結論

SMAIにおける現時点の最適解は、単一の新規モデルへ置き換えることではない。

1. 中心価格は長期ほどゼロreturn近傍へ縮める保守的なprice head
2. 上下方向は既存advanced consensusを使うdirection head
3. 下限・上限は`advanced_quantile`を使うuncertainty head
4. LLM材料スコアはニュース・決算・開示のevent / risk / freshness / evidence qualityを表すconfidence head

この4層を分離する構成が最も現実的である。LLMに価格そのものを生成させたり、LLMスコアで
予測returnを直接上書きしたりしない。現行runtime consensusは維持し、追加候補はshadow評価を
続ける。

`advanced_regime_gated_ensemble`は一部splitで改善したが、すべてのvalidation / audit gateを
満たさなかったため不採用とする。LLM Factorも現行のbroader fixtureがsynthetic/staticであり、
実市場での追加価値を証明していないため、Forecast、Ranking、Investment Scoreへ統合しない。

追加評価した`horizon_conditioned_conservative_calibration`はoverall RMSEをvalidation / auditの
20日・60日すべてで改善した。ただしvalidationの20日downtrend群で重大劣化gateに抵触したため、
runtimeへ採用せずshadowを継続する。audit結果を見た再調整は行わない。

その後、profileをversioned JSONとして固定し、過去3評価群と重複しない60銘柄へ再調整なしで
適用した。直近再現は20日14.96%、60日7.42%のoverall RMSE改善でgateを通過したが、2021年末で
封印した履歴再現ではETF・60日が19.08%悪化した。2023年末再現でもETF・60日が27.18%、
downtrend・60日が36.70%悪化し、いずれもsubgroup gateを通過しなかった。したがって
Cockpit、Ranking、Forecast consensusへ統合しない。この評価は同日中の履歴再現であり、将来の
新暦期間を使ったsealed auditの代替でもない。

さらに、固定weightの時期・asset type依存を減らす目的で`point_in_time_adaptive_calibration`を
評価専用で実装した。過去の60銘柄・1,440点だけを調整履歴とし、それらとも全既存評価群とも
symbol非重複の新規40銘柄を監査用に取得した。39銘柄・936点の監査では20日RMSEを4.95%改善したが、
60日は0.53%悪化し、適応weight採用率も47.01%で事前条件50%未満だった。固定候補は同じ監査で
20日8.11%、60日2.46%改善して適応型を上回った。ただし固定候補には前述の過去年代別失敗が
残るため、どちらもruntimeへ採用しない。

さらに、固定profileをanchorとして残差だけを予測する`horizon_anchored_residual_calibration`を
評価専用で実装した。全既存評価pointに現れた258銘柄を除外した新規76銘柄から143,349日足を
取得し、履歴800 bars以上の52銘柄・1,248点をsealed監査した。残差RidgeはConsensus比で20日
2.94%、60日10.40%改善したが、固定anchor比では20日3.49%、60日1.16%悪化した。20日downtrendも
固定anchor比13.21%悪化し、補正採用率42.79%で50% gate未満だった。既に結果を確認済みの旧39銘柄を
参考再現しても固定anchor比20日0.06%、60日1.10%悪化した。したがって残差Ridgeも不採用とし、
parameterを監査結果へ合わせて再調整しない。

## 2. 評価範囲

評価は2つの非重複cohortで実施した。

| Cohort | 取得symbol | 評価可能symbol | 日足 | Split | 備考 |
| --- | ---: | ---: | ---: | --- | --- |
| Phase 34 primary | 66 | 62 | 160,555 | tuning 22 / validation 21 / audit 19 | 価格不連続2symbolを品質gateで除外 |
| Extended live | 71 | 71 | 88,044 | tuning 25 / validation 23 / audit 23 | 日本株30、米国株31、ETF10。取得失敗0 |
| 合計 | 137 | 133 | 248,599 | symbol-disjoint | cohort間もsymbol非重複 |

両cohortとも直近750営業日、20日・60日horizon、最大3 rolling originsで評価した。
各origin以後の価格は特徴量へ入れず、advanced adapter内部のvalidationもhorizon相当をpurgeする。
1モデル・1horizonあたり、validationは合計132点、sealed auditは126点である。

比較対象は`naive`、`moving_average_3`、`momentum_3`、4つのadvanced adapter、現行
`forecast_consensus`、評価専用`advanced_regime_gated_ensemble`である。続く保守校正では、両cohortの
tuning 141点 / horizonだけでprofileを固定し、validation 132点 / horizon、audit 126点 / horizonへ
再調整なしで適用した。

固定後の再現評価には、上記2cohortおよびPhase 33の銘柄をすべて除外した別の60銘柄
（日本株25、米国株25、ETF10、148,370日足）を使った。固定profile SHA-256は
`5afb4094987065cf7d1d30ae58ab57d53d57071d43f5c3d988741c4c87297806`である。

| 再現評価 | 取得symbol | 評価可能symbol | 評価点 / horizon | Origin範囲 | 備考 |
| --- | ---: | ---: | ---: | --- | --- |
| 直近・新規symbol | 60 | 60 | 180 | 2023-08-25〜2026-06-19 | profile再調整なし |
| 2021年末cutoff | 60 | 59 | 177 | 2019-02-05〜2021-12-02 | QQQMは308/500 barsで除外 |
| 2023年末cutoff | 60 | 60 | 180 | 2021-02-15〜2023-12-01 | profile再調整なし |

3期間の評価点は重複せず合計1,074点（537点 / horizon）で、originは2019-02-05から
2026-06-19までを覆う。日付を変えて同じ観測点を重複集計していない。

履歴cutoffは未来barを除去してからeligibility、価格不連続、regimeを判定する。さらに各originの
regimeと`moving_average_3`は、そのoriginまでのbarsだけから再計算した。actual returnは評価label
にだけ使用し、予測入力へ渡していない。

適応型候補は、上記60銘柄の10年履歴から作った1,440点をdevelopment historyとし、全既存評価群・
development historyとsymbol非重複の新規40銘柄を別監査群とした。40銘柄から96,580日足を取得し、
履歴500 bars未満のSPLGを除く39銘柄、20日・60日各468点、合計936点を評価した。監査originは
2016-12-26〜2026-06-19である。銘柄台帳は
`data/forecast_evaluation/profiles/adaptive_calibration_development_symbols_2026-07-19.csv`と
`data/forecast_evaluation/profiles/adaptive_calibration_audit_symbols_2026-07-19.csv`へ固定した。

残差Ridgeの最終監査群は、上記cohortを含む過去22個のpoint / symbol CSVに出現した258銘柄を
すべて除外した。active、data quality OK、平均出来高10万以上、非leveraged / 非inverseを条件とし、
market、asset type、stockの時価総額tier内で固定seedのSHA-256順に76銘柄を事前選定した。10年分
143,349日足は全76銘柄で取得でき、履歴800 bars以上の52銘柄（日本株20、日本ETF3、米国株15、
米国ETF14）を評価した。新規上場・新設ETFを中心とする24銘柄は履歴不足としてcoverageへ残し、
評価から除外した。20日・60日各624点、合計1,248点、originは2016-12-21〜2026-06-19である。
銘柄台帳は`data/forecast_evaluation/profiles/anchored_residual_audit_symbols_2026-07-19.csv`へ固定した。

## 3. Cohort統合結果

### 3.1 Validation

| Horizon | Model | RMSE | MAE | Direction accuracy | 読み方 |
| ---: | --- | ---: | ---: | ---: | --- |
| 20 | `moving_average_3` | **0.0826** | **0.0630** | 54.55% | 中心値の最良候補 |
| 20 | `advanced_quantile` | 0.0866 | 0.0656 | 53.03% | rangeと中心の有力候補 |
| 20 | `forecast_consensus` | 0.0994 | 0.0721 | 54.54% | directionは維持、値幅が過大 |
| 60 | `naive` | **0.2053** | **0.1322** | 43.18% | RMSE基準。方向予測ではない |
| 60 | `moving_average_3` | 0.2085 | 0.1335 | **51.52%** | RMSEと方向の均衡が最良 |
| 60 | `advanced_quantile` | 0.2124 | 0.1498 | 46.22% | consensusより保守的 |
| 60 | `forecast_consensus` | 0.2377 | 0.1676 | 47.72% | return振幅の校正が必要 |

### 3.2 Sealed audit

| Horizon | Model | RMSE | MAE | Direction accuracy | 読み方 |
| ---: | --- | ---: | ---: | ---: | --- |
| 20 | `naive` | **0.0729** | **0.0558** | 35.71% | zero-return RMSE baseline |
| 20 | `advanced_quantile` | 0.0742 | 0.0561 | **55.56%** | 有効な20日候補 |
| 20 | `moving_average_3` | 0.0751 | 0.0570 | 53.18% | 保守的な中心値 |
| 20 | `forecast_consensus` | 0.0770 | 0.0580 | 50.79% | 単純baselineとの差は小さい |
| 60 | `moving_average_3` | **0.1630** | **0.1148** | **52.38%** | RMSEと方向の均衡が最良 |
| 60 | `naive` | 0.1644 | 0.1158 | 37.30% | zero-return RMSE baseline |
| 60 | `advanced_quantile` | 0.1868 | 0.1371 | 49.20% | consensusより良好 |
| 60 | `forecast_consensus` | 0.2019 | 0.1454 | 45.24% | 長期return振幅が過大 |

`naive`の方向一致率が低いのは、予測returnが常に0であり、上昇・下落方向を出さないためである。
RMSEだけならzero-returnが強い一方、方向判定には使えない。`momentum_3`は一部で方向一致率が
高くても、return外挿によりRMSEが大幅に悪化したため不採用である。

## 4. どのモデルが良いか

目的別の選定は次のとおり。

| 目的 | 現時点の最良候補 | 判断 |
| --- | --- | --- |
| 20日中心価格 | `moving_average_3`と`advanced_quantile`の保守的校正 | shadow候補 |
| 60日中心価格 | `moving_average_3` | 最有力shadow候補 |
| 上下方向 | advanced adapter / consensus | runtime維持 |
| 予測幅 | `advanced_quantile` | runtimeのrange役を維持 |
| regime別weight | `advanced_regime_gated_ensemble` | gate未通過、不採用 |
| 固定anchorの残差補正 | `horizon_anchored_residual_calibration` | anchor比悪化、不採用 |
| event / adverse risk | LLM material score | 実履歴監査前は参考表示のみ |
| 数値価格を直接出すLLM | generative LLM / Time-LLM | SMAI本線では不採用 |

新しい中心価格候補は、`consensus_return`をそのまま置き換えるのではなく、horizonが長くなるほど
保守baselineへ縮める`horizon-conditioned conservative calibration`とした。方向signalと中心returnを
別出力にし、中心returnの縮小で方向signalまで消さないtyped contractを実装した。

### 4.1 Horizon-conditioned conservative calibration結果

tuningで`advanced_quantile` / `moving_average_3`とconsensus weight 0.0～1.0を0.1刻みで比較し、
60日のconsensus weightが20日を超えない制約を置いた。選択profileは次のとおりである。

| Horizon | Price center | Tuning RMSE改善 | Validation RMSE改善 | Audit RMSE改善 |
| ---: | --- | ---: | ---: | ---: |
| 20 | consensus 30% + `moving_average_3` 70% | 7.72% | **15.65%** | **4.61%** |
| 60 | `moving_average_3` 100% | 13.97% | **12.26%** | **19.23%** |

direction headは全ケースで元のadvanced consensus returnを保持した。price center自体のdirection
accuracyはvalidationで20日57.58%、60日51.52%、auditで20日50.79%、60日52.38%だった。
最大絶対予測returnはvalidation / auditとも0.75の安全上限内だった。

一方、validationの20日downtrend 21点ではRMSEが0.0593から0.0657へ10.92%、絶対0.0065
悪化した。10点以上のsubgroupで相対10%超かつ絶対0.005超を重大劣化とする事前gateに抵触する。
overallの改善だけで本番採用せず、profileをauditやこのdowntrend結果へ合わせて再調整しない。

### 4.2 固定profileの新規symbol・履歴再現

既存評価結果を見た再調整経路を持たない専用runnerで、固定profileを新規60symbolへ適用した。

| 再現評価 | Horizon | Consensus RMSE | 候補RMSE | 改善率 | Retained direction | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 直近 | 20 | 0.1108 | 0.0943 | **14.96%** | 49.44% | 通過 |
| 直近 | 60 | 0.2216 | 0.2052 | **7.42%** | 47.22% | 通過 |
| 2021年末cutoff | 20 | 0.0860 | 0.0730 | **15.13%** | 62.15% | overall通過 |
| 2021年末cutoff | 60 | 0.1522 | 0.1331 | **12.55%** | 65.54% | subgroup不通過 |
| 2023年末cutoff | 20 | 0.0929 | 0.0803 | **13.59%** | 46.11% | overall通過 |
| 2023年末cutoff | 60 | 0.1559 | 0.1516 | **2.80%** | 61.11% | subgroup不通過 |

direction headは候補中心値と分離し、全点で元のconsensus方向を保持した。直近60日downtrendは
11点でRMSEが0.1467から0.1565へ6.68%悪化したが、重大劣化の相対10%条件には届かなかった。
一方、2021年末cutoffのETF・60日は27点で0.0492から0.0586へ19.08%、絶対0.0094悪化し、
相対10%超かつ絶対0.005超の重大劣化gateに抵触した。ETF・20日も12.37%悪化したが、絶対悪化は
0.0040でgate閾値未満だった。

2023年末cutoffではETF・60日30点が0.0732から0.0931へ27.18%、絶対0.0199悪化し、
downtrend・60日14点も0.1085から0.1484へ36.70%、絶対0.0399悪化した。直近期間だけでは
現れなかった重大劣化が2つの履歴期間で再現され、銘柄構成だけでなく評価日・asset type・regimeへの
依存がある。

全体平均は再現したものの、asset typeをまたぐ安定性は証明できなかった。今回の履歴結果を使った
ETF専用weightの後付け調整は行わない。新しいpolicyを検討する場合は、別の調整群で事前定義し、
さらに未使用symbolと後日の暦期間で監査する。

### 4.3 Point-in-time適応型weightの分離監査

固定weightの弱点に対して、`forecast_consensus`、`advanced_quantile`、`moving_average_3`、
zero-returnの非負weightを0.1刻みで推定するshadow候補を追加した。weightはstock / ETFと
20日 / 60日を分け、各監査originで`target_at <= origin_at`となるdevelopment labelだけを利用する。
利用可能なoriginの古い70%だけでweightを選び、新しい30%は1%以上のRMSE改善を確認する内部
validation gateに限定した。履歴不足またはfit / validation gate未通過時は現行Consensusへ完全
fallbackし、direction headは全点で現行Consensusを保持する。

| 候補 | Horizon | Samples | Consensus RMSE | 候補RMSE | 改善率 | 判定 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 適応型 | 20 | 468 | 0.0848 | 0.0806 | **4.95%** | overall通過 |
| 適応型 | 60 | 468 | 0.1584 | 0.1592 | **-0.53%** | overall不通過 |
| 固定profile | 20 | 468 | 0.0848 | 0.0780 | **8.11%** | 同一監査で通過 |
| 固定profile | 60 | 468 | 0.1584 | 0.1545 | **2.46%** | 同一監査で通過 |

適応weightは440 / 936点、47.01%で採用され、残る496点はConsensus fallbackだった。20日は改善した
一方、60日の2024年以降118点で7.24%、drawdown 51点で5.86%、日本株180点で3.88%悪化した。
これらは相対10%かつ絶対0.005超の重大劣化閾値には達しなかったが、60日overall 1%改善gateと
適応weight採用率50% gateに失敗した。監査結果を見たweight grid、最低標本数、採用率閾値の変更は
行わない。

この結果では、適応型は固定候補より良くない。固定候補は今回の新規symbol監査を通過したが、
2021年末・2023年末のETF / downtrend失敗を打ち消す証拠にはならない。したがって現行runtime
Consensusを維持し、Forecast、Cockpit、Ranking、Investment Scoreへどちらも接続しない。

### 4.4 固定anchor残差Ridgeの新規symbol監査

固定profileの中心値をanchorとし、`actual_return - anchor_return`だけを予測する小規模Ridgeを
追加した。候補は事前に次の2本へ限定した。

- global Ridge: anchorとConsensus / quantile / moving averageのanchor差、alpha 10
- context Ridge: 上記にmarket、asset type、regimeのone-hotを追加し、alpha 25で強く縮小

20日・60日は分離し、各監査originで`target_at <= origin_at`のdevelopment labelだけを使う。
利用可能originの古い70%で2候補を比較し、新しい30%で固定anchor比1%以上改善しない場合は補正を
使わない。補正幅はfit残差絶対値の90%点か25%の小さい方、最終returnは絶対75%で制限した。
direction headは全点でConsensusを保持した。

| Model | Horizon | Samples | Consensus RMSE | Model RMSE | vs Consensus | vs 固定anchor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 固定anchor | 20 | 624 | 0.120205 | **0.112739** | **6.21%** | 基準 |
| 適応weight | 20 | 624 | 0.120205 | 0.117532 | 2.22% | -4.25%相当 |
| 残差Ridge | 20 | 624 | 0.120205 | 0.116676 | 2.94% | **-3.49%** |
| 固定anchor | 60 | 624 | 0.218857 | **0.193853** | **11.42%** | 基準 |
| 適応weight | 60 | 624 | 0.218857 | 0.207594 | 5.15% | -7.09%相当 |
| 残差Ridge | 60 | 624 | 0.218857 | 0.196102 | 10.40% | **-1.16%** |

残差補正は534 / 1,248点、42.79%で内部gateを通過した。しかし、その外側監査で補正採用点だけを
見ると固定anchor比20日5.01%、60日4.08%悪化した。内部validationで選ばれた補正関係が別symbolへ
一般化していない。20日downtrend 28点は固定anchor RMSE 0.077899から0.088193へ13.21%、絶対
0.010294悪化し、重大劣化gateにも抵触した。return capは0件、residual clipは3件であり、安全上限
ではなく補正自体の汎化誤差が不採用理由である。

期間別でも、固定anchor比で60日・2024年以降だけ1.03%改善した一方、20日・2024年以降は5.33%、
60日・2022〜2023年は5.39%悪化した。旧39銘柄・936点での参考再現も20日-0.06%、60日-1.10%、
採用率40.38%であり、新規監査の不採用判断と整合した。旧cohortは設計時に結果を確認済みのため
最終gateには使っていない。

結論として、全候補中のprice center最良は今回も固定anchorだった。ただし固定anchor自体も
2021年末・2023年末のETF / downtrend gateに失敗済みなのでruntimeへは接続しない。残差Ridgeの
feature、alpha、clip、最低標本数、50%採用率を今回の結果へ合わせて変更することは禁止し、次は
価格中心の微調整ではなくpoint-in-time event / risk情報のconfidence・range寄与を検証する。

## 5. LLM scoringの使い方

SMAIにはすでに、source URL、published date、model、prompt version、source hash、cache metadataを
保持する`LLMFactorResult`と検証基盤がある。既存fixture検証は35symbol、280 samples、8 datesで、
synthetic/static fixture上では`llm_risk_score`の5日・20日drawdown AUCが0.9744、
`llm_quality_adjusted_net`の20日up AUCが0.9052だった。ただしfixture生成過程にsignalとreturnの
関係が含まれるため、実市場での精度として報告してはいけない。

最初の実運用候補はLLMのnet bullish scoreを価格returnへ足すことではない。次の限定用途とする。

- adverse materialが強い場合にconfidence上限を下げる
- event riskが高い場合にquantile予測幅を広げる
- freshnessまたはevidence qualityが低い場合にLLM寄与を0へ近づける
- deterministic ranking上位候補だけを対象にし、全銘柄へ同期LLM callを行わない
- source公開時刻がorigin以後の材料を除外する
- LLM失敗、schema違反、stale sourceでは既存予測へ完全fallbackする

実ニュース履歴で`without LLM`と`with LLM`を比較し、Brier score / log loss、方向一致率、RMSE、
drawdown識別、false-positive削減をvalidationとauditの両方で改善した場合だけ、confidence / range
調整へ進める。中心returnへの直接加算はその後も別gateとする。

## 6. 最新研究からの位置づけ

時系列foundation modelやLLM再プログラミングは研究候補として有用だが、SMAIの現データ量、
local-first、説明性、CPU負荷には重い。公開研究にもLLM部分の必須性を疑う結果があるため、
小さな価格モデルと構造化LLM factorを分離する。

- [FinCast: A Foundation Model for Financial Time-Series Forecasting](https://doi.org/10.1145/3746252.3761261), 2025: 金融時系列専用foundation model。将来の比較対象だが初期導入には大きい。
- [Deep learning for time series forecasting: a survey](https://doi.org/10.1007/s13042-025-02560-w), 2025: architecture選択と評価課題を整理。単一architectureの万能性を前提にしない。
- [Chronos: Learning the Language of Time Series](https://doi.org/10.48550/arxiv.2403.07815), 2024: 時系列をtoken化するfoundation-model系候補。
- [A decoder-only foundation model for time-series forecasting](https://doi.org/10.48550/arxiv.2310.10688), TimesFM: decoder-only事前学習モデルの比較候補。
- [GPT4MTS](https://doi.org/10.1609/aaai.v38i21.30383), 2024: multimodal時系列へLLM promptを使う研究。価格・文章の分離評価が必要。
- [Are Language Models Actually Useful for Time Series Forecasting?](https://doi.org/10.48550/arxiv.2406.16964), 2024: LLM componentの寄与をablationsで厳しく確認する必要性を示す比較材料。

調査日は2026-07-19。論文の公開情報は将来変わり得るため、採用時には原文、code、license、
reproducibilityを再確認する。

## 7. 採用gateと次の実装順

1. `horizon-conditioned conservative calibration`の固定profile化と3期間1,074点の再現評価は完了。
2. point-in-time適応型weightも、development 60symbol / 1,440点とsymbol非重複監査39symbol /
   936点で評価したが、60日と採用率gateに失敗した。適応型・固定型ともruntimeへ接続せず、監査
   結果に合わせた再調整もしない。
3. 固定anchor残差Ridgeも全既存群と非重複の52symbol / 1,248点で監査し、anchor比20日・60日と
   downtrend / 採用率gateに失敗した。runtimeへ接続せず、監査結果に合わせた再調整もしない。
4. 実ニュース・IRのpoint-in-time LLM factor archiveを作る。raw本文は保存方針に従い、source traceと
   structured factorを保存する。
5. LLMはconfidence / range調整からshadow評価し、数値returnへ直接混ぜない。
6. 保守的price headは後日の新暦期間で再監査する。全体とmarket / asset type / regimeのgateを
   すべて通過した場合だけCockpit / Ranking接続を再検討する。

## 8. 再実行成果物

- `reports/2026-07-19_1300/forecast_model_broad_comparison/forecast_model_broad_comparison.md`
- `reports/2026-07-19_1300/extended_live_model_comparison/forecast_model_broad_comparison.md`
- `reports/2026-07-19_1300/regime_gated_ensemble_broad_backtest.md`
- `reports/2026-07-19_1300/conservative_forecast_calibration/horizon_conditioned_conservative_calibration.md`
- `reports/2026-07-19_1300/frozen_profile_replication/recent_new_symbols/frozen_calibration_replication.md`
- `reports/2026-07-19_1300/frozen_profile_replication/historical_2021/frozen_calibration_replication.md`
- `reports/2026-07-19_1300/frozen_profile_replication/historical_2023/frozen_calibration_replication.md`
- `reports/2026-07-19_1300/adaptive_calibration/adaptive_audit_result/adaptive_calibration_evaluation.md`
- `reports/2026-07-19_1300/adaptive_calibration/adaptive_audit_result/adaptive_calibration_manifest.json`
- `reports/2026-07-19_1300/adaptive_calibration/adaptive_audit_result/adaptive_calibration_metrics.csv`
- `reports/2026-07-19_1300/adaptive_calibration/adaptive_audit_result/adaptive_calibration_weight_decisions.csv`
- `reports/2026-07-19_1300/anchored_residual_calibration/audit_76_result/anchored_residual_calibration_evaluation.md`
- `reports/2026-07-19_1300/anchored_residual_calibration/audit_76_result/anchored_residual_calibration_manifest.json`
- `reports/2026-07-19_1300/anchored_residual_calibration/audit_76_result/anchored_residual_calibration_metrics.csv`
- `reports/2026-07-19_1300/anchored_residual_calibration/retrospective_audit_39_result/anchored_residual_calibration_evaluation.md`
- `reports/2026-07-19_1300/llm_factor_validation/llm_factor_validation_report.md`

これらはローカル評価artifactであり、runtime設定、Ranking順、Forecast値、Investment Scoreを変更しない。
