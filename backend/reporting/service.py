from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal, Mapping, Sequence

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.core.errors import ValidationAppError

DECISION_REPORT_SCHEMA_VERSION = "decision-report-context-v1"
DECISION_SUPPORT_NOTE = "このレポートは投資判断の補助資料であり、売買推奨ではありません。"

ReportSourceKind = Literal["cockpit", "ranking", "rebalance", "metadata", "manual"]


class DecisionReportSource(StrictBaseModel):
    """Origin metadata for a reusable decision-report section."""

    kind: ReportSourceKind
    provider: str | None = Field(default=None, min_length=1)
    symbol: str | None = Field(default=None, min_length=1)
    as_of: date | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class DecisionReportSection(StrictBaseModel):
    """One reusable block of existing UI/API output for a future report."""

    title: str = Field(min_length=1)
    source: DecisionReportSource
    summary: dict[str, str] = Field(default_factory=dict)
    rows: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DecisionReportContext(StrictBaseModel):
    """Local-first report context shared by API, UI, export, and future assistants."""

    schema_version: str = DECISION_REPORT_SCHEMA_VERSION
    title: str = Field(min_length=1)
    created_at: datetime
    sections: list[DecisionReportSection] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    decision_support_note: str = DECISION_SUPPORT_NOTE


class DecisionReportManifest(StrictBaseModel):
    """Small export manifest for local Decision Report artifacts."""

    schema_version: str = DECISION_REPORT_SCHEMA_VERSION
    created_at: datetime
    title: str
    section_count: int = Field(ge=1)
    sources: list[str]
    files: list[dict[str, str]]
    decision_support_note: str = DECISION_SUPPORT_NOTE


def build_report_section(
    *,
    title: str,
    source_kind: ReportSourceKind,
    provider: str | None = None,
    symbol: str | None = None,
    as_of: date | None = None,
    summary: Mapping[str, object] | None = None,
    rows: Sequence[Mapping[str, object]] | None = None,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
    metadata: dict[str, str] | None = None,
) -> DecisionReportSection:
    """Build a report section from existing table-like UI/API outputs."""

    normalized_summary = _normalize_mapping(summary or {})
    normalized_rows = [_normalize_mapping(row) for row in rows or []]
    normalized_warnings = _normalize_strings(warnings or [])
    normalized_notes = _normalize_strings(notes or [])
    if not (normalized_summary or normalized_rows or normalized_warnings or normalized_notes):
        raise ValidationAppError(
            "Decision report section must include summary, rows, warnings, or notes.",
            details={"title": title, "source_kind": source_kind},
        )

    return DecisionReportSection(
        title=title.strip(),
        source=DecisionReportSource(
            kind=source_kind,
            provider=provider.strip() if provider else None,
            symbol=symbol.strip() if symbol else None,
            as_of=as_of,
            metadata=_normalize_mapping(metadata or {}),
        ),
        summary=normalized_summary,
        rows=normalized_rows,
        warnings=normalized_warnings,
        notes=normalized_notes,
    )


def build_decision_report_context(
    *,
    title: str,
    sections: list[DecisionReportSection],
    created_at: datetime | None = None,
    tags: list[str] | None = None,
) -> DecisionReportContext:
    """Create the reusable context object for a deterministic Decision Report."""

    if not sections:
        raise ValidationAppError("Decision report context requires at least one section.")
    timestamp = created_at or datetime.now(UTC)
    return DecisionReportContext(
        title=title.strip(),
        created_at=timestamp,
        sections=sections,
        tags=_normalize_strings(tags or []),
    )


def build_data_confidence_section(
    *,
    provider: str | None = None,
    symbol: str | None = None,
    as_of: date | None = None,
    price_period: str | None = None,
    data_quality: str | None = None,
    metadata_source: str | None = None,
    metadata_as_of: str | None = None,
    missing_fields: list[str] | None = None,
    coverage_rows: Sequence[Mapping[str, object]] | None = None,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
) -> DecisionReportSection:
    """Build the standard report section for data availability and confidence."""

    summary: dict[str, object] = {
        "provider": provider,
        "price_period": price_period,
        "data_quality": data_quality,
        "metadata_source": metadata_source,
        "metadata_as_of": metadata_as_of,
    }
    normalized_missing = _normalize_strings(missing_fields or [])
    normalized_warnings = _normalize_strings(warnings or [])
    if normalized_missing:
        summary["missing_fields"] = ", ".join(normalized_missing)
        normalized_warnings.append(
            "一部のメタデータは空欄です。0として扱わず、未取得の確認項目として見てください。"
        )
    normalized_notes = _normalize_strings(notes or [])
    normalized_notes.append(
        "未確認のメタデータは、確認済み source または明示 opt-in refresh で取得できるまで空欄のまま保持します。"
    )

    return build_report_section(
        title="データ取得状況と信頼性",
        source_kind="metadata",
        provider=provider,
        symbol=symbol,
        as_of=as_of,
        summary=summary,
        rows=[_normalize_mapping(row) for row in coverage_rows or []],
        warnings=normalized_warnings,
        notes=normalized_notes,
    )


def build_symbol_metadata_section(
    *,
    symbol: str,
    name: str | None = None,
    as_of: date | None = None,
    metadata: Mapping[str, object] | None = None,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
) -> DecisionReportSection:
    """Build the standard report section for local symbol-master attributes."""

    summary: dict[str, object] = {"symbol": symbol, "name": name}
    summary.update(metadata or {})
    return build_report_section(
        title="銘柄メタデータ",
        source_kind="metadata",
        symbol=symbol,
        as_of=as_of,
        summary=summary,
        warnings=warnings,
        notes=notes,
    )


def build_decision_checkpoints_section(
    *,
    checkpoints: Sequence[Mapping[str, object]],
    symbol: str | None = None,
    as_of: date | None = None,
    notes: list[str] | None = None,
) -> DecisionReportSection:
    """Build the standard section for next checks without turning them into advice."""

    if not checkpoints:
        raise ValidationAppError("Decision checkpoints require at least one row.")
    normalized_notes = _normalize_strings(notes or [])
    normalized_notes.append("これらは確認作業を整理するための項目であり、売買指示ではありません。")
    return build_report_section(
        title="確認ポイント",
        source_kind="manual",
        symbol=symbol,
        as_of=as_of,
        rows=[_normalize_mapping(row) for row in checkpoints],
        notes=normalized_notes,
    )


def render_decision_report_markdown(context: DecisionReportContext) -> str:
    """Render a deterministic Markdown report from a Decision Report context."""

    lines = [
        f"# {context.title}",
        "",
        f"- スキーマ: {context.schema_version}",
        f"- 作成日時: {context.created_at.isoformat()}",
        f"- 位置づけ: {context.decision_support_note}",
    ]
    if context.tags:
        lines.append(f"- タグ: {', '.join(context.tags)}")

    for section in context.sections:
        lines.extend(["", f"## {section.title}", ""])
        lines.append(f"- 情報元: {_display_value('source_kind', section.source.kind)}")
        if section.source.provider:
            lines.append(f"- 取得元: {section.source.provider}")
        if section.source.symbol:
            lines.append(f"- 銘柄: {section.source.symbol}")
        if section.source.as_of:
            lines.append(f"- 基準日: {section.source.as_of.isoformat()}")
        for key, value in section.source.metadata.items():
            lines.append(f"- {_display_key(key)}: {_display_value(key, value)}")
        if section.summary:
            lines.extend(["", "### サマリ"])
            lines.extend(
                f"- {_display_key(key)}: {_display_value(key, value)}"
                for key, value in section.summary.items()
            )
        if section.rows:
            lines.extend(["", "### 明細"])
            lines.extend(_markdown_table(section.rows))
        if section.warnings:
            lines.extend(["", "### 注意点"])
            lines.extend(f"- {warning}" for warning in section.warnings)
        if section.notes:
            lines.extend(["", "### 補足"])
            lines.extend(f"- {note}" for note in section.notes)

    return "\n".join(lines) + "\n"


def build_decision_report_manifest(context: DecisionReportContext) -> DecisionReportManifest:
    """Describe local export files that can be produced from the report context."""

    return DecisionReportManifest(
        created_at=context.created_at,
        title=context.title,
        section_count=len(context.sections),
        sources=[section.source.kind for section in context.sections],
        files=[
            {
                "filename": "decision_report_context.json",
                "description": "Structured context used to render the Decision Report.",
            },
            {
                "filename": "decision_report.md",
                "description": "Deterministic Markdown report rendered from local context.",
            },
        ],
    )


def _normalize_mapping(values: Mapping[str, object]) -> dict[str, str]:
    return {
        str(key).strip(): str(value).strip()
        for key, value in values.items()
        if str(key).strip() and value is not None and str(value).strip()
    }


def _normalize_strings(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


def _markdown_table(rows: list[dict[str, str]]) -> list[str]:
    headers: list[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)

    lines = [
        "| " + " | ".join(_display_key(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = [
            _escape_table_cell(_display_value(header, row.get(header, ""))) for header in headers
        ]
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


_DISPLAY_KEY_LABELS = {
    "provider": "取得元",
    "price_period": "取得期間",
    "data_quality": "データ品質",
    "metadata_source": "メタデータ出所",
    "metadata_as_of": "メタデータ基準日",
    "missing_fields": "未取得項目",
    "symbol": "銘柄",
    "name": "銘柄名",
    "market": "市場",
    "asset_type": "商品分類",
    "currency": "通貨",
    "nisa_category": "NISA",
    "investment_style": "投資スタイル",
    "market_cap_tier": "時価総額",
    "broker": "取扱元",
    "tradability": "取扱状況",
    "is_sbi_supported": "SBI対応",
    "metadata_updated_at": "メタデータ更新日時",
    "dividend_yield_pct": "配当利回り",
    "dividend_category": "配当カテゴリ",
    "per": "PER",
    "pbr": "PBR",
    "roe_pct": "ROE",
    "risk_band": "リスク帯",
    "index_family": "連動指数",
    "expense_ratio_pct": "経費率",
    "complexity": "複雑さ",
    "total_score": "総合スコア",
    "score_band": "見方",
    "screening_score": "Screening",
    "forecast_agreement_score": "予測一致",
    "risk_signal_score": "Risk",
    "warnings": "注意点",
    "reasons": "理由",
    "field": "項目",
    "status": "状態",
    "value": "内容",
    "component": "要素",
    "score": "スコア",
    "area": "観点",
    "metric": "指標",
    "finding": "確認内容",
    "confirmation_point": "確認ポイント",
    "rank": "順位",
    "ranking_purpose": "並べ替え方針",
    "display_weight": "表示重み",
    "comparison": "比較条件",
    "reported_rows": "出力行数",
    "note": "補足",
    "review_point": "確認観点",
}

_DISPLAY_VALUE_LABELS = {
    "available": "取得あり",
    "missing": "未取得",
    "cockpit": "銘柄コックピット",
    "ranking": "銘柄ランキング",
    "rebalance": "リバランス",
    "metadata": "銘柄メタデータ",
    "manual": "確認メモ",
}


def _display_key(key: str) -> str:
    return _DISPLAY_KEY_LABELS.get(key, key)


def _display_value(key: str, value: str) -> str:
    if key in {"status", "source_kind"}:
        return _DISPLAY_VALUE_LABELS.get(value, value)
    if key == "field":
        return _display_key(value)
    if key == "component":
        return {
            "Screening": "スクリーニング",
            "Forecast agreement": "予測一致",
            "Data quality": "データ品質",
            "Risk signal": "Risk",
        }.get(value, value)
    if key == "score_band":
        return {
            "STRONG": "強め",
            "BALANCED": "バランス型",
            "CAUTION": "注意",
            "WEAK": "弱め",
        }.get(value, value)
    if key in {"warnings", "reasons"}:
        return _display_reason_codes(value)
    return value


def _display_reason_codes(value: str) -> str:
    replacements = {
        "model_disagreement:high": "モデル見解のばらつき:高",
        "data_quality:warn": "データ品質:注意",
        "forecast_agreement:low": "予測一致:低",
        "risk_signal:caution": "Risk:注意",
        "screening:neutral": "スクリーニング:中立",
        "missing:dividend_yield": "未取得:配当利回り",
        "missing:market_cap_jpy": "未取得:時価総額",
    }
    rendered = value
    for raw, label in replacements.items():
        rendered = rendered.replace(raw, label)
    return rendered
