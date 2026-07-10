# Forecast Model Evaluation Summary

未来情報を使わないrolling-origin評価です。予測は投資助言や将来成果の保証ではありません。

- 評価ケース数: 19
- 対象horizon: 20, 60営業日
- rolling-origin予測数: 950
- 改善weightは後半holdoutで現行consensusと比較し、条件通過時だけ採用候補にします。

| Model | Horizon | Cases | Samples | MAE | RMSE | Direction | RMSE improvement | Disagreement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| advanced_linear | 20 | 19 | 95 | 0.0608 | 0.0884 | 0.5789 | 0.0031 | - |
| advanced_tree_sklearn | 20 | 19 | 95 | 0.0527 | 0.0810 | 0.6421 | 0.0105 | - |
| advanced_gbdt_sklearn | 20 | 19 | 95 | 0.0585 | 0.0877 | 0.5368 | 0.0038 | - |
| advanced_quantile | 20 | 19 | 95 | 0.0530 | 0.0882 | 0.6947 | 0.0033 | - |
| forecast_consensus | 20 | 19 | 95 | 0.0549 | 0.0838 | 0.6105 | 0.0077 | 0.0369 |
| advanced_linear | 60 | 19 | 95 | 0.1234 | 0.1940 | 0.6105 | -0.0267 | - |
| advanced_tree_sklearn | 60 | 19 | 95 | 0.1056 | 0.1580 | 0.6526 | 0.0093 | - |
| advanced_gbdt_sklearn | 60 | 19 | 95 | 0.1148 | 0.1749 | 0.5789 | -0.0076 | - |
| advanced_quantile | 60 | 19 | 95 | 0.1056 | 0.1594 | 0.5895 | 0.0079 | - |
| forecast_consensus | 60 | 19 | 95 | 0.1078 | 0.1625 | 0.6316 | 0.0048 | 0.0814 |

## 注意

- 改善候補weightは同一fold比較を通過していないため、自動採用されません。
