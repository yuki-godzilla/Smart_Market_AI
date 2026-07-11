# UI delivery diagnostics

This is a deterministic source/static-asset baseline. Runtime render time, rerun count, and session-state size are measured from the in-app external connection diagnostics.

- Optimized static assets: 29
- Optimized static asset bytes: 409,678

| Screen | Source bytes | base64 refs | data URI links | dataframe/editor | session_state refs | expanders |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 初期ユーザー選択 | 46,439 | 0 | 0 | 0 | 38 | 2 |
| ランキング | 1,023,675 | 0 | 0 | 9 | 180 | 35 |
| 銘柄コックピット | 956,116 | 0 | 0 | 9 | 180 | 35 |
| Watchlist | 917,501 | 0 | 0 | 9 | 180 | 35 |
| 投資レーダー | 76,847 | 0 | 0 | 0 | 5 | 1 |
| SMAIアシスタント | 227,748 | 0 | 0 | 0 | 82 | 2 |

## Interpretation

- Generated-file data URI links in the target UI source should remain zero.
- Static image URLs keep image bytes out of rerun HTML and allow browser caching.
- Source counts locate review hotspots; they are not network-byte measurements.
- Use the settings-page diagnostic snapshot for actual session key/byte estimates.
