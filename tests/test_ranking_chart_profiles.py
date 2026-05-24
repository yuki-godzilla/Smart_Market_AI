from __future__ import annotations

from ui.views.ranking_chart_profiles import (
    PROFILE_SCORE_CONFIDENCE,
    PROFILE_SCORE_FORECAST,
    PROFILE_SCORE_RISK,
    chart_profile_for_purpose,
    ranking_chart_frame,
)


def _ranking_rows() -> list[dict[str, str]]:
    return [
        {
            "順位": "1",
            "銘柄": "AAA",
            "銘柄名": "Alpha",
            "総合スコア": "82",
            "Risk": "74",
            "予測一致": "68",
            "DB信頼度": "92",
            "見方": "比較候補",
        },
        {
            "順位": "2",
            "銘柄": "BBB",
            "銘柄名": "Beta",
            "総合スコア": "76",
            "Risk": "55",
            "予測一致": "80",
            "DB信頼度": "90",
            "見方": "比較候補",
        },
        {
            "順位": "3",
            "銘柄": "CCC",
            "銘柄名": "Gamma",
            "総合スコア": "61",
            "Risk": "40",
            "予測一致": "66",
            "DB信頼度": "88",
            "見方": "確認候補",
        },
    ]


def test_chart_profile_for_purpose_maps_data_confidence_to_confidence_chart():
    assert chart_profile_for_purpose("data_confidence").key == PROFILE_SCORE_CONFIDENCE
    assert chart_profile_for_purpose("multi_factor").key == PROFILE_SCORE_RISK


def test_ranking_chart_frame_uses_available_primary_profile_columns():
    selection = ranking_chart_frame(_ranking_rows(), chart_profile_for_purpose("multi_factor"))

    assert selection is not None
    assert selection.profile.key == PROFILE_SCORE_RISK
    assert selection.x_column == "総合スコア"
    assert selection.y_column == "Risk"
    assert selection.used_fallback is False
    assert selection.frame["symbol"].tolist() == ["AAA", "BBB", "CCC"]


def test_ranking_chart_frame_falls_back_when_profile_columns_are_missing():
    selection = ranking_chart_frame(_ranking_rows(), chart_profile_for_purpose("growth"))

    assert selection is not None
    assert selection.profile.key == PROFILE_SCORE_FORECAST
    assert selection.x_column == "総合スコア"
    assert selection.y_column == "予測一致"
    assert selection.used_fallback is True


def test_ranking_chart_frame_returns_none_when_not_enough_rows():
    rows = _ranking_rows()[:2]

    assert ranking_chart_frame(rows, chart_profile_for_purpose("multi_factor")) is None
