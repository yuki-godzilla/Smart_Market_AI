# AGENTS.md

## Purpose / 目的

Smart Market AI（SMAI）の開発者・coding agent向け共通作業ガイドです。

このファイルには、長期間変わりにくい原則、作業開始時の最短経路、責務境界、最低限の完了条件だけを記載します。現在地、フェーズ、個別障害、詳細手順は別資料へ置きます。

- `AGENTS.md`: 安定ルールと最短手順
- `PROJECT_CONTEXT.md`: 現在の実装状況と直近優先順位
- `Documents/05_Implementation_Roadmap.md`: フェーズ計画と完了条件
- `Documents/06_MVP_Operations_Guide.md`: 起動、Provider、検証、運用、障害対応
- `Documents/99_Work_Log.md`: 過去の作業履歴
- `Documents/98_Codex_Task_Template.md`: 実装指示テンプレート

変動するフェーズ番号、一時的な優先順位、個別障害の詳細をAGENTS.mdへ追加しないでください。

## Core Principles / 基本原則

SMAIは、Python、Streamlit、FastAPIを中心に構成されたlocal-firstの個人向け投資判断支援システムです。

### Local-first

ユーザーデータ、設定、分析状態、主要処理、LLM利用の主導権をローカル環境に置きます。市場データ、ニュース、開示情報、通知には外部通信を利用できますが、外部障害でローカル状態や保存データを破損させてはいけません。

### Decision support

SMAIの出力は投資判断を支援する情報であり、売買推奨、利益保証、確定的な将来予測ではありません。必要に応じて根拠、不確実性、データ品質、更新日時を示します。

### Deterministic core

市場データ、財務指標、特徴量、スクリーニング、スコア、ランキング、リスク、ポートフォリオ計算、Forecast数値は原則としてdeterministicな処理を正とします。

LLMは説明、要約、調査整理、対話支援、レポート生成に使います。LLMの自由文だけで基礎数値、ランキング、スコア、保存状態、売買判断を暗黙に上書きしてはいけません。

LLM出力を後続処理へ渡す場合は、typed contract、schema検証、timeout、fallback、sanitizationを用意します。

### Verification

通常の自動テスト、lint、型確認、CIはnetwork-freeかつdeterministicにします。Live MarketData、Web、外部LLM、通知配送は通常確認から分離したlive smokeとして扱います。

## Source Of Truth / 判断優先順位

1. ユーザーの明示要求
2. `backend/`、`ui/`、各subproject、`tests/`の実コードとテスト
3. `PROJECT_CONTEXT.md`
4. `Documents/05_Implementation_Roadmap.md`
5. その他の設計・運用資料

ドキュメントと実コードが異なる場合、現在挙動は実コードと通過テストを優先します。重要な不一致は対象文書へ反映してください。

## Fast Start / 最初に見るもの

安全に作業できる最小限のコード、テスト、資料だけを確認します。

| タスク | 最初に確認 | 主な追加確認先 |
|---|---|---|
| 小規模バグ | エラー、失敗テスト | 対象moduleと対応テスト |
| FastAPI | `backend/app/` | contract、domain service、APIテスト |
| Streamlit UI | 対象`ui/` module | view、component、state、CSS、UIテスト |
| MarketData | `backend/marketdata/` | Provider、adapter、fixture |
| 銘柄DB・検索 | `backend/symbols/` | import/refresh tool、cache、検索テスト |
| Ranking / Scoring | 対象service | 特徴量、contract、回帰テスト |
| Forecast | `backend/forecast/` | adapter、evaluation、時系列検証 |
| Research / News | `backend/research/`、`backend/news/` | source trace、archive、cache |
| Assistant / LLM | `backend/assistant/`、`backend/llm_factor/` | Gateway contract、sanitizer、scenario test |
| Watchlist / Radar | 対象UIとrepository | `user_id`境界、保存、session state |
| Notification | `backend/notifications/` | gateway、設定、履歴、scheduler |
| External access | `backend/server_ops/`、`scripts/` | server operation docs、session、security |
| 新規フェーズ | `PROJECT_CONTEXT.md` | Roadmap、対象設計、対象service |
| 文書のみ | 対象文書 | 現在地変更時のみ`PROJECT_CONTEXT.md` |

履歴調査が不要なら、最初から`Documents/99_Work_Log.md`全体を読まないでください。

## Architecture Boundaries / 責務境界

### Main application

- `backend/app`: FastAPI entrypoint、routing、dependency wiring
- `backend/core`: 共通contract、設定、error
- domain packages: 計算、取得、評価、保存などの業務ロジック
- `ui/views`: 画面構成
- `ui/components`: 再利用UI部品
- `ui/content`: ユーザー向け文言
- `ui/state.py`など: Streamlit session state境界

FastAPI entrypointやStreamlit描画コードに、複雑なdomain logic、永続化、Provider固有処理を埋め込まないでください。UIのみの変更でMarketData、Forecast、Ranking、Scoringの計算結果を変えてはいけません。

### SMAI AI Gateway

`smai-ai-gateway`はSMAI本体から分離された汎用HTTP API Gatewayです。

- SMAI本体のPython moduleをimportしない
- request/response contractで接続する
- Provider固有処理を本体へ漏らさない
- Gateway停止時も主要なdeterministic機能を利用可能にする
- model名や能力を固定せず、discoveryと設定を尊重する
- prompt、schema、routing変更はGateway側でもテストする

### Notification Gateway

`smai-notification-gateway`は通知配送とchannel差異を分離します。

- SMAI本体は通知イベントと設定を管理し、配送実装へ密結合しない
- channel固有のcredentialやpayload変換を本体UIへ漏らさない
- 配送失敗を成功扱いしない
- duplicate、quiet hours、severity、retryの意味を層間で一致させる

## User Data And Persistence / ユーザーデータと保存

Watchlist、Radar、通知設定、履歴、メモ、タグ、保存レポート、ユーザー設定は必ず`user_id`単位で分離します。

- defaultユーザーとカスタムユーザーを暗黙に共有しない
- ユーザー切替時に前ユーザーのstateやcacheを表示しない
- rerun、再読込、session timeout、logoutを区別する
- UIの一時状態と永続データを混同しない
- 保存失敗を成功扱いしない
- migrationでは既存データの互換性とfallbackを考慮する
- 複数ファイル更新は可能な限りatomicに行う
- 読み込み不能データは安全にfallbackし、診断情報を残す
- 保存時刻と表示timezoneを分離する

具体的なtimeout、復元条件、保存先は設定とOperations Guideを参照します。

## External Access And Security / 外部接続と安全性

- インターネットへの直接公開を既定にしない
- 外部アクセスはTailscaleなど認証されたprivate networkを優先する
- API key、token、credentialをrepositoryへcommitしない
- secretをUI state、ログ、例外、通知本文へ出力しない
- 外部応答、URL、HTML、ニュース本文、LLM出力を信頼済み入力として扱わない
- timeout、response size、content type、schemaを検証する
- 外部取得失敗時にDB、cache、sessionを破損させない
- server binding、CORS、allowed host変更は影響を確認する

## Implementation Rules / 実装ルール

- 小さく一貫したvertical sliceで変更する
- 無関係なリファクタを同じ差分へ混ぜない
- 既存contract、helper、fixture、error、repositoryを再利用する
- Pythonはsimple、explicit、typedを基本とする
- 既存のPydantic v2などproject patternに合わせる
- hidden global stateを増やさない
- Provider、model、user、timezone選択を暗黙化しない
- fallbackの原因と採用経路を追跡可能にする
- errorを握りつぶして正常値や空データに見せない
- 変更した振る舞いを証明する最小テストを追加する
- performance改善で正しさと観測可能性を失わない
- generated cacheやruntime artifactは既存の追跡方針を確認してcommitする
- typoや内部refactorだけで文書を大量更新しない

## High-Risk Changes / 高リスク変更

以下は差分量にかかわらず、追加の設計確認と回帰検証を行います。

- Forecast、Ranking、Scoring、Risk
- 学習・検証データ、特徴量、評価指標
- 銘柄DB、symbol mapping、通貨、市場区分
- ユーザー別保存、session復元、migration
- 外部公開、認証、secret、Gateway contract
- 通知配送、quiet hours、重複抑制
- destructive operation、大量更新、history rewrite

高リスク変更では、通常実装より深い推論・レビュー手段を選びます。モデル固有名ではなく、影響範囲と失敗時の損害で判断してください。

### Forecast, scoring and ranking

変更時は可能な範囲で以下を確認します。

- future data leakageがない
- 学習、調整、検証、最終監査の境界を維持している
- horizonに応じたpurgeがある
- temporal holdoutまたはrolling-originで評価している
- 単一銘柄・単一期間だけで改善判定していない
- market、asset type、regime別の大幅劣化がない
- 異常な外挿値と非現実的returnを制御している
- 目的に合う誤差、方向、分離指標を確認している
- tuning未使用の監査群で最終確認している
- 改善gateを満たさない変更を採用しない
- API、UI、exportで意味と単位を一致させる

評価閾値、baseline、採用モデルは`PROJECT_CONTEXT.md`とForecast関連資料を参照します。

### Data quality

データ品質は投資魅力度と原則別軸です。欠損、stale、Provider失敗を根拠なく上昇・下落スコアへ加点・減点せず、confidence、coverage、quality warning、unavailableとして扱います。

## UI And Responsive Design / UI設計

正式な利用対象はPC、iPhone、iPadです。

- ページ全体の不要な横スクロールを発生させない
- 表、ヒートマップ、チャートは必要時のみcomponent内スクロールを許可する
- 共通CSS、component、文言を優先する
- page-local CSSと画面固有stateを増やしすぎない
- スマホでは主要判断を先に、詳細を後に配置する
- touch targetを小さくしすぎない
- 空、未取得、取得中、失敗、N/A、staleを区別する
- 取得日時はtimezoneが分かる形式で表示する
- rerunでsession、user selection、入力中stateを失わない
- clickable cardと内部buttonのevent競合を避ける
- 同一指標の名称、単位、色、警告を画面間で統一する
- UI変更ではスマホ、タブレット、PCを確認する

詳細は`docs/responsive/README.md`と`docs/responsive_checklist.md`を参照します。

## Command Approval Policy / コマンド確認方針

本project workspace内に閉じる通常作業は、原則として追加確認なしで進めて構いません。

確認不要の例：ファイル参照、依頼範囲内の編集、ローカル確認、fixtureやcache更新、`git status`、`git diff`、通常commit、通常push。

ユーザーが明示的に不要としない限り、完了した実装はcommitとpushまで行います。

以下は追加確認または明示指示を必要とします。

- `git push --force`、history rewrite
- repository、大量ファイル、ユーザーデータの復元困難な削除
- 破壊的DB migration
- secretやcredentialの作成・変更・送信
- workspace外の変更
- OS、BIOS、firewall、network、scheduled taskの大きな変更
- 依頼範囲を超える外部サービスへの書き込み

通常のcommit、push、cache更新を過度に確認待ちにしないでください。

## Work Loop / 作業手順

1. 要求と完了条件を確認する
2. 最小限の関連コード、テスト、資料を確認する
3. 変更予定と影響範囲を短く整理する
4. 小さく一貫した差分を実装する
5. targeted verificationを実行する
6. 挙動、契約、運用、現在地が変わった場合だけ文書を更新する
7. `git diff`と`git status`で不要差分とruntime artifactを確認する
8. 原則としてcommit、pushまで完了する
9. 変更、検証、未確認事項、残リスクを報告する

テスト成功は自動的な停止地点ではありません。方向性が承認済みで新たな重大判断がなければ、依頼された完了状態まで進めます。

## Verification / 確認

小さな変更ではtargeted checkを優先し、handoff前に影響範囲に応じたproject checkを行います。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

WindowsではBlack CLIを直接実行せずproject helperを使います。Subprojectを変更した場合は、そのsubprojectのtestsも確認します。

コマンドが停止した場合は無期限に待たず、成功扱いせず、最後の出力を記録して小さいdiagnosticへ切り替えます。

## Definition Of Done / 完了条件

適用可能な範囲で以下を満たします。

- ユーザー要求と完了条件を満たす
- 対象外の挙動を不用意に変えない
- 変更した振る舞いにテストがある
- 通常テストがnetwork依存でない
- error、warning、fallback、採用経路を追跡できる
- API、UI、export、保存形式の意味が一致する
- ユーザー別データ境界を破らない
- 金融ロジック変更では時系列回帰を確認する
- UI変更では対象viewportを確認する
- 必要な文書だけ更新する
- `git diff`にsecret、不要生成物、偶発変更がない
- 未実行確認を実行済みとして報告しない
- commit、push結果を確認する

## Documentation Rules / 文書更新

- `PROJECT_CONTEXT.md`: 現在地、重要前提、完了フェーズ、優先順位、verification baseline、architecture boundaryが変わった場合
- `Documents/99_Work_Log.md`: 作業履歴と過去判断
- Roadmap: フェーズ、scope、完了条件、優先順位が変わった場合
- Operations Guide: 起動、API、保存形式、Provider、Gateway、検証、運用、障害対応が変わった場合
- AI / Notification Gateway資料: contract、setup、architecture変更時に本体とsubprojectを同期
- `Documents/07_UI_Wording_Policy.md`と`ui/content/`: ラベル、警告、説明、凡例、レポート文言変更時

人向け文書とUI文言は日本語を基本とし、MarkdownはUTF-8 without BOMとします。

## Handoff Report / 完了報告

以下を簡潔に報告します。

- 変更ファイルと目的
- 実行した確認と結果
- 実行していない確認と理由
- 残リスク、TODO
- commit hash
- push結果

推測、未確認、失敗した確認は、その状態を明示してください。
