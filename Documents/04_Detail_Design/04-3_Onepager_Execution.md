# 04-3_Onepager_Execution

#### [BACK TO DETAIL DESIGN README](./04_Detail_Design_README.md)

## 0) Current Sync Status

この文書は **deferred design note** です。
2026-05-17 時点のSMAIは **brokerへ発注しません**。`backend/execution/` も未実装です。

現在実装済みなのは、発注そのものではなく、発注前の判断材料です。

- `TradeIntent`: order-like intent contract
- `/risk/pre-trade-check`: pre-trade risk check
- `/portfolio/rebalance-check`: rebalance proposal + risk check
- Streamlit Rebalance Cockpit: proposed trades and risk breaches display

## 1) Purpose & Scope

将来 broker order sending を再開する場合に、発注・webhook・冪等化・署名検証を安全に実装するための設計メモです。
現段階では **実装対象外** とし、SMAIの通常導線に含めません。

## 2) Current Non-Execution Flow

```text
User / UI
  -> PortfolioService.rebalance
  -> list[TradeIntent]
  -> RiskService.pre_trade_check
  -> RiskDecision
  -> UI / JSON / CSV download
```

この流れでは `TradeIntent` は「売買案」であり、実注文ではありません。

## 3) Planned Public Interfaces

将来実装時の候補です。現時点ではコードに存在しません。

```python
class ExecutionService:
    async def place_orders(
        self,
        orders: list[TradeIntent],
        *,
        account_id: str,
        idempotency_key: str,
    ) -> ExecutionReceipt: ...

    async def cancel_order(self, broker_order_id: str) -> ExecutionStatus: ...

    async def handle_fill_webhook(
        self,
        payload: dict[str, object],
        signature: str,
    ) -> FillEvent: ...
```

## 4) Planned Data Contracts

候補:

- `ExecutionReceipt`: accepted batch, broker order ids, accepted_at
- `ExecutionStatus`: submitted / accepted / rejected / partially_filled / filled / cancelled
- `FillEvent`: broker_order_id, fill_qty, fill_price, ts
- `ExecutionError`: broker error normalized into domain error

## 5) Safety Rules For Future Implementation

- Risk `BLOCK` must never be sent to broker.
- `REVIEW` requires explicit user confirmation.
- idempotency key is required for any external side-effect.
- webhook signature verification is required.
- dry-run mode should exist before live mode.
- logs must not include secrets or credentials.

## 6) Config Knobs

Current config has placeholder contracts only:

```yaml
execution:
  webhook:
    secret: ""
  idempotency:
    storage: memory
    ttl_hours: 24
```

These settings do not imply an implemented execution service.

## 7) Test Plan When Resumed

- Unit: idempotency duplicate detection, signature verification, state transitions
- Integration: fake broker adapter, 429/5xx retry, reject/partial fill
- E2E: dry-run only; pre-trade -> place_orders(dry-run) -> status aggregation

## 8) Out of Scope Now

- SBI / Rakuten / Interactive Brokers などの実接続
- credential storage
- live order submission
- margin / options / futures
- VWAP / TWAP execution algorithms

## 9) Resume Condition

Execution を再開するのは、以下が揃ってからが安全です。

1. Investment Score / Risk / Portfolio / Report の説明導線が安定する。
2. dry-run Execution の価値が明確になる。
3. broker API の利用規約・認証・セキュリティ設計を確認する。
4. ユーザーが明示的に broker 連携を優先する。
