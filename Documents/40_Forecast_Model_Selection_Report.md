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
`forecast_consensus`、評価専用`advanced_regime_gated_ensemble`である。

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
| event / adverse risk | LLM material score | 実履歴監査前は参考表示のみ |
| 数値価格を直接出すLLM | generative LLM / Time-LLM | SMAI本線では不採用 |

新しい中心価格候補は、`consensus_return`をそのまま置き換えるのではなく、horizonが長くなるほど
保守baselineへ縮める`horizon-conditioned conservative calibration`とする。方向signalと中心returnを
別出力にし、中心returnの縮小で方向signalまで消さないcontractが必要である。

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

1. `horizon-conditioned conservative calibration`をevaluation-only contractとして追加する。
2. tuningだけで縮小係数を決め、validationとauditでは固定する。
3. 20日・60日のRMSEを各1%以上改善し、direction accuracyを悪化させないことを必須にする。
4. market、asset type、regime別で重大劣化がないことを確認する。
5. 実ニュース・IRのpoint-in-time LLM factor archiveを作る。raw本文は保存方針に従い、source traceと
   structured factorを保存する。
6. LLMはconfidence / range調整からshadow評価し、数値returnへ直接混ぜない。
7. 新期間・新symbolのsealed auditを通過した場合だけCockpit / Ranking接続を検討する。

## 8. 再実行成果物

- `reports/2026-07-19_1300/forecast_model_broad_comparison/forecast_model_broad_comparison.md`
- `reports/2026-07-19_1300/extended_live_model_comparison/forecast_model_broad_comparison.md`
- `reports/2026-07-19_1300/regime_gated_ensemble_broad_backtest.md`
- `reports/2026-07-19_1300/llm_factor_validation/llm_factor_validation_report.md`

これらはローカル評価artifactであり、runtime設定、Ranking順、Forecast値、Investment Scoreを変更しない。
