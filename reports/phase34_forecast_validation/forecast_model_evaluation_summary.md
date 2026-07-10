# Forecast Model Evaluation Summary

未来情報を使わないrolling-origin評価です。予測は投資助言や将来成果の保証ではありません。

- 評価ケース数: 21
- 対象horizon: 20, 60営業日
- rolling-origin予測数: 1050
- 改善weightは後半holdoutで現行consensusと比較し、条件通過時だけ採用候補にします。

| Model | Horizon | Cases | Samples | MAE | RMSE | Direction | RMSE improvement | Disagreement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| advanced_linear | 20 | 21 | 105 | 0.0710 | 0.1209 | 0.6000 | -0.0363 | - |
| advanced_tree_sklearn | 20 | 21 | 105 | 0.0636 | 0.1161 | 0.5810 | -0.0315 | - |
| advanced_gbdt_sklearn | 20 | 21 | 105 | 0.0712 | 0.1372 | 0.5333 | -0.0526 | - |
| advanced_quantile | 20 | 21 | 105 | 0.0605 | 0.1056 | 0.6000 | -0.0210 | - |
| forecast_consensus | 20 | 21 | 105 | 0.0637 | 0.1145 | 0.5905 | -0.0299 | 0.0495 |
| advanced_linear | 60 | 21 | 105 | 0.1579 | 0.2576 | 0.5905 | -0.0384 | - |
| advanced_tree_sklearn | 60 | 21 | 105 | 0.1535 | 0.3017 | 0.6000 | -0.0825 | - |
| advanced_gbdt_sklearn | 60 | 21 | 105 | 0.1590 | 0.2813 | 0.5333 | -0.0621 | - |
| advanced_quantile | 60 | 21 | 105 | 0.1514 | 0.2899 | 0.6381 | -0.0707 | - |
| forecast_consensus | 60 | 21 | 105 | 0.1520 | 0.2768 | 0.5619 | -0.0576 | 0.0800 |

## 注意

- 改善候補weightは同一fold比較を通過していないため、自動採用されません。
