# UI delivery diagnostics

This is a deterministic source/static-asset baseline. Runtime render time, rerun count, and session-state size are measured from the in-app external connection diagnostics.

- Optimized static assets: 29
- Optimized static asset bytes: 409,678

| Screen | Source bytes | base64 refs | data URI links | dataframe/editor | session_state refs | expanders |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 初期ユーザー選択 | 47,494 | 0 | 0 | 0 | 38 | 2 |
| ランキング | 1,031,243 | 0 | 0 | 9 | 186 | 36 |
| 銘柄コックピット | 963,476 | 0 | 0 | 9 | 186 | 36 |
| Watchlist | 924,977 | 0 | 0 | 9 | 186 | 36 |
| 投資レーダー | 139,765 | 0 | 0 | 0 | 36 | 6 |
| SMAIアシスタント | 218,598 | 0 | 0 | 0 | 83 | 2 |

## Interpretation

- Generated-file data URI links in the target UI source should remain zero.
- Static image URLs keep image bytes out of rerun HTML and allow browser caching.
- Source counts locate review hotspots; they are not network-byte measurements.
- Use the settings-page diagnostic snapshot for actual session key/byte estimates.
