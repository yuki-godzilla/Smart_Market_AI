# Forecast Model Tuning Summary

既存4モデルのbounded candidateを時系列holdoutで比較します。
採用条件未達の候補は通常予測へ反映しません。

## advanced_linear / 20営業日

- 候補: `ridge_alpha_4`
- 判定: 既定維持
- 既定holdout RMSE: 0.0000
- 候補holdout RMSE: 0.0000
- 既定方向一致率: 0.0000
- 候補方向一致率: 0.0000
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_linear / 60営業日

- 候補: `ridge_alpha_4`
- 判定: 既定維持
- 既定holdout RMSE: 0.0000
- 候補holdout RMSE: 0.0000
- 既定方向一致率: 0.0000
- 候補方向一致率: 0.0000
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_tree_sklearn / 20営業日

- 候補: `conservative_tree`
- 判定: 既定維持
- 既定holdout RMSE: 0.0000
- 候補holdout RMSE: 0.0000
- 既定方向一致率: 0.0000
- 候補方向一致率: 0.0000
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_tree_sklearn / 60営業日

- 候補: `conservative_tree`
- 判定: 既定維持
- 既定holdout RMSE: 0.0000
- 候補holdout RMSE: 0.0000
- 既定方向一致率: 0.0000
- 候補方向一致率: 0.0000
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_gbdt_sklearn / 20営業日

- 候補: `regularized_gbdt`
- 判定: 既定維持
- 既定holdout RMSE: 0.0000
- 候補holdout RMSE: 0.0000
- 既定方向一致率: 0.0000
- 候補方向一致率: 0.0000
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_gbdt_sklearn / 60営業日

- 候補: `regularized_gbdt`
- 判定: 既定維持
- 既定holdout RMSE: 0.0000
- 候補holdout RMSE: 0.0000
- 既定方向一致率: 0.0000
- 候補方向一致率: 0.0000
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_quantile / 20営業日

- 候補: `lower_center_quantile`
- 判定: 既定維持
- 既定holdout RMSE: 0.0000
- 候補holdout RMSE: 0.0000
- 既定方向一致率: 0.0000
- 候補方向一致率: 0.0000
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。

## advanced_quantile / 60営業日

- 候補: `lower_center_quantile`
- 判定: 既定維持
- 既定holdout RMSE: 0.0000
- 候補holdout RMSE: 0.0000
- 既定方向一致率: 0.0000
- 候補方向一致率: 0.0000
- 理由: 時系列holdoutの採用条件を満たさないため既定設定を維持します。
