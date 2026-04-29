# 05\_Implementation\_Checklist\_and\_Stubs

#### [BACK TO README](../README.md)

> 01〜04の設計を**そのまま実装に落とすためのToDo＋最小スケルトン**。各項はチケット化しやすい粒度で記載。

## A. レポジトリ初期化（共通）

* [x] `python 3.11` / `ruff` / `mypy` / `pytest`
* [ ] `poetry`
* [x] ディレクトリ: `/backend/app` `/backend/core` `/tests` `/Documents`
* [x] `setup/requirements.txt` に `pydantic`, `fastapi`, `uvicorn`, `httpx` を記載
* [ ] `pyproject.toml` に runtime dependencies を記載するか、現行の `setup/requirements*.txt` 方針を継続するかを決定する
* [ ] `orjson`, `prometheus_client`
* [ ] 後続フェーズで `redis`, `pulp`（or `ortools`）を必要時に追加
* [ ] `.env` / `.env.example` / `docker-compose.yml`（redisは運用時候補）

## B. data\_contracts.py（共通型）

> Risk/Portfolio/Executionの間で型を揃える。**ProposedOrder/Orderの橋渡し**は`TradeIntent`で。

```python
# backend/core/data_contracts.py
from datetime import datetime, date
from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel

class Symbol(BaseModel):
    raw: str  # e.g. 7203.T, AAPL
    exchange: str  # TSE/NYSE/NASDAQ
    currency: Literal['JPY','USD']

class FxRate(BaseModel):
    pair: Literal['USDJPY']
    rate: Decimal
    ts: datetime

class TradeIntent(BaseModel):
    symbol: str
    side: Literal['BUY','SELL']
    qty: Decimal
    price_hint: Optional[Decimal] = None
    currency: Literal['JPY','USD']

class Position(BaseModel):
    symbol: str
    qty: Decimal
    avg_price: Decimal
    currency: Literal['JPY','USD']

class DailySnapshot(BaseModel):
    symbol: str
    as_of: date
    last: Optional[Decimal]
    close_1d: Optional[Decimal]
    adv_20d: Optional[Decimal]
    vol_20d: Optional[Decimal]
    dividend_yield: Optional[Decimal]
    market_cap_jpy: Optional[Decimal]
    missing: dict[str, bool]
```

## C. config.yml スキーマ（抜粋）

```yaml
app:
  timezone: UTC
  base_currency: JPY
  log_json: true

dataaccess:
  provider: mock|csv|yahoo|polygon
  cache:
    backend: memory
    ttl_intraday_sec: 60
    ttl_daily_sec: 86400
  timeouts_ms:
    connect: 1000
    read: 5000

feature_builder:
  adv_window: 20
  vol_window: 20
  vol_method: close2close  # NOTE: 'parkinson' も許容（綴り修正TODO）

risk:
  thresholds:
    max_notional_per_symbol: 3000000
    max_notional_per_basket: 10000000
    max_concentration: 0.25
    min_dividend_yield: 0.03

portfolio:
  solver:
    backend: none
    tolerance: 1e-6

execution:
  webhook:
    secret: ${WEBHOOK_SECRET}
  idempotency:
    storage: memory
    ttl_hours: 24
```

## D. Errorコード規約（errors.md 抜粋）

* `APP-1001` ValidationError
* `APP-2001` RateLimit
* `APP-3001` BrokerError
* `APP-3101` UnsupportedTIF
* `APP-4001` Security/HMACFailed
* `APP-5001` SchemaMismatch

## E. DataAccess スケルトン

```python
# backend/marketdata/data_access.py
from typing import Literal
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel

class Bar(BaseModel):
    symbol: str; ts: datetime; open: Decimal; high: Decimal; low: Decimal; close: Decimal; volume: Decimal; interval: str; provider: str

class Quote(BaseModel):
    symbol: str; bid: Decimal|None; ask: Decimal|None; last: Decimal|None; ts: datetime

class DataAccess:
    def __init__(self, cfg, cache):
        self.cfg = cfg; self.cache = cache
    async def fetch_ohlcv(self, symbols: list[str], start: datetime, end: datetime, interval: Literal['1m','5m','15m','1h','1d']='1d') -> list[Bar]:
        # TODO: provider adapter, cache key = f"ohlcv:{interval}:{start:%Y%m%d}:{end:%Y%m%d}:{','.join(symbols)}"
        ...
    async def fetch_quotes(self, symbols: list[str], at: datetime|None=None) -> list[Quote]:
        ...
    async def get_fx_rates(self, pairs: list[str], at: datetime|None=None, method: Literal['spot','close','twap']='spot'):
        ...
```

## F. FeatureBuilder スケルトン（綴り修正TODO）

```python
# backend/marketdata/feature_builder.py
from typing import Literal
from datetime import date
from decimal import Decimal
from statistics import pstdev
from common.data_contracts import DailySnapshot

class FeatureBuilder:
    def __init__(self, da):
        self.da = da
    async def build_daily_snapshot(self, symbols: list[str], as_of: date) -> list[DailySnapshot]:
        # 1) quotes/ohlcv, 2) fx, 3) 指標計算, 4) missingフラグ
        ...
    def compute_vol(self, symbol: str, as_of: date, window: int = 20, method: Literal['close2close','parkinson']='close2close') -> Decimal:
        ...
```

## G. RiskService ルール評価エンジン

Status: initial MVP implemented in `backend/risk/service.py` and exposed through `POST /risk/pre-trade-check`. Remaining work is API contract/error hardening and richer rule output.

```python
# backend/risk/service.py
from common.data_contracts import TradeIntent, DailySnapshot

class RiskService:
    def __init__(self, cfg, fb):
        self.cfg = cfg; self.fb = fb
    async def pre_trade_check(self, basket: list[TradeIntent], as_of, account_id: str):
        # 集計→しきい値比較→ALLOW/REVIEW/BLOCKを返却
        ...
```

## H. PortfolioService（pulp例）

```python
# backend/portfolio/service.py
class PortfolioService:
    def rebalance(self, constraints, as_of):
        # 変数 w_i ∈ [0,1], Σ w_i = 1
        # 目的: maximize (yield - λ*vol)
        ...
```

## I. Execution（FastAPI Webhook雛形＋Idempotency）

```python
# backend/execution/webhook.py
from fastapi import APIRouter, Header, HTTPException
router = APIRouter()

@router.post('/exec/fill')
async def on_fill_webhook(payload: dict, x_signature: str = Header(...), x_sent_at: str = Header(...)):
    # verify_hmac(payload, x_signature) → raise 401
    # check_skew(x_sent_at) → raise 401
    # dedupe(event_id) → return 200 if dup
    # normalize_event → update_state
    return {"status": "ok"}
```

```python
# backend/execution/idempotency.py
import json, hashlib

def idem_key(body: dict, headers: dict) -> str:
    h = hashlib.sha256((json.dumps(body, sort_keys=True)+json.dumps(headers, sort_keys=True)).encode()).hexdigest()
    return f"idem:{h}"
```

## J. 観測性（logging/metrics）

```python
# common/logging.py
import json, sys

def log_json(level, **kw):
    print(json.dumps({"level": level, **kw}), file=sys.stdout)
```

```python
# common/metrics.py
from prometheus_client import Counter, Histogram
REQUEST_LATENCY = Histogram('request_latency_ms','', buckets=(50,100,250,500,1000))
ERRORS = Counter('app_errors_total','', ['code'])
```

## K. テスト雛形（pytestベース）

```python
# tests/test_idempotency.py
from app.execution.idempotency import idem_key

def test_same_body_same_headers_same_key():
    assert idem_key({"a":1},{"b":2}) == idem_key({"a":1},{"b":2})
```

```python
# tests/test_featurebuilder_vol.py
# pytest + hypothesis でGoldenデータ検証
import pytest, hypothesis.strategies as st
from hypothesis import given

@given(st.lists(st.floats(min_value=0, max_value=100), min_size=2, max_size=50))
def test_vol_non_negative(data):
    # ボラ計算が常に非負
    ...
```

## L. CI（GitHub Actions例）

* [ ] `lint → typecheck → test` の3ジョブ（pytest実行）
* [ ] 主要ブランチでDockerイメージをビルド

## M. Runbook（運用）

* 重大障害時：`rate-limit急増`→バックオフ設定確認→`circuit breaker`有効化
* Redis障害：キャッシュ/冪等性ともフォールバック戦略（読み取りは直叩き、書き込みはBest-effort）

---

### 備考/軽微修正

* `FeatureBuilder.compute_vol` の引数 `parkison` は **`parkinson`** に統一（設計04-5の綴り修正）。
* DataAccess/Execution のキャッシュ/Idempotencyは **MVPではmemory**、運用時に **Redis** へ移行（運用簡素化）。
* 休日カレンダー/配当/発行株式の **データ源確定**（Yahoo/CSV/取引所公式等）は別表で後続反映。
