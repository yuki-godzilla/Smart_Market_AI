# Forecast Model Adoption Decision

## Decision

- Adopt: `robust-linear-clip-v1`
- Keep runtime defaults: consensus weights and all adapter hyperparameters
- Shadow only: `regularized_gbdt` 20-day and `lower_center_quantile` 20-day
- Reject for now: all 60-day parameter candidates and both consensus-weight candidates

## Evidence

23 symbols and 28,529 daily bars were evaluated with five future-safe rolling origins per horizon.

- Linear RMSE improved from 0.4131 to 0.1066 at 20 days (-74.2%).
- Linear RMSE improved from 1.6000 to 0.1675 at 60 days (-89.5%).
- Consensus RMSE improved from 0.1181 to 0.0898 at 20 days (-24.0%).
- Consensus RMSE improved from 0.3099 to 0.1598 at 60 days (-48.4%).
- Consensus direction accuracy did not decline.

The clipping rule limits only unstable linear extrapolation using the training target distribution. It does not add a new model or use future prices.

The 20-day consensus-weight candidate improved holdout RMSE by only about 0.5%, below the 1% minimum gate. The 60-day candidate was worse. Runtime weights therefore remain unchanged.

The GBDT and quantile 20-day candidates passed the aggregate 1% gate, but they have not yet demonstrated stability within every market, asset type, and regime subgroup. They remain shadow candidates rather than runtime defaults.

## Safety boundary

This evaluation supports model maintenance only. It is not evidence of guaranteed returns or a buy/sell recommendation. Ranking, Investment Score, and broker behavior are unchanged except for safer advanced-linear extrapolation.
