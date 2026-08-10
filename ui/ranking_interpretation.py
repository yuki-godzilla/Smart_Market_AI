from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from backend.interpretation import (
    RankingCandidateEvidence,
    RankingInterpretationInput,
    RankingSectorEvidence,
)

_SECTOR_FIELDS = (
    "sector",
    "sector_gics",
    "tse_33_industry",
    "topix_17",
    "industry",
)


@dataclass(frozen=True)
class RankingResultOverviewContext:
    provider: str
    ranking_policy: str
    policy_preset: str
    region: str
    product_type: str
    selected_count: int
    ranking_source: str
    as_of: date
    user_id: str
    forecast_horizon_days: int


def ranking_summary_cards(
    display_rows: Sequence[Mapping[str, object]],
    *,
    ranking_axis: str,
    weight_preset: str,
    region: str,
    product_type: str,
    selected_count: int,
) -> list[dict[str, str]]:
    """Return result quantities; scope labels already appear in the dashboard header."""

    _ = ranking_axis, weight_preset, region, product_type
    scores = [
        score
        for row in display_rows
        if (score := _display_decimal(row.get("総合スコア"))) is not None
    ]
    confidence_values = [
        confidence
        for row in display_rows
        if (confidence := _display_decimal(row.get("DB信頼度"))) is not None
    ]
    average_score = (
        str((sum(scores, Decimal("0")) / Decimal(len(scores))).quantize(Decimal("0.1")))
        if scores
        else "未計算"
    )
    high_confidence_count = sum(
        1 for confidence in confidence_values if confidence >= Decimal("75")
    )
    return [
        {
            "label": "対象銘柄数",
            "value": str(selected_count),
            "help": "現在の条件で取得対象になった銘柄数です。",
        },
        {
            "label": "表示候補数",
            "value": str(len(display_rows)),
            "help": "ランキング結果として表示している比較候補数です。",
        },
        {
            "label": "平均投資スコア",
            "value": average_score,
            "help": "表示候補の総合スコア平均です。売買判断そのものではありません。",
        },
        {
            "label": "データ信頼度高め",
            "value": str(high_confidence_count),
            "help": "DB信頼度が75以上の候補数です。投資魅力度ではなく評価信頼度です。",
        },
    ]


def build_ranking_interpretation_input(
    display_rows: Sequence[Mapping[str, object]],
    candidate_cards: Sequence[Mapping[str, object]],
    *,
    result_id: str,
    as_of: date,
    ranking_policy: str,
    weight_preset: str,
    region: str,
    product_type: str,
    metadata_by_symbol: Mapping[str, Mapping[str, object]] | None = None,
    candidate_count: int | None = None,
    max_candidates: int = 5,
    max_sector_groups: int = 4,
) -> RankingInterpretationInput:
    """Copy only bounded, already-displayed Ranking values into the LLM input."""

    rows_by_symbol = {
        _text(row.get("銘柄")).upper(): row for row in display_rows if _text(row.get("銘柄"))
    }
    candidates: list[RankingCandidateEvidence] = []
    selected_rows: list[Mapping[str, object]] = []
    seen: set[str] = set()
    for card in candidate_cards[:max_candidates]:
        symbol = _text(card.get("symbol")).upper()
        if not symbol or symbol in seen or symbol not in rows_by_symbol:
            continue
        seen.add(symbol)
        row = rows_by_symbol[symbol]
        selected_rows.append(row)
        candidates.append(_candidate_evidence(row, card=card, symbol=symbol))
    if not candidates:
        raise ValueError("ranking_interpretation_candidates_missing")
    sectors = _sector_groups(
        selected_rows,
        metadata_by_symbol=metadata_by_symbol or {},
        max_groups=max_sector_groups,
    )
    warnings = _input_warnings(candidates, sectors)
    return RankingInterpretationInput(
        result_id=result_id,
        as_of=as_of,
        ranking_policy=ranking_policy,
        weight_preset=weight_preset,
        region=region,
        product_type=product_type,
        candidate_count=(len(display_rows) if candidate_count is None else candidate_count),
        candidates=candidates,
        sector_groups=sectors,
        warnings=warnings,
    )


def _candidate_evidence(
    row: Mapping[str, object],
    *,
    card: Mapping[str, object],
    symbol: str,
) -> RankingCandidateEvidence:
    metric_label = _text(card.get("primary_label")) or "総合スコア"
    metric_value = _text(card.get("primary_value")) or _text(card.get("score")) or "未計算"
    forecast_parts = [
        _labeled("予測変化率", row.get("予測変化率")),
        _labeled("高度予測", row.get("高度予測")),
        _labeled("方向一致", row.get("方向一致")),
    ]
    return RankingCandidateEvidence(
        candidate_id=_candidate_id(symbol),
        rank=_positive_int(card.get("rank") or row.get("順位"), fallback=1),
        symbol=symbol,
        company_name=_text(card.get("name") or row.get("銘柄名")) or None,
        primary_metric_id=f"metric:{_stable_slug(metric_label)}",
        primary_metric_label=metric_label,
        primary_metric_value=metric_value,
        total_score=_text(row.get("総合スコア")),
        screening_score=_text(row.get("Screening")),
        upside_signal=_text(row.get("上昇気配")),
        upward_signal=_text(row.get("上向き兆候")),
        downside_warning=_text(row.get("下降警戒")),
        risk_score=_text(row.get("Risk")),
        data_quality=_text(row.get("データ品質")),
        database_fit=_text(row.get("条件適合度")),
        metadata_confidence=_text(row.get("DB信頼度")),
        forecast_summary=" / ".join(item for item in forecast_parts if item),
        reason=_text(card.get("reason")),
        caution=_text(card.get("caution") or row.get("注意点")),
        research_status=_text(card.get("research_status")),
    )


def _sector_groups(
    rows: Sequence[Mapping[str, object]],
    *,
    metadata_by_symbol: Mapping[str, Mapping[str, object]],
    max_groups: int,
) -> list[RankingSectorEvidence]:
    buckets: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        symbol = _text(row.get("銘柄")).upper()
        label = _sector_label(metadata_by_symbol.get(symbol, {}))
        buckets.setdefault(label, []).append(row)
    ordered = sorted(
        buckets.items(),
        key=lambda item: (-len(item[1]), min(_rank(row) for row in item[1]), item[0]),
    )
    result: list[RankingSectorEvidence] = []
    for label, group_rows in ordered[:max_groups]:
        representative = min(group_rows, key=_rank)
        average = _average_display(row.get("総合スコア") for row in group_rows)
        result.append(
            RankingSectorEvidence(
                sector_id=f"sector:{_stable_slug(label)}",
                sector_label=label,
                candidate_count=len(group_rows),
                best_rank=_rank(representative),
                representative_candidate_id=_candidate_id(_text(representative.get("銘柄"))),
                primary_metric_average=average,
                comparison_state="comparable" if len(group_rows) >= 2 else "insufficient",
            )
        )
    return result


def _input_warnings(
    candidates: Sequence[RankingCandidateEvidence],
    sectors: Sequence[RankingSectorEvidence],
) -> list[str]:
    warnings: list[str] = []
    if any(not item.data_quality or item.data_quality == "未計算" for item in candidates):
        warnings.append("一部候補のデータ品質が未計算です。")
    if sectors and all(item.comparison_state == "insufficient" for item in sectors):
        warnings.append("上位候補内で同一セクターがなく、セクター間の数値比較は限定的です。")
    return warnings


def _sector_label(metadata: Mapping[str, object]) -> str:
    for field in _SECTOR_FIELDS:
        value = _text(metadata.get(field))
        if value:
            return value
    return "セクター未登録"


def _candidate_id(symbol: str) -> str:
    return f"ranking_candidate:{_text(symbol).upper()}"


def _rank(row: Mapping[str, object]) -> int:
    return _positive_int(row.get("順位"), fallback=999999)


def _positive_int(value: object, *, fallback: int) -> int:
    match = re.search(r"\d+", _text(value))
    if match:
        parsed = int(match.group())
        if parsed > 0:
            return parsed
    return max(1, fallback)


def _average_display(values: Iterable[object]) -> str | None:
    parsed: list[Decimal] = []
    for value in values:
        match = re.search(r"[-+]?\d+(?:\.\d+)?", _text(value).replace(",", ""))
        if not match:
            continue
        try:
            parsed.append(Decimal(match.group()))
        except InvalidOperation:
            continue
    if not parsed:
        return None
    average = sum(parsed, Decimal("0")) / Decimal(len(parsed))
    return f"{average.quantize(Decimal('0.1'))}"


def _display_decimal(value: object) -> Decimal | None:
    text = _text(value).replace("%", "").replace(",", "")
    if text in {"", "-", "N/A", "未接続", "未登録", "未取得", "取得不可", "異常値"}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _labeled(label: str, value: object) -> str:
    text = _text(value)
    return f"{label} {text}" if text else ""


def _stable_slug(value: str) -> str:
    readable = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if readable:
        return readable[:32]
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _text(value: object) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split()).strip()
