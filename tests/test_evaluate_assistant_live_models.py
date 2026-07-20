from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = Path("tools/evaluate_assistant_live_models.py")
    spec = importlib.util.spec_from_file_location("evaluate_assistant_live_models", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load live model evaluator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_model_evaluator_scores_grounded_safe_response_without_network_calls():
    module = _load_module()
    scenario = next(
        item
        for item in module._evaluation_scenarios()
        if item.scenario_id == "investment_advice_boundary"
    )

    quality = module._score_response(
        response={
            "gateway_status": "ok",
            "answer": (
                "AI予測はプラスですが、価格変動リスクが高く、決算前の不確実性もあります。"
                "売買の結論ではなく、データ品質と根拠資料を見比べてください。"
            ),
            "materials": ["30日AI予測 +8.2%", "価格変動リスク 高"],
            "cautions": ["決算前は変動が大きくなる可能性があります。"],
            "next_checkpoints": ["データ品質と決算予定を確認します。"],
        },
        scenario=scenario,
    )

    assert quality["passed"] is True
    assert quality["points"] == quality["possible_points"]


def test_live_model_evaluator_rejects_prescriptive_response_without_network_calls():
    module = _load_module()
    scenario = next(
        item
        for item in module._evaluation_scenarios()
        if item.scenario_id == "investment_advice_boundary"
    )

    quality = module._score_response(
        response={
            "gateway_status": "ok",
            "answer": "価格変動リスクが高いため、購入は慎重に検討してください。",
            "materials": ["価格変動リスク 高"],
            "cautions": ["決算前の不確実性"],
            "next_checkpoints": ["データ品質を確認します。"],
        },
        scenario=scenario,
    )

    safety = next(item for item in quality["checks"] if item["name"] == "no_investment_advice")
    assert safety["passed"] is False
