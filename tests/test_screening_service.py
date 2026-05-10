from datetime import date
from decimal import Decimal

from backend.core.data_contracts import DailySnapshot, FeatureSnapshot
from backend.screening import ScreeningService


def test_screening_service_ranks_feature_snapshot_with_breakdown():
    snapshot = FeatureSnapshot(
        as_of=date(2026, 5, 10),
        provider="mock",
        rows=[
            DailySnapshot(
                symbol="AAPL",
                as_of=date(2026, 5, 10),
                momentum_5d=Decimal("0.03"),
                adv_20d=Decimal("12000000000"),
                vol_20d=Decimal("0.10"),
                drawdown_20d=Decimal("0.01"),
                data_quality="OK",
            ),
            DailySnapshot(
                symbol="7203.T",
                as_of=date(2026, 5, 10),
                momentum_5d=Decimal("-0.02"),
                adv_20d=Decimal("500000000"),
                vol_20d=Decimal("0.20"),
                drawdown_20d=Decimal("0.05"),
                data_quality="WARN",
                data_quality_reasons=["partial_data_completeness:0.60"],
            ),
        ],
    )

    scores = ScreeningService().score(snapshot)

    assert [score.symbol for score in scores] == ["AAPL", "7203.T"]
    assert [score.rank for score in scores] == [1, 2]
    assert scores[0].total_score > scores[1].total_score
    assert scores[1].data_quality_score == Decimal("60")
    assert scores[1].summary == (
        "7203.T は中立寄りの候補です。スコア内訳と注意点を確認してください。"
    )
    assert scores[1].reason_labels == ["期待する履歴データのうち 60% 程度しかそろっていません。"]
    assert scores[1].reasons == ["partial_data_completeness:0.60"]


def test_screening_service_uses_neutral_momentum_when_missing():
    snapshot = FeatureSnapshot(
        as_of=date(2026, 5, 10),
        provider="mock",
        rows=[
            DailySnapshot(
                symbol="AAPL",
                as_of=date(2026, 5, 10),
                adv_20d=Decimal("12000000000"),
            )
        ],
    )

    scores = ScreeningService().score(snapshot)

    assert scores[0].momentum_score == Decimal("50.00")
    assert scores[0].reason_labels[0] == ("5日分の値動きデータが足りないため、勢いは中立評価です。")
    assert "neutral_momentum:missing" in scores[0].reasons
