# Prompt Policy

## LLM の役割

LLM は数値予測そのもの、ランキング順位、スコア計算、売買判断を担当しません。
担当範囲は以下に限定します。

- 説明
- 要約
- 確認観点の整理
- ユーザーが見ている材料の読み方の補助

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

## 将来の SMAI RAG context

将来的には、SMAI RAG / Research Evidence の要約済み context を Gateway 入力へ渡します。
その場合も、全文を無制限に渡すのではなく、出典、公開日、要約、確認ポイントを構造化して渡します。
