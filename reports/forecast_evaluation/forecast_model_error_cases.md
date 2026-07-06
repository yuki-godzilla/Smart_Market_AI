# Forecast Model Error Cases

誤差が大きいrolling-origin例です。売買判断ではなくモデル改善用です。

| Symbol | Model | Horizon | Origin | Predicted | Actual | Absolute error |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| 8035.T | advanced_gbdt_sklearn | 60 | 2026-04-07 | 0.0321 | 0.8814 | 0.8493 |
| 8035.T | advanced_quantile | 60 | 2026-04-07 | 0.0491 | 0.8814 | 0.8323 |
| 8035.T | forecast_consensus | 60 | 2026-04-07 | 0.0535 | 0.8814 | 0.8279 |
| 8035.T | advanced_tree_sklearn | 60 | 2026-04-07 | 0.0654 | 0.8814 | 0.8160 |
| 8035.T | advanced_linear | 60 | 2026-04-07 | 0.0668 | 0.8814 | 0.8146 |
| NVDA | advanced_tree_sklearn | 60 | 2022-12-08 | -0.2598 | 0.4084 | 0.6682 |
| NVDA | advanced_gbdt_sklearn | 60 | 2022-12-08 | -0.2590 | 0.4084 | 0.6674 |
| 9984.T | advanced_quantile | 60 | 2026-04-07 | 0.0119 | 0.6771 | 0.6652 |
| NVDA | forecast_consensus | 60 | 2022-12-08 | -0.1964 | 0.4084 | 0.6048 |
| 9984.T | advanced_tree_sklearn | 60 | 2026-04-07 | 0.1148 | 0.6771 | 0.5623 |
| NVDA | advanced_linear | 60 | 2022-12-08 | -0.1469 | 0.4084 | 0.5553 |
| 9984.T | forecast_consensus | 60 | 2026-04-07 | 0.1360 | 0.6771 | 0.5411 |
| NVDA | advanced_quantile | 60 | 2022-12-08 | -0.1213 | 0.4084 | 0.5297 |
| 9984.T | advanced_linear | 60 | 2026-04-07 | 0.1955 | 0.6771 | 0.4816 |
| 9984.T | advanced_gbdt_sklearn | 60 | 2026-04-07 | 0.2129 | 0.6771 | 0.4642 |
| NVDA | advanced_linear | 20 | 2022-11-09 | -0.1812 | 0.2463 | 0.4275 |
| NVDA | advanced_quantile | 60 | 2024-01-18 | 0.1033 | 0.5060 | 0.4027 |
| NVDA | advanced_gbdt_sklearn | 20 | 2022-11-09 | -0.1497 | 0.2463 | 0.3960 |
| 8035.T | advanced_linear | 60 | 2021-11-09 | 0.3569 | -0.0336 | 0.3905 |
| NVDA | advanced_gbdt_sklearn | 60 | 2021-11-02 | 0.2437 | -0.1349 | 0.3786 |
