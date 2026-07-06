# Forecast Model Tuning Summary

既存4モデルのbounded candidateを時系列holdoutで比較します。
採用条件（RMSE 1%以上改善・方向一致率維持）未達の候補は通常予測へ反映しません。

## advanced_linear / 20営業日

- 候補: `ridge_alpha_4`
- 判定: 既定維持
- 既定holdout RMSE: 0.0888
- 候補holdout RMSE: 0.0887
- 既定方向一致率: 0.4130
- 候補方向一致率: 0.4130
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_linear / 60営業日

- 候補: `ridge_alpha_4`
- 判定: 既定維持
- 既定holdout RMSE: 0.1786
- 候補holdout RMSE: 0.1786
- 既定方向一致率: 0.7455
- 候補方向一致率: 0.7455
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_tree_sklearn / 20営業日

- 候補: `conservative_tree`
- 判定: 既定維持
- 既定holdout RMSE: 0.0805
- 候補holdout RMSE: 0.0803
- 既定方向一致率: 0.3261
- 候補方向一致率: 0.3261
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_tree_sklearn / 60営業日

- 候補: `conservative_tree`
- 判定: 既定維持
- 既定holdout RMSE: 0.1813
- 候補holdout RMSE: 0.1799
- 既定方向一致率: 0.6364
- 候補方向一致率: 0.6909
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_gbdt_sklearn / 20営業日

- 候補: `regularized_gbdt`
- 判定: 採用候補
- 既定holdout RMSE: 0.0791
- 候補holdout RMSE: 0.0775
- 既定方向一致率: 0.4348
- 候補方向一致率: 0.4565
- 理由: 時系列holdoutでRMSEを1%以上改善し、方向一致率を維持しました。

## advanced_gbdt_sklearn / 60営業日

- 候補: `regularized_gbdt`
- 判定: 既定維持
- 既定holdout RMSE: 0.1862
- 候補holdout RMSE: 0.1907
- 既定方向一致率: 0.5273
- 候補方向一致率: 0.5091
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_quantile / 20営業日

- 候補: `lower_center_quantile`
- 判定: 採用候補
- 既定holdout RMSE: 0.0810
- 候補holdout RMSE: 0.0798
- 既定方向一致率: 0.3913
- 候補方向一致率: 0.3913
- 理由: 時系列holdoutでRMSEを1%以上改善し、方向一致率を維持しました。

## advanced_quantile / 60営業日

- 候補: `lower_center_quantile`
- 判定: 既定維持
- 既定holdout RMSE: 0.1814
- 候補holdout RMSE: 0.1867
- 既定方向一致率: 0.6909
- 候補方向一致率: 0.6727
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。
