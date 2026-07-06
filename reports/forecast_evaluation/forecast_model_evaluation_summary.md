# Forecast Model Evaluation Summary

未来情報を使わないrolling-origin評価です。予測は投資助言や将来成果の保証ではありません。

- 評価ケース数: 0
- 対象horizon: 20, 60営業日
- rolling-origin予測数: 0
- 改善weightは同一foldで現行consensusと比較し、条件通過時だけ採用候補にします。

| Model | Horizon | Cases | Samples | MAE | RMSE | Direction | RMSE improvement | Disagreement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| advanced_linear | 20 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | - |
| advanced_tree_sklearn | 20 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | - |
| advanced_gbdt_sklearn | 20 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | - |
| advanced_quantile | 20 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | - |
| forecast_consensus | 20 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | - |
| advanced_linear | 60 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | - |
| advanced_tree_sklearn | 60 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | - |
| advanced_gbdt_sklearn | 60 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | - |
| advanced_quantile | 60 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | - |
| forecast_consensus | 60 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | - |

## 注意

- 評価ケースがありません。
- 改善候補weightは同一fold比較を通過していないため、自動採用されません。
