from __future__ import annotations

from typing import Any

import ui.app as app_module
from ui.views.ranking_chart_profiles import chart_profile_for_purpose


class _Expander:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: object) -> None:
        return None


def test_reversal_evidence_renderer_uses_heatmap_without_quality_bubbles(monkeypatch):
    captured: dict[str, Any] = {}
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
            "データ品質": "85",
            "チャート形状": "押し目反発待ち",
        }
        for index in range(1, 4)
    ]

    monkeypatch.setattr(app_module, "render_section_heading", lambda *_: None)
    monkeypatch.setattr(app_module.st, "caption", lambda *_: None)
    monkeypatch.setattr(app_module.st, "info", lambda *_: None)
    monkeypatch.setattr(app_module.st, "expander", lambda *_args, **_kwargs: _Expander())
    monkeypatch.setattr(
        app_module.st,
        "altair_chart",
        lambda chart, **_: captured.update(chart=chart),
    )

    app_module._render_ranking_reversal_evidence_map(
        rows,
        chart_profile_for_purpose("reversal_expectation"),
    )

    specification = captured["chart"].to_dict()
    assert [layer["mark"]["type"] for layer in specification["layer"]] == ["rect", "text"]
    assert "size" not in str(specification)
    assert "data_quality" in str(specification)
