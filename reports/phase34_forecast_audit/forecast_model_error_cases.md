# Forecast Model Error Cases

誤差が大きいrolling-origin例です。売買判断ではなくモデル改善用です。

| Symbol | Model | Horizon | Origin | Predicted | Actual | Absolute error |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| 6723.T | advanced_quantile | 60 | 2026-04-13 | 0.0428 | 0.8815 | 0.8387 |
| 6723.T | forecast_consensus | 60 | 2026-04-13 | 0.0628 | 0.8815 | 0.8187 |
| 6723.T | advanced_tree_sklearn | 60 | 2026-04-13 | 0.0629 | 0.8815 | 0.8186 |
| 6723.T | advanced_gbdt_sklearn | 60 | 2026-04-13 | 0.0749 | 0.8815 | 0.8066 |
| 6723.T | advanced_linear | 60 | 2026-04-13 | 0.0753 | 0.8815 | 0.8062 |
| 6723.T | advanced_linear | 60 | 2016-11-14 | -0.3910 | 0.3465 | 0.7375 |
| NFLX | advanced_linear | 60 | 2016-11-07 | -0.5794 | 0.1258 | 0.7052 |
| UBER | advanced_gbdt_sklearn | 60 | 2021-04-30 | 0.4645 | -0.1634 | 0.6279 |
| 9101.T | advanced_quantile | 20 | 2021-07-14 | 0.0258 | 0.6042 | 0.5784 |
| 9101.T | forecast_consensus | 20 | 2021-07-14 | 0.1099 | 0.6042 | 0.4943 |
| META | advanced_gbdt_sklearn | 60 | 2023-11-29 | -0.0236 | 0.4661 | 0.4897 |
| 9101.T | advanced_tree_sklearn | 20 | 2021-07-14 | 0.1317 | 0.6042 | 0.4725 |
| 9101.T | advanced_linear | 20 | 2021-07-14 | 0.1361 | 0.6042 | 0.4681 |
| 9101.T | advanced_gbdt_sklearn | 20 | 2021-07-14 | 0.1403 | 0.6042 | 0.4639 |
| META | forecast_consensus | 60 | 2023-11-29 | 0.0285 | 0.4661 | 0.4376 |
| META | advanced_tree_sklearn | 60 | 2023-11-29 | 0.0334 | 0.4661 | 0.4327 |
| META | advanced_linear | 60 | 2023-11-29 | 0.0421 | 0.4661 | 0.4240 |
| 6723.T | advanced_linear | 60 | 2019-02-22 | 0.1098 | -0.3125 | 0.4223 |
| META | advanced_quantile | 60 | 2023-11-29 | 0.0518 | 0.4661 | 0.4143 |
| 9101.T | advanced_quantile | 60 | 2021-07-14 | 0.0384 | 0.4402 | 0.4018 |
