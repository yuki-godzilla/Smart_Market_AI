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
    assert symbol_texts.SYMBOL_UNIVERSE_DETAIL_LABELS
    assert common_texts.MARKET_DATA_PERIOD_PRESETS
    assert research_texts.RESEARCH_STATUS_WITH_EVIDENCE == "根拠あり"


def test_score_texts_include_direction_signal_labels():
    assert score_texts.SCORE_TEXTS["upside_signal_score"].label == "上昇気配"
    assert score_texts.SCORE_TEXTS["downside_signal_score"].label == "下降警戒"


def test_ui_modules_reference_content_catalogs():
    assert cockpit.COCKPIT_SCORE_EVALUATION_TABLE is cockpit_texts.COCKPIT_SCORE_EVALUATION_TABLE
    assert ui_ranking.RANKING_PURPOSE_LABELS is ranking_texts.RANKING_PURPOSE_LABELS
    assert ui_ranking.RANKING_WEIGHT_PRESET_LABELS is ranking_texts.RANKING_WEIGHT_PRESET_LABELS
    assert ui_ranking.RANKING_PURPOSE_HELP_TEXTS is ranking_texts.RANKING_PURPOSE_HELP_TEXTS
    assert ui_ranking.RANKING_FILTER_HELP_TEXTS is ranking_texts.RANKING_FILTER_HELP_TEXTS
    assert ranking_texts.RANKING_CHART_PROFILE_TEXTS["upside_downside"]["title"]
    assert ui_app.MARKET_DATA_PERIOD_PRESETS is common_texts.MARKET_DATA_PERIOD_PRESETS
    assert ui_app.SYMBOL_UNIVERSE_DETAIL_LABELS is symbol_texts.SYMBOL_UNIVERSE_DETAIL_LABELS
    assert ui_app.SYMBOL_UNIVERSE_DISPLAY_LABELS is symbol_texts.SYMBOL_UNIVERSE_DISPLAY_LABELS


def test_major_ui_code_does_not_directly_use_ng_investment_advice_terms():
    source_paths = [
        Path("ui/app.py"),
        Path("ui/ranking.py"),
        Path("ui/views/cockpit.py"),
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
