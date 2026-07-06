# Forecast Model Improvement Comparison

## 評価条件

- Yahoo Finance明示live取得
- 23銘柄、28,529 daily bars、全銘柄180 bars以上
- 日本株9、米国株14、個別株14、ETF9
- 20 / 60営業日、各23銘柄×5 rolling origins
- horizon purge適用、前半originで調整、後半originをholdoutとして判定

## Robust linear clipping 前後

| Model | Horizon | Before RMSE | After RMSE | RMSE change | Before direction | After direction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| advanced_linear | 20 | 0.4131 | 0.1066 | -74.2% | 42.61% | 42.61% |
| forecast_consensus | 20 | 0.1181 | 0.0898 | -24.0% | 41.74% | 42.61% |
| advanced_linear | 60 | 1.6000 | 0.1675 | -89.5% | 60.87% | 60.87% |
| forecast_consensus | 60 | 0.3099 | 0.1598 | -48.4% | 59.13% | 60.00% |

linear modelの小標本外挿を、学習targetの95% absolute quantileを基準にwinsorizeした。方向判定を変えず、極端なreturnだけを抑制している。

## 採用判断

- 採用: `advanced_linear` robust clipping。20日・60日の双方で大幅にRMSEを改善し、方向一致率を悪化させなかった。
- 保留: consensus weight候補。20日holdout改善は約0.5%で、新しい1% minimum gateを満たさない。60日は悪化。
- Shadow候補: regularized GBDT 20日、lower-center quantile 20日。1% gate通過後もmarket / asset type / regime別の安定性確認まではruntime既定値へ反映しない。
- 既定維持: 60日GBDT、60日quantile、およびgate未通過parameter候補。

## 注意

この結果は23銘柄・5 rolling originsの評価であり、将来成果や売買判断を保証しない。通常Rankingのweightやadapter既定parameterは変更せず、robust clippingだけを外れ値安全策として採用する。
