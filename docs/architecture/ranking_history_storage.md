# ランキング履歴 データ保存設計

## 1. 推奨保存先

既存のプロフィール別 favorites / watchlist snapshot と同じ境界を使う。

```text
data/user/profiles/<user_id>/
  favorites.json
  watchlist_snapshots.json
  ranking_history/
    index.json
    snapshots/
      rh_<UTC timestamp>_<random>.json.gz
```

`profile_data_path("ranking_history/index.json")` のような相対パス解決を許すか、`ranking_history_root(user_id)` を `ui/user_data.py` へ追加する。パスは run_id や payload 内の `snapshot_path` を信用して連結せず、検証済み run_id からサービスが決定する。

default ユーザーは `profile_data_path()` が `None` を返す既存仕様に合わせ、永続保存しない。`data/user/favorites.json` の legacy fallback は新機能に持ち込まない。

## 2. 責務

保存ロジックは Streamlit から分離し、候補として `backend/ranking_history/` に置く。

- `models.py`: versioned Pydantic v2 contract
- `repository.py`: user-scoped path、atomic read/write、index/snapshot整合
- `service.py`: save、dedupe、pin、delete、prune、list/get
- `ui/ranking_history.py`: 表示と session-state 遷移

## 3. index schema

```json
{
  "schema_version": 1,
  "updated_at": "2026-07-03T00:04:12+09:00",
  "items": [
    {
      "run_id": "rh_20260702T150412Z_a1b2c3d4",
      "user_id": "u_xxxxxxxxxxxx",
      "created_at": "2026-07-03T00:04:12+09:00",
      "data_as_of": "2026-07-02",
      "ranking_type": "multi_factor",
      "target": {"region": "all", "product_type": "stock", "market": "us"},
      "target_label": "米国株",
      "condition_summary": "AI総合 / 米国 / 金融ほか",
      "candidate_count": 14,
      "saved_row_count": 14,
      "top_symbols": ["JPM", "KO", "NEE"],
      "is_pinned": true,
      "title": null,
      "memo": null,
      "snapshot_file": "rh_20260702T150412Z_a1b2c3d4.json.gz",
      "signature": "sha256:...",
      "snapshot_status": "available"
    }
  ]
}
```

`snapshot_file` は basename のみ許可する。一覧ロード時は index だけを読み、詳細選択時に snapshot を読む。

## 4. snapshot schema

```json
{
  "schema_version": 1,
  "run_id": "rh_...",
  "user_id": "u_...",
  "created_at": "2026-07-03T00:04:12+09:00",
  "data_as_of": "2026-07-02",
  "provider": "yahoo",
  "period": {"start": "2025-07-02", "end": "2026-07-02"},
  "ranking_type": "multi_factor",
  "weight_preset": "multi_factor",
  "filters": {},
  "condition_summary": "...",
  "candidate_count": 14,
  "saved_row_count": 14,
  "top_symbols": ["JPM", "KO", "NEE"],
  "result_rows": [],
  "is_pinned": false,
  "title": null,
  "memo": null,
  "ranking_logic_version": "ranking.v1",
  "universe_version": "optional-cache-version",
  "signature": "sha256:..."
}
```

## 5. result_rows

現行 `RANKING_TABLE_BASE_COLUMNS`、`RANKING_TABLE_DETAIL_COLUMNS`、`RANKING_TABLE_HIDDEN_COLUMNS` と、再表示・CSVに必要な安定キーを保存する。

- 識別: `rank`, `symbol`, `name`, `market`, `country`, `asset_type`, `currency`
- 価格: `price`, `price_jpy`, `price_as_of`
- score: `total_score`, `screening_score`, `risk_score`, `data_quality_score`, `condition_fit_score`
- forecast: `upside_signal_score`, `downside_signal_score`, `forecast_change_pct`, `forecast_confidence`, `forecast_days`, `model_direction`
- fundamentals: `dividend_yield_pct`, `per`, `pbr`, `roe_pct`, `market_cap`, `volume`, `volatility`, `equity_ratio`, `operating_margin`, `revenue_growth_pct`, `expense_ratio`
- product metadata: `nisa_eligibility`, `investment_style`, `benchmark_index`, `complexity`
- explanation: `ranking_reason`, `confirmation_point`, `smai_memo`, `warning`
- research reference: 表示済みの短い status/score/count/freshness のみ。本文・raw provider response は保存しない
- audit: `favorite_status_at_save`（現在のお気に入りとは別物）
- `display`: 保存時の日本語表示値を持つ任意 map

JSON の内部キーは英語 snake_case に固定し、UIラベル変更から保存契約を分離する。数値は可能な限り number/null、日時は timezone 付き ISO 8601 とする。

## 6. 保存形式比較

| 形式 | 長所 | 短所 | 判断 |
| --- | --- | --- | --- |
| JSON | 調査・復旧が容易 | 行数増加で容量増 | index に採用 |
| JSON.GZ | JSON契約を維持し容量削減 | 手動閲覧に展開が必要 | snapshot に採用 |
| CSV | 表結果には簡単 | nested filters/version/null型に弱い | export のみ |
| SQLite | transaction/検索に強い | 既存profile file構造より重い | 件数・並行性増加時の移行先 |

## 7. atomicity と整合

既存 favorites / snapshots は direct write であり、ランキング履歴の複数ファイル更新には不十分。`ui/last_session.py`、`backend/news/cache.py` の temp + `os.replace` パターンを再利用する。

保存順:

1. contract 検証と signature 算出
2. snapshot を一時ファイルへ gzip 書込、flush、同一ディレクトリへ atomic replace
3. index に item を追加して一時ファイルへ書込、atomic replace
4. 30件 prune 後の不要 snapshot を削除（index commit 後の best effort）

削除順は index から除外して atomic commit 後、snapshot を best effort で削除する。孤立 snapshot は起動時に自動削除せず、将来の明示 cleanup で grace period 後に処理する。

同一プロフィールを複数ブラウザから更新する競合は既存課題でもある。MVPでは user directory 内 lock file の排他、短い timeout、index 再読込後の更新を必須とする。

## 8. 重複防止

signature は次の canonical JSON の SHA-256 とする。

```text
schema_version
user_id
normalized filters
ranking_type / weight_preset
provider / data_as_of / period
ordered [(symbol, rank, stable score fields)]
candidate_count / saved_row_count
```

`created_at` は signature に含めない。同一ユーザー・同一 signature かつ直近保存から5分未満なら既存 run_id を返し、保存しない。5分以上経過、または data/result が変われば新規保存する。UI の rerun token だけには依存しない。

## 9. prune

```text
pinned = all items where is_pinned
normal = non-pinned sorted created_at descending
keep = pinned + normal[:30]
remove = normal[30:]
```

ピン解除により通常履歴が31件以上になる場合は、同じ transaction で最古通常履歴を prune する。pin数にはMVP上限を設けないが、一覧に容量警告を出せるよう総 bytes を算出可能にする。

## 10. 読込障害と migration

- index 不在: 空一覧
- index 不正/oversize: UIを落とさず repository error。破損ファイルは自動上書きしない
- snapshot 不在/不正: item に unavailable を付け、他履歴は表示
- unknown schema: 読取専用エラー。黙って変換しない
- 将来 migration: `v1 -> v2` の純粋関数、backup、dry-run、atomic replace。古い snapshot は遅延 migration を選択可能にする
