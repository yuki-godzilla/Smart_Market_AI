from __future__ import annotations

from ui.views.ranking_chart_profiles import (
    PROFILE_CONFIDENCE_QUALITY,
    PROFILE_ETF_COST_SCORE,
    PROFILE_ETF_FIT_CONFIDENCE,
    PROFILE_SCORE_FORECAST,
    PROFILE_SCREENING_RISK,
    PROFILE_UPSIDE_DOWNSIDE,
    chart_profile_for_purpose,
    ranking_chart_frame,
    ranking_data_quality_gate,
    ranking_reversal_evidence_frame,
)


def _ranking_rows() -> list[dict[str, str]]:
    return [
        {
            "順位": "1",
            "銘柄": "AAA",
            "銘柄名": "Alpha",
            "総合スコア": "82",
            "Screening": "79",
            "Risk": "74",
            "上昇気配": "76",
            "下降警戒": "42",
            "DB信頼度": "92",
            "データ品質": "90",
            "見方": "比較候補",
        },
        {
            "順位": "2",
            "銘柄": "BBB",
            "銘柄名": "Beta",
            "総合スコア": "76",
            "Screening": "72",
            "Risk": "55",
            "上昇気配": "84",
            "下降警戒": "30",
            "DB信頼度": "90",
            "データ品質": "95",
            "見方": "比較候補",
        },
        {
            "順位": "3",
            "銘柄": "CCC",
            "銘柄名": "Gamma",
            "総合スコア": "61",
            "Screening": "64",
            "Risk": "40",
            "上昇気配": "72",
            "下降警戒": "40",
            "DB信頼度": "88",
            "データ品質": "92",
            "見方": "確認候補",
        },
    ]


def test_chart_profile_for_purpose_maps_data_confidence_to_confidence_chart():
    assert chart_profile_for_purpose("data_confidence").key == PROFILE_CONFIDENCE_QUALITY
    assert chart_profile_for_purpose("multi_factor").key == PROFILE_UPSIDE_DOWNSIDE
    assert chart_profile_for_purpose("upside_signal").key == PROFILE_UPSIDE_DOWNSIDE
    assert chart_profile_for_purpose("etf_core_cost").key == PROFILE_ETF_COST_SCORE
    assert chart_profile_for_purpose("etf_income").key == PROFILE_ETF_FIT_CONFIDENCE
    assert chart_profile_for_purpose("reversal_expectation").key == "reversal_expectation"


def test_reversal_chart_uses_pullback_forecast_and_safety():
    rows = [
        {
            "銘柄": f"R{index}",
            "reversal_pullback_score": str(50 + index),
            "reversal_forecast_score": str(60 + index * 2),
            "reversal_safety_score": str(70 + index),
        }
        for index in range(3)
    ]
    selection = ranking_chart_frame(rows, chart_profile_for_purpose("reversal_expectation"))

    assert selection is not None
    assert selection.profile.key == "reversal_expectation"
    assert selection.x_column == "reversal_pullback_score"
    assert selection.y_column == "reversal_forecast_score"
    assert selection.color_column == "reversal_safety_score"


def test_reversal_chart_uses_next_varied_axis_before_falling_back():
    rows = [
        {
            "銘柄": f"R{index}",
            "reversal_pullback_score": "30",
            "20日高値乖離": str(-3 - index),
            "reversal_forecast_score": str(60 + index),
            "reversal_safety_score": str(70 + index),
        }
        for index in range(3)
    ]

    selection = ranking_chart_frame(rows, chart_profile_for_purpose("reversal_expectation"))

    assert selection is not None
    assert selection.profile.key == "reversal_expectation"
    assert selection.x_column == "20日高値乖離"
    assert selection.used_fallback is False


def test_reversal_chart_falls_back_when_technical_axes_are_fixed():
    rows = [
        {
            "銘柄": f"R{index}",
            "reversal_pullback_score": "30",
            "reversal_forecast_score": str(60 + index),
            "上昇気配": str(55 + index),
            "下降警戒": str(45 - index),
            "Risk": str(70 + index),
        }
        for index in range(3)
    ]

    selection = ranking_chart_frame(rows, chart_profile_for_purpose("reversal_expectation"))

    assert selection is not None
    assert selection.profile.key == PROFILE_UPSIDE_DOWNSIDE
    assert selection.x_column == "上昇気配"
    assert selection.y_column == "下降警戒"
    assert selection.used_fallback is True


def test_reversal_evidence_frame_compares_top_ten_components_and_quality_gate():
    rows = [
        {
            "順位": str(index),
            "銘柄": f"R{index}",
            "銘柄名": f"Candidate {index}",
            "上向き兆候": str(90 - index),
            "reversal_chart_shape_score": str(80 - index),
            "reversal_forecast_score": str(70 + index),
            "reversal_safety_score": "75",
            "reversal_pullback_score": "82",
            "reversal_quality_score": "68",
            "reversal_material_score": "60",
            "データ品質": "85" if index != 2 else "55",
            "チャート形状": "押し目反発待ち",
        }
        for index in range(1, 13)
    ]

    frame = ranking_reversal_evidence_frame(rows)

    assert frame["symbol"].nunique() == 10
    assert frame["component"].drop_duplicates().tolist() == [
        "総合",
        "形状",
        "予測余地",
        "下落安全",
        "押し目",
        "補助品質",
        "上向き材料",
    ]
    assert set(frame.loc[frame["symbol"] == "R2", "quality_status"]) == {"要確認"}
    assert "データ品質" not in set(frame["component"])


def test_reversal_data_quality_gate_blocks_unevaluated_rows_without_scoring_attractiveness():
    assert ranking_data_quality_gate({"データ品質": "90"}) == "評価可能"
    assert ranking_data_quality_gate({"データ品質": "55"}) == "要確認"
    assert ranking_data_quality_gate({"データ品質": ""}) == "要確認"
    assert (
        ranking_data_quality_gate(
            {
                "データ品質": "90",
                "reversal_expectation_label": "未評価",
                "warnings_raw": "data_quality:block",
            }
        )
        == "評価対象外"
    )


def test_ranking_chart_frame_uses_available_primary_profile_columns():
    selection = ranking_chart_frame(_ranking_rows(), chart_profile_for_purpose("multi_factor"))

    assert selection is not None
    assert selection.profile.key == PROFILE_UPSIDE_DOWNSIDE
    assert selection.x_column == "上昇気配"
    assert selection.y_column == "下降警戒"
    assert selection.color_column == "Risk"
    assert selection.used_fallback is False
    assert selection.frame["symbol"].tolist() == ["AAA", "BBB", "CCC"]


def test_ranking_chart_frame_falls_back_when_profile_columns_are_missing():
    selection = ranking_chart_frame(_ranking_rows(), chart_profile_for_purpose("growth"))

    assert selection is not None
    assert selection.profile.key == PROFILE_SCORE_FORECAST
    assert selection.x_column == "総合スコア"
    assert selection.y_column == "上昇気配"
    assert selection.used_fallback is True


def test_ranking_chart_frame_uses_upside_downside_profile_for_upside_purpose():
    selection = ranking_chart_frame(
        _ranking_rows(),
        chart_profile_for_purpose("upside_signal"),
    )

    assert selection is not None
    assert selection.profile.key == PROFILE_UPSIDE_DOWNSIDE
    assert selection.x_column == "上昇気配"
    assert selection.y_column == "下降警戒"
    assert selection.color_column == "Risk"
    assert selection.used_fallback is False


def test_ranking_chart_frame_falls_back_when_upside_axes_overlap():
    rows = [
        {
            **row,
            "上昇気配": "50",
            "下降警戒": "50",
        }
        for row in _ranking_rows()
    ]

    selection = ranking_chart_frame(rows, chart_profile_for_purpose("upside_signal"))

    assert selection is not None
    assert selection.profile.key == PROFILE_SCREENING_RISK
    assert selection.x_column == "Screening"
    assert selection.y_column == "Risk"
    assert selection.used_fallback is True


def test_ranking_chart_frame_returns_none_when_not_enough_rows():
    rows = _ranking_rows()[:2]

    assert ranking_chart_frame(rows, chart_profile_for_purpose("multi_factor")) is None
