from __future__ import annotations

from pathlib import Path

import ui.app as ui_app
import ui.ranking as ui_ranking
from ui.content import (
    cockpit_texts,
    common_texts,
    ranking_texts,
    research_texts,
    score_texts,
    symbol_texts,
)
from ui.views import cockpit


def test_ui_content_catalogs_are_importable():
    assert score_texts.SCORE_TEXTS
    assert cockpit_texts.COCKPIT_SCORE_EVALUATION_TABLE
    assert ranking_texts.RANKING_PURPOSE_LABELS
    assert ranking_texts.RANKING_CRITERIA_GUIDE_ROWS
    assert symbol_texts.SYMBOL_UNIVERSE_DETAIL_LABELS
    assert common_texts.MARKET_DATA_PERIOD_PRESETS
    assert research_texts.RESEARCH_STATUS_WITH_EVIDENCE == "根拠あり"


def test_score_texts_include_direction_signal_labels():
    assert score_texts.SCORE_TEXTS["upside_signal_score"].label == "上昇気配"
    assert score_texts.SCORE_TEXTS["downside_signal_score"].label == "下降警戒"


def test_score_texts_keep_cockpit_score_forecast_and_risk_guardrails():
    assert "売買指示ではありません" in score_texts.SCORE_TEXTS["investment_score"].description
    assert "将来の保証ではありません" in score_texts.SCORE_TEXTS["forecast_return_pct"].description
    assert "安全保証ではありません" in score_texts.SCORE_TEXTS["risk"].description


def test_ui_modules_reference_content_catalogs():
    assert cockpit.COCKPIT_SCORE_EVALUATION_TABLE is cockpit_texts.COCKPIT_SCORE_EVALUATION_TABLE
    assert ui_ranking.RANKING_PURPOSE_LABELS is ranking_texts.RANKING_PURPOSE_LABELS
    assert ui_ranking.RANKING_WEIGHT_PRESET_LABELS is ranking_texts.RANKING_WEIGHT_PRESET_LABELS
    assert ui_ranking.RANKING_PURPOSE_HELP_TEXTS is ranking_texts.RANKING_PURPOSE_HELP_TEXTS
    assert ui_ranking.RANKING_FILTER_HELP_TEXTS is ranking_texts.RANKING_FILTER_HELP_TEXTS
    assert ui_ranking.RANKING_CRITERIA_GUIDE_ROWS is ranking_texts.RANKING_CRITERIA_GUIDE_ROWS
    assert ranking_texts.RANKING_CHART_PROFILE_TEXTS["upside_downside"]["title"]
    assert ui_app.MARKET_DATA_PERIOD_PRESETS is common_texts.MARKET_DATA_PERIOD_PRESETS
    assert ui_app.SYMBOL_UNIVERSE_DETAIL_LABELS is symbol_texts.SYMBOL_UNIVERSE_DETAIL_LABELS
    assert ui_app.SYMBOL_UNIVERSE_DISPLAY_LABELS is symbol_texts.SYMBOL_UNIVERSE_DISPLAY_LABELS


def test_ranking_texts_keep_criteria_confidence_and_product_guardrails():
    purpose_help = ranking_texts.RANKING_PURPOSE_HELP_TEXTS
    filter_help = ranking_texts.RANKING_FILTER_HELP_TEXTS
    guide_rows = {row["表示"]: row for row in ranking_texts.RANKING_CRITERIA_GUIDE_ROWS}

    assert "投資適合性や安全性" in purpose_help["nisa_long_term"]
    assert "制度上の候補条件" in filter_help["nisa_eligibility"]
    assert "減配" in filter_help["dividend_category"]
    assert "減配" in filter_help["dividend_yield"]
    assert "万能評価や商品適合性" in purpose_help["etf_core_cost"]
    assert "分配金の継続や商品適合性" in purpose_help["etf_income"]
    assert "将来成長の保証ではありません" in purpose_help["growth"]
    assert "投資魅力度ではなく" in guide_rows["条件適合度"]["読み方"]
    assert "投資魅力度ではなく" in guide_rows["DB信頼度"]["読み方"]
    assert "売買推奨ではなく" in guide_rows["評価方針"]["読み方"]


def test_major_ui_code_does_not_directly_use_ng_investment_advice_terms():
    source_paths = [
        Path("ui/app.py"),
        Path("ui/ranking.py"),
        Path("ui/views/cockpit.py"),
        Path("ui/views/news.py"),
        Path("ui/views/ranking_chart_profiles.py"),
    ]
    banned_terms = (
        "買い推奨",
        "売り推奨",
        "上がる銘柄",
        "下がる銘柄",
        "上昇確定",
        "下落確定",
        "必ず上がる",
        "必ず下がる",
    )
    for path in source_paths:
        text = path.read_text(encoding="utf-8")
        assert not set(banned_terms).intersection(text), path
