# 04-10 通知基盤 Onepager

## 1. 目的

Smart Market AI 本体へ通知処理を密結合させず、アプリ内通知と外部通知を独立して育てられる通知基盤を設ける。
初期 MVP はアプリ内通知履歴と ntfy によるスマートフォン Push 通知を対象とし、Discord、Telegram、Email などは後続 adapter とする。

通知は投資判断や売買推奨を行わず、SMAI 内で発生した事実や処理結果をユーザーへ届ける補助機能に限定する。

## 2. 境界と基本フロー

```text
SMAI 本体でイベント発生
  -> NotificationEvent を作成
  -> SMAI のアプリ内通知履歴へ保存
  -> ユーザー設定、severity threshold、quiet hours を判定
  -> 必要な場合だけ smai-notification-gateway から ntfy へ送信
  -> DeliveryResult を記録
```

必須ルール:

- ntfy 送信の成否より先に、アプリ内通知履歴を保存する。
- ntfy の timeout、通信失敗、不正応答で SMAI 本体処理を失敗させない。
- 通知 gateway は投資判断、スコア計算、画面描画、お気に入り管理を行わない。
- Streamlit の描画コードへ HTTP 送信や retry loop を直書きしない。
- 通常テストと CI は fake transport / fixture を使い、network-free に保つ。
- 外部送信はユーザーが ntfy を有効化し、必要な設定を完了した場合だけ行う。
- 初期段階では過剰な自動通知を避け、対象イベントを限定する。

## 3. モジュール構成

```text
Smart_Market_AI/
  smai-notification-gateway/
    README.md
    pyproject.toml
    src/notification_gateway/
      models.py
      settings.py
      dispatcher.py
      api.py
      channels/
        base.py
        ntfy.py
      storage/
        sqlite_store.py
      rules/
        evaluator.py
    tests/
  backend/notifications/
    client.py
    service.py
    repository.py
    contracts.py
  ui/
    notification_ui.py
```

実装時は既存構成に合わせて配置を調整してよい。ただし、親 SMAI と子 gateway の境界は request / response contract または明示的な client interface とし、UI から channel 実装を直接呼ばない。

初期 MVP は Python import でもよいが、dispatcher と channel を分離し、将来の HTTP API 化を妨げない構造にする。

## 4. データ契約

### NotificationEvent

- `event_id: str`
- `user_id: str`
- `event_type: str`
- `category: MARKET | RESEARCH | NEWS | SYSTEM | MY_RADAR | AI_SCORE | PRICE_ALERT | DATA_REFRESH | LLM`
- `severity: critical | high | medium | low | silent`
- `title: str`
- `message: str`
- `symbol: str | None`
- `source: str | None`
- `action_url: str | None`
- `metadata: dict[str, Any]`
- `created_at: datetime`

### DeliveryResult

- `event_id: str`
- `channel: str`
- `success: bool`
- `status_code: int | None`
- `error_message: str | None`
- `delivered_at: datetime | None`

### UserNotificationSetting

- `user_id: str`
- `app_enabled: bool = true`
- `ntfy_enabled: bool = false`
- `ntfy_server_url: str = "https://ntfy.sh"`
- `ntfy_topic: str | None`
- `severity_threshold: str = "medium"`
- `quiet_hours_enabled: bool = false`
- `quiet_hours_start: str | None`
- `quiet_hours_end: str | None`

### AppNotification

通知履歴は最低限、`event_id`、`user_id`、イベント本文、`status`、`created_at`、`read_at`、`archived_at` を保持する。
状態は `unread | read | archived` とする。外部配信結果は履歴本体から分離し、1イベントに複数 channel の結果を追加できる形にする。

## 5. ntfy channel

送信先は `{server_url}/{topic}` とし、UTF-8 の本文を HTTP POST する。timeout の初期値は 10 秒とする。

severity と ntfy priority の対応:

| severity | ntfy priority |
| --- | --- |
| `critical` | `urgent` |
| `high` | `high` |
| `medium` | `default` |
| `low` | `low` |
| `silent` | `min`。ただし外部送信しない |

安全要件:

- `topic` は実質的な秘密情報として扱い、ログ、例外、画面へ不用意に出さない。
- topic には推測困難なランダム文字列を推奨する。
- 設定画面では topic を常時平文表示せず、将来の自動生成に対応できる UI contract とする。
- server URL は `https://ntfy.sh` を初期値とし、将来のセルフホスト URL を許容する。
- ntfy 無効、topic 未設定、`silent`、severity threshold 未満、quiet hours 中は外部送信しない。
- retry は bounded とし、失敗理由を安全に短縮して `DeliveryResult` と運用ログへ残す。

## 6. 初期イベント

MVP で event producer を接続する場合も、次の候補へ限定し、一括自動接続はしない。

- `SYSTEM`: テスト通知、DB 更新完了、データ取得失敗
- `RESEARCH`: AI 調査完了
- `MY_RADAR`: My Radar 銘柄の情報取得完了
- `AI_SCORE`: AI 総合スコアがユーザー指定閾値を超えた

AI_SCORE 通知はスコア計算ロジックを gateway に持たせない。SMAI 本体が確定したイベントだけを渡す。

## 7. UI 方針

設定画面:

- ntfy 通知 ON / OFF
- ntfy server URL
- ntfy topic
- severity threshold
- quiet hours
- 明示操作によるテスト通知

通知センター:

- 今日などの日付グループ
- 未読のみ、重要のみ、お気に入り関連のみ、カテゴリの簡易 filter
- 未読 / 既読 / archive 操作
- 外部配信失敗があってもアプリ内通知を表示

テスト通知はユーザー操作時だけ送信する。Streamlit の通常 rerun、初期表示、設定項目変更だけでは送信しない。

## 8. 将来 HTTP API

候補 endpoint:

- `GET /health`
- `POST /api/v1/notify`
- `POST /api/v1/test`

`POST /api/v1/notify` は `NotificationEvent` 相当を受け、`event_id` と `DeliveryResult` の一覧を返す。認証、rate limit、idempotency は HTTP 化を実運用する前に別途設計する。

## 9. 段階導入

### Phase N1: 独立 gateway

- `smai-notification-gateway` scaffold
- contracts、NtfyChannel、Dispatcher
- rule evaluator と SQLite delivery store の境界
- network-free 単体テスト

### Phase N2: SMAI 連携口

- 親側 notification client / service
- テスト通知関数
- gateway 失敗を本体へ伝播させない contract

### Phase N3: 通知設定

- ntfy ON / OFF、server URL、topic、severity threshold、quiet hours
- topic の秘匿表示
- 明示的なテスト通知操作

### Phase N4: アプリ内通知

- SQLite 通知履歴
- unread / read / archived
- 通知センターと簡易 filter
- delivery result の確認導線

## 10. 受け入れ条件

- アプリ内通知が外部送信より先に保存される。
- 正常な event と severity / priority 変換を検証できる。
- ntfy 成功時は `DeliveryResult.success=true` になる。
- ntfy 失敗時も例外で SMAI を止めず、`success=false` を返す。
- ntfy 無効、`silent`、quiet hours、threshold 未満では送信しない。
- topic や秘密情報をログへ出さない。
- 既存 Streamlit 画面と既存テストを壊さない。
- README / 運用ガイドに安全な ntfy 設定と network-free テスト手順がある。

