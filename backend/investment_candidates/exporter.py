"""Sequential, failure-tolerant export of existing SMAI ranking presets.

This module intentionally owns no ranking formula.  It filters the existing
symbol universe, calls the caller-supplied existing ranking runner, and writes
analysis artifacts for a user to review outside SMAI.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import subprocess
import time
import zipfile
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ui.ranking import (
    RANKING_PRODUCT_STOCK,
    apply_ranking_weight_preset,
    filter_symbol_universe_rows,
    ranking_period_dates,
    ranking_weight_preset_for_purpose,
)

EXPORT_COLUMNS = (
    "ranking_id", "ranking_name", "ranking_category", "ranking_purpose", "ranking_region", "ranking_period", "generated_at_jst", "rank", "symbol", "company_name", "product_type", "sector", "investment_theme", "currency", "stock_price", "total_score", "screening_score", "fit_score", "decision_policy", "smai_memo", "dividend_yield", "per", "pbr", "roe", "market_cap", "dividend_category", "payout_ratio", "dividend_growth", "free_cash_flow", "revenue_growth", "eps_growth", "operating_margin", "equity_ratio", "earnings_stability", "upside_signal", "upward_indication", "downside_warning", "predicted_change_rate", "forecast_confidence", "forecast_days", "model_direction", "forecast_basis", "risk_score", "risk_band", "volatility", "beta", "drawdown", "downside_signal_score", "data_quality", "data_confidence", "database_confidence", "metadata_confidence", "evidence_status", "research_score", "research_confidence", "news_material", "material_count", "material_confidence", "material_freshness", "latest_document_date", "warning_count", "nisa_eligibility", "investment_style", "caution_notes", "dividend_value_warning", "dividend_value_warning_reason",
)


@dataclass(frozen=True)
class RankingDefinition:
    ranking_id: str
    filename: str
    name: str
    category: str
    region: str
    purpose: str
    period: str
    risk_band: str = "all"
    allowed_risk_bands: tuple[str, ...] = ()
    market_caps: tuple[str, ...] = ()
    dividend_range: tuple[str, str] | None = None
    per_range: tuple[str, str] | None = None
    pbr_range: tuple[str, str] | None = None
    roe_min: str | None = None


def _definition(identifier: str, filename: str, name: str, category: str, region: str, purpose: str, period: str, **filters: Any) -> RankingDefinition:
    return RankingDefinition(identifier, filename, name, category, region, purpose, period, **filters)


RANKING_DEFINITIONS = (
    _definition("01", "01_jp_nisa_long_term_3y.csv", "日本株 NISA長期安定", "stable_income", "japan", "nisa_long_term", "3y", risk_band="standard_or_lower", market_caps=("mega", "large", "mid"), dividend_range=("2.0", "5.0"), per_range=("5", "30"), pbr_range=("0.5", "3.0"), roe_min="8"),
    _definition("02", "02_jp_sustainable_income_3y.csv", "日本株 高配当持続", "stable_income", "japan", "sustainable_income", "3y", risk_band="standard_or_lower", market_caps=("mega", "large", "mid"), dividend_range=("3.0", "5.5"), per_range=("5", "25"), pbr_range=("0.5", "3.0"), roe_min="8"),
    _definition("03", "03_jp_min_volatility_3y.csv", "日本株 低変動・安定", "stable_income", "japan", "min_volatility", "3y", risk_band="standard_or_lower", market_caps=("mega", "large", "mid")),
    _definition("04", "04_us_nisa_long_term_3y.csv", "米国株 NISA長期安定", "stable_income", "us", "nisa_long_term", "3y", risk_band="standard_or_lower", market_caps=("mega", "large", "mid"), dividend_range=("1.5", "4.5"), per_range=("8", "35"), roe_min="10"),
    _definition("05", "05_us_sustainable_income_3y.csv", "米国株 高配当持続", "stable_income", "us", "sustainable_income", "3y", risk_band="standard_or_lower", market_caps=("mega", "large", "mid"), dividend_range=("2.5", "5.5"), per_range=("7", "30"), roe_min="8"),
    _definition("06", "06_us_min_volatility_3y.csv", "米国株 低変動・安定", "stable_income", "us", "min_volatility", "3y", risk_band="standard_or_lower", market_caps=("mega", "large", "mid")),
    _definition("07", "07_jp_quality_growth_3y.csv", "日本株 高品質成長", "growth", "japan", "quality_growth", "3y", market_caps=("mega", "large", "mid"), allowed_risk_bands=("MEDIUM", "HIGH"), per_range=("8", "50"), roe_min="10"),
    _definition("08", "08_jp_small_growth_3y.csv", "日本株 小型・成長探索", "growth", "japan", "small_growth", "3y", market_caps=("small", "mid"), allowed_risk_bands=("MEDIUM", "HIGH"), per_range=("5", "60"), roe_min="8"),
    _definition("09", "09_us_quality_growth_3y.csv", "米国株 高品質成長", "growth", "us", "quality_growth", "3y", market_caps=("mega", "large", "mid"), allowed_risk_bands=("MEDIUM", "HIGH"), per_range=("10", "60"), roe_min="12"),
    _definition("10", "10_us_momentum_1y.csv", "米国株 成長モメンタム", "timing_confirmation", "us", "momentum", "1y", market_caps=("mega", "large", "mid")),
    _definition("11", "11_jp_ai_multi_factor_1y.csv", "日本株 AI総合", "final_confirmation", "japan", "multi_factor", "1y"),
    _definition("12", "12_us_ai_multi_factor_1y.csv", "米国株 AI総合", "final_confirmation", "us", "multi_factor", "1y"),
    _definition("13", "13_jp_upside_signal_1y.csv", "日本株 上昇気配", "timing_confirmation", "japan", "upside_signal", "1y"),
    _definition("14", "14_us_upside_signal_1y.csv", "米国株 上昇気配", "timing_confirmation", "us", "upside_signal", "1y"),
)

RankingRunner = Callable[[list[str], Any, Any, str, Callable[[str, float], None]], tuple[list[dict[str, str]], list[dict[str, str]]]]


def export_investment_candidates(*, output_root: Path, universe_rows: list[dict[str, str]], runner: RankingRunner, top_n: int = 30, fetch_limit: int = 300, now: datetime | None = None, application_version: str = "SMAI") -> dict[str, Any]:
    """Run every definition sequentially and retain partial artifacts on failure."""
    current = (now or datetime.now(UTC)).astimezone()
    stamp = current.strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / stamp
    output_dir.mkdir(parents=True, exist_ok=False)
    combined: list[dict[str, str]] = []
    results: list[dict[str, Any]] = []
    for definition in RANKING_DEFINITIONS:
        started = time.monotonic()
        warnings: list[str] = []
        try:
            candidates = _candidates(definition, universe_rows)[:fetch_limit]
            symbols = [row["symbol"] for row in candidates if row.get("symbol")]
            start, end = ranking_period_dates(definition.period, current.date())
            raw_rows, errors = runner(symbols, start, end, "yahoo", lambda _message, _ratio: None)
            preset = ranking_weight_preset_for_purpose(definition.purpose)
            symbol_map = {row.get("symbol", "").upper(): row for row in candidates}
            ranked = apply_ranking_weight_preset(raw_rows, preset, symbol_map)[:top_n]
            rows = [_export_row(definition, row, symbol_map.get(row.get("symbol", "").upper(), {}), current) for row in ranked]
            warnings.extend(str(item.get("message") or item.get("code") or "ranking warning") for item in errors)
            status = "success"
            error_message = ""
        except Exception as error:  # keep all remaining exports usable
            rows, status, error_message = [], "failed", f"{type(error).__name__}: {error}"
            warnings.append(error_message)
        _write_csv(output_dir / definition.filename, rows, EXPORT_COLUMNS)
        combined.extend(rows)
        results.append({"ranking_id": definition.ranking_id, "ranking_name": definition.name, "status": status, "requested_count": fetch_limit, "exported_count": len(rows), "execution_time_seconds": round(time.monotonic() - started, 3), "applied_filters": _filters(definition), "missing_columns": [], "warnings": warnings, "error_message": error_message})
    _write_csv(output_dir / "all_rankings_combined.csv", combined, EXPORT_COLUMNS)
    overlap = _overlap_rows(combined)
    _write_csv(output_dir / "ranking_overlap_summary.csv", overlap, tuple(overlap[0]) if overlap else ("symbol", "company_name", "region", "appearance_count"))
    summary = {"generated_at_jst": current.isoformat(), "application_version": application_version, "git_commit_sha": _git_sha(), "ranking_count": len(RANKING_DEFINITIONS), "success_count": sum(row["status"] == "success" for row in results), "failure_count": sum(row["status"] == "failed" for row in results), "ranking_results": results, "warnings": [warning for row in results for warning in row["warnings"]], "export_directory": str(output_dir), "zip_file": str(output_dir / f"smai_investment_candidates_{stamp}.zip")}
    (output_dir / "execution_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with zipfile.ZipFile(summary["zip_file"], "w", zipfile.ZIP_DEFLATED) as archive:
        for path in output_dir.glob("*.csv"):
            archive.write(path, path.name)
        archive.write(output_dir / "execution_summary.json", "execution_summary.json")
    return summary


def _candidates(definition: RankingDefinition, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    filtered = filter_symbol_universe_rows(rows, region=definition.region, product_type=RANKING_PRODUCT_STOCK, nisa_eligibility="eligible", risk_band=definition.risk_band, dividend_yield_enabled=definition.dividend_range is not None, min_dividend_yield_pct=(definition.dividend_range or ("0", "20"))[0], dividend_yield_max_pct=(definition.dividend_range or ("0", "20"))[1], per_enabled=definition.per_range is not None, per_min=(definition.per_range or ("0", "999"))[0], per_max=(definition.per_range or ("0", "999"))[1], pbr_enabled=definition.pbr_range is not None, pbr_min=(definition.pbr_range or ("0", "999"))[0], pbr_max=(definition.pbr_range or ("0", "999"))[1], roe_enabled=definition.roe_min is not None, roe_min_pct=definition.roe_min or "-100", roe_max_pct="100", limit=len(rows), apply_universe_policy=True)
    return [row for row in filtered if (not definition.market_caps or row.get("market_cap_tier") in definition.market_caps) and (not definition.allowed_risk_bands or row.get("risk_band") in definition.allowed_risk_bands)]


def _export_row(definition: RankingDefinition, row: Mapping[str, str], symbol_row: Mapping[str, str], current: datetime) -> dict[str, str]:
    def value(*keys: str) -> str:
        return next(
            (
                str(row.get(key) or symbol_row.get(key) or "")
                for key in keys
                if row.get(key) or symbol_row.get(key)
            ),
            "",
        )
    dividend = value("dividend_yield_pct", "配当利回り")
    warning = "" if not dividend or _number(dividend) is not None and 0 <= _number(dividend) <= 20 else "要確認"
    return {column: {"ranking_id": definition.ranking_id, "ranking_name": definition.name, "ranking_category": definition.category, "ranking_purpose": definition.purpose, "ranking_region": definition.region, "ranking_period": definition.period, "generated_at_jst": current.isoformat(), "company_name": value("company_name", "name") or value("symbol"), "product_type": "stock", "sector": value("official_sector", "sector"), "investment_theme": value("investment_theme", "theme"), "currency": value("currency"), "stock_price": value("close", "stock_price"), "total_score": value("total_score", "総合スコア"), "screening_score": value("screening_score", "Screening"), "fit_score": value("database_fit_score", "条件適合度"), "decision_policy": definition.name, "smai_memo": value("note", "smai_memo"), "dividend_yield": dividend, "per": value("per", "PER"), "pbr": value("pbr", "PBR"), "roe": value("roe_pct", "ROE"), "market_cap": value("market_cap", "時価総額"), "dividend_category": value("dividend_category"), "payout_ratio": value("payout_ratio"), "dividend_growth": value("dividend_growth"), "free_cash_flow": value("free_cash_flow"), "revenue_growth": value("revenue_growth"), "eps_growth": value("eps_growth"), "operating_margin": value("operating_margin"), "equity_ratio": value("equity_ratio"), "earnings_stability": value("earnings_stability"), "upside_signal": value("upside_signal", "上昇気配"), "upward_indication": value("direction_signal", "方向一致"), "downside_warning": value("downside_warning", "下降警戒"), "predicted_change_rate": value("predicted_change_rate", "予測変化率"), "forecast_confidence": value("forecast_confidence"), "forecast_days": value("forecast_days"), "model_direction": value("model_direction"), "forecast_basis": value("forecast_basis"), "risk_score": value("risk_score", "Risk"), "risk_band": value("risk_band"), "volatility": value("volatility", "ボラティリティ"), "beta": value("beta"), "drawdown": value("drawdown"), "downside_signal_score": value("downside_signal_score"), "data_quality": value("data_quality", "データ品質"), "data_confidence": value("data_confidence"), "database_confidence": value("database_fit_score", "DB信頼度"), "metadata_confidence": value("metadata_confidence_score", "メタデータ信頼度"), "evidence_status": value("evidence_status", "根拠状態"), "research_score": value("research_score"), "research_confidence": value("research_confidence"), "news_material": value("news_material"), "material_count": value("material_count"), "material_confidence": value("material_confidence"), "material_freshness": value("material_freshness"), "latest_document_date": value("latest_document_date"), "warning_count": str(len([item for item in value("warnings", "注意点").split("|") if item])), "nisa_eligibility": value("nisa_category", "NISA"), "investment_style": value("investment_style", "投資スタイル"), "caution_notes": value("warnings", "注意点"), "dividend_value_warning": warning, "dividend_value_warning_reason": "配当利回りが0%未満・20%超または単位不明" if warning else ""}.get(column, value(column)) for column in EXPORT_COLUMNS}


def _overlap_rows(rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row.get("ranking_region", ""), row.get("symbol", "").upper())].append(row)
    result = []
    for (_, symbol), items in groups.items():
        ranks = [_number(item.get("rank", "")) for item in items]
        ranks = [rank for rank in ranks if rank is not None]
        result.append({"symbol": symbol, "company_name": items[0].get("company_name", symbol), "region": items[0].get("ranking_region", ""), "appearance_count": str(len(items)), "stable_income_appearance_count": str(sum(item.get("ranking_category") == "stable_income" for item in items)), "growth_appearance_count": str(sum(item.get("ranking_category") == "growth" for item in items)), "confirmation_appearance_count": str(sum(item.get("ranking_category") in {"final_confirmation", "timing_confirmation"} for item in items)), "best_rank": _fmt(min(ranks)) if ranks else "", "average_rank": _fmt(statistics.mean(ranks)) if ranks else "", "median_rank": _fmt(statistics.median(ranks)) if ranks else "", "appeared_ranking_names": " | ".join(item.get("ranking_name", "") for item in items), "average_total_score": _mean(items, "total_score"), "average_data_quality": _mean(items, "data_quality"), "average_risk_score": _mean(items, "risk_score"), "average_upside_signal": _mean(items, "upside_signal"), "average_downside_warning": _mean(items, "downside_warning"), "dividend_yield": items[0].get("dividend_yield", ""), "per": items[0].get("per", ""), "pbr": items[0].get("pbr", ""), "roe": items[0].get("roe", ""), "market_cap": items[0].get("market_cap", ""), "sector": items[0].get("sector", ""), "investment_theme": items[0].get("investment_theme", "")})
    return sorted(result, key=lambda row: (-int(row["appearance_count"]), float(row["best_rank"] or 999999), -float(row["average_total_score"] or -1)))


def _write_csv(path: Path, rows: Sequence[Mapping[str, str]], columns: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({key: _safe(value) for key, value in row.items()} for row in rows)


def _filters(definition: RankingDefinition) -> dict[str, Any]:
    return {"region": definition.region, "product_type": "stock", "nisa_eligibility": "eligible", "purpose": definition.purpose, "period": definition.period, "risk_band": definition.risk_band, "allowed_risk_bands": list(definition.allowed_risk_bands), "market_cap_tiers": list(definition.market_caps), "dividend_yield": definition.dividend_range, "per": definition.per_range, "pbr": definition.pbr_range, "roe_min": definition.roe_min}


def _number(value: object) -> float | None:
    try:
        result = float(str(value).replace("%", "").replace(",", ""))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _mean(rows: Sequence[Mapping[str, str]], key: str) -> str:
    values = [number for row in rows if (number := _number(row.get(key, ""))) is not None]
    return _fmt(statistics.mean(values)) if values else ""


def _safe(value: object) -> str:
    return "" if value is None or (isinstance(value, float) and not math.isfinite(value)) else str(value)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""
