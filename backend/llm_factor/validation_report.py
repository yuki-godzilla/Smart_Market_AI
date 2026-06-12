from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from backend.llm_factor.backtest_contracts import LLMFactorBacktestWarning
from backend.llm_factor.backtest_metrics import (
    build_llm_factor_evaluation_samples,
    compute_baseline_comparison_metrics,
    compute_classification_metrics,
    compute_return_metrics,
    compute_risk_metrics,
    compute_segment_metrics,
    factor_definitions,
    low_evidence_coverage_warning,
)
from backend.llm_factor.validation_contracts import (
    LLMFactorHistoricalFixturePack,
    LLMFactorRecommendationStatus,
    LLMFactorValidationConfig,
    LLMFactorValidationRecommendation,
    LLMFactorValidationReport,
    LLMFactorValidationSummary,
)

NON_INTEGRATION_NOTICE_JA = (
    "本レポートは LLM材料スコアの検証用です。Ranking、Forecast、Investment Score "
    "には反映していません。売買推奨ではありません。"
)


def run_llm_factor_validation_report(
    fixture_pack: LLMFactorHistoricalFixturePack,
    config: LLMFactorValidationConfig,
) -> LLMFactorValidationReport:
    """Build a deterministic validation report for LLM material scores."""

    horizons = _canonical_horizons(config.horizons)
    normalized_config = config.model_copy(update={"horizons": horizons})
    factor_getters = factor_definitions(normalized_config)
    samples_by_horizon, sample_warnings = build_llm_factor_evaluation_samples(
        signals=fixture_pack.signals,
        prices=fixture_pack.prices,
        horizons=horizons,
        entry_lag_bars=normalized_config.entry_lag_bars,
        symbol_segments=fixture_pack.symbol_segments,
    )
    warnings: list[LLMFactorBacktestWarning] = list(sample_warnings)
    classification_metrics, classification_warnings = compute_classification_metrics(
        samples_by_horizon=samples_by_horizon,
        config=normalized_config,
        factor_getters=factor_getters,
    )
    warnings.extend(classification_warnings)
    return_metrics = compute_return_metrics(
        samples_by_horizon=samples_by_horizon,
        signal_count=len(fixture_pack.signals),
        config=normalized_config,
        factor_getters=factor_getters,
    )
    risk_metrics, risk_warnings = compute_risk_metrics(
        samples_by_horizon=samples_by_horizon,
        config=normalized_config,
        factor_getters=factor_getters,
    )
    warnings.extend(risk_warnings)
    baseline_comparison_metrics, baseline_warnings = compute_baseline_comparison_metrics(
        samples_by_horizon=samples_by_horizon,
        baseline_scores=fixture_pack.baseline_scores,
        config=normalized_config,
        factor_getters=factor_getters,
    )
    warnings.extend(baseline_warnings)
    segment_metrics, segment_warnings = compute_segment_metrics(
        samples_by_horizon=samples_by_horizon,
        baseline_scores=fixture_pack.baseline_scores,
        config=normalized_config,
        factor_getters=factor_getters,
    )
    warnings.extend(segment_warnings)
    low_evidence_warning = low_evidence_coverage_warning(
        fixture_pack.signals,
        normalized_config,
    )
    if low_evidence_warning is not None:
        warnings.append(low_evidence_warning)
    test_count = len(factor_getters) * len(horizons) * 4
    if test_count >= 100:
        warnings.append(
            LLMFactorBacktestWarning(
                code="MULTIPLE_TESTING_RISK",
                message=(
                    f"factor_count × horizon_count × metric_family_count = {test_count} です。"
                    "探索的検証として扱い、別期間検証なしに予測モデルへ混ぜないでください。"
                ),
                severity="info",
            )
        )
    warnings.append(
        LLMFactorBacktestWarning(
            code="THRESHOLD_OPTIMIZATION_DISABLED",
            message=(
                "今回の validation report は固定 threshold / 日別 top quantile のみを使い、"
                "同一 validation set 上で threshold 最適化をしていません。"
            ),
            severity="info",
        )
    )
    warnings = _dedupe_and_sort_warnings(warnings)
    summary = _summary(
        fixture_pack=fixture_pack,
        horizons=horizons,
        factor_count=len(factor_getters),
        samples_by_horizon=samples_by_horizon,
        classification_metrics=classification_metrics,
        return_metrics=return_metrics,
        segment_metrics=segment_metrics,
    )
    recommendation = _recommendation(summary)
    report = LLMFactorValidationReport(
        fixture_id=fixture_pack.fixture_id,
        fixture_version=fixture_pack.version,
        config_hash=_hash_payload(normalized_config.model_dump(mode="json")),
        input_hash=_hash_payload(fixture_pack.model_dump(mode="json")),
        generated_report_hash="pending",
        summary=summary,
        classification_metrics=classification_metrics,
        return_metrics=return_metrics,
        risk_metrics=risk_metrics,
        baseline_comparison_metrics=baseline_comparison_metrics,
        segment_metrics=segment_metrics,
        warnings=warnings,
        recommendation=recommendation,
    )
    return report.model_copy(
        update={"generated_report_hash": _report_hash(report)},
    )


def build_llm_factor_validation_report_json(report: LLMFactorValidationReport) -> str:
    """Export the validation report as canonical JSON."""

    return json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def build_llm_factor_validation_report_markdown(report: LLMFactorValidationReport) -> str:
    """Export the validation report as a stable Japanese Markdown summary."""

    top_auc = report.summary.best_factors_by_auc[:5]
    top_return = report.summary.best_factors_by_top_n_return[:5]
    top_drawdown = report.summary.best_factors_by_drawdown_signal[:5]
    warnings = report.warnings[:20]
    lines = [
        "# SMAI LLM Factor Validation Report",
        "",
        "## Fixture summary",
        f"- fixture_id: `{report.fixture_id}`",
        f"- fixture_version: `{report.fixture_version}`",
        f"- input_hash: `{report.input_hash}`",
        f"- config_hash: `{report.config_hash}`",
        f"- report_hash: `{report.generated_report_hash}`",
        f"- symbols: {report.summary.symbol_count}",
        f"- samples: {report.summary.sample_count}",
        f"- dates: {report.summary.date_count}",
        f"- horizons: {', '.join(str(horizon) for horizon in report.summary.horizons)}",
        "",
        "## Scope",
        NON_INTEGRATION_NOTICE_JA,
        "",
        "## Key findings",
        _markdown_list("AUC 上位", top_auc),
        _markdown_list("Top-N return 上位", top_return),
        _markdown_list("Drawdown signal 上位", top_drawdown),
        _markdown_list("効きやすい segment 候補", report.summary.best_segments[:5]),
        _markdown_list("弱い / 過信注意 segment 候補", report.summary.weak_segments[:5]),
        "",
        "## Factor leaderboard",
        *_factor_leaderboard_lines(report),
        "",
        "## Metrics by horizon",
        *_metrics_by_horizon_lines(report),
        "",
        "## Metrics by segment",
        *_segment_lines(report),
        "",
        "## Baseline comparison",
        *_baseline_lines(report),
        "",
        "## Risk metrics",
        *_risk_lines(report),
        "",
        "## Warnings",
        *[
            f"- `{warning.code}`"
            f"{' / ' + warning.factor_name if warning.factor_name else ''}"
            f"{' / h=' + str(warning.horizon_days) if warning.horizon_days else ''}: "
            f"{warning.message}"
            for warning in warnings
        ],
        "",
        "## Recommendation",
        f"- status: `{report.recommendation.status}`",
        *[f"- {reason}" for reason in report.recommendation.reasons],
        "- should_integrate_into_ranking_now: false",
        "- should_integrate_into_forecast_now: false",
        "- should_integrate_into_investment_score_now: false",
        "",
        "## Explicit non-integration note",
        NON_INTEGRATION_NOTICE_JA,
    ]
    return "\n".join(lines).rstrip() + "\n"


def _summary(
    *,
    fixture_pack: LLMFactorHistoricalFixturePack,
    horizons: list[int],
    factor_count: int,
    samples_by_horizon: dict[int, list],
    classification_metrics: list,
    return_metrics: list,
    segment_metrics: list,
) -> LLMFactorValidationSummary:
    unique_samples = {
        (sample.symbol, sample.signal_date)
        for samples in samples_by_horizon.values()
        for sample in samples
    }
    unique_dates = {signal_date for _, signal_date in unique_samples}
    best_auc = [
        _metric_label(metric.factor_name, metric.horizon_days, metric.prediction_task)
        for metric in sorted(
            (metric for metric in classification_metrics if metric.auc is not None),
            key=lambda metric: (
                -(metric.auc or 0),
                metric.factor_name,
                metric.horizon_days,
                metric.prediction_task,
            ),
        )[:8]
    ]
    best_return = [
        _metric_label(metric.factor_name, metric.horizon_days)
        for metric in sorted(
            (metric for metric in return_metrics if metric.top_n_mean_return is not None),
            key=lambda metric: (
                -(metric.top_n_mean_return or 0),
                metric.factor_name,
                metric.horizon_days,
            ),
        )[:8]
    ]
    best_drawdown = [
        _metric_label(metric.factor_name, metric.horizon_days, metric.prediction_task)
        for metric in sorted(
            (
                metric
                for metric in classification_metrics
                if metric.prediction_task == "drawdown" and metric.auc is not None
            ),
            key=lambda metric: (-(metric.auc or 0), metric.factor_name, metric.horizon_days),
        )[:8]
    ]
    segment_scores = _segment_score_summary(segment_metrics)
    best_segments = [
        segment
        for segment, score in sorted(segment_scores.items(), key=lambda item: (-item[1], item[0]))[
            :8
        ]
    ]
    weak_segments = [
        segment
        for segment, score in sorted(segment_scores.items(), key=lambda item: (item[1], item[0]))[
            :8
        ]
    ]
    return LLMFactorValidationSummary(
        sample_count=len(unique_samples),
        symbol_count=len({symbol for symbol, _ in unique_samples}),
        date_count=len(unique_dates),
        segments=fixture_pack.manifest.segments,
        horizons=horizons,
        factor_count=factor_count,
        best_factors_by_auc=best_auc,
        best_factors_by_top_n_return=best_return,
        best_factors_by_drawdown_signal=best_drawdown,
        best_segments=best_segments,
        weak_segments=weak_segments,
    )


def _recommendation(summary: LLMFactorValidationSummary) -> LLMFactorValidationRecommendation:
    status: LLMFactorRecommendationStatus
    if summary.sample_count < 30 or not summary.best_factors_by_auc:
        status = "evidence_insufficient"
        reasons = [
            "検証 sample または分類指標が不足しているため、参考表示の域を出ません。",
            "Ranking / Forecast / Investment Score への統合は行いません。",
        ]
    elif summary.best_factors_by_top_n_return and summary.best_factors_by_drawdown_signal:
        status = "candidate_for_optional_integration_later"
        reasons = [
            "一部 factor で分類・リターン・リスク指標の確認候補が見えます。",
            "ただし synthetic/static fixture による検証であり、実運用統合は後続の別期間検証後に限定します。",
            "現時点では Ranking / Forecast / Investment Score へ統合しません。",
        ]
    else:
        status = "reference_display_only"
        reasons = [
            "有効性は限定的なため、参考表示として扱います。",
            "Ranking / Forecast / Investment Score への統合は行いません。",
        ]
    return LLMFactorValidationRecommendation(status=status, reasons=reasons)


def _segment_score_summary(segment_metrics: list) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for metric in segment_metrics:
        key = f"{metric.segment_name}={metric.segment_value}"
        if metric.top_bottom_spread is not None:
            values[key].append(metric.top_bottom_spread)
        if metric.classification_auc is not None:
            values[key].append(metric.classification_auc - 0.5)
    return {
        key: (sum(items) / len(items) if items else 0.0) for key, items in sorted(values.items())
    }


def _factor_leaderboard_lines(report: LLMFactorValidationReport) -> list[str]:
    rows = sorted(
        (metric for metric in report.classification_metrics if metric.auc is not None),
        key=lambda metric: (-(metric.auc or 0), metric.factor_name, metric.horizon_days),
    )[:10]
    return [
        f"- `{metric.factor_name}` h={metric.horizon_days} task={metric.prediction_task}: "
        f"AUC={_fmt(metric.auc)}, F1={_fmt(metric.f1)}"
        for metric in rows
    ] or ["- no classification metrics"]


def _metrics_by_horizon_lines(report: LLMFactorValidationReport) -> list[str]:
    lines: list[str] = []
    for horizon in report.summary.horizons:
        rows = [metric for metric in report.return_metrics if metric.horizon_days == horizon]
        best = max(
            rows,
            key=lambda metric: (
                metric.top_n_mean_return if metric.top_n_mean_return is not None else -999
            ),
            default=None,
        )
        if best is None:
            lines.append(f"- h={horizon}: no return metrics")
        else:
            lines.append(
                f"- h={horizon}: best `{best.factor_name}` "
                f"Top-N={_fmt(best.top_n_mean_return)}, spread={_fmt(best.top_bottom_spread)}"
            )
    return lines


def _segment_lines(report: LLMFactorValidationReport) -> list[str]:
    rows = sorted(
        report.segment_metrics,
        key=lambda metric: (
            metric.segment_name,
            metric.segment_value,
            metric.factor_name,
            metric.horizon_days,
        ),
    )[:20]
    return [
        f"- `{metric.segment_name}={metric.segment_value}` `{metric.factor_name}` h={metric.horizon_days}: "
        f"AUC={_fmt(metric.classification_auc)}, spread={_fmt(metric.top_bottom_spread)}, "
        f"Sharpe={_fmt(metric.period_sharpe)}"
        for metric in rows
    ] or ["- no segment metrics"]


def _baseline_lines(report: LLMFactorValidationReport) -> list[str]:
    rows = sorted(
        report.baseline_comparison_metrics,
        key=lambda metric: (
            metric.baseline_name,
            metric.factor_name,
            metric.horizon_days,
        ),
    )[:20]
    return [
        f"- `{metric.factor_name}` vs `{metric.baseline_name}` h={metric.horizon_days}: "
        f"delta_auc={_fmt(metric.delta_auc)}, "
        f"delta_top_n={_fmt(metric.delta_top_n_mean_return)}, "
        f"delta_sharpe={_fmt(metric.delta_period_sharpe)}"
        for metric in rows
    ] or ["- baseline scores missing or skipped"]


def _risk_lines(report: LLMFactorValidationReport) -> list[str]:
    rows = sorted(
        report.risk_metrics,
        key=lambda metric: (
            metric.factor_name != "llm_risk_score",
            metric.factor_name,
            metric.horizon_days,
        ),
    )[:20]
    return [
        f"- `{metric.factor_name}` h={metric.horizon_days}: "
        f"period_sharpe={_fmt(metric.top_n_period_sharpe)}, "
        f"max_drawdown={_fmt(metric.top_n_max_drawdown)}, "
        f"vol={_fmt(metric.top_n_volatility)}"
        for metric in rows
    ] or ["- no risk metrics"]


def _markdown_list(title: str, items: list[str]) -> str:
    if not items:
        return f"- {title}: なし"
    return f"- {title}: " + ", ".join(f"`{item}`" for item in items)


def _metric_label(
    factor_name: str,
    horizon_days: int,
    prediction_task: str | None = None,
) -> str:
    suffix = f":{prediction_task}" if prediction_task else ""
    return f"{factor_name}@{horizon_days}d{suffix}"


def _dedupe_and_sort_warnings(
    warnings: list[LLMFactorBacktestWarning],
) -> list[LLMFactorBacktestWarning]:
    unique: dict[tuple[str, str, int, str], LLMFactorBacktestWarning] = {}
    for warning in warnings:
        key = (
            warning.code,
            warning.factor_name or "",
            warning.horizon_days or 0,
            warning.message,
        )
        unique.setdefault(key, warning)
    return [
        unique[key]
        for key in sorted(
            unique,
            key=lambda item: (item[0], item[1], item[2], item[3]),
        )
    ]


def _canonical_horizons(horizons: list[int]) -> list[int]:
    normalized = sorted({horizon for horizon in horizons if horizon > 0})
    return normalized or [1]


def _report_hash(report: LLMFactorValidationReport) -> str:
    payload = report.model_dump(mode="json")
    payload["generated_report_hash"] = ""
    return _hash_payload(payload)


def _hash_payload(payload: object) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _fmt(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.4f}"
