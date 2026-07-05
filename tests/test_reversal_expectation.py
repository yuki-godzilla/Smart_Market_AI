from datetime import date
from decimal import Decimal

from backend.scoring.reversal import calculate_reversal_expectation
from ui.app import (
    _favorite_status_label,
    _investment_score_report_section,
    investment_score_display_rows,
    ranking_result_aggrid_frame,
    ranking_top_candidate_cards,
)
from ui.ranking import RANKING_PRESET_REVERSAL_EXPECTATION, apply_ranking_weight_preset
from ui.ranking_history import build_ranking_history_save_request
from ui.views.cockpit import cockpit_direction_signal_detail_rows, cockpit_kpi_cards
from ui.watchlist_snapshots import (
    WatchlistSnapshot,
    load_watchlist_snapshots,
    save_watchlist_snapshots,
)


def _candidate(**overrides: object) -> dict[str, str]:
    row: dict[str, object] = {
        "symbol": "AAA",
        "total_score": "71",
        "drawdown_20d": "-9",
        "momentum_5d": "-1",
        "forecast_return_pct": "7",
        "up_model_count": "3",
        "down_model_count": "1",
        "upside_signal_score": "65",
        "downside_signal_score": "45",
        "risk_signal_score": "70",
        "volatility_20d": "24",
        "data_quality_score": "82",
        "screening_score": "76",
        "database_fit_score": "80",
        "metadata_confidence_score": "85",
    }
    row.update(overrides)
    return {key: str(value) for key, value in row.items()}


def test_healthy_pullback_with_positive_forecast_scores_highly():
    result = calculate_reversal_expectation(_candidate())
    assert result.reversal_expectation_score >= Decimal("65")
    assert result.reversal_pullback_score >= Decimal("85")


def test_reversal_caps_cover_falling_knife_and_missing_up_models():
    falling_knife = calculate_reversal_expectation(
        _candidate(drawdown_20d="-38", momentum_5d="-10", downside_signal_score="86")
    )
    no_up_models = calculate_reversal_expectation(_candidate(up_model_count="0"))
    assert falling_knife.reversal_expectation_score <= Decimal("45")
    assert no_up_models.reversal_expectation_score <= Decimal("50")


def test_already_rising_candidate_is_capped_and_total_score_is_not_changed():
    row = _candidate(drawdown_20d="-1", momentum_5d="5")
    result = calculate_reversal_expectation(row)
    ranked = apply_ranking_weight_preset([row], RANKING_PRESET_REVERSAL_EXPECTATION, {"AAA": row})
    assert result.reversal_expectation_score <= Decimal("55")
    assert ranked[0]["total_score"] == "71"


def test_reversal_ranking_uses_safety_before_total_score_for_ties():
    first = _candidate(symbol="SAFE", total_score="60")
    second = _candidate(symbol="RISKY", total_score="90", downside_signal_score="60")
    ranked = apply_ranking_weight_preset(
        [second, first],
        RANKING_PRESET_REVERSAL_EXPECTATION,
        {"SAFE": first, "RISKY": second},
    )
    assert [row["symbol"] for row in ranked] == ["SAFE", "RISKY"]
    assert [row["total_score"] for row in ranked] == ["60", "90"]


def test_watchlist_snapshot_round_trips_reversal_fields(tmp_path):
    path = tmp_path / "watchlist.json"
    save_watchlist_snapshots(
        {
            "AAA": WatchlistSnapshot(
                symbol="AAA",
                reversal_expectation_score=72.5,
                reversal_expectation_label="反転期待 中",
                reversal_expectation_reason="下落理由を確認します。",
            )
        },
        path,
    )
    restored = load_watchlist_snapshots(path)["AAA"]
    assert restored.reversal_expectation_score == 72.5
    assert restored.reversal_expectation_label == "反転期待 中"


def test_reversal_fields_flow_to_ranking_cards_table_and_cockpit(monkeypatch):
    ranked = apply_ranking_weight_preset(
        [_candidate()], RANKING_PRESET_REVERSAL_EXPECTATION, {"AAA": _candidate()}
    )
    monkeypatch.setattr("ui.app._symbol_universe_rows_by_symbol", lambda: {})
    display = investment_score_display_rows(ranked)
    cards = ranking_top_candidate_cards(display, ranking_purpose="reversal_expectation", limit=1)
    frame = ranking_result_aggrid_frame(
        display, ranking_purpose="reversal_expectation", include_detail_columns=True
    )
    kpis = cockpit_kpi_cards(display[0])
    details = cockpit_direction_signal_detail_rows(display[0], {})

    assert display[0]["反転期待"]
    assert cards[0]["score_label"] == "反転期待"
    assert cards[0]["score"] == display[0]["反転期待"]
    assert "反転期待" in frame.columns
    assert any(card["label"] == "反転期待" for card in kpis)
    assert any(row["観点"] == "反転期待の内訳" for row in details)


def test_favorite_status_uses_reversal_and_downside_guardrail():
    assert (
        _favorite_status_label(
            price="100", ai_score="60", upside="50", downside="45", reversal="72"
        )
        == "反転期待"
    )
    assert (
        _favorite_status_label(
            price="100", ai_score="60", upside="50", downside="75", reversal="72"
        )
        == "落ちるナイフ注意"
    )


def test_history_and_decision_report_preserve_reversal_context():
    row = {
        "順位": "1",
        "銘柄": "AAA",
        "反転期待": "72.5",
        "反転安全性": "74",
        "反転理由": "下落理由を確認します。",
        "総合スコア": "61",
    }
    request = build_ranking_history_save_request(
        rows=[row],
        filters={"market_data_ranking_region": "japan"},
        provider="mock",
        data_as_of=date(2026, 7, 5),
        start=date(2026, 4, 1),
        end=date(2026, 7, 5),
        ranking_type="reversal_expectation",
        weight_preset=RANKING_PRESET_REVERSAL_EXPECTATION,
        product_type="stock",
        target_label="日本株",
        condition_summary="反転期待",
        candidate_count=1,
        ranking_logic_version="test",
    )
    report = _investment_score_report_section(
        {
            "reversal_expectation_score": "72.5",
            "reversal_expectation_label": "反転期待 中",
            "reversal_expectation_reason": "下落理由を確認します。",
        },
        source_kind="ranking",
        provider="mock",
    )

    assert request.result_rows[0].reversal_expectation_score == 72.5
    assert request.result_rows[0].reversal_expectation_reason == "下落理由を確認します。"
    assert report.summary["reversal_expectation_score"] == "72.5"
