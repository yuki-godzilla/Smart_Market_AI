# Phase XX: News / Sentiment Intelligence

目的:
- 価格系列だけでは見えない市場心理・イベント情報を補助 signal として扱う
- Forecast / Risk / Reporting の説明力と confidence 評価を強化する
- 将来的な FinBERT / LLM / foundation model adapter 追加の土台を作る

## Scope

実装対象:
- News Signal Snapshot
- Sentiment score
- Topic classification
- Forecast confidence integration
- Risk warning integration
- Reporting summary integration

非対象:
- 完全自動売買判断
- ニュース単独による売買推奨
- 高頻度リアルタイム配信基盤

---

## Initial Design

追加コンポーネント:
- SentimentProviderAdapter
- NewsSignalBuilder
- SentimentSnapshot
- ForecastConfidenceEvaluator

構成イメージ:

```text
News Provider
↓
SentimentProviderAdapter
↓
NewsSignalBuilder
↓
SentimentSnapshot
↓
Forecast / Risk / Reporting
```

---

## SentimentSnapshot

初期 data contract 案:

```python
class SentimentSnapshot(BaseModel):
    symbol: str
    as_of: datetime
    sentiment_score: float
    confidence: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    topic: str | None
    source_count: int
    summary: str | None
```

---

## Phase 1: Deterministic Baseline

初期は deterministic rule-based implementation を採用する。

例:

positive:
- beat
- growth
- raised
- upgrade
- 増配
- 上方修正

negative:
- miss
- downgrade
- lawsuit
- cut
- 減配
- 下方修正

目的:
- local-first
- explainable
- reproducible
- 外部AI依存を最小化

---

## Forecast Integration

Forecast result に以下を追加:

- sentiment_adjustment
- forecast_confidence
- model_agreement_score

例:

```json
{
  "forecast_direction": "UP",
  "forecast_confidence": "LOW",
  "model_agreement": 0.42,
  "sentiment_score": -0.35
}
```

---

## Risk Integration

Risk warning に sentiment signal を統合する。

例:
- negative earnings news
- lawsuit / regulation signals
- dividend cut warnings

UI 表示例:
- 「直近ニュースに注意材料があります」
- 「決算関連のネガティブ signal を検知しました」

---

## Reporting Integration

Markdown / UI report に summary を追加する。

例:
- 「価格トレンドは上向きですが、直近ニュースでは慎重な材料もあります」

文言方針:
- 過度な断定を避ける
- 短く簡潔に表示する
- 売買推奨表現は避ける

---

## Future Extensions

将来的な adapter 候補:
- FinBERT
- LLM summarizer
- RAG-based analyst
- Reddit / SNS sentiment
- IR / earnings transcript analysis
- regime-aware sentiment weighting

---

## Testing

- deterministic snapshot generation
- keyword classification
- confidence calculation
- negative/positive mixed cases
- missing news fallback
- external provider unavailable handling

---

## Notes

- sentiment は補助 signal として扱う
- 単独で売買判断しない
- baseline forecast / risk / data quality を優先する
- Research Model Adapter 方針と整合させる
