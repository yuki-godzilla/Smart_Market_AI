# SMAI ホームサーバー運用ガイド

SMAI を Windows PC 上で常時運用するための手順です。既存の LAN
（`0.0.0.0:8501`）と Tailscale の接続方法は変更しません。

## 初回設定

管理者として PowerShell またはコマンドプロンプトを開き、プロジェクトルートで実行します。

```powershell
.\scripts\server_ops\apply_power_policy.bat
.\scripts\server_ops\register_smai_autostart_task.ps1
```

電源設定は AC 電源時だけを対象にし、スリープと休止状態を無効化、
ディスプレイの電源断を10分に設定します。スクリプト末尾に現在の設定が表示されます。

自動起動登録では次の2タスクを作成します。

- `SmartMarketAI-Server-Autostart`: Windows 起動60秒後に既存の
  `scripts/start_smai_server.bat` を起動
- `SmartMarketAI-Server-Watch`: Streamlit、TCP 8501、メンテナンス条件を5分ごとに確認

旧 `SmartMarketAI-LAN-Server` タスクがあれば二重起動防止のため無効化します。
登録解除は次で行います。

```powershell
.\scripts\server_ops\unregister_smai_autostart_task.ps1
```

Tailscale は `tailscale status` と `tailscale ip -4` で稼働とIPを確認します。
LAN/Tailscaleともに `http://<PCのIP>:8501` を使用します。ルーターから8501番を
インターネットへ直接公開しないでください。

## 推奨運用

- PCは常時起動し、AC電源で運用する
- スリープと休止状態を使わない
- ディスプレイだけを自動OFFにする
- Windowsアカウントのパスワード変更後はタスク状態を確認する
- Windows Updateによる再起動時間は別途Windows側で管理する

## 自動メンテナンス

`MaintenanceManager` は SMAI の起動時刻、UIセッションheartbeat、
バックグラウンド更新、書き込みlockをローカル状態として管理します。

1. SMAIが24時間連続稼働すると「メンテナンス再起動待ち」になります。
2. 5分ごとに、利用者・セッション・処理・更新・ジョブ・書き込みlockがないか確認します。
3. 一つでも安全を確認できない条件があれば再起動を延期します。
4. 条件成立時はUIへ30秒前通知を公開します。
5. 30秒後に全条件を再確認します。この間にアクセスや処理が始まれば取り消します。
6. 二度目の確認にも通った場合だけWindowsを再起動します。
7. Windows起動後、自動起動タスクがSMAIと監視を復旧します。

安全判定は fail-closed です。状態ファイルの破損、未知の8501プロセス、
処理中マーカー、`.lock` / `.tmp` がある場合は再起動しません。UIは接続中に
1分ごとにheartbeatを更新し、切断後3分間は安全側に延期します。

再起動なしで監視を1回だけ確認するには次を実行します。

```powershell
.\scripts\server_ops\watch_smai_server.ps1 -Once -NoRestart
```

## ログ

`logs/server_ops/` を確認します。

- `autostart.log`: 起動要求、二重起動スキップ、起動失敗
- `watch_server.log`: 5分ごとの8501監視、停止検出、復旧結果
- `maintenance.log`: 24時間判定、延期、30秒通知、再起動実施
- `smai_server_YYYYMMDD_HHMMSS.log`: Streamlit本体の起動ログ

## トラブル対応

### Streamlitが停止した

`watch_server.log` を確認します。監視は停止を検知すると
`start_smai_server.bat` を非表示で起動し、20秒後に8501を再確認します。

### タスクが失敗する

タスクスケジューラで2タスクの「前回の実行結果」を確認します。プロジェクトや
仮想環境を移動した場合は登録解除後、管理者端末から再登録します。

### Tailscaleから接続できない

`tailscale status`、WindowsのTailscaleサービス、端末の認証状態を確認します。
SMAI自体は `http://localhost:8501` で切り分けます。

### Windows Update

今回の機能はWindows Updateを制御しません。アクティブ時間と再起動通知は
Windows設定で管理してください。

### 再起動ループ

タスクスケジューラで `SmartMarketAI-Server-Watch` を停止・無効化し、
`maintenance.log` と `data/ops/server_ops/maintenance_state.json` を確認します。
状態ファイルを手動削除する前にログを退避してください。

### 手動停止

SMAIだけを停止する場合は既存のガード付きスクリプトを使います。

```powershell
.\scripts\stop_smai_server.bat
```
