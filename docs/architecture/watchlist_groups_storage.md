# ウォッチリストグループ データ保存設計

## 1. 保存境界

カスタムユーザー:

```text
data/user/profiles/<user_id>/watchlist_groups.json
```

defaultユーザー:

```text
Streamlit session_state["smai_default_user_watchlist_groups"]
```

`ui.user_data.profile_data_path()`、`is_default_session_user()`、
`session_payload()`、`set_session_payload()`を既存favoritesと同じ規則で利用する。
legacy共有pathへのfallbackは新機能には設けない。

## 2. favoritesとの関係

`watchlist_groups.json`は`favorites.json`を複製しない。
placementにname、市場、スコア、favorite状態を保存せず、normalized symbolだけをkeyにする。

```text
visible = current favorite symbols
grouped = visible symbols whose placement points to an existing user group
unclassified = visible - grouped
```

お気に入りにないplacementは保存されていても表示しない。

## 3. schema v1

```json
{
  "schema_version": 1,
  "updated_at": "2026-07-03T07:00:00+09:00",
  "groups": [
    {
      "group_id": "wg_7f2c91a4d3b8",
      "name": "日本個別株",
      "description": null,
      "order": 10,
      "tone": "cyan",
      "is_system": false,
      "created_at": "2026-07-03T07:00:00+09:00",
      "updated_at": "2026-07-03T07:00:00+09:00"
    }
  ],
  "placements": {
    "7974.T": {
      "group_id": "wg_7f2c91a4d3b8",
      "order": 10,
      "updated_at": "2026-07-03T07:00:00+09:00"
    }
  }
}
```

## 4. groups

| field | type | v1制約 |
| --- | --- | --- |
| `group_id` | string | `^wg_[a-f0-9]{12,32}$`、一意、変更不可 |
| `name` | string | trim後1〜32文字、制御文字なし、同一ユーザー内で一意 |
| `description` | string/null | 任意、最大200文字、制御文字なし |
| `order` | integer | 10刻みの正整数、同値時はcreated_at/group_idで安定化 |
| `tone` | string | 8種のpreset allowlist |
| `is_system` | boolean | v1保存groupは必ずfalse |
| `created_at` | ISO 8601 string | timezone付き |
| `updated_at` | ISO 8601 string | timezone付き |

最大20group。未分類はgroupsへ保存しない。

## 5. placements

| field | type | v1制約 |
| --- | --- | --- |
| key | normalized symbol | trim＋uppercase、空文字不可、長さ上限を設ける |
| `group_id` | string | 保存時に既存groupを参照 |
| `order` | integer | 将来の手動順予約。v1表示順の主値にはしない |
| `updated_at` | ISO 8601 string | timezone付き |

dict keyにより1 symbol = 1 groupを構造的に保証する。
同一group内のv1表示順は現行Myウォッチリストの選択sortを使う。

## 6. ID生成

`group_id = "wg_" + secrets.token_hex(6)`を基本とし、衝突時は再生成する。
ユーザー入力、時刻、pathをIDへ含めない。IDはpath要素として使用しない。

## 7. symbol正規化

v1は既存`normalize_favorite_symbol()`と同じ`strip().upper()`を唯一の境界とする。

- `7974.T`と`7974.t`は同一。
- `7974`と`7974.T`は別symbol。suffixを推測補完しない。
- `Nintendo`を`7974.T`へ名称解決しない。
- 米国株、ETF、ADRの`.`や`-`を変換しない。

将来resolverを導入する場合はfavoritesとplacementsを同じmigrationで扱う。

## 8. 未分類

未分類用group IDを永続化しない。次の場合に計算上の未分類とする。

- placementなし
- placementの`group_id`が削除済みまたは不正
- group recordのvalidation失敗

未分類への移動はplacement削除で表す。

## 9. 更新規則

### お気に入り追加

placementを自動作成せず未分類とする。過去placementが残る再登録の場合だけ以前のgroupへ復帰する。

### お気に入り解除

placementを残す。UIからは即時非表示とする。自動cleanupは行わない。

### group削除

1回のrepository更新でgroupと参照placementを同時に削除する。
結果として対象銘柄は未分類になる。favorites/snapshotsには書き込まない。

### group改名・並べ替え

groupsだけを更新し、placementsは書き換えない。

## 10. atomic write

現行favoritesの`Path.write_text()`を新機能へコピーせず、
`RankingHistoryRepository._atomic_write()`と同型の実装をrepository helperへ置く。

1. 同一directoryにランダム名のtemporary fileを作る。
2. UTF-8、LF、末尾改行でJSONを書く。
3. `flush()`と`os.fsync()`を行う。
4. `os.replace(temporary, target)`で置換する。
5. `finally`でtemporaryを削除する。

Windows onedirでもtargetと同一volumeになるよう、temporaryは同一directoryに置く。
MVPはprocess内lockまたはranking historyと同型の短時間lockを検討し、
少なくともread-modify-write全体をrepository method内に閉じる。

## 11. 破損時fallback

- JSON parse、schema、version validation失敗は「空group＋空placement」へfallbackする。
- お気に入りは全件未分類として表示し、favoritesを変更しない。
- 破損ファイルを通常保存で即上書きせず、UIに復旧操作を示す。
- 復旧時は破損fileをtimestamp付き`.corrupt`へ退避してから新規schemaを保存する。
- pathや生JSONをユーザー向けmessageに出さず、詳細はsanitized logへ送る。

単なる未知group参照はfile全体破損とせず、そのsymbolだけ未分類にする。

## 12. validation

- schema version
- group数、ID形式・一意性、名前、重複名、order、timestamp
- placement symbol、group ID、order、timestamp
- `is_system=false`
- payload size上限

保存前とload後の両方で検証する。厳密なPydantic v2 modelを
domain/repository境界に置く。

## 13. migration

- `schema_version`必須。versionなしをv1と推測しない。
- migrationは純粋関数として旧payloadから新payloadを生成し、atomic保存する。
- migration前fileを上書き前にbackupする。
- favoritesへのfield追加で本機能をmigrationしない。
- 将来`placement.order`を有効化し、既存値がない場合は現行sortから安定値を生成する。

## 14. defaultユーザー

defaultはfile pathを解決せず、session payloadに同じschemaを保持する。
ブラウザsession終了で失われることを現行captionで明示する。
defaultからcustomへの自動copyは意図しないデータ混入を避けるため行わない。
