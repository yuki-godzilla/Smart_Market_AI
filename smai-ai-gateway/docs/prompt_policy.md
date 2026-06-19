# Prompt Policy

## LLM の役割

現在の Assistant / `context-answer` では、LLM は数値予測そのもの、ランキング順位、スコア計算、売買判断を担当しません。
担当範囲は以下に限定します。

- 説明
- 要約
- 確認観点の整理
- ユーザーが見ている材料の読み方の補助

`SMAI LLM Factor` では、LLM を最終予測器ではなく、出典付きの定性材料を構造化特徴量へ変換する provider として扱います。
この場合も、LLM が直接「株価が上がる / 下がる」を予測したり、Ranking / Investment Score / Forecast の最終値を決定したりすることは禁止します。
LLM が出す 0-100 の材料スコアは domain schema で検証される参考特徴量であり、SMAI 側の backtest と UI 境界を通るまで既存予測モデルへ統合しません。

## 投資助言ではない

SMAI / Gateway の出力は投資判断の補助情報です。
買う、売る、保有するといった指示を出しません。

## 根拠データ

ハルシネーション抑制のため、SMAI から Gateway へ渡す context は明示的な根拠データに限定します。

- 画面名
- セクション名
- 表示済みサマリ
- 注意点
- 確認ポイント
- Decision Report context

Provider raw fields、debug logs、保存対象でない外部本文全文は通常 request に含めません。

## 構造化回答

`/api/v1/context-answer` では、LLM に自由な JSON 生成を任せません。
LLM は `answer` の本文生成を担当し、`materials`、`cautions`、`next_checkpoints`、`referenced_sections` は Gateway が受け取った context から安定生成します。
これにより、SMAI 側 UI が必要とする表示順と安全境界を保ちます。

## Tool Planner

`/api/v1/assistant/tool-plan` では、LLM は許可済み action_id を使った確認手順案だけを JSON で返します。

- action を実行しない。
- 外部取得、レポート作成、state change は `requires_confirmation=true` にする。
- `create_ranking` / `refresh_news` を ready 実行のように扱わない。
- 買う / 売る / 保有する、利益保証、broker / order / execution などの文言を出さない。
- スコア、ランキング順位、Forecast値、AI総合、Investment Score、Research Score、Decision Report本文を変更しない。
- Gateway は plan案を返すだけで、親SMAI側が schema / allowlist / safety validation と deterministic fallback を行う。

## 将来の SMAI RAG context

将来的には、SMAI RAG / Research Evidence の要約済み context を Gateway 入力へ渡します。
その場合も、全文を無制限に渡すのではなく、出典、公開日、要約、確認ポイントを構造化して渡します。

## Cockpit 解釈支援

`cockpit_interpretation` では、LLM は Cockpit に表示済みの価格、Forecast / AI予測インサイト、Investment Score、Research Evidence、AI材料分析を読み解く補助だけを担当します。

- 強い材料、注意点、矛盾・不確実性、次の確認を整理する。
- score、ランキング順位、Forecast値、AI総合、Investment Score、Research Score、Decision Report本文を変更しない。
- 買う / 売る / 保有するなどの行動指示を出さない。
- context にない根拠を追加しない。
- 不明点は未確認事項として扱う。

## 構造化特徴量生成

`SMAI LLM Factor` 用の prompt では、以下を必ず制約として含めます。

- 売買推奨をしない。
- 断定表現を避ける。
- 出典にない情報を作らない。
- score は 0-100 に限定する。
- factor ごとに source URL、source date、source type を保持する。
- JSON のみ返す。
- 不明な場合は低 confidence にする。

Gateway は provider 呼び出しと prompt 実行の境界を担い、`LLMFactorResult` などの SMAI domain schema、source hash、file-backed cache、deterministic backtest evaluator、broader historical fixture / validation report、Cockpit / Ranking 参考表示は SMAI 本体側で扱います。cache policy expansion、UI 統合拡張も SMAI 本体側で進めます。
