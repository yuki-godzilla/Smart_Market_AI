# Rolling Conformal予測レンジ校正 検証レポート

更新日: 2026-07-20

## 1. 結論

60%想定rangeのcoverage不足に対し、中心returnと方向returnを一切変更しない
Rolling Conformal Calibrationをevaluation-onlyで実装した。

標準的な正規化CQRをそのまま移送すると、audit coverageは約67〜71%まで上がったが、range幅が過大になり、
proper interval scoreは20 / 40 / 60 / 80 / 100 / 120日の全horizonで悪化した。そこで、元rangeの
最大約1.50倍に相当する正規化quantile上限と、成熟済み履歴内の時間順fit / validation gateを追加した。

最終のbounded candidateでも、proper scoreが改善したのは60日の0.68%だけで、事前定義した1% gateに
届かなかった。20 / 40 / 80 / 100 / 120日は0.79〜3.91%悪化した。よってruntime range、Forecast、
Cockpit、Ranking、Scoringへ接続せず、現行rangeと長期center confidence lowを維持する。

## 2. 実装契約

`backend/forecast/rolling_conformal.py`に
`bounded-normalized-cqr-temporal-gate-v1`を実装した。

- 対象は`forecast_consensus`のreturn intervalだけ
- `adjusted_center == baseline_center`をschemaで強制
- `adjusted_direction == baseline_direction`をschemaで強制
- calibration labelは`target_at <= evaluation origin_at`の場合だけ使用
- 区間外への外れ幅を元intervalの半幅で正規化
- 有限標本quantileは`ceil((n + 1) * coverage)`を使用
- expansion-onlyとし、過去誤差が小さい場合も元rangeを縮めない
- 既定target coverageは60%
- 正規化quantile上限0.50、すなわち元interval幅の最大約1.50倍
- 最大500点の成熟履歴を使用
- `market + asset type + regime`、`asset type`、`horizon pooled`の順にfallback
- 詳細groupは30点以上、pooledは40点以上、2 origin以上を必要とする
- calibration履歴内を古い70% originのfitと新しい30% originのvalidationに分離
- fit / validationは各10点以上
- internal validationでproper score 1%以上改善かつcoverage非悪化の場合だけ適用
- 履歴不足またはinternal gate未通過は元intervalへ完全fallback

prequential optionも用意した。これを有効にしても、評価点自身のlabelは`target_at`が後続origin以前に
成熟した場合だけ後続decisionへ追加される。同一originや未来targetは使用しない。

## 3. 外側採用gate

新しいsealed auditであっても、次をすべて満たさなければruntime review候補にならない。

- horizonごと100点以上
- calibration適用率50%以上
- horizonごとのproper interval score改善1%以上
- coverageがbaseline以上
- 60% targetとの差が5 percentage points以内
- 10点以上のmarket / asset type / regimeで重大なproper score劣化がない
- symbol-disjointまたは完全なtemporal-disjoint境界を満たす
- unbounded conformalではない

既確認データを`historical_replay`として渡した場合は、数値gateに関係なく
`runtime_review_eligible=false`となる。

## 4. Backtestデータ

| Role | Cohort | Symbols | Consensus points |
| --- | --- | ---: | ---: |
| calibration | Phase 34 validation | 21 | 378 |
| calibration | Extended validation | 23 | 414 |
| historical replay | Phase 34 audit | 19 | 342 |
| historical replay | Extended audit | 23 | 414 |
| pooled calibration | 2群 | 44 | 792 |
| pooled replay | 2群 | 42 | 756 |

20 / 40 / 60 / 80 / 100 / 120日、各audit 126点で評価した。calibrationとevaluationのsymbol重複は0件。
今回のauditは以前に結果を確認しているため、方法の安全性再生であり、新しいsealed auditではない。

## 5. 最終bounded candidate

| Horizon | N | Applied | Coverage before | Coverage after | Width before | Width after | Proper score improvement |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | 126 | 42 | 53.97% | 61.90% | 0.0968 | 0.1157 | -3.79% |
| 40 | 126 | 84 | 46.03% | 59.52% | 0.1238 | 0.1754 | -3.91% |
| 60 | 126 | 84 | 36.51% | 48.41% | 0.1542 | 0.2179 | +0.68% |
| 80 | 126 | 42 | 40.48% | 46.83% | 0.1721 | 0.2077 | -0.79% |
| 100 | 126 | 42 | 36.51% | 42.06% | 0.1708 | 0.2077 | -2.22% |
| 120 | 126 | 42 | 37.30% | 43.65% | 0.1887 | 0.2285 | -2.33% |

coverageだけを見ると上がるが、幅の増加を含むproper scoreでは改善しない。60日も0.68%で1% gate未達、
かつcoverageは48.41%でtarget下限55%に届かない。

## 6. 上限感度

正規化quantile上限を、元幅の約1.10 / 1.25 / 1.50倍に相当する0.10 / 0.25 / 0.50で比較した。

| Horizon | Cap 0.10: coverage / score改善 | Cap 0.25: coverage / score改善 | Cap 0.50: coverage / score改善 |
| ---: | ---: | ---: | ---: |
| 20 | 55.56% / -0.40% | 61.90% / -2.67% | 61.90% / -3.79% |
| 40 | 48.41% / -0.04% | 54.76% / -0.98% | 59.52% / -3.91% |
| 60 | 39.68% / +0.56% | 44.44% / +0.93% | 48.41% / +0.68% |
| 80 | 40.48% / 0.00% | 42.86% / -0.03% | 46.83% / -0.79% |
| 100 | 37.30% / -0.13% | 38.10% / -0.56% | 42.06% / -2.22% |
| 120 | 37.30% / 0.00% | 41.27% / -0.69% | 43.65% / -2.33% |

60日のcap 0.25が最良でも0.93%であり、結果を見てgateを1%未満へ下げない。単一horizonだけを採用するにも
coverage不足が残る。

## 7. Cohort分離とsubgroup

Cap 0.50を2つのaudit cohortへ分けても結論は変わらなかった。

- Phase 34 audit: 60日+0.82%、80日+0.13%。他horizonは悪化
- Extended audit: 60日+0.50%。他horizonは悪化
- いずれも1% gate未達

主なmaterial failureは次のとおりだった。

- ETF 40日: proper score 10.12%悪化
- ETF 60日: proper score 10.02%悪化
- downtrend 40日: 9.80%悪化
- US 20日: 6.68%悪化
- sideways 40日: 4.86%悪化
- US 60日は1.40%悪化し、JP 60日の3.74%改善と方向が一致しない

一部subgroupだけの改善を全体採用へ読み替えない。

## 8. 比較した失敗経路

内部gateを持たないunbounded CQRは、coverageを66.7〜70.6%まで上げた一方、平均幅を大きくし、
proper scoreを20日19.43%、40日34.97%、60日43.14%、80日44.75%、100日101.48%、120日48.20%
悪化させた。prequential更新でもこの分布移動を十分に吸収できなかった。

したがって、単純な「coverageが上がった」という理由だけでrangeを広げるのは危険である。今回追加した
bounded cap、内部temporal gate、外側proper-score gateは、こうした候補をruntimeへ流さないために残す。

## 9. 採否と次の条件

| 対象 | 判定 |
| --- | --- |
| Rolling Conformal evaluator / CLI | 採用。evaluation-only |
| range校正のruntime接続 | 不採用 |
| center / direction変更 | 禁止、schema上不変 |
| cap 0.10 / 0.25 / 0.50 | すべてruntime不採用 |
| prequential update | 評価optionのみ |

次の採用判断は、今回の結果へ合わせて閾値を変えず、後日の新暦期間または新symbol sealed auditで行う。
それまでは現行range、長期center confidence low、条件付きdirection confidence mediumを維持する。

参考となる基本手法:

- Romano, Patterson, Candès, *Conformalized Quantile Regression*, NeurIPS 2019
- Gibbs, Candès, *Adaptive Conformal Inference Under Distribution Shift*, NeurIPS 2021
- Barber et al., *Conformal Prediction Beyond Exchangeability*, Annals of Statistics 2023

時系列・市場regimeではexchangeabilityを仮定できないため、理論coverageだけでなく、時点整合した
proper interval scoreとsubgroup監査を採用条件とする。

SMAIの出力は投資判断支援情報であり、将来価格、利益、方向、予測区間内への収束を保証しない。
