# 07_API_Specification

#### [BACK TO README](../README.md)

## 目的

Smart Market AI では、MVP 段階の API 仕様書として FastAPI が自動生成する
OpenAPI / Swagger UI を主に利用します。

この文書では、Swagger UI の確認方法と、API 契約として維持したい共通ルールを整理します。

## Swagger UI の確認方法

ローカル API サーバーを起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Swagger UI は次の URL で確認できます。

```text
http://127.0.0.1:8000/docs
```

OpenAPI JSON は次の URL で確認できます。

```text
http://127.0.0.1:8000/openapi.json
```

## API グループ

- `Health`: 稼働確認用のヘルスチェック API。
- `Risk`: 注文候補バスケットに対する取引前リスク判定 API。
- `Portfolio`: ポートフォリオ評価とリバランス提案ワークフロー API。

## 現在のエンドポイント

### `GET /health`

API が起動していることを確認するための最小ヘルスチェックです。

### `POST /risk/pre-trade-check`

注文候補バスケットを deterministic な MVP リスクルールで評価します。

主なレスポンスモデル:

- `RiskDecision`

### `POST /portfolio/rebalance-check`

現在ポジションを評価し、目標配分から solver なしのリバランス取引案を生成します。
生成された取引案がある場合は、Risk の取引前判定にも接続します。

主なレスポンスモデル:

- `PortfolioRiskResult`

挙動メモ:

- リバランス取引案が生成されない場合、`risk_decision` は `null` になります。

## API 契約ルール

- リクエストとレスポンスは JSON です。
- 日付は `YYYY-MM-DD` 形式です。
- Decimal 値は、浮動小数点の曖昧さを避けるため JSON 文字列で送れます。
- MVP の主要経路では deterministic な `mock` market-data provider を使います。
- 現在の API は broker や execution provider に注文を送信しません。

## エラー形式

ドメインエラーは次の JSON 形式で返します。

```json
{
  "code": "APP-2002",
  "message": "Target weights must not exceed 1",
  "details": {
    "target_weight_sum": "1.1"
  }
}
```

MVP でよく使うステータス:

- `422`: リクエスト検証エラー、またはドメイン計算エラー。
- `502`: market-data source に関するエラー。

## 更新ルール

API の挙動を追加または変更する場合は、次も合わせて更新します。

- FastAPI endpoint metadata、request example、response documentation
- `/openapi.json` の契約を確認するテスト
- `PROJECT_CONTEXT.md`
- `Documents/06_Implementation_Roadmap.md`
