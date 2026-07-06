# Forecast Model Evaluation Summary

未来情報を使わないrolling-origin評価です。予測は投資助言や将来成果の保証ではありません。

- 評価ケース数: 23
- 対象horizon: 20, 60営業日
- rolling-origin予測数: 1150
- 改善weightは後半holdoutで現行consensusと比較し、条件通過時だけ採用候補にします。

| Model | Horizon | Cases | Samples | MAE | RMSE | Direction | RMSE improvement | Disagreement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| advanced_linear | 20 | 23 | 115 | 0.0806 | 0.1066 | 0.4261 | -0.0233 | - |
| advanced_tree_sklearn | 20 | 23 | 115 | 0.0676 | 0.0901 | 0.3478 | -0.0068 | - |
| advanced_gbdt_sklearn | 20 | 23 | 115 | 0.0660 | 0.0908 | 0.4348 | -0.0075 | - |
| advanced_quantile | 20 | 23 | 115 | 0.0650 | 0.0873 | 0.4174 | -0.0040 | - |
| forecast_consensus | 20 | 23 | 115 | 0.0670 | 0.0898 | 0.4261 | -0.0065 | 0.0473 |
| advanced_linear | 60 | 23 | 115 | 0.1214 | 0.1675 | 0.6087 | -0.0053 | - |
| advanced_tree_sklearn | 60 | 23 | 115 | 0.1143 | 0.1632 | 0.5565 | -0.0010 | - |
| advanced_gbdt_sklearn | 60 | 23 | 115 | 0.1197 | 0.1678 | 0.5043 | -0.0056 | - |
| advanced_quantile | 60 | 23 | 115 | 0.1087 | 0.1605 | 0.5826 | 0.0017 | - |
| forecast_consensus | 60 | 23 | 115 | 0.1123 | 0.1598 | 0.6000 | 0.0024 | 0.0776 |

## 注意

- 改善候補weightは同一fold比較を通過していないため、自動採用されません。
