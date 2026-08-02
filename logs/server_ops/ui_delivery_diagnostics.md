# UI delivery diagnostics

This is a deterministic source/static-asset baseline. Runtime render time, rerun count, and session-state size are measured from the in-app external connection diagnostics.

- Optimized static assets: 29
- Optimized static asset bytes: 409,678

| Screen | Source bytes | base64 refs | data URI links | dataframe/editor | session_state refs | expanders |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 初期ユーザー選択 | 47,460 | 0 | 0 | 0 | 38 | 2 |
| ランキング | 1,016,977 | 0 | 0 | 9 | 177 | 25 |
| 銘柄コックピット | 961,656 | 0 | 0 | 9 | 177 | 31 |
| Watchlist | 910,482 | 0 | 0 | 9 | 177 | 25 |
| 投資レーダー | 151,098 | 0 | 0 | 0 | 36 | 7 |
| SMAIアシスタント | 217,423 | 0 | 0 | 0 | 83 | 2 |

## Interpretation

- Generated-file data URI links in the target UI source should remain zero.
- Static image URLs keep image bytes out of rerun HTML and allow browser caching.
- Source counts locate review hotspots; they are not network-byte measurements.
- Use the settings-page diagnostic snapshot for actual session key/byte estimates.
