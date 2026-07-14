# Smart Market AI Desktop PCサーバー運用ガイド

この文書は、Smart Market AI（SMAI）をTailscale tailnet内のDesktop PCサーバーとして
継続運用するための手順です。iPhone / iPadでのSafariアクセスやホーム画面追加は
[MagicDNS / PWA風アクセスガイド](LAN_PWA_ACCESS_GUIDE.md)を参照してください。

## 1. 運用の全体像

- SMAI本体と重い処理はDesktop PCで動きます。
- iPhone / iPad、別PCはTailscaleを起動して同じtailnetから閲覧・操作します。
- 手動利用は `scripts\run_lan_server.bat` を使います。
- 手動・自動・監視復旧は共通の排他起動を使い、TCP 8501の競合を防ぎます。
- ログオン時の自動起動はWindowsタスクスケジューラへ登録できます。
- 自動起動は60秒遅延し、Windowsとネットワークの準備を待ちます。
- 8501番でSMAIが既に動いている場合は二重起動しません。
- Assistant Gatewayは親SMAIのautostartを基本とし、常時起動タスクを別途追加しません。

待受アドレス `0.0.0.0:8501` は全ネットワークインターフェースで接続を受けるための
設定値であり、ブラウザーで開くURLではありません。通常アクセスは
`http://desktop-bqrpr4c:8501` に統一します。Desktop PC自身での確認だけは
`http://localhost:8501` を使います。

## 2. 手動で起動する

エクスプローラーから次を実行します。

```text
scripts\run_lan_server.bat
```

BATは `config/server.yaml`（または `SMAI_TAILSCALE_HOSTNAME`）からMagicDNS URLを
解決して1つだけ表示します。Tailscale CLIが利用できない場合も、明示設定があれば
起動は継続します。ブラウザー起動・health checkには `localhost` を使います。venvが
ない場合は起動しません。

## 3. ログオン時の自動起動を登録する

通常のPowerShellからプロジェクトルートで実行します。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\register_smai_startup_task.ps1
```

登録されるタスク:

| 項目 | 設定 |
| --- | --- |
| タスク名 | `SmartMarketAI-LAN-Server` |
| トリガー | 現在のユーザーのログオン |
| 遅延 | 60秒 |
| 実行対象 | `scripts\start_smai_server.bat` |
| 多重起動 | 新しいインスタンスを開始しない |
| 失敗時 | 1分間隔で最大3回再試行 |

同名タスクがある場合は現在のプロジェクトパスと設定で更新します。自動起動BATは
コンソール操作を要求せず、次へログを保存します。

```text
logs\server_ops\smai_server_YYYYMMDD_HHMMSS.log
```

自動起動時は次の環境変数を設定します。

```text
SMAI_ASSISTANT_GATEWAY_AUTOSTART=1
```

`SMAI_PERFORMANCE_PROFILE` が未設定の場合は `workstation` を既定にします。ユーザー
環境で `local_workstation` など、利用する設定ファイルに存在するprofileが明示されて
いる場合は上書きせず維持します。profileはResearch外部取得の並列度・timeout・
cache TTLを実行PC向けに切り替えます。Assistant GatewayはSMAIアシスタント利用時に
親SMAIから必要に応じて起動します。Gateway専用タスクやOllama自動起動の追加は
本MVP対象外です。

## 4. 状態を確認する

```text
scripts\check_smai_server_status.bat
```

次を個別に `OK` / `NG` 表示します。

- SMAI: `http://localhost:8501/_stcore/health`
- Assistant Gateway（任意）: `http://127.0.0.1:8088/health`
- Ollama（任意）: `http://127.0.0.1:11434/api/tags`

GatewayやOllamaが `NG` でも、SMAI本体が `OK` なら通常画面とdeterministic fallbackは
利用できます。状態確認BATは通常アクセスURL `http://desktop-bqrpr4c:8501` も表示します。

## 5. SMAIサーバーを停止する

対話確認付き:

```text
scripts\stop_smai_server.bat
```

無人停止:

```text
scripts\stop_smai_server.bat /quiet
```

停止BATはTCP 8501のLISTEN PIDとコマンドラインを表示し、コマンドラインが
`streamlit ... ui/app.py` と一致するSMAIプロセスだけを停止します。別アプリが8501番を
使っている場合は停止しません。`/quiet` は確認プロンプトだけを省略し、対象確認は
省略しません。

## 6. 自動起動を解除する

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\unregister_smai_startup_task.ps1
```

タスクが存在しない場合もエラーにはせず、その旨を表示します。解除してもSMAI本体、
設定、ログ、銘柄DBは削除しません。既に起動中のサーバーは停止BATで終了します。

## 7. Windows FirewallとMagicDNS

- Windows FirewallがTCP 8501のSMAI待受を遮断していないことを確認します。
- ルーターのポート開放・ポート転送は行いません。
- MagicDNS URLを使うため、LAN IPv4のDHCP予約やIP固定は通常不要です。
- 接続端末とサーバーPCはTailscaleを起動し、同じtailnetへ参加させます。

## 8. 銘柄DBメンテナンス

`run_symbol_universe_import_all.bat` は外部取得、バックアップ、coverage確認を含む
重い処理です。SMAI LANサーバー起動とは別タスクにし、ログオンのたびに直接実行
しません。ログオン10分後に軽い期限判定だけを行い、最終成功から既定7日以上
経過している場合だけ一括更新を呼び出します。

### 状態・lock・ログ

| 用途 | パス |
| --- | --- |
| 最終実行状態 | `data\ops\symbol_maintenance_state.json` |
| 二重起動防止 | `data\ops\symbol_maintenance.lock` |
| wrapperログ | `logs\maintenance\symbol_maintenance_*.log` |
| 一括更新の既存ログ | `logs\symbol_universe_import_all_*.log` |
| 一括更新レポート | `reports\<実施日時>\` |
| CSVバックアップ | `data\marketdata\backup\` |

状態ファイルには `last_success_at`、`last_attempt_at`、`last_exit_code`、
`last_log_path`、`interval_days`、`retry_cooldown_hours` を保存します。日時は実行PCの
ローカルタイムゾーンをoffset付きISO 8601で保存します。日本標準時に設定されたPCでは
`+09:00`です。状態ファイルがない場合や成功日時がない場合は未実行として扱います。
JSONが壊れている場合は警告をログへ残し、未実行として安全側に判定します。
一括更新レポートはPCローカルの実施日時ごとに `reports\YYYY-MM-DD_HHMM\` へ保存します。
同じ日に複数回実行しても実行単位が混ざらず、秒は各reportファイル名に残ります。
初回は状態ファイルがないため実行対象です。初回ログオンで重い更新を走らせたくない
場合は、先にタスクを登録せず手動BATで実施タイミングを確認するか、登録後最初の
ログオン前にタスクを一時無効化してください。実行していないのに成功日時だけを
書き込む運用は行いません。

### 自動実行の判定

実行対象:

- 状態ファイルがない
- `last_success_at` がない
- 最終成功から `interval_days` 以上経過した

正常スキップ:

- 最終成功から `interval_days` 未満
- 前回失敗から `retry_cooldown_hours` 未満
- lockが存在する

既定値は7日と24時間です。必要な場合はタスク実行環境またはシステム環境変数で
変更できます。短すぎる間隔は外部sourceとPC負荷を増やすため推奨しません。

```text
SMAI_SYMBOL_MAINTENANCE_INTERVAL_DAYS=7
SMAI_SYMBOL_MAINTENANCE_RETRY_COOLDOWN_HOURS=24
```

### 自動判定タスクを登録する

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\register_symbol_maintenance_if_due_task.ps1
```

タスク名は `SmartMarketAI-Symbol-Maintenance-IfDue` です。現在のユーザーのログオンから
10分後に `scripts\run_symbol_maintenance_if_due.bat` を実行します。既に実行中なら
新しいインスタンスを開始せず、タスク自体の失敗時再試行は30分後の1回だけです。
再試行時も24時間cooldown判定を通るため、重い一括更新を連続実行しません。
`run_symbol_universe_import_all.bat` をタスクへ直接登録することはありません。

解除:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\unregister_symbol_maintenance_if_due_task.ps1
```

登録状態の確認:

```powershell
Get-ScheduledTask -TaskName "SmartMarketAI-LAN-Server"
Get-ScheduledTask -TaskName "SmartMarketAI-Symbol-Maintenance-IfDue"
```

Action、WorkingDirectory、TriggerのDelay、SettingsのMultipleInstancesを詳しく確認する
場合は、各戻り値の `Actions`、`Triggers`、`Settings` を表示します。

### 手動実行

期限を無視して実行する場合:

```text
scripts\run_symbol_maintenance_manual.bat
```

外部取得、CSV/metadata更新、バックアップ・ログ・レポート保存について注意を表示し、
実行前に確認します。確認を省略する明示実行:

```text
scripts\run_symbol_maintenance_manual.bat /force
```

手動実行も同じatomic lockと状態ファイルを使うため、自動ジョブとの二重起動は
できません。SMAI LANサーバーの起動・停止とは独立しており、メンテナンス失敗時も
LANサーバーを停止しません。

### 失敗とlockの確認

一括更新が失敗すると `last_attempt_at` と `last_exit_code` を更新し、
`last_success_at` は以前の成功日時を維持します。最新のwrapperログと、その中に
記録された既存一括更新ログ・レポートを確認してください。

lockは開始時に排他的に作成し、状態更新完了後に削除します。異常終了で残ったlockが
24時間以上経過している場合はstale警告を出しますが、自動削除しません。タスクや
メンテナンスプロセスが本当に動いていないことをタスクマネージャーで確認してから、
`data\ops\symbol_maintenance.lock` を手動削除してください。実行中に削除すると
二重更新を招くため、確認せず削除しないでください。

metadata coverage、Yahoo coverageの個別定期ジョブ化、失敗通知、lockのPID生存確認、
自動バックアップ復元は次フェーズ候補です。

## 9. セキュリティ境界

本MVPはTailscale tailnet内の利用を対象とします。次は対象外です。

- インターネットへの直接公開
- ルーターのポート開放
- 認証なしの外部公開
- Tailscale Funnel、Cloudflare Tunnelなどの公開経路
- Service Workerを含む完全PWA

インターネット上の外部公開が必要になった場合は、認証・HTTPS・ログ監視を含む別フェーズで
設計してください。

## 10. トラブルシュート

### 自動起動しない

1. タスクスケジューラで `SmartMarketAI-LAN-Server` の最終実行結果を確認します。
2. `logs\server_ops\` の最新ログを確認します。
3. `venv_SMAI\Scripts\python.exe` が存在するか確認します。
4. `scripts\check_smai_server_status.bat` を実行します。

### 8501番が使用中と表示される

状態確認BATを実行します。SMAIなら二重起動防止が働いた正常な状態です。別プロセスなら
自動起動ログにPIDとコマンドラインが残り、SMAIはそのプロセスを停止しません。

### Assistantだけ使えない

GatewayとOllamaの状態を確認します。親SMAIのGateway autostartが失敗しても、
SMAI本体はdeterministic fallbackを維持します。詳細は
`smai-ai-gateway\SETUP.md` を参照してください。

### 銘柄メンテナンスが実行されない

`logs\maintenance\` の最新ログと `data\ops\symbol_maintenance_state.json` を確認します。
`maintenance is not due` は期限内、`retry cooldown` は失敗後24時間以内、`lock exists`
は別実行中またはlock残存を意味します。lockの対処は「銘柄DBメンテナンス」の
手順に従ってください。
