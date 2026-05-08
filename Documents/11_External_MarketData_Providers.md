# 11_External_MarketData_Providers

#### [BACK TO README](../README.md)

## 目的

この文書は、将来の live market-data provider を導入する前の準備状態を説明します。
現在の MVP は、外部 API に接続しない deterministic な `mock` / `csv` provider を既定経路にしています。

`yahoo` / `polygon` は provider 名として予約されていますが、現時点ではまだ実装されていません。
誤ってネットワーク依存の挙動が入らないように、live provider は明示 opt-in がない限り拒否されます。

## 現在使える provider

| provider | 実装状況 | ネットワーク | 用途 |
| --- | --- | --- | --- |
| `mock` | 実装済み | 不要 | 既定の MVP 確認 |
| `csv` | 実装済み | 不要 | ローカル CSV による手動確認 |
| `yahoo` | 未実装 | 将来必要 | live provider 候補 |
| `polygon` | 未実装 | 将来必要 | live provider 候補 |

provider の capability は `backend/marketdata/provider_registry.py` で管理します。

## 明示 opt-in

live provider を指定するには、設定ファイルで `dataaccess.allow_external_providers: true` を明示する必要があります。

```yaml
dataaccess:
  provider: yahoo
  allow_external_providers: true
```

ただし、現時点では live provider 本体が未実装のため、この設定をしても外部 API へは接続しません。
API からは「明示 opt-in されたが未実装」という `DataSourceError` が返ります。

## 既定経路

通常のローカル確認では、次のどちらかを使います。

```yaml
dataaccess:
  provider: mock
  allow_external_providers: false
```

```yaml
dataaccess:
  provider: csv
  csv_data_dir: data/marketdata
  allow_external_providers: false
```

この状態ではネットワーク接続は発生しません。
CI とローカル MVP 確認も、この offline / deterministic な経路を前提にします。

## 失敗時の API 表現

live provider 周辺の失敗は、次のような構造化 JSON で返します。

```json
{
  "code": "APP-2000",
  "message": "Live market-data provider requires explicit opt-in",
  "details": {
    "provider": "yahoo",
    "registered": true,
    "implemented": false,
    "deterministic": false,
    "requires_external_opt_in": true,
    "supported_providers": ["mock", "csv"],
    "planned_live_providers": ["yahoo", "polygon"],
    "allow_external_providers": false,
    "opt_in_status": "explicit_config_required"
  }
}
```

主な status code は次の通りです。

| status | 意味 |
| --- | --- |
| `429` | provider rate limit |
| `422` | provider payload の schema mismatch |
| `502` | provider 設定拒否、未実装、その他 data source error |
| `503` | provider unavailable |
| `504` | provider timeout |

## 将来実装時の注意

live provider adapter を追加するときは、次を守ります。

- `mock` / `csv` の既定経路を offline / deterministic のまま維持する
- live provider は `allow_external_providers: true` なしでは有効化しない
- CI は外部 API に依存させない
- provider の capability は `provider_registry.py` に追加する
- rate limit、unavailable、timeout、schema mismatch は既存のドメインエラーに mapping する
- API 仕様、手動確認手順、`PROJECT_CONTEXT.md` を同じ作業単位で更新する
