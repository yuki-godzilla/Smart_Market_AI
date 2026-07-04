# UI delivery diagnostics

This is a deterministic source/static-asset baseline. Runtime render time, rerun count, and session-state size are measured from the in-app external connection diagnostics.

- Optimized static assets: 29
- Optimized static asset bytes: 409,678

| Screen | Source bytes | base64 refs | data URI links | dataframe/editor | session_state refs | expanders |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 初期ユーザー選択 | 46,394 | 0 | 0 | 0 | 38 | 2 |
| ランキング | 975,358 | 0 | 0 | 6 | 168 | 34 |
| 銘柄コックピット | 911,509 | 0 | 0 | 6 | 168 | 34 |
| Watchlist | 874,550 | 0 | 0 | 6 | 168 | 34 |
| 投資レーダー | 73,944 | 0 | 0 | 0 | 4 | 1 |
| SMAIアシスタント | 227,748 | 0 | 0 | 0 | 82 | 2 |

## Interpretation

- Generated-file data URI links in the target UI source should remain zero.
- Static image URLs keep image bytes out of rerun HTML and allow browser caching.
- Source counts locate review hotspots; they are not network-byte measurements.
- Use the settings-page diagnostic snapshot for actual session key/byte estimates.
