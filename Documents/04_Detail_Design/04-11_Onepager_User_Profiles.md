# 04-11 Local User Profiles

## 目的

LAN内で複数人が利用しても、お気に入り、判断メモ、Decision Trail、更新状態、
Watchlist Snapshot、通知設定・履歴が別ユーザーへ混ざらないようにする。
プロフィール選択はローカルデータの表示境界であり、認証やアクセス制御ではない。

## ユーザー

- カスタムユーザーは `u_<random id>` を内部IDとし、表示名変更の影響を受けない。
- 表示名はtrim後1〜32文字、制御文字を禁止する。
- `default / SMAIデフォルト` は編集・削除不可のsystem userとする。
- アイコンは有効なlocal manifest assetから選択し、DBにはasset IDだけを保存する。

## データ境界

カスタムユーザーは次へ保存する。

```text
data/user/profiles/<user_id>/favorites.json
data/user/profiles/<user_id>/watchlist_snapshots.json
```

favoritesには銘柄、memo、tags、Watch理由、判断状態、判断メモ、次回確認日、
Decision Trail、確認・調査日時、refresh状態を含む。画面は固定パスではなく、
現在ユーザーを解決するStore境界を通す。

defaultは同じモデルをStreamlit session stateだけに保存する。通常rerunでは保持し、
新しいStreamlit sessionでは空に戻す。default用ファイルは作成しない。

## 通知

defaultではベル、未読件数、通知センター、通知設定、テスト通知を表示しない。
設定保存、履歴作成、Producer、Scheduler、ntfy送信もサービス境界で拒否する。
通常ユーザーは既存のuser_id別SQLite設定・履歴を利用し、ntfyは明示設定までOFFとする。

## 移行

旧 `data/user/favorites.json` と `watchlist_snapshots.json` は、移行先が未作成の場合だけ
既存通常ユーザー（優先 `local_user`）へcopyする。元ファイルは削除せず、
`data/user/migrations/user_profile_favorites_v1.done` を一度限りのmarkerとする。
破損JSONやcopy失敗でアプリを停止しない。

## N6接続条件

通知の実favorite/news/market Producerは、system userを除外し、必ず対象user_idのStoreを
入力にする。共有favoritesを通知元にしてはならない。

## U1-Verify結果

- user profile / favorite / snapshot / notification対象test 71件をnetwork-freeで確認した。
- defaultのNotificationService、test send、history、Producer、gateway拒否をtestで固定した。
- snapshot pruneが現在ユーザーの保存先だけを変更することをtestで固定した。
- Desktop 1366x768とSmartphone 375x812でユーザー作成、作成直後開始、default通知UI非表示、
  add-user cancel、ページ横overflowなし、Streamlit例外なしをPlaywright smokeで確認した。
- 同一ユーザーを複数browser sessionから同時更新する場合、JSONはlast-write-winsである。
  SQLite化またはfile lockは将来の競合対策候補とし、N6開始条件には含めない。
