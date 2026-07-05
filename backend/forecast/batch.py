from __future__ import annotations

from backend.core.data_contracts import Bar
from backend.forecast.advanced_registry import advanced_forecast_adapter_specs
from backend.forecast.service import AdvancedForecastEvaluation, evaluate_advanced_forecast


def evaluate_advanced_forecasts_for_symbol(
    symbol: str,
    bars: list[Bar],
    horizon_days: int,
) -> tuple[str, list[AdvancedForecastEvaluation], str | None]:
    """Evaluate all supported advanced models in a process-safe worker."""

    try:
        results: list[AdvancedForecastEvaluation] = []
        for spec in advanced_forecast_adapter_specs():
            try:
                results.append(
                    evaluate_advanced_forecast(
                        bars,
                        adapter_name=spec.key,
                        horizon_days=horizon_days,
                    )
                )
            except ValueError:
                continue
        return symbol, results, None
    except Exception as exc:  # noqa: BLE001 - one symbol must not stop a broad ranking.
        return symbol, [], type(exc).__name__
