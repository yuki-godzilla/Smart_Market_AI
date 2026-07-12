# SMAI ホームサーバー運用ガイド

## 2026-07 運用更新

- 自動起動は launcher の `--resilient` モードを使い、Streamlit を別の
  Windows process group で起動します。共有サーバーへ届いたコンソール割り込みは
  launcher が無視し、意図しない `KeyboardInterrupt` 停止を防ぎます。
- 手動の `scripts\run_lan_server.bat` は従来どおり Ctrl+C で停止できます。
- `--resilient` launcher は子Streamlitが終了コード0を含む任意の終了を返しても、
  2秒後に同じ設定で再起動します。通常時は5分監視を待たずTCP 8501を復旧します。
- 常時運用では `server.runOnSave=false` とし、ソース変更による自動リロードで
  実行中のランキングやユーザーセッションを失わないようにします。コード反映は
  自動起動タスクの明示再起動時に行います。
- 手動停止と24時間メンテナンスは停止要求ファイルを先に作成し、子Streamlitだけでなく
  `--resilient` launcherも終了させます。メンテナンス時はその後に新しいlauncherを
  起動するため、意図した再起動と異常終了からの自動復旧が競合しません。
- 24時間メンテナンスはWindows PC全体ではなく、SMAI Streamlitサービスだけを
  再起動します。30秒通知と二段階の安全確認は維持します。
- 管理者実行ではWindows起動60秒後、通常ユーザー実行ではログオン60秒後に、
  本体と5分監視の2タスクを登録します。

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

手動起動、自動起動、監視復旧はすべて
`backend.server_ops.launcher` の排他ロックを通ります。同時に起動要求が来た場合は
1プロセスだけがStreamlitを起動し、後続処理は既存サーバーを検出して正常終了します。

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

`data/ops/server_ops/activity_state.json` の新しいheartbeat記録は、
`last_seen_at`、`client_type`、`connection_state`だけを保存します。
端末種別は`desktop`、`smartphone`、`tablet`、`unknown`に正規化し、生の
User-Agent、IPアドレス、Cookieは保存しません。旧形式の時刻文字列セッションも
再起動安全判定のため継続して読み取ります。WindowsではPID確認に`os.kill`を使わず、
プロセス照会APIを使うため、drain判定が確認対象プロセスを停止させることはありません。

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
`smai_server_*.log` に `Streamlit exited unexpectedly` がある場合は、
resilient launcherが2秒後に子プロセスを再生成した記録です。

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
