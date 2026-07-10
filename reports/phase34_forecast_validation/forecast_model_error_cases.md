# Forecast Model Error Cases

誤差が大きいrolling-origin例です。売買判断ではなくモデル改善用です。

| Symbol | Model | Horizon | Origin | Predicted | Actual | Absolute error |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| PLTR | advanced_tree_sklearn | 60 | 2021-01-29 | 1.8761 | -0.3212 | 2.1973 |
| PLTR | advanced_quantile | 60 | 2021-01-29 | 1.7293 | -0.3212 | 2.0505 |
| PLTR | advanced_gbdt_sklearn | 60 | 2021-01-29 | 1.4853 | -0.3212 | 1.8065 |
| PLTR | forecast_consensus | 60 | 2021-01-29 | 1.4602 | -0.3212 | 1.7814 |
| MU | advanced_linear | 60 | 2026-04-13 | 0.0221 | 1.3247 | 1.3026 |
| MU | advanced_tree_sklearn | 60 | 2026-04-13 | 0.0570 | 1.3247 | 1.2677 |
| MU | forecast_consensus | 60 | 2026-04-13 | 0.0642 | 1.3247 | 1.2605 |
| MU | advanced_quantile | 60 | 2026-04-13 | 0.0837 | 1.3247 | 1.2410 |
| MU | advanced_gbdt_sklearn | 60 | 2026-04-13 | 0.0855 | 1.3247 | 1.2392 |
| PLTR | advanced_linear | 60 | 2021-01-29 | 0.7500 | -0.3212 | 1.0712 |
| PLTR | advanced_gbdt_sklearn | 20 | 2022-04-18 | 0.6352 | -0.3383 | 0.9735 |
| PLTR | advanced_tree_sklearn | 20 | 2020-12-01 | 0.7726 | -0.0222 | 0.7948 |
| PLTR | advanced_linear | 20 | 2020-12-01 | 0.7500 | -0.0222 | 0.7722 |
| PLTR | advanced_linear | 60 | 2022-05-16 | -0.5614 | 0.1716 | 0.7330 |
| INTC | advanced_quantile | 60 | 2026-04-13 | 0.0016 | 0.7266 | 0.7250 |
| 6098.T | advanced_gbdt_sklearn | 60 | 2026-04-13 | 0.0360 | 0.7496 | 0.7136 |
| 6098.T | advanced_tree_sklearn | 60 | 2026-04-13 | 0.0498 | 0.7496 | 0.6998 |
| 6098.T | advanced_linear | 60 | 2026-04-13 | 0.0503 | 0.7496 | 0.6993 |
| 6098.T | forecast_consensus | 60 | 2026-04-13 | 0.0536 | 0.7496 | 0.6960 |
| INTC | advanced_linear | 60 | 2026-04-13 | 0.0345 | 0.7266 | 0.6921 |
