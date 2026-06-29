# SMAI Notification Gateway

Smart Market AI から外部通知チャネルを分離する、Python 3.11+ 対応の軽量サブモジュールです。
Phase N1 では dataclass / enum / typing のみで通知契約、配信ルール、ntfy channel、dispatcher を提供します。親 SMAI との接続、Streamlit UI、HTTP API、アプリ内通知履歴の本実装はまだ行いません。

## 安全方針

- ntfy はユーザーが明示的に有効化した場合だけ送信します。
- `silent`、severity threshold 未満、quiet hours 中は外部送信しません。
- ntfy の失敗は `DeliveryResult(status="failed")` に変換し、呼び出し元を例外で停止させません。
- HTTP transport は差し替え可能です。通常テストは fake transport のみを使い、外部通信しません。
- topic、topic を含む full URL、Authorization 相当の値はログ、例外文字列、`DeliveryResult.error_message` に含めません。

> **ntfy topic は秘密情報として扱ってください。**
> 推測困難なランダム値を使い、ログ、画面共有、issue、スクリーンショットへ貼り付けないでください。

## 構成

```text
src/notification_gateway/
  models.py
  settings.py
  dispatcher.py
  channels/
    base.py
    ntfy.py
  rules/
    evaluator.py
  storage/
    sqlite_store.py
```

## 配信状態

| status | 意味 |
| --- | --- |
| `skipped` | `silent` など、仕様上送信しない |
| `disabled` | ntfy 無効または必要設定なし |
| `filtered` | threshold 未満または quiet hours |
| `sent` | ntfy が成功応答を返した |
| `failed` | transport error、timeout、HTTP error |

`NtfyChannel` は `HttpTransport` protocol だけに依存します。実送信用には依存追加のない
`UrllibHttpTransport` を明示注入でき、テストや別runtimeでは fake / 別HTTP clientへ交換できます。

## quiet hours

同日内と日跨ぎの両方を扱います。

- `09:00`〜`17:00`: 09:00以上17:00未満
- `22:00`〜`07:00`: 22:00以上または07:00未満
- 開始と終了が同じ場合: 終日 quiet hours

## 開発確認

親リポジトリの仮想環境を使う場合:

```powershell
..\venv_SMAI\Scripts\python.exe -m pytest tests -q
..\venv_SMAI\Scripts\python.exe -m ruff check src tests --no-cache
```

テストは fake transport のみを注入します。実際の `ntfy.sh` を使う live smoke は Phase N1 の通常確認に含めません。

## Phase N1 の非対象

- 親 SMAI からの import
- Streamlit 通知設定 / 通知センター
- 自動通知 event producer
- HTTP API
- SQLite 履歴の本実装
- Discord / Telegram / Email
