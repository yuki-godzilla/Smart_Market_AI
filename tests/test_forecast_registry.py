import pytest

from backend.forecast import (
    available_forecast_models,
    default_forecast_models,
    forecast_model_display_name,
    forecast_model_registry_rows,
    forecast_model_specs,
)


def test_forecast_model_specs_are_deterministic_and_descriptive():
    specs = forecast_model_specs()

    assert [spec.key for spec in specs] == ["naive", "moving_average", "momentum"]
    assert specs[0].display_name == "予測: 直近値維持"
    assert "平均" in specs[1].description
    assert "値動き" in specs[2].description


def test_default_forecast_models_use_reference_period():
    models = default_forecast_models(reference_period=5)

    assert [model.name for model in models] == ["naive", "moving_average_5", "momentum_5"]
    assert [model.min_history for model in models] == [1, 5, 6]


def test_available_forecast_models_filters_by_history_length():
    assert [model.name for model in available_forecast_models(1, reference_period=3)] == ["naive"]
    assert [model.name for model in available_forecast_models(3, reference_period=3)] == [
        "naive",
        "moving_average_3",
    ]
    assert [model.name for model in available_forecast_models(4, reference_period=3)] == [
        "naive",
        "moving_average_3",
        "momentum_3",
    ]


def test_forecast_model_display_name_handles_dynamic_models():
    assert forecast_model_display_name("naive") == "予測: 直近値維持"
    assert forecast_model_display_name("moving_average_10") == "予測: 10日移動平均"
    assert forecast_model_display_name("momentum_10") == "予測: 10日モメンタム"
    assert forecast_model_display_name("custom") == "custom"


def test_forecast_model_registry_rows_are_ui_ready():
    rows = forecast_model_registry_rows(reference_period=8)

    assert rows == [
        {
            "key": "naive",
            "display_name": "予測: 直近値維持",
            "description": "直近の終値をそのまま予測値として使う基準モデル。",
        },
        {
            "key": "moving_average",
            "display_name": "予測: 8日移動平均",
            "description": "直近の参照期間の平均終値を予測値として使う基準モデル。",
        },
        {
            "key": "momentum",
            "display_name": "予測: 8日モメンタム",
            "description": "直近の参照期間の値動きを延長する基準モデル。",
        },
    ]


def test_forecast_model_registry_rejects_invalid_reference_period():
    with pytest.raises(ValueError, match="reference_period must be at least 1"):
        default_forecast_models(reference_period=0)
