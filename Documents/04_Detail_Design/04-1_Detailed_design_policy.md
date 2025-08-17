# 🧭 04-1\_Detailed\_Design\_Policy

#### [BACK TO README](../../README.md)

## 0. 目的（Purpose）

* 01〜03で固めた要件・SLO・非機能を実装可能な粒度に落とし込み、**後戻り最小・スピード最大**で開発を進める。
* すべてのコンポーネントに厚い詳細設計は行わず、**リスクベース**で深掘り対象を限定する。

## 1. 適用範囲（Scope）

* サービス：Execution / Portfolio / MarketData(DataAccess/FeatureBuilder) / Risk / Forecast / Reporting / UI
* 共通基盤：スキーマ、例外規約、ログ/メトリクス、設定、CI、テスト戦略

## 2. 深さの方針（Risk-based Depth）

* **One-Pager 必須（優先度高）**

  * Execution Service（発注・Webhook・冪等化・署名検証）
  * Portfolio Management（制約定義・ソルバ設定・数値安定性）
  * Market Data / DataAccess & FeatureBuilder（スキーマ・キャッシュ・欠損/為替処理）
  * Risk Analysis（事前チェック規則・しきい値・例外パス）
* **簡易設計（優先度中）**

  * Forecast（モデル入出力・メトリクス・保存形式）
  * Reporting（テンプレ・チャート仕様）
  * Streamlit UI（ページ/状態/イベント・UXフロー）

## 3. 成果物（Deliverables）

* コンポーネント別 **One-Pager**（必要なもののみ）
* コンポーネント別 **簡易設計ノート**（I/F図・データ契約・主要フローの要点）
* **共通規約ブック**（data-contracts.md, errors.md, logging.md, config.md, testing.md）

## 4. One-Pager テンプレート（共通）

1. **Purpose & Scope**：何を／どこまで

2. **Public Interfaces**：関数/エンドポイント/キュー名、引数・戻り値・例外、HTTP/GRPC仕様

3. **Data Contracts**：Pydantic/SQLスキーマ、単位、通貨、タイムゾーン、整合性制約

4. **Algorithms & Rules**：数式・最適化条件・ビジネスルール・近似と限界

5. **Error Handling & Retries**：分類（4xx/5xx/外部）、バックオフ、DLQ、ユーザー通知

6. **Idempotency & Security**：冪等ID、重複検知、署名検証、ロール/権限、監査ログ

7. **Performance Budget**：レイテンシ/スループット/コスト上限（03のSLOに紐づけ）

8. **Observability**：ログ項目（corr\_id等）、メトリクス、トレース、サンプリング

9. **Config Knobs**：config.yml キー、デフォルト値、動的変更可否

10. **Test Plan**：Unit/Integration/E2E、モック・固定種・再現シード

11. **Migration/Compatibility**：バージョニング、後方互換、移行手順

12. **Open Questions**：未決/TBD、外部合意が必要な点

---

## 5. 共通規約（Cross-cutting Standards）

* **データ型/単位**：Decimal(通貨), timezone=UTC, symbolはISO/取引所接頭辞付、量は最小取引単位に正規化
* **ID/キー**：`corr_id`（全リクエスト必須）、`idempotency_key`（外部副作用API必須）
* **例外とエラーコード**：アプリ内コード体系（`APP-XXXX`）とHTTPマッピング表を `errors.md` に定義
* **ログ/メトリクス**：構造化JSONログ、PII除外ルール、主要メトリクス（受注成功率、レイテンシ、欠損率 等）
* **設定**：`config.yml` 中央集約、必須キー一覧、セキュア値はSecret管理
* **セキュリティ**：Webhook HMAC、時刻偏差±5分、権限（最小権限/監査）

## 6. レポジトリ構成（提案）

```
/ app
  /execution
  /portfolio
  /marketdata
    /dataaccess
    /feature_builder
  /risk
  /forecast
  /reporting
  /ui
/common
  data_contracts.py
  errors.py
  logging.py
  config.py
/tests
  /unit  /integration  /e2e
/docs
  /onepagers
  /standards
```

## 7. 作業順序（Implementation Order）

1. **共通規約ブック**の初版（data-contracts・errors・logging・config）
2. **Market Data（DataAccess→FeatureBuilder）** One-Pager & スケルトン
3. **Execution** One-Pager & Webhook受信器の枠組み（HMAC/冪等）
4. **Risk** One-Pager & 同期/非同期チェック実装の雛形
5. **Portfolio** One-Pager & ソルバI/F雛形（数値安定化のガード）
6. Forecast / Reporting / UI の簡易設計・実装開始

## 8. レビューとDoD（Definition of Done）

* **レビュー観点**：I/Fの明確性、データ契約の完全性、例外・冪等・観測可能性、SLO整合
* **DoD**

  * One-Pagerがテンプレ全項目を埋め、未決が明記されている
  * スケルトンコード＋最小ユニットテストが通過
  * ログ/メトリクス/設定がスタブでも配線済み

## 9. テスト戦略の割当（Mapping）

* Unit：バリデーション、丸め、再試行分岐
* Integration：モック外部（ブローカ/データ源）でI/F検証、冪等再送確認
* E2E：サンドボックスで受注〜約定集計、データ欠損〜補間の観測

## 10. リスクと緩和

* 外部API制限（429/レート）：指数バックオフ、キュー保留、サーキットブレーカ
* 数値不安定（最適化）：スケール調整、バウンド、ウォームスタート、検証用固定シード
* データ品質（欠損/タイムゾーン/為替）：欠損ルール、UTC原則、為替レートソースの優先度

## 11. 未決事項（初期）

* ブローカ/データ供給元の最終選定
* ソルバ（商用/OSS）とライセンス条件
* UIの最小機能セット（MVP）

---

### 付録A：サンプル One-Pager（Execution 抜粋）

* I/F

  * `Execution.place_orders(orders: list[Order], idempotency_key: str) -> ExecReceipt`
  * `Execution.on_fill_webhook(payload: dict, signature: str) -> None`
  * `Execution.get_status(order_id: str) -> OrderStatus`
* Data Contracts（抜粋）

  * `Order{ symbol, side:'BUY'|'SELL', qty:int|Decimal, type:'MKT'|'LMT'|'STP'|'IOC', limit_price?:Decimal }`
  * `Fill{ order_id, qty:Decimal, price:Decimal, ts:datetime }`
  * `ExecReceipt{ batch_id, broker_order_ids:list[str], accepted_at:datetime }`
* 主要ルール

  * LMTは`limit_price>0`、数量は最小取引単位へ丸め
  * IOCは部分約定のみ許容
* リトライ

  * 429/5xx：指数バックオフ（0.5→1→2s、最大3回）
* 冪等/セキュリティ

  * 送信ごとに`Idempotency-Key`必須、WebhookはHMAC検証＋±5分時刻許容
* 観測性

  * 構造化ログ：`corr_id, idempotency_key, broker_order_id, latency_ms, http_status`
  * メトリクス：受注成功率、部分約定比率、平均レイテンシ
