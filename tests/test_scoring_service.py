from decimal import Decimal

from backend.core.config import ScoringWeightsConfig
from backend.forecast import ForecastConsensus
from backend.scoring import InvestmentScoringService
from backend.screening import ScreeningScore


def test_investment_scoring_service_returns_separate_contract_with_breakdown():
    scores = InvestmentScoringService().score(
        [
            _screening_score(
                symbol="AAPL",
                total_score=Decimal("80"),
                data_quality_score=Decimal("100"),
                data_quality="OK",
                forecast_agreement="HIGH",
            )
        ]
    )

    score = scores[0]
    assert score.symbol == "AAPL"
    assert score.rank == 1
    assert score.total_score == Decimal("85.00")
    assert score.score_band == "STRONG"
    assert score.screening_score == Decimal("80")
    assert score.forecast_agreement_score == Decimal("90")
    assert score.data_quality_score == Decimal("100")
    assert score.risk_signal_score == Decimal("70")
    assert score.decision_support_note == (
        "Decision-support score only; not a buy/sell recommendation."
    )
    assert [component.component for component in score.breakdown] == [
        "screening",
        "forecast_agreement",
        "data_quality",
        "risk_signal",
    ]


def test_investment_scoring_service_surfaces_data_quality_warning_reason():
    scores = InvestmentScoringService().score(
        [
            _screening_score(
                symbol="7203.T",
                total_score=Decimal("55"),
                data_quality_score=Decimal("60"),
                data_quality="WARN",
                reasons=["partial_data_completeness:0.60"],
            )
        ]
    )

    score = scores[0]
    assert score.total_score == Decimal("56.50")
    assert score.score_band == "CAUTION"
    assert "data_quality:warn" in score.reasons
    assert "partial_data_completeness:0.60" in score.reasons
    assert "data_quality:warn" in score.warnings
    data_quality = _breakdown(score, "data_quality")
    assert data_quality.input_score == Decimal("60.00")
    assert data_quality.contribution == Decimal("12.00")


def test_investment_scoring_service_surfaces_model_disagreement_reason():
    forecast = ForecastConsensus(
        symbol="AAPL",
        horizon_days=5,
        model_count=3,
        ensemble_forecast_close=Decimal("108"),
        median_forecast_close=Decimal("107"),
        min_forecast_close=Decimal("100"),
        max_forecast_close=Decimal("116"),
        forecast_range=Decimal("16"),
        forecast_range_pct=Decimal("0.1495"),
        agreement="LOW",
    )

    scores = InvestmentScoringService().score(
        [
            _screening_score(
                symbol="AAPL",
                total_score=Decimal("80"),
                data_quality_score=Decimal("100"),
                data_quality="OK",
                forecast_agreement="HIGH",
            )
        ],
        forecast_consensus_by_symbol={"AAPL": forecast},
    )

    score = scores[0]
    assert score.forecast_agreement == "LOW"
    assert score.forecast_agreement_score == Decimal("40")
    assert score.total_score == Decimal("75.00")
    assert score.score_band == "BALANCED"
    assert "forecast_agreement:low" in score.reasons
    assert "model_disagreement:high" in score.reasons
    assert "model_disagreement:high" in score.warnings
    forecast_component = _breakdown(score, "forecast_agreement")
    assert forecast_component.contribution == Decimal("8.00")


def test_investment_scoring_service_uses_configurable_weights():
    scores = InvestmentScoringService(
        weights=ScoringWeightsConfig(
            screening=0.40,
            forecast_agreement=0.30,
            data_quality=0.20,
            risk_signal=0.10,
        )
    ).score(
        [
            _screening_score(
                symbol="AAPL",
                total_score=Decimal("80"),
                data_quality_score=Decimal("100"),
                data_quality="OK",
                forecast_agreement="HIGH",
            )
        ]
    )

    score = scores[0]
    assert score.total_score == Decimal("86.00")
    assert _breakdown(score, "screening").weight == Decimal("0.4")
    assert _breakdown(score, "forecast_agreement").contribution == Decimal("27.00")


def _breakdown(score, component_name):
    return next(component for component in score.breakdown if component.component == component_name)


def _screening_score(
    *,
    symbol: str,
    total_score: Decimal,
    data_quality_score: Decimal,
    data_quality: str,
    forecast_agreement: str = "",
    reasons: list[str] | None = None,
) -> ScreeningScore:
    return ScreeningScore(
        rank=1,
        symbol=symbol,
        total_score=total_score,
        momentum_score=Decimal("70"),
        liquidity_score=Decimal("70"),
        risk_score=Decimal("70"),
        data_quality_score=data_quality_score,
        forecast_score=Decimal("50"),
        forecast_agreement=forecast_agreement,
        data_quality=data_quality,
        reasons=reasons or [],
    )
