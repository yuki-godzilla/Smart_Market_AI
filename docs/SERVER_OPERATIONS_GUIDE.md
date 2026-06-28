# Smart Market AI Desktop PCサーバー運用ガイド

この文書は、Smart Market AI（SMAI）を家庭内LANのDesktop PCサーバーとして
継続運用するための手順です。iPhone / iPadでのSafariアクセスやホーム画面追加は
[LAN / PWA風アクセスガイド](LAN_PWA_ACCESS_GUIDE.md)を参照してください。

## 1. 運用の全体像

- SMAI本体と重い処理はDesktop PCで動きます。
- iPhone / iPadは同じ家庭内Wi-Fiから閲覧・操作します。
- 手動利用は `scripts\run_lan_server.bat` を使います。
- ログオン時の自動起動はWindowsタスクスケジューラへ登録できます。
- 自動起動は60秒遅延し、Windowsとネットワークの準備を待ちます。
- 8501番でSMAIが既に動いている場合は二重起動しません。
- Assistant Gatewayは親SMAIのautostartを基本とし、常時起動タスクを別途追加しません。

待受アドレス `0.0.0.0:8501` は全ネットワークインターフェースで接続を受けるための
設定値であり、ブラウザーで開くURLではありません。Desktop PC自身は
`http://localhost:8501`、iPhone / iPadは
`http://<Desktop PCのIPv4>:8501` を開きます。

## 2. 手動で起動する

エクスプローラーから次を実行します。

```text
scripts\run_lan_server.bat
```

BATは既定ゲートウェイを持つアダプターのIPv4を自動検出し、利用可能なLAN URLを
表示します。IPを取得できない場合は、開けない仮URLではなく `localhost` を
Streamlit表示へ渡し、`ipconfig` での確認を案内します。venvがない場合は起動しません。

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
SMAI_PERFORMANCE_PROFILE=workstation
SMAI_ASSISTANT_GATEWAY_AUTOSTART=1
```

`workstation` はResearch外部取得の並列度・timeout・cache TTLをDesktop PC向けに
切り替える既存profileです。Assistant GatewayはSMAIアシスタント利用時に親SMAIから
必要に応じて起動します。Gateway専用タスクやOllama自動起動の追加は本MVP対象外です。

## 4. 状態を確認する

```text
scripts\check_smai_server_status.bat
```

次を個別に `OK` / `NG` 表示します。

- SMAI: `http://localhost:8501/_stcore/health`
- Assistant Gateway（任意）: `http://127.0.0.1:8088/health`
- Ollama（任意）: `http://127.0.0.1:11434/api/tags`

GatewayやOllamaが `NG` でも、SMAI本体が `OK` なら通常画面とdeterministic fallbackは
利用できます。LAN IPv4を取得できた場合はiPhone / iPad向けURLも表示します。

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

## 7. Windows FirewallとIP固定

- Windows FirewallはTCP 8501をプライベートネットワークだけ許可します。
- パブリックネットワークは許可しません。
- ルーターのポート開放・ポート転送は行いません。
- Desktop PCのIP固定はWindows側の手入力より、Deco X50などルーター側のDHCP予約を
  推奨します。

IPが変わるとiPhone / iPadのホーム画面ショートカットの接続先も変わります。

## 8. 銘柄DBメンテナンス

`run_symbol_universe_import_all.bat` はログオン時の自動起動に含めません。外部取得、
バックアップ、coverage確認を含む重いメンテナンスであり、SMAIサーバー起動とは
役割を分離します。

現時点では週次または必要時の手動実行を推奨します。銘柄DB一括更新、
metadata coverage、Yahoo coverageなどの定期ジョブ化は次フェーズで、実行時間、
失敗通知、排他、バックアップ復元を含めて検討します。

## 9. セキュリティ境界

本MVPは信頼できる家庭内LANだけを対象とします。次は対象外です。

- インターネットへの直接公開
- ルーターのポート開放
- 認証なしの外部公開
- 外出先アクセス
- HTTPS、VPN、Tailscale、Cloudflare Tunnel
- Service Workerを含む完全PWA

外部アクセスが必要になった場合は、認証・HTTPS・VPN・ログ監視を含む別フェーズで
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

