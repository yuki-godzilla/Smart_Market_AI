from __future__ import annotations

from datetime import UTC, date, datetime
from io import BytesIO
from typing import Literal, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.core.errors import ValidationAppError

DECISION_REPORT_SCHEMA_VERSION = "decision-report-context-v1"
DECISION_SUPPORT_NOTE = (
    "このレポートは、ある時点の判断材料、根拠、不確実性、確認ポイントを保存する補助資料であり、"
    "売買推奨ではありません。また、投資助言でもありません。"
)

ReportSourceKind = Literal["cockpit", "ranking", "rebalance", "metadata", "manual", "research"]


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


def build_research_evidence_section(
    *,
    symbol: str,
    as_of: date | None = None,
    summary: str | None = None,
    points: Sequence[Mapping[str, object]] | None = None,
    evidence_rows: Sequence[Mapping[str, object]] | None = None,
    data_quality: Mapping[str, object] | None = None,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
) -> DecisionReportSection:
    """Build a standard Decision Report section for local Research RAG evidence."""

    normalized_summary: dict[str, object] = {
        "symbol": symbol,
        "research_summary": summary,
    }
    if data_quality:
        normalized_summary.update(data_quality)

    rows: list[dict[str, object]] = []
    for point in points or []:
        rows.append({"row_type": "summary_point", **dict(point)})
    for evidence in evidence_rows or []:
        rows.append({"row_type": "evidence", **dict(evidence)})

    normalized_warnings = _normalize_strings(warnings or [])
    data_quality_warnings = data_quality.get("warnings") if data_quality else None
    if isinstance(data_quality_warnings, str) and data_quality_warnings:
        normalized_warnings.append(data_quality_warnings)
    normalized_notes = _normalize_strings(notes or [])
    normalized_notes.append(
        "Research RAG は登録済み資料から確認材料を整理する機能であり、売買推奨ではありません。"
    )

    return build_report_section(
        title="Research Evidence",
        source_kind="research",
        symbol=symbol,
        as_of=as_of,
        summary=normalized_summary,
        rows=rows,
        warnings=normalized_warnings,
        notes=normalized_notes,
    )


def build_external_research_trace_section(
    *,
    symbol: str,
    provider: str,
    fetched_at: datetime,
    retention_policy: str,
    entries: Sequence[Mapping[str, object]],
    as_of: date | None = None,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
) -> DecisionReportSection:
    """Build a trace section for opt-in transient external Research / News sources."""

    rows = [{**dict(entry), "row_type": "external_research_source"} for entry in entries]
    normalized_notes = _normalize_strings(notes or [])
    normalized_notes.append(
        "外部参照ソースはこのセッションの確認材料として一時参照した情報であり、売買推奨ではありません。"
    )
    normalized_notes.append(
        "取得本文は既定では保存せず、Report にはURL、取得元、公開日、取得日時、鮮度、短い要約だけを残します。"
    )

    return build_report_section(
        title="外部参照ソース",
        source_kind="research",
        provider=provider,
        symbol=symbol,
        as_of=as_of,
        summary={
            "symbol": symbol,
            "provider": provider,
            "fetched_at": fetched_at.isoformat(),
            "retention_policy": retention_policy,
            "entry_count": str(len(rows)),
        },
        rows=rows,
        warnings=warnings,
        notes=normalized_notes,
        metadata={"retention_policy": retention_policy},
    )


_RESEARCH_SCORE_COMPONENTS = (
    (
        "growth_score",
        "成長材料",
        "成長戦略や事業拡大の根拠資料がどの程度確認できるかを見ます。",
    ),
    (
        "profitability_score",
        "収益性",
        "利益率、営業利益、ROEなど収益性に関する記述の充実度を見ます。",
    ),
    (
        "shareholder_return_score",
        "株主還元",
        "配当方針や自社株買いなど、株主還元に関する根拠を見ます。",
    ),
    (
        "financial_safety_score",
        "財務安全性",
        "自己資本、現金、流動性など財務余力に関する根拠を見ます。",
    ),
    (
        "business_risk_score",
        "事業リスク確認",
        "為替、規制、競争、供給網などリスク記述が確認できるかを見ます。",
    ),
    (
        "disclosure_quality_score",
        "根拠の充実度",
        "資料数、根拠数、資料種別、信頼度を合わせて見ます。",
    ),
    (
        "freshness_score",
        "情報の鮮度",
        "公開日が古すぎないか、現在の確認材料として扱えるかを見ます。",
    ),
)


def build_research_score_section(
    *,
    symbol: str,
    as_of: date | None = None,
    total_score: object,
    confidence: object,
    evidence_count: object,
    summary: str | None = None,
    component_scores: Mapping[str, object] | None = None,
    supporting_evidence_rows: Sequence[Mapping[str, object]] | None = None,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
) -> DecisionReportSection:
    """Build a Decision Report section for optional evidence-backed Research Score."""

    normalized_summary: dict[str, object] = {
        "symbol": symbol,
        "total_score": total_score,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "research_score_summary": summary,
    }

    rows: list[dict[str, object]] = []
    scores = component_scores or {}
    for key, label, review_point in _RESEARCH_SCORE_COMPONENTS:
        if key in scores:
            rows.append(
                {
                    "row_type": "research_score_component",
                    "component": label,
                    "score": scores[key],
                    "review_point": review_point,
                }
            )
    for evidence in supporting_evidence_rows or []:
        rows.append({"row_type": "research_score_evidence", **dict(evidence)})

    normalized_notes = _normalize_strings(notes or [])
    normalized_notes.append(
        "Research Score は根拠資料の充実度・鮮度・信頼度を整理する参考スコアであり、売買推奨ではありません。"
    )
    normalized_notes.append(
        "資料不足による低スコアは確認不足の警告であり、銘柄評価そのものではありません。"
    )

    return build_report_section(
        title="Research Score",
        source_kind="research",
        symbol=symbol,
        as_of=as_of,
        summary=normalized_summary,
        rows=rows,
        warnings=warnings,
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
        "- 形式: Markdownは人が読むためのメモ、JSON・manifest・ZIPは再現や保存のための形式です。",
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
                "filename": "decision_report_manifest.json",
                "description": "レポート一式に含まれるファイル一覧と用途を示すmanifestです。",
            },
            {
                "filename": "decision_report_context.json",
                "description": "レポートを再現するための構造化contextです。",
            },
            {
                "filename": "decision_report.md",
                "description": "人が読むためのMarkdown形式の判断材料メモです。",
            },
        ],
    )


def decision_report_json_download(context: DecisionReportContext) -> str:
    """Serialize the structured Decision Report context for local download."""

    return context.model_dump_json(indent=2)


def decision_report_manifest_json_download(context: DecisionReportContext) -> str:
    """Serialize the deterministic Decision Report export manifest."""

    manifest = build_decision_report_manifest(context)
    return manifest.model_dump_json(indent=2)


def decision_report_export_files(context: DecisionReportContext) -> dict[str, str]:
    """Return the standard local Decision Report export package."""

    return {
        "decision_report_context.json": decision_report_json_download(context),
        "decision_report_manifest.json": decision_report_manifest_json_download(context),
        "decision_report.md": render_decision_report_markdown(context),
    }


def decision_report_zip_download(context: DecisionReportContext) -> bytes:
    """Return a deterministic ZIP archive containing the standard report package."""

    buffer = BytesIO()
    with ZipFile(buffer, mode="w") as archive:
        for filename, payload in sorted(decision_report_export_files(context).items()):
            info = ZipInfo(filename, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, payload.encode("utf-8"))
    return buffer.getvalue()


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
    "direction_net_score": "互換スコア",
    "upside_signal_score": "上昇気配",
    "downside_signal_score": "下降警戒",
    "direction_signal_label": "互換ラベル",
    "forecast_return_pct": "予測変化率",
    "forecast_agreement_score": "モデル一致度(補助)",
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
    "research_summary": "Research Summary",
    "document_count": "資料数",
    "latest_document_date": "最新資料日",
    "evidence_count": "根拠数",
    "row_type": "行種別",
    "category": "観点",
    "label": "項目",
    "summary": "要約",
    "title": "資料名",
    "source_type": "資料種別",
    "published_at": "公開日",
    "section_title": "セクション",
    "excerpt": "抜粋",
    "relevance_score": "関連度",
    "reliability": "信頼度",
    "research_score_summary": "Research Score メモ",
    "confidence": "信頼度",
    "fetched_at": "取得日時",
    "retention_policy": "保持方針",
    "entry_count": "参照元数",
    "source_url": "URL",
    "freshness_status": "鮮度",
    "content_summary": "短い要約",
}

_DISPLAY_VALUE_LABELS = {
    "available": "取得あり",
    "missing": "未取得",
    "cockpit": "銘柄コックピット",
    "ranking": "銘柄ランキング",
    "rebalance": "リバランス",
    "metadata": "銘柄メタデータ",
    "manual": "確認メモ",
    "research": "Research RAG",
    "summary_point": "要約",
    "evidence": "根拠",
    "grounded_answer": "根拠付き説明",
    "retrieval_quality": "検索品質",
    "extracted_claim": "抽出論点",
    "research_score_component": "Research Score 内訳",
    "research_score_evidence": "Research Score 根拠",
    "external_research_source": "外部参照元",
    "session": "このセッションのみ",
    "archive": "保存済み",
    "latest": "最新",
    "recent": "最近",
    "stale": "古め",
    "unknown": "未確認",
    "annual_report": "有価証券報告書",
    "earnings_report": "決算短信",
    "earnings_presentation": "決算説明資料",
    "medium_term_plan": "中期経営計画",
    "integrated_report": "統合報告書",
    "tdnet": "TDnet",
    "news": "ニュース",
    "provider_profile": "取得元プロフィール",
    "user_note": "ユーザーメモ",
}


def _display_key(key: str) -> str:
    return _DISPLAY_KEY_LABELS.get(key, key)


def _display_value(key: str, value: str) -> str:
    if key in {"status", "source_kind", "row_type"}:
        return _DISPLAY_VALUE_LABELS.get(value, value)
    if key in {"retention_policy", "freshness_status", "source_type"}:
        return _DISPLAY_VALUE_LABELS.get(value, value)
    if key == "field":
        return _display_key(value)
    if key == "component":
        return {
            "Screening": "スクリーニング",
            "Direction Signal": "上昇気配・下降警戒",
            "Forecast agreement": "モデル一致度(補助)",
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
        "forecast_agreement:low": "モデル一致度(補助):低",
        "risk_signal:caution": "Risk:注意",
        "screening:neutral": "スクリーニング:中立",
        "missing:dividend_yield": "未取得:配当利回り",
        "missing:market_cap_jpy": "未取得:時価総額",
    }
    rendered = value
    for raw, label in replacements.items():
        rendered = rendered.replace(raw, label)
    return rendered
