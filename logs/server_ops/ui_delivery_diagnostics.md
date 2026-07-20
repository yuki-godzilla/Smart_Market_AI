# UI delivery diagnostics

This is a deterministic source/static-asset baseline. Runtime render time, rerun count, and session-state size are measured from the in-app external connection diagnostics.

- Optimized static assets: 29
- Optimized static asset bytes: 409,678

| Screen | Source bytes | base64 refs | data URI links | dataframe/editor | session_state refs | expanders |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 初期ユーザー選択 | 47,460 | 0 | 0 | 0 | 38 | 2 |
| ランキング | 1,036,781 | 0 | 0 | 9 | 189 | 36 |
| 銘柄コックピット | 969,014 | 0 | 0 | 9 | 189 | 36 |
| Watchlist | 930,515 | 0 | 0 | 9 | 189 | 36 |
| 投資レーダー | 151,098 | 0 | 0 | 0 | 36 | 7 |
| SMAIアシスタント | 218,598 | 0 | 0 | 0 | 83 | 2 |

## Interpretation

- Generated-file data URI links in the target UI source should remain zero.
- Static image URLs keep image bytes out of rerun HTML and allow browser caching.
- Source counts locate review hotspots; they are not network-byte measurements.
- Use the settings-page diagnostic snapshot for actual session key/byte estimates.
