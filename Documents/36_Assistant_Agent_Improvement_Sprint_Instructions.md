# SMAIアシスタント / チャット / エージェント改善スプリント 指示書

作成日: 2026-07-12

## 次セッションへ渡す依頼文

```text
SMAIアシスタントのチャット機能と確認型エージェント機能を、大規模改善スプリントとして完了させてください。

まず既存の `AGENTS.md`、`PROJECT_CONTEXT.md`、`Documents/30_Assistant_Agent_Roadmap.md`、
`Documents/06_MVP_Operations_Guide.md`、`backend/assistant/`、`ui/views/copilot.py`、
`smai-ai-gateway/`、関連testsを確認し、未完了・未接続・品質不足の箇所を実コードとテストで特定してください。

目的は、SMAIアシスタントを、自然で役立つチャット体験と、ユーザー確認を必須にした安全な確認フローの両面で完成度を上げることです。
決定論的な投資分析とデータ境界を守り、LLMは説明・整理・計画提案に限定してください。

この文書の「スコープ」「安全境界」「完了条件」「検証」「成果物」を守り、
小さく一貫したvertical sliceで実装、テスト、必要文書更新、git diff確認、commit、pushまで完了してください。
既存の未関連差分は変更・混入・破棄しないでください。
```

## 1. スプリントの目的

SMAIアシスタント（SMAIナビ）を、次の二つを両立するプロダクトへ改善する。

1. **チャット体験**
   - 質問の意図、画面、銘柄、取得済み材料を適切に読み取り、最初に直接的で自然な回答を返す。
   - 雑談、SMAIの使い方、概念説明、銘柄確認、予測・リスク比較、ニュース・RAG確認、Decision Report作成を混同しない。
   - 未取得・不足・stale・fallback・外部取得失敗を、内部実装用語ではなく利用者が判断できる表現で示す。

2. **確認型エージェント体験**
   - 依頼を安全なTool Plan / Guided Workflowへ整理し、現在地、必要な材料、次の確認、実行結果を一貫して見せる。
   - 画面遷移はsame-app navigationに限定し、外部取得・レポート作成・保存などは必ずユーザー確認後にだけ実行する。
   - Gatewayは提案JSONのみを返し、親SMAIのvalidation・allowlist・confirmation・auditを通らない操作を実行しない。

このスプリントは、回答の自然さ、材料の根拠性、確認フローの明瞭さ、失敗時の回復性を上げる。Ranking順位、Investment Score、Research Score既定weight、Forecast数値、銘柄データ、売買行為を変更するスプリントではない。

## 2. 現在の土台

実装済みの機能は削除せず、再利用・統合する。

- `backend/assistant/`
  - intent router、context builder、deterministic assistant service
  - Tool Registry / Tool Plan / plan validation
  - Guided Workflow、session-local workflow runtime、action audit / executor
  - agent evaluation fixture / harness
- `ui/views/copilot.py`
  - 専用SMAIアシスタント画面、チャット履歴、composer、runtime status
  - warmup / dynamic model selector / fallback表示
  - 確認カード、Tool Plan、Guided Workflow、action result、Decision Report下書き
- `smai-ai-gateway/`
  - `/api/v1/context-answer` と `/api/v1/assistant/tool-plan`
  - model discovery / routing、schema validation、Gateway側テスト
- Research RAG
  - 現在のhybrid retrievalとResearch Summaryを、Assistantの**根拠材料**として利用できる。
  - RAGの検索品質、Research Score、Ranking順位をAssistantの自由文だけで変更してはいけない。

現在の実装状況はコードとテストを正とし、ロードマップや本書に古い記述があれば、対象の現在文書を最小限更新する。

## 3. 必須スコープ

### 3.1 会話品質と文脈設計

- intent / conversation mode / entity resolutionの実装とシナリオfixtureを見直す。
- 短い挨拶・自己紹介・SMAIの使い方・概念説明では、不要なTool PlanやAction Cardを表示しない。
- 銘柄、比較対象、画面文脈、RAG材料、ニュース材料が曖昧な場合は、推測して断定せず、回答可能な範囲と追加確認を分ける。
- 銘柄を指定した質問では、取得済みの価格・Forecast・Risk・Research・News材料の有無と品質を一貫した優先順位で扱う。
- LLM応答、deterministic fallback、Tool結果で、表現・注意書き・材料表記・source表示が矛盾しないようにする。
- raw provider field、内部prompt、request ID、例外詳細、Gateway内部情報、LLM内部推論を通常回答・コピー・exportへ漏らさない。

### 3.2 Tool Plan / Guided Workflowの完成度

- 明示的な「調べる」「比較する」「画面を開く」「レポートを作る」依頼だけに、目的に合うPlan / Workflowを出す。
- action allowlist、対象ページ、必要材料、確認要否、disabled reason、順序、次のステップを単一の意味に保つ。
- navigation、`update_research`、`create_decision_report`の既存導線を壊さず、成功・部分成功・失敗・キャンセル・skip・retry・既存材料で続行を明確に表示する。
- `refresh_news` / `create_ranking`を実行可能にする場合は、既存の安全なbackend操作・confirmation・idempotency・timeout・監査が揃う場合に限る。揃わなければready actionにせず、理由を表示する。
- 同じactionの重複実行、古いターンの確認、画面切替後の別銘柄への誤実行、session再描画による自動再実行を防ぐ。
- Workflow sessionはsession-localを維持し、Gatewayに実行権限・保存権限・session状態管理を渡さない。

### 3.3 LLM Gatewayとdeterministic fallback

- Gateway利用はopt-inを維持し、通常のpytest / CIにnetwork、Ollama、外部LLMを必須化しない。
- `/models` discoveryで実在するモデルだけを表示し、ユーザー選択をsession内で保持する。
- timeout、Gateway停止、model未取得、provider失敗、malformed schema、空回答、unsafe planで、画面を止めずdeterministic fallbackへ戻す。
- fallbackの理由は技術詳細に限定し、通常表示では利用者向けの次の確認を示す。
- parent SMAIと`smai-ai-gateway`のimport境界を維持する。GatewayはSMAIのPython moduleをimportしない。

### 3.4 UX・状態管理・レスポンシブ

- チャットの回答、pending表示、擬似ストリーミング、runtime status、model selector、action confirmation、workflow controlsを一つの会話導線として整える。
- 送信中・失敗・fallback・retry時に、入力中テキスト、会話履歴、明示選択モデル、workflow sessionを不必要に失わない。
- PC、iPhone、iPadで横スクロール、重複ボタン、固定composerとの重なり、タップ領域、長い回答の可読性を確認する。
- 初期表示はLLM起動待ちでブロックせず、準備中・ready・degraded・failed・timeoutを区別する。

### 3.5 安全・データ・投資判断境界

- 売買推奨、利益保証、価格の断定予測、注文・発注・約定・broker連携・自動売買を実装しない。
- LLMの自由文でRanking、Score、Forecast、保存済み状態を上書きしない。
- 外部取得、report作成、archive / exportなどの副作用はユーザー確認を経由し、失敗を成功扱いしない。
- user_id境界、session state、Decision Report保存、外部取得のtransient-by-default方針を維持する。
- 外部データ、URL、LLM出力を信頼済み入力として扱わず、schema、長さ、内容、action ID、confirmationを検証する。

## 4. 推奨する実施順序

1. **現状監査とベースライン**
   - 対象コード、現在のassistant scenario fixture、agent evaluation、UI smoke、Gateway testsを確認する。
   - 実装済み・未接続・重複・壊れやすい状態遷移を表にして、スプリント内の優先順位を短く共有する。

2. **会話契約と評価ケース**
   - 先にintent、期待する回答形、Action Card水準、許可actions、確認要否、fallbackをfixture化する。
   - 国内株、米国株、ETF / 投信、銘柄未指定テーマ、曖昧な対象、材料不足、stale、外部取得失敗、Gateway失敗、unsafe wording、古い確認を必ず含める。

3. **backend / Gateway contract**
   - schema、context縮約、planner adoption、validation、action execution、workflow sessionを小さなvertical sliceで強化する。
   - 新しい副作用actionは、backend contract・confirmation・audit・idempotency・失敗回復・テストが揃うまでUIからreadyにしない。

4. **チャットUIと導線**
   - 回答カード、pending、Tool Plan、確認フロー、実行結果、retry / cancel、技術詳細を同じ会話ターンで読みやすく接続する。
   - UI文言を`ui/content/`と`Documents/07_UI_Wording_Policy.md`へ集約する。

5. **評価・回帰・実画面確認**
   - network-free testを先に通し、Gateway live smokeとStreamlit / Playwright smokeは明示opt-inで分離する。
   - 変更後にscenario / agent evaluationの結果を比較し、unsafe action、confirmation漏れ、fallback劣化、回答の重複を回帰させない。

6. **文書・commit・push**
   - 既存実装の現在地や運用が変わった箇所だけを更新し、過去ログの過剰な書き換えを避ける。
   - 関連差分だけをstageし、未関連のdirty worktreeを混ぜずcommit / pushする。

## 5. 明示的な非スコープ

- Ranking順位、Investment Score、Research Score既定weight、Forecast値の変更
- broker / 証券会社接続、発注、約定、資金移動、自動売買
- 確認なしの外部取得、確認なしのレポート保存、確認なしのニュース更新 / ランキング作成
- GatewayへのSMAI module import、GatewayからのSMAI action直接実行
- 通常CIでのlive provider、Ollama、外部LLM依存
- RAG本文の自動永続archive、ユーザー別保存形式の破壊的変更

これらに着手する必要が判明した場合は、実装前に必要性、影響、代替案を説明してユーザーに確認する。

## 6. 完了条件

以下を、適用可能な範囲で満たすこと。

- チャットの各主要intentに、自然な回答、利用材料、不足材料、次の確認がある。
- 雑談・概念説明には不要なAction Cardが出ず、明示依頼には適切なPlan / Workflowが出る。
- LLM planはallowlist、schema、unsafe wording、confirmation、action statusを通過したものだけを採用する。
- confirmable actionはユーザー確認なしに実行されず、重複・古いターン・対象不一致の実行を防ぐ。
- 失敗・timeout・malformed response・model未取得で、利用可能なdeterministic回答へ安全に戻る。
- user_id、session-local workflow、外部取得のtransient性、Decision Report保存境界を壊さない。
- deterministic計算値とRanking順位を変えない。
- 新規・変更済みの振る舞いをnetwork-freeテストで証明する。
- Assistant scenario / agent evaluationのfixtureが、正常系・失敗系・安全性回帰をカバーする。
- UI変更はPC、iPhone、iPadを確認し、横はみ出し・例外・入力保持・confirmation導線を確認する。
- `git diff`にsecret、raw provider payload、不要なruntime cache、未関連変更を含めない。

## 7. 検証の標準セット

対象に応じて絞り込みつつ、handoff前に実行結果を報告する。

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
.\venv_SMAI\Scripts\python.exe -m mypy backend/assistant ui
```

追加で確認する候補:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q -k "assistant or agent or workflow or gateway"
.\venv_SMAI\Scripts\python.exe -m pytest smai-ai-gateway/tests -q
$env:SMAI_RUN_ASSISTANT_UI_SMOKE = "1"
# 隔離Streamlitを起動した通常端末でAssistant Playwright smokeを実行
```

live Gateway / Ollama / 外部取得の確認は明示opt-inのsmokeとして分離し、通常pytestの成功と混同しない。実行できなかった確認は成功扱いにせず、理由と再実行方法を残す。

## 8. 成果物とhandoff

- 実装コードと対象テスト
- 必要最小限の`PROJECT_CONTEXT.md`、`Documents/30_Assistant_Agent_Roadmap.md`、`Documents/06_MVP_Operations_Guide.md`、UI文言資料の更新
- scenario / agent evaluationの結果、必要なら短いスプリント報告
- 変更ファイル、検証結果、未実行確認、残リスク、commit hash、push結果を含む完了報告

## 9. 優先順位の判断

次の順で優先する。

1. confirmation漏れ、unsafe action、投資助言・実行表現、user/session境界の不具合
2. fallback不能、二重実行、失敗から回復できないworkflow、Gateway contract不整合
3. 回答品質・文脈不足・Action Card過剰表示・材料表示の矛盾
4. UI可読性、待機表示、model selector、レスポンシブ
5. 新しいactionや高度な自動化

新機能を増やす前に、既存の確認型操作が安全に説明・実行・失敗回復・評価できる状態を優先する。
