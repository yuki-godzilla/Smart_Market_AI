# 04-2\_Onepager\_Marketdata\_DataAccess

#### [BACK TO README](../../README.md)

## 1) Purpose & Scope

* **Purpose**: 市場データ（株式・為替・インデックス等）の取得を統一I/Fで提供し、下流（FeatureBuilder/Risk/Portfolio/Execution検証）に**完全なデータ契約**で引き渡す。
* **Scope**: 読み取り専用のデータアクセス層（外部API/CSV/DB）＋キャッシュ＋欠損/為替/タイムゾーン処理。書き込みは対象外。
* **Out of Scope**: 高度な特徴量生成（FeatureBuilder）、バックフィルのバッチオーケストレーション、データレイク設計の詳細。

### 1.1 01の要件を反映した前提

* **投資対象**: 高配当銘柄で *日本株に限定しない*（JP + US を想定）。
* **主要市場**: JP=TSE（例: 7203.T 形式）、US=NYSE/NASDAQ（例: AAPL）。
* **通貨/為替**: ベース通貨は **JPY**。USD建て資産は USDJPY で換算。
* **粒度**: 分析は日足（`1d`）を主、検証/実行確認は最短で `1m` を許容。
* **UI/利用者**: 個人投資家向け（Streamlit想定）。

## 2) Public Interfaces (Python想定)

```python
class DataAccess:
    def fetch_ohlcv(self, symbols: list[str], start: datetime, end: datetime, interval: Literal['1m','5m','15m','1h','1d'], tz: str='UTC') -> list[Bar]:
        ...
    def fetch_quotes(self, symbols: list[str], at: datetime | None = None) -> list[Quote]:
        ...
    def get_fx_rates(self, pairs: list[str], at: datetime | None = None, method: Literal['spot','close','twap']='spot') -> list[FxRate]:
        ...
    def get_calendar(self, markets: list[str], start: date, end: date) -> list[CalendarEvent]:
        ...
```

* 例外: `DataSourceError`, `RateLimitError`, `SchemaValidationError`, `UnavailableError`
* 非機能I/F: `close()`, `healthcheck()`, `warmup_cache(symbols)`

## 3) Data Contracts (Pydantic)

```python
class Symbol(BaseModel):
    raw: str  # 入力文字列（例: 7203.T）
    exchange: str  # ex: TSE, NYSE
    code: str      # ex: 7203
    currency: str  # ex: JPY

class Bar(BaseModel):
    symbol: Symbol
    ts: datetime  # UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | int
    interval: str  # '1d' 等
    provider: str  # 供給元トレース

class Quote(BaseModel):
    symbol: Symbol
    bid: Decimal | None
    ask: Decimal | None
    last: Decimal | None
    ts: datetime  # UTC

class FxRate(BaseModel):
    pair: str      # ex: USDJPY
    rate: Decimal
    ts: datetime   # UTC
    source: str

class CalendarEvent(BaseModel):
    market: str    # ex: JP, US
    date: date
    open: time | None
    close: time | None
    holiday: bool
```

* **正規化規約**: 通貨=発行市場通貨, 時刻=UTC, 小数=Decimal。最小刻みと単位は`data_contracts.py`に集約。

## 4) Algorithms & Rules

* **欠損処理**: `OHLCV`の穴は`NA`とし補間は下流で。`twap`計算時のみ近接バーにより内部補間可（ウィンドウ=5分/構成案）。
* **為替変換**: `base_currency` を `config.yml` で指定（初期値: JPY）。`close`換算は当日終値、`spot`は取得時刻のレート、`twap`は\[開始,終了)の加重平均。
* **タイムゾーン**: 受領TZ→UTCへ正規化。夏時間は`pytz`/`zoneinfo`で厳密処理。
* **キャッシュ**: `symbols x interval x date` をキー、`TTL`は intraday=60s, daily=24h（初期）。`stale-while-revalidate`方式。
* **レート制限**: 供給元ごとに`token bucket`でスロットリング。バックオフ=指数(0.5→1→2s, max 3)。

## 5) Error Handling & Retries

* 分類: `4xx`（クライアント）、`429`（レート）、`5xx/ネットワーク`、`整合性`（スキーマ不一致）。
* 再試行: `429/5xx`は指数バックオフ最大3回。`SchemaValidationError`は即時失敗＋監査ログ。
* `DLQ`: バックフィル・バッチ時のみ。リアルタイム要求は即時失敗。

## 6) Idempotency & Security

* 外部呼び出しは読み取り専用のため副作用なし。認証はプロバイダAPIキー/署名。キーはSecret管理、ローテーション方針を`security.md`に記載。
* 輸送層はTLS必須。PIIは扱わない想定（扱う場合はマスキング規約を追加）。

## 7) Performance Budget（03のSLO準拠）

* `fetch_ohlcv`: 1銘柄・日足100本取得でP95 < 300ms（キャッシュヒット時 < 50ms）。
* `fetch_quotes`: 同時50銘柄でP95 < 500ms。
* スループット: 100 RPS（キャッシュ込み）を初期目標。コスト上限は\$X/day（TBD）。

## 8) Observability

* 構造化ログ: `corr_id, provider, endpoint, http_status, latency_ms, cache_hit, symbol_count`。
* メトリクス: `request_count{provider,endpoint}`, `latency_ms_pXX`, `cache_hit_ratio`, `error_rate`。
* トレース: 外部APIコールをspan化、`X-Correlation-Id`を伝播。

## 9) Config Knobs（config.yml）

```yaml
dataaccess:
  provider: yahoo|csv|polygon|mock # 初期はyahoo/csvで開始、必要に応じpolygonを追加
  base_currency: JPY # 01の要件に基づく既定通貨
  cache:
    backend: redis|memory
    ttl_intraday_sec: 60
    ttl_daily_sec: 86400
  rate_limit:
    rps: 10
    burst: 20
  timeouts_ms:
    connect: 1000
    read: 5000
```

## 10) Test Plan

* **Unit**: シンボル正規化、UTC変換、FX換算、キャッシュキー、レート制限分岐。
* **Integration**: モックサーバで`429/5xx`再試行、スキーマ検証、`twap`一致性。
* **E2E（サンドボックス）**: CSV→DataAccess→FeatureBuilderへの連携、日跨ぎTZ、祝日カレンダ。

## 11) Migration/Compatibility

* バージョン化されたスキーマ`v1`から開始。ブレイキング変更は`v2`を追加し段階的移行。
* プロバイダ差分はAdapter層で吸収（`ProviderClient`インタフェース）。

## 12) Open Questions（TBD）

* 主要データ供給元 → **初期は `yahoo`/`csv` を採用**、有料API（polygon等）はスループット要求次第で追加。
* 対応市場/銘柄 → **JP: TSE 上場の高配当候補、US: S\&P500 高配当候補**（初期は数十銘柄から拡大）。
* 足種 → **必須: `1d`、任意: `1m/5m`**（Execution検証用途）。
* ベース通貨 → **JPY を既定**。必要に応じ USD/EUR への切替オプションを追加。
* キャッシュ基盤 → **Redis 推奨**（メモリから移行可能）。初期TTL: intraday 60s / daily 24h。
* コスト上限 → 03でのSLO/利用頻度を踏まえて設定（TBD）。

---

### 付録: 参照フロー（擬似）

```
Client -> DataAccess.fetch_ohlcv -> Cache[miss] -> ProviderClient.request -> Validate(Schema) -> Normalize(UTC/Decimal) -> Cache[set] -> Return
                                                    \-> [429/5xx] Retry/Backoff -> Error
```
