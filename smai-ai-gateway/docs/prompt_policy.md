# Prompt Policy

## LLM の役割

現在の Assistant / `context-answer` では、LLM は数値予測そのもの、ランキング順位、スコア計算、売買判断を担当しません。
担当範囲は以下に限定します。

- 説明
- 要約
- 確認観点の整理
- ユーザーが見ている材料の読み方の補助

将来の `SMAI LLM Factor` では、LLM を最終予測器ではなく、出典付きの定性材料を構造化特徴量へ変換する provider として扱う余地があります。
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

## 将来の SMAI RAG context

将来的には、SMAI RAG / Research Evidence の要約済み context を Gateway 入力へ渡します。
その場合も、全文を無制限に渡すのではなく、出典、公開日、要約、確認ポイントを構造化して渡します。

## 将来の構造化特徴量生成

`SMAI LLM Factor` 用の prompt では、以下を必ず制約として含めます。

- 売買推奨をしない。
- 断定表現を避ける。
- 出典にない情報を作らない。
- score は 0-100 に限定する。
- factor ごとに source URL、source date、source type を保持する。
- JSON のみ返す。
- 不明な場合は低 confidence にする。

Gateway は provider 呼び出しと prompt 実行の境界を担い、`LLMFactorResult` などの SMAI domain schema、source hash、cache、backtest、UI 統合は SMAI 本体側で扱います。
