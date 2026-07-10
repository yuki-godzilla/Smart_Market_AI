# Forecast Model Evaluation Summary

未来情報を使わないrolling-origin評価です。予測は投資助言や将来成果の保証ではありません。

- 評価ケース数: 22
- 対象horizon: 20, 60営業日
- rolling-origin予測数: 1100
- 改善weightは後半holdoutで現行consensusと比較し、条件通過時だけ採用候補にします。

| Model | Horizon | Cases | Samples | MAE | RMSE | Direction | RMSE improvement | Disagreement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| advanced_linear | 20 | 22 | 110 | 0.0645 | 0.0906 | 0.5545 | -0.0187 | - |
| advanced_tree_sklearn | 20 | 22 | 110 | 0.0512 | 0.0692 | 0.6000 | 0.0027 | - |
| advanced_gbdt_sklearn | 20 | 22 | 110 | 0.0561 | 0.0768 | 0.6273 | -0.0049 | - |
| advanced_quantile | 20 | 22 | 110 | 0.0489 | 0.0676 | 0.6636 | 0.0043 | - |
| forecast_consensus | 20 | 22 | 110 | 0.0521 | 0.0710 | 0.6182 | 0.0009 | 0.0428 |
| advanced_linear | 60 | 22 | 110 | 0.1240 | 0.1796 | 0.5636 | 0.0153 | - |
| advanced_tree_sklearn | 60 | 22 | 110 | 0.1149 | 0.1788 | 0.6091 | 0.0161 | - |
| advanced_gbdt_sklearn | 60 | 22 | 110 | 0.1270 | 0.1921 | 0.5364 | 0.0028 | - |
| advanced_quantile | 60 | 22 | 110 | 0.1193 | 0.1815 | 0.5273 | 0.0134 | - |
| forecast_consensus | 60 | 22 | 110 | 0.1186 | 0.1794 | 0.5636 | 0.0155 | 0.0681 |

## 注意

- 改善候補weightは同一fold比較を通過していないため、自動採用されません。
