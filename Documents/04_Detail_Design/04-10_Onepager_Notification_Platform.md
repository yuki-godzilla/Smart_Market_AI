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

### NotificationContent

イベントの事実とチャネル別表示を分離するため、通知本文は共通コンテンツモデルから生成する。

- `presentation_category: FAVORITE | MARKET_TREND | INVESTMENT_NEWS | SMAI_INSIGHT | SYSTEM`
- `icon_key: str`
- `headline: str`
- `summary: str`
- `what_happened: str`
- `why_it_matters: str | None`
- `smai_assessment: str | None`
- `next_check: str | None`
- `metrics: list[NotificationMetric]`
- `cta: NotificationAction | None`
- `content_version: str`

`NotificationMetric` は `label`、`value`、任意の `previous_value`、`direction`、`as_of` を持つ。
`NotificationAction` はユーザー向けlabelとアプリ内の安全な遷移先を持つ。CTAは画面遷移または確認導線に限定し、AI調査、外部取得、レポート作成、売買、注文を自動実行しない。

既存の技術カテゴリはevent routingに使い、表示カテゴリは次のように対応させる。

| 表示カテゴリ | 主な技術カテゴリ |
| --- | --- |
| `FAVORITE` | `MY_RADAR`、`AI_SCORE`、銘柄単位の`MARKET` |
| `MARKET_TREND` | 市場・セクター・テーマ単位の`MARKET` |
| `INVESTMENT_NEWS` | `NEWS` |
| `SMAI_INSIGHT` | `AI_SCORE`、`MY_RADAR`、`RESEARCH` |
| `SYSTEM` | `SYSTEM`、`DATA_REFRESH`、`LLM` |

この分離により、実装済みevent enumを直ちに壊さず、通知センターの表示分類を追加できる。

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

実装状態: N1〜N3-B 実装済み。親側は `backend/notifications/notification_client.py` に独立した軽量 contract、`NotificationClient` protocol、`SafeNotificationClient`、明示呼び出し専用の `send_test_notification()` を持つ。`backend/notifications/gateway_adapter.py` は親request / 設定を子event / settingへ変換し、子delivery resultを親resultへ戻す。子packageのimport失敗、dispatcher例外、不正response、子failed messageは秘密値なしの短いfailed resultへ変換する。`settings_repository.py`はschema version付き`notifications.sqlite`を自動作成し、`settings_service.py`はtopic維持/明示削除、URL、severity、quiet hoursを検証する。`ui/notification_ui.py`は既存設定画面だけに通知設定を追加し、テストボタン押下時だけ送信する。既存イベント、起動処理、自動通知には未接続。

### Phase N3: 通知設定

- ntfy ON / OFF、server URL、topic、severity threshold、quiet hours
- topic の秘匿表示
- 明示的なテスト通知操作

### Phase N4: アプリ内通知

- SQLite 通知履歴
- unread / read / archived
- 通知センターと簡易 filter
- delivery result の確認導線

実装状態: Phase N4実装済み。schema v2へ`app_notifications`、`delivery_results`、`users`、`trusted_devices`を追加し、N3設定を保持したままmigrationする。`NotificationService`は履歴保存成功後だけ外部clientを呼び、テスト通知だけをProducerとして接続する。右上固定ユーザーエリアのpopoverから通知センター、ユーザー切替、マスコット選択、登録端末管理を開き、サイドメニューには通知画面を追加しない。

### Trusted Device

- ブラウザごとに`crypto.randomUUID()`でdevice IDを生成し、localStorageへ保存する。
- IPアドレスは識別に使わない。
- localStorage値は同一originのbridgeから`device_id` query parameterとしてStreamlitへ渡す。
- `trusted_devices`はdevice ID、user ID、端末名、作成/最終利用日時、trusted状態を保持する。
- trustedかつactiveなuserだけを自動選択する。未登録・解除済み・不正UUIDはユーザー選択へ戻す。
- ユーザー切替は`この端末の既定を変更`と`今回だけ`を分ける。
- 端末名変更、現在/他端末の解除、ユーザーごとのマスコット選択を提供する。
- 端末記憶は認証ではなく表示ユーザー選択の自動化である。password省略や高度操作の認可には現時点で使わない。

## 10. 受け入れ条件

- アプリ内通知が外部送信より先に保存される。
- 正常な event と severity / priority 変換を検証できる。
- ntfy 成功時は `DeliveryResult.success=true` になる。
- ntfy 失敗時も例外で SMAI を止めず、`success=false` を返す。
- ntfy 無効、`silent`、quiet hours、threshold 未満では送信しない。
- topic や秘密情報をログへ出さない。
- 既存 Streamlit 画面と既存テストを壊さない。
- README / 運用ガイドに安全な ntfy 設定と network-free テスト手順がある。

## 11. 通知コンテンツの目的

通知は単なる情報配信ではなく、SMAIが確認した材料を短く整理し、「今日何を見るべきか」を把握する入口とする。

通知カードは原則として次の順で構成する。

1. 何が起きたか
2. なぜ確認したいか
3. SMAI上の変化・評価材料
4. 次に確認すること
5. 安全なCTA

通知だけで売買判断を完結させず、Cockpit、投資レーダー、AI調査、My Radarなどの確認画面へつなぐ。

## 12. 表示カテゴリと通知候補

### 12.1 My Favorite / お気に入り

対象はユーザーがお気に入り登録した銘柄。

日次候補:

- 上昇・下落レポート
- AI総合、上昇気配、下振れ警戒、AI予測の変化
- ニュース・開示まとめ

随時候補:

- 急騰・急落
- AI総合の大きな変化
- 出来高急増
- 決算・開示・重要ニュース

初期実装では閾値、dedupe、cooldown、データ鮮度を必須とし、全候補を一括で自動有効化しない。

### 12.2 Market Trend / 市場動向

- 上昇・下落セクター
- 上昇・下落テーマ
- 国別比較
- ETF比較

値動きや順位は市場確認材料として示し、銘柄推奨には使わない。

### 12.3 Investment News / 投資ニュース

日次候補:

- 今日の重要ニュース
- 世界市場
- AI・半導体
- 金利・為替
- 日銀・FOMCなどの主要イベント

随時通知は重大ニュースに限定する。一般ニュース、公式開示、IR資料はsource種別と鮮度を区別する。

### 12.4 SMAI Insight / SMAI分析

- SMAI注目候補
- ランキングの大きな変化
- 新しい確認テーマ
- My Radarの状態変化
- AI分析完了
- 中長期で確認したい候補

`AIおすすめ銘柄`、`将来有望`のような断定・推奨表現は使わない。Ranking、AI総合、Forecast、Researchなど既存結果の変化を確認候補として通知し、通知生成によってスコアや順位を変更しない。

### 12.5 System / システム

- DB更新
- AI調査完了
- LLM起動状態
- エラー
- バックアップ

初期設定はOFFを推奨する。ただしユーザー操作に対応する完了通知は、操作結果としてアプリ内へ表示できる。重大障害以外を`critical`にしない。

## 13. お気に入り銘柄レポート

### 13.1 固定期間

- 今日
- 1週間
- 1か月
- 3か月
- 1年

各期間は基準日、基準価格、現在価格、変化率、データ更新日時を揃える。期間データ不足時は推定値で埋めず、`未取得`または`比較期間不足`とする。

### 13.2 お気に入り追加以降

表示候補:

- お気に入り追加日
- 登録時株価
- 現在株価
- 監視開始時点からの変化率
- AI総合の変化
- 期間中の最大上昇・最大下落

これは投資成績やSMAIの推奨実績ではなく、ユーザーが監視を始めてからの参考変化である。
登録時株価を保存していない既存お気に入りについて、後から現在値や近似値で捏造しない。将来データが揃った項目だけを表示する。

## 14. アプリ内通知カード

基本表示:

- 大きめのカテゴリicon
- 通知タイトル
- 銘柄名 / symbolまたは市場カテゴリ
- 1〜2行の要約
- 主要な変化値
- SMAIの確認メモ
- 次に見る項目
- CTA

例:

```text
📈 SMAI Market Report
NVIDIA（NVDA）  +3.2%

AI総合  76 -> 83
半導体セクターの動きと関連ニュース3件を確認しました。

次に見る: 上昇の背景が決算・需給・市場全体のどれか
[銘柄コックピットを見る]
```

CTA候補:

- `銘柄コックピットを見る`
- `AI調査の画面を開く`
- `ニュースを見る`
- `My Radarで確認する`

CTAは同一アプリ内の対象画面を開く。`AI調査の画面を開く`は調査開始ではなく、対象銘柄と確認案内を渡すだけとする。

## 15. ntfy向けレンダリング

ntfyは短いPush表示に限定し、詳細はアプリ内通知へ委ねる。

```text
Title: SMAI
Body:
📈 NVDA
AI総合が 76 から 83 に変化しました
次に見る: 半導体セクターと直近材料
```

要件:

- titleは原則`SMAI`または`SMAI | 重要通知`
- 本文は銘柄 / 市場、主要変化、次の確認を短く示す
- topic、内部ID、provider raw data、debug情報を含めない
- 将来のtap先は通知センターまたは対象画面とし、外部取得や売買操作を直接実行しない
- OSの通知文字数制限に備え、詳細項目を優先順で省略できるrendererとする

## 16. 通知センターの情報設計

一覧ではなくカード表示を基本とする。

カテゴリfilter:

- すべて
- お気に入り
- 市場
- ニュース
- SMAI分析
- システム

状態・期間filter:

- 未読
- 重要のみ
- 今日
- 今週

通知状態は`unread | read | archived`とし、将来候補としてpinを検討する。外部配信に失敗してもアプリ内カードは残す。

## 17. 視覚・アクセシビリティ方針

SMAIの既存ダーク金融ダッシュボードと整合する、抑制したネオン調カードを使う。

| 用途 | 主なaccent |
| --- | --- |
| critical / risk | レッド |
| high / important | ゴールド、オレンジ |
| normal market / news | シアン、ブルー |
| system | ブルーグレー、グレー |

色だけで重要度を伝えず、icon、severity label、見出し、短い理由を併用する。文字contrast、スマートフォンのtap target、折り返し、画面全体の横overflowを確認する。点滅や強い常時animationは使わず、reduced-motion設定を尊重する。

## 18. 通知疲れを防ぐルール

- 日次通知は銘柄ごとの大量送信ではなく、可能な限りまとめる。
- 同一event / symbol / materialはdedupe keyで重複抑制する。
- 随時通知は閾値とcooldownを持ち、重大な変化だけを対象にする。
- quiet hoursとseverity thresholdをすべての外部通知に適用する。
- ユーザーがカテゴリ単位で無効化できる将来設定を見込む。
- 通知生成時点の価格、score、source、as-ofを保持し、後から値が変わっても通知内容を再解釈しない。
- データが古い、不足、矛盾している場合は強い通知を作らず、確認不足として扱う。

## 19. チャネル別renderer

共通の`NotificationContent`から、次のrendererを分ける。

- `InAppNotificationRenderer`: card title、summary、metrics、assessment、next check、CTA
- `NtfyNotificationRenderer`: 短いtitle/body、priority、tags、将来のtap action
- 将来: Discord、Email、Telegram

event producerはチャネル固有文字列を作らず、事実と安全な確認材料だけを渡す。renderer追加で投資分析ロジックやevent producerを変更しない構造にする。
