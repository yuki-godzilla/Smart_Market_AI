from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from backend.marketdata.symbol_metadata_refresh import summarize_validation_issues
from backend.marketdata.symbol_metadata_schema import (
    symbol_universe_optional_columns,
    symbol_universe_required_columns,
)

SYMBOL_UNIVERSE_SOURCE_ALIASES = {
    "symbol": ("symbol", "ticker", "code"),
    "name": ("name", "security_name", "company_name", "fund_name"),
    "market": ("market", "region"),
    "asset_type": ("asset_type", "product_type"),
    "currency": ("currency",),
    "country": ("country", "region_name", "国", "国・地域", "取扱国"),
    "exchange": ("exchange", "market_name", "取引所", "市場"),
    "local_symbol": ("local_symbol", "local_code", "現地銘柄コード"),
    "primary_listing_country": ("primary_listing_country", "listing_country", "主上場国"),
    "trading_currency": ("trading_currency", "取引通貨"),
    "settlement_currency": ("settlement_currency", "決済通貨"),
    "quote_currency": ("quote_currency", "価格表示通貨"),
    "fx_pair_to_jpy": ("fx_pair_to_jpy", "円換算FXペア"),
    "foreign_market_group": ("foreign_market_group", "外国株市場グループ"),
    "country_risk_band": ("country_risk_band", "カントリーリスク"),
    "liquidity_tier": ("liquidity_tier", "流動性ランク"),
    "foreign_data_quality": ("foreign_data_quality", "外国株データ品質"),
    "foreign_data_quality_reasons": ("foreign_data_quality_reasons", "外国株データ品質理由"),
    "sbi_foreign_tradability": ("sbi_foreign_tradability", "SBI外国株取扱"),
    "sbi_foreign_tradability_as_of": ("sbi_foreign_tradability_as_of", "SBI外国株取扱確認日"),
    "sbi_foreign_tradability_source": ("sbi_foreign_tradability_source", "SBI外国株取扱確認元"),
    "theme": ("theme", "investment_theme", "テーマ"),
    "sector": ("sector", "industry", "gics_sector", "業種", "セクター"),
    "sector_gics": ("sector_gics", "gics_sector", "source_sector_gics"),
    "industry_gics": ("industry_gics", "gics_industry"),
    "subindustry_gics": ("subindustry_gics", "gics_subindustry"),
    "tse_33_industry": ("tse_33_industry", "source_industry_33", "東証33業種"),
    "topix_17": ("topix_17", "source_industry_17", "TOPIX-17"),
    "smai_theme_tags": ("smai_theme_tags", "investment_theme_tags"),
    "theme_confidence": ("theme_confidence",),
    "theme_source": ("theme_source",),
    "aliases": ("aliases", "search_aliases", "検索別名"),
    "yahoo_symbol": ("yahoo_symbol", "yahoo_ticker", "provider_yahoo_symbol", "Yahoo用銘柄コード"),
    "yahoo_symbol_status": ("yahoo_symbol_status", "yahoo_status", "Yahoo銘柄コード確認状態"),
    "yahoo_symbol_checked_at": ("yahoo_symbol_checked_at", "Yahoo銘柄コード確認日"),
    "yahoo_symbol_note": ("yahoo_symbol_note", "Yahoo銘柄コードメモ"),
    "dividend_category": ("dividend_category", "dividend_type", "配当カテゴリ"),
    "dividend_yield_pct": ("dividend_yield_pct", "dividend_yield", "配当利回り"),
    "market_cap_tier": ("market_cap_tier", "market_cap_size", "時価総額"),
    "market_cap": ("market_cap", "market_cap_value"),
    "index_family": ("index_family", "underlying_index", "benchmark_index", "連動指数"),
    "expense_ratio_pct": ("expense_ratio_pct", "expense_ratio", "経費率", "信託報酬"),
    "complexity": ("complexity", "leverage_type", "複雑さ"),
    "tags": ("tags", "investment_style_tags", "タグ"),
    "per": ("per", "pe_ratio", "PER"),
    "pbr": ("pbr", "price_to_book", "PBR"),
    "roe_pct": ("roe_pct", "roe", "ROE"),
    "consensus_rating": ("consensus_rating", "rating", "コンセンサス"),
    "forecast_agreement": ("forecast_agreement", "予測一致"),
    "data_quality": ("data_quality", "データ品質"),
    "risk_band": ("risk_band", "risk", "リスク"),
    "sbi_tradability_status": ("sbi_tradability_status",),
    "sbi_tradability_verified": ("sbi_tradability_verified",),
    "sbi_tradability_as_of": ("sbi_tradability_as_of",),
    "sbi_tradability_source": ("sbi_tradability_source",),
    "nisa_growth_status": ("nisa_growth_status",),
    "nisa_growth_verified": ("nisa_growth_verified",),
    "nisa_growth_as_of": ("nisa_growth_as_of",),
    "nisa_growth_source": ("nisa_growth_source",),
    "nisa_tsumitate_status": ("nisa_tsumitate_status",),
    "nisa_tsumitate_verified": ("nisa_tsumitate_verified",),
    "nisa_tsumitate_as_of": ("nisa_tsumitate_as_of",),
    "nisa_tsumitate_source": ("nisa_tsumitate_source",),
    "nisa_category": ("nisa_category", "nisa_type", "nisa_eligibility"),
    "trust_fee_pct": ("trust_fee_pct", "trust_fee", "fee_pct"),
    "aum": ("aum", "total_net_assets", "net_assets"),
    "average_volume": ("average_volume", "avg_volume"),
    "asset_class": ("asset_class",),
    "region_exposure": ("region_exposure",),
    "is_hedged": ("is_hedged", "currency_hedged"),
    "nisa_tsumitate_eligible": (
        "nisa_tsumitate_eligible",
        "tsumitate_nisa",
        "tsumitate_eligible",
    ),
    "nisa_growth_eligible": (
        "nisa_growth_eligible",
        "growth_nisa",
        "growth_eligible",
    ),
    "installment_available": ("installment_available", "recurring_available"),
    "management_style": ("management_style", "fund_category"),
    "distribution_policy": ("distribution_policy", "distribution"),
}


@dataclass(frozen=True)
class SymbolUniverseImportFailure:
    """One source row that could not be imported into the symbol universe."""

    source_row: int
    symbol: str
    code: str
    message: str


@dataclass(frozen=True)
class SymbolUniverseImportResult:
    """Proposed symbol-universe rows and manifest details."""

    rows: list[dict[str, str]]
    manifest: dict[str, object]


@dataclass(frozen=True)
class SymbolUniverseImportDefaults:
    """Defaults used when source CSVs omit symbol-universe columns."""

    market: str = ""
    asset_type: str = ""
    currency: str = ""
    symbol_suffix: str = ""
    column_defaults: Mapping[str, str] = field(default_factory=dict)
    update_columns: frozenset[str] = frozenset()
    allow_new_with_update_columns: bool = False


@dataclass(frozen=True)
class SymbolUniverseSourceProfile:
    """Named import defaults for common local source CSVs."""

    name: str
    source_name: str
    defaults: SymbolUniverseImportDefaults


SBI_POLICY_COLUMN_DEFAULTS = {
    "broker": "sbi_securities",
    "is_sbi_supported": "true",
    "is_active": "true",
    "is_leveraged": "false",
    "is_inverse": "false",
}
FOREIGN_STOCK_COMMON_DEFAULTS = {
    **SBI_POLICY_COLUMN_DEFAULTS,
    "tradability": "tradable",
    "sbi_foreign_tradability": "tradable",
    "nisa_category": "unknown",
    "nisa_growth_eligible": "false",
    "nisa_tsumitate_eligible": "false",
    "investment_style": "lump_sum",
    "asset_type": "stock",
    "theme": "balanced",
    "sector": "consumer",
    "complexity": "standard",
    "foreign_data_quality": "WARN",
    "foreign_data_quality_reasons": "new_foreign_source_requires_review",
    "liquidity_tier": "unknown",
    "data_quality": "WARN",
    "risk_band": "standard",
}
MANIFEST_SYMBOL_SAMPLE_LIMIT = 200


def _foreign_stock_profile(
    *,
    name: str,
    market: str,
    currency: str,
    exchange: str,
    country: str,
    group: str,
    country_risk_band: str,
    yahoo_suffix: str = "",
) -> SymbolUniverseSourceProfile:
    return SymbolUniverseSourceProfile(
        name=name,
        source_name=name,
        defaults=SymbolUniverseImportDefaults(
            market=market,
            asset_type="stock",
            currency=currency,
            symbol_suffix=yahoo_suffix,
            column_defaults={
                **FOREIGN_STOCK_COMMON_DEFAULTS,
                "currency": currency,
                "country": country,
                "exchange": exchange,
                "primary_listing_country": country,
                "trading_currency": currency,
                "settlement_currency": currency,
                "quote_currency": currency,
                "fx_pair_to_jpy": "" if currency == "JPY" else f"{currency}JPY",
                "foreign_market_group": group,
                "country_risk_band": country_risk_band,
            },
        ),
    )

SOURCE_PROFILES: dict[str, SymbolUniverseSourceProfile] = {
    "jpx_listed_stock": SymbolUniverseSourceProfile(
        name="jpx_listed_stock",
        source_name="jpx_listed_stock",
        defaults=SymbolUniverseImportDefaults(
            market="jp",
            asset_type="stock",
            currency="JPY",
            symbol_suffix=".T",
            column_defaults={
                **SBI_POLICY_COLUMN_DEFAULTS,
                "tradability": "unknown",
                "nisa_category": "growth",
                "nisa_growth_eligible": "true",
                "nisa_tsumitate_eligible": "false",
                "investment_style": "lump_sum",
            },
        ),
    ),
    "jpx_stock": SymbolUniverseSourceProfile(
        name="jpx_stock",
        source_name="jpx",
        defaults=SymbolUniverseImportDefaults(
            market="jp",
            asset_type="stock",
            currency="JPY",
            symbol_suffix=".T",
            column_defaults={
                **SBI_POLICY_COLUMN_DEFAULTS,
                "tradability": "unknown",
                "nisa_category": "growth",
                "nisa_growth_eligible": "true",
                "nisa_tsumitate_eligible": "false",
                "investment_style": "lump_sum",
            },
        ),
    ),
    "jpx_etf": SymbolUniverseSourceProfile(
        name="jpx_etf",
        source_name="jpx",
        defaults=SymbolUniverseImportDefaults(
            market="jp",
            asset_type="etf",
            currency="JPY",
            column_defaults={
                **SBI_POLICY_COLUMN_DEFAULTS,
                "tradability": "unknown",
                "nisa_category": "unknown",
                "investment_style": "unknown",
                "theme": "index",
                "sector": "index",
                "complexity": "beginner",
                "tags": "low_cost",
            },
            update_columns=frozenset(
                {
                    "theme",
                    "sector",
                    "index_family",
                    "expense_ratio_pct",
                    "complexity",
                    "tags",
                    "aliases",
                    "is_leveraged",
                    "is_inverse",
                    "metadata_source",
                    "metadata_as_of",
                    "metadata_updated_at",
                }
            ),
            allow_new_with_update_columns=True,
        ),
    ),
    "jpx_reit": SymbolUniverseSourceProfile(
        name="jpx_reit",
        source_name="jpx_reit",
        defaults=SymbolUniverseImportDefaults(
            market="jp",
            asset_type="reit",
            currency="JPY",
            column_defaults={
                **SBI_POLICY_COLUMN_DEFAULTS,
                "tradability": "unknown",
                "nisa_category": "unknown",
                "investment_style": "lump_sum",
                "theme": "reit",
                "sector": "real_estate",
                "complexity": "standard",
                "tags": "dividend,balanced",
            },
        ),
    ),
    "sbi_us_stock": SymbolUniverseSourceProfile(
        name="sbi_us_stock",
        source_name="sbi_us_stock",
        defaults=SymbolUniverseImportDefaults(
            market="us",
            asset_type="stock",
            currency="USD",
            column_defaults={
                **SBI_POLICY_COLUMN_DEFAULTS,
                "tradability": "tradable",
                "nisa_category": "growth",
                "nisa_growth_eligible": "true",
                "nisa_tsumitate_eligible": "false",
                "investment_style": "lump_sum",
            },
        ),
    ),
    "sbi_us_etf": SymbolUniverseSourceProfile(
        name="sbi_us_etf",
        source_name="sbi_us_etf",
        defaults=SymbolUniverseImportDefaults(
            market="us",
            asset_type="etf",
            currency="USD",
            column_defaults={
                **SBI_POLICY_COLUMN_DEFAULTS,
                "tradability": "tradable",
                "nisa_category": "unknown",
                "investment_style": "both",
                "theme": "index",
                "sector": "index",
                "complexity": "beginner",
                "tags": "low_cost",
            },
        ),
    ),
    "sbi_hk_stock": _foreign_stock_profile(
        name="sbi_hk_stock",
        market="hong_kong",
        currency="HKD",
        exchange="HKEX",
        country="Hong Kong",
        group="china_hk",
        country_risk_band="MEDIUM",
        yahoo_suffix=".HK",
    ),
    "sbi_korea_stock": _foreign_stock_profile(
        name="sbi_korea_stock",
        market="korea",
        currency="KRW",
        exchange="KRX",
        country="South Korea",
        group="korea",
        country_risk_band="MEDIUM",
        yahoo_suffix=".KS",
    ),
    "sbi_vietnam_stock": _foreign_stock_profile(
        name="sbi_vietnam_stock",
        market="vietnam",
        currency="VND",
        exchange="HOSE",
        country="Vietnam",
        group="asean",
        country_risk_band="HIGH",
        yahoo_suffix=".VN",
    ),
    "sbi_indonesia_stock": _foreign_stock_profile(
        name="sbi_indonesia_stock",
        market="indonesia",
        currency="IDR",
        exchange="IDX",
        country="Indonesia",
        group="asean",
        country_risk_band="HIGH",
        yahoo_suffix=".JK",
    ),
    "sbi_singapore_stock": _foreign_stock_profile(
        name="sbi_singapore_stock",
        market="singapore",
        currency="SGD",
        exchange="SGX",
        country="Singapore",
        group="asean",
        country_risk_band="MEDIUM",
        yahoo_suffix=".SI",
    ),
    "sbi_thailand_stock": _foreign_stock_profile(
        name="sbi_thailand_stock",
        market="thailand",
        currency="THB",
        exchange="SET",
        country="Thailand",
        group="asean",
        country_risk_band="HIGH",
        yahoo_suffix=".BK",
    ),
    "sbi_malaysia_stock": _foreign_stock_profile(
        name="sbi_malaysia_stock",
        market="malaysia",
        currency="MYR",
        exchange="BURSA",
        country="Malaysia",
        group="asean",
        country_risk_band="MEDIUM",
        yahoo_suffix=".KL",
    ),
    "nisa_eligibility": SymbolUniverseSourceProfile(
        name="nisa_eligibility",
        source_name="fsa",
        defaults=SymbolUniverseImportDefaults(
            column_defaults={
                "nisa_category": "unknown",
            },
            update_columns=frozenset(
                {
                    "nisa_category",
                    "nisa_tsumitate_eligible",
                    "nisa_growth_eligible",
                    "nisa_growth_status",
                    "nisa_growth_verified",
                    "nisa_growth_as_of",
                    "nisa_growth_source",
                    "nisa_tsumitate_status",
                    "nisa_tsumitate_verified",
                    "nisa_tsumitate_as_of",
                    "nisa_tsumitate_source",
                    "metadata_source",
                    "metadata_as_of",
                    "metadata_updated_at",
                }
            ),
        ),
    ),
    "sbi_availability": SymbolUniverseSourceProfile(
        name="sbi_availability",
        source_name="sbi_availability",
        defaults=SymbolUniverseImportDefaults(
            update_columns=frozenset(
                {
                    "tradability",
                    "is_sbi_supported",
                    "sbi_tradability_status",
                    "sbi_tradability_verified",
                    "sbi_tradability_as_of",
                    "sbi_tradability_source",
                    "metadata_source",
                    "metadata_as_of",
                    "metadata_updated_at",
                }
            ),
        ),
    ),
    "quality_review": SymbolUniverseSourceProfile(
        name="quality_review",
        source_name="manual",
        defaults=SymbolUniverseImportDefaults(
            update_columns=frozenset(
                {
                    "data_quality",
                    "metadata_source",
                    "metadata_as_of",
                    "metadata_updated_at",
                }
            ),
        ),
    ),
    "ranking_metadata": SymbolUniverseSourceProfile(
        name="ranking_metadata",
        source_name="curated_csv",
        defaults=SymbolUniverseImportDefaults(
            update_columns=frozenset(
                {
                    "theme",
                    "sector",
                    "aliases",
                    "dividend_category",
                    "dividend_yield_pct",
                    "market_cap_tier",
                    "index_family",
                    "expense_ratio_pct",
                    "complexity",
                    "tags",
                    "per",
                    "pbr",
                    "roe_pct",
                    "consensus_rating",
                    "forecast_agreement",
                    "data_quality",
                    "risk_band",
                    "metadata_source",
                    "metadata_as_of",
                    "metadata_updated_at",
                }
            ),
        ),
    ),
    "mutual_fund_seed": SymbolUniverseSourceProfile(
        name="mutual_fund_seed",
        source_name="mutual_fund_seed",
        defaults=SymbolUniverseImportDefaults(
            market="jp",
            asset_type="mutual_fund",
            currency="JPY",
            column_defaults={
                **SBI_POLICY_COLUMN_DEFAULTS,
                "tradability": "unknown",
                "nisa_category": "unknown",
                "investment_style": "recurring",
                "theme": "index",
                "sector": "index",
                "complexity": "standard",
                "tags": "installment,low_cost",
            },
        ),
    ),
}


def symbol_universe_source_profile_names() -> tuple[str, ...]:
    return tuple(SOURCE_PROFILES)


def symbol_universe_source_profile(name: str) -> SymbolUniverseSourceProfile:
    return SOURCE_PROFILES[name]


def symbol_universe_import_fieldnames() -> list[str]:
    """Return the canonical symbol_universe.csv field order."""

    return [
        *symbol_universe_required_columns(),
        *symbol_universe_optional_columns(),
    ]


def merge_symbol_universe_source_rows(
    existing_rows: Sequence[dict[str, str]],
    source_rows: Sequence[dict[str | None, Any]],
    *,
    source_name: str,
    as_of: date,
    updated_at: datetime,
    defaults: SymbolUniverseImportDefaults | None = None,
    update_existing: bool = False,
    dry_run: bool = True,
    validation_before: Sequence[dict[str, str]] | None = None,
    validation_after: Sequence[dict[str, str]] | None = None,
) -> SymbolUniverseImportResult:
    """Merge a local curated source CSV into symbol_universe-shaped rows."""

    effective_defaults = defaults or SymbolUniverseImportDefaults()
    fieldnames = symbol_universe_import_fieldnames()
    proposed_rows = [_complete_existing_row(row, fieldnames) for row in existing_rows]
    row_index_by_symbol = {
        row["symbol"].strip().upper(): index
        for index, row in enumerate(proposed_rows)
        if row.get("symbol", "").strip()
    }

    imported_symbols: list[str] = []
    updated_symbols: list[str] = []
    skipped_existing_symbols: list[str] = []
    failures: list[SymbolUniverseImportFailure] = []
    changed_columns: set[str] = set()

    for source_row_number, source_row in enumerate(source_rows, start=2):
        normalized_row, failure = _source_row_to_symbol_universe_row(
            source_row,
            fieldnames=fieldnames,
            source_name=source_name,
            as_of=as_of,
            updated_at=updated_at,
            defaults=effective_defaults,
            source_row_number=source_row_number,
        )
        if failure is not None:
            failures.append(failure)
            continue

        symbol = normalized_row["symbol"]
        normalized_symbol = symbol.upper()
        existing_index = row_index_by_symbol.get(normalized_symbol)
        if existing_index is None:
            if (
                effective_defaults.update_columns
                and not effective_defaults.allow_new_with_update_columns
            ):
                failures.append(
                    SymbolUniverseImportFailure(
                        source_row=source_row_number,
                        symbol=symbol,
                        code="SYMBOL-UNIVERSE-IMPORT-UNKNOWN-SYMBOL",
                        message=(
                            "symbol is not in the existing symbol universe, "
                            "so update-only source rows cannot be imported."
                        ),
                    )
                )
                continue
            proposed_rows.append(normalized_row)
            row_index_by_symbol[normalized_symbol] = len(proposed_rows) - 1
            imported_symbols.append(symbol)
            changed_columns.update(
                column for column, value in normalized_row.items() if value.strip()
            )
            continue

        if not update_existing:
            skipped_existing_symbols.append(symbol)
            continue

        existing_row = proposed_rows[existing_index]
        row_changed = False
        for column, value in normalized_row.items():
            if column == "symbol":
                continue
            if (
                effective_defaults.update_columns
                and column not in effective_defaults.update_columns
            ):
                continue
            if not value.strip() and column not in _operational_metadata_columns():
                continue
            if existing_row.get(column, "") == value:
                continue
            existing_row[column] = value
            changed_columns.add(column)
            row_changed = True
        if row_changed:
            updated_symbols.append(symbol)

    manifest = {
        "operation": "symbol_universe_source_import",
        "source": source_name,
        "dry_run": dry_run,
        "update_existing": update_existing,
        "defaults": {
            "market": (defaults.market if defaults else ""),
            "asset_type": (defaults.asset_type if defaults else ""),
            "currency": (defaults.currency if defaults else ""),
            "symbol_suffix": (defaults.symbol_suffix if defaults else ""),
        },
        "default_columns": dict(defaults.column_defaults) if defaults else {},
        "update_columns": sorted(defaults.update_columns) if defaults else [],
        "as_of": as_of.isoformat(),
        "updated_at": updated_at.isoformat(),
        "existing_rows": len(existing_rows),
        "source_rows": len(source_rows),
        "total_rows": len(proposed_rows),
        "imported_rows": len(imported_symbols),
        "updated_rows": len(updated_symbols),
        "skipped_existing_rows": len(skipped_existing_symbols),
        "failed_rows": len(failures),
        "manifest_symbol_sample_limit": MANIFEST_SYMBOL_SAMPLE_LIMIT,
        "imported_symbols": _manifest_symbol_sample(imported_symbols),
        "updated_symbols": _manifest_symbol_sample(updated_symbols),
        "skipped_existing_symbols": _manifest_symbol_sample(skipped_existing_symbols),
        "failed_symbols": _manifest_symbol_sample(
            [failure.symbol for failure in failures if failure.symbol]
        ),
        "imported_symbols_truncated": _manifest_symbol_list_truncated(imported_symbols),
        "updated_symbols_truncated": _manifest_symbol_list_truncated(updated_symbols),
        "skipped_existing_symbols_truncated": _manifest_symbol_list_truncated(
            skipped_existing_symbols
        ),
        "failed_symbols_truncated": _manifest_symbol_list_truncated(
            [failure.symbol for failure in failures if failure.symbol]
        ),
        "failures": [
            {
                "source_row": failure.source_row,
                "symbol": failure.symbol,
                "code": failure.code,
                "message": failure.message,
            }
            for failure in failures
        ],
        "changed_columns": sorted(changed_columns),
        "validation_before": summarize_validation_issues(validation_before or []),
        "validation_after": summarize_validation_issues(validation_after or []),
    }
    return SymbolUniverseImportResult(rows=proposed_rows, manifest=manifest)


def _complete_existing_row(
    row: dict[str, str],
    fieldnames: Sequence[str],
) -> dict[str, str]:
    return {column: str(row.get(column, "") or "").strip() for column in fieldnames}


def _source_row_to_symbol_universe_row(
    source_row: dict[str | None, Any],
    *,
    fieldnames: Sequence[str],
    source_name: str,
    as_of: date,
    updated_at: datetime,
    defaults: SymbolUniverseImportDefaults,
    source_row_number: int,
) -> tuple[dict[str, str], SymbolUniverseImportFailure | None]:
    row = {column: _source_value(source_row, column) for column in fieldnames}
    _apply_defaults(row, defaults)
    symbol = _normalize_symbol(row["symbol"], suffix=defaults.symbol_suffix)
    name = row["name"].strip()
    if not symbol:
        return row, SymbolUniverseImportFailure(
            source_row=source_row_number,
            symbol="",
            code="SYMBOL-UNIVERSE-IMPORT-MISSING-SYMBOL",
            message="symbol is required.",
        )
    row["symbol"] = symbol
    if not name and not defaults.update_columns:
        return row, SymbolUniverseImportFailure(
            source_row=source_row_number,
            symbol=symbol,
            code="SYMBOL-UNIVERSE-IMPORT-MISSING-NAME",
            message="name is required.",
        )

    if not row["market"]:
        row["market"] = "jp" if symbol.endswith(".T") else "us"
    if not row["asset_type"]:
        row["asset_type"] = "stock"
    if not row["currency"]:
        row["currency"] = "JPY" if row["market"] == "jp" else "USD"
    if not row.get("local_symbol", ""):
        row["local_symbol"] = _local_symbol_from_provider_symbol(symbol)
    if not row.get("yahoo_symbol", ""):
        row["yahoo_symbol"] = symbol
    if not row.get("yahoo_symbol_status", ""):
        row["yahoo_symbol_status"] = _default_yahoo_symbol_status(row)
    _apply_foreign_operational_defaults(row)
    if not row["theme"] and row["asset_type"] == "etf":
        row["theme"] = "index"
    if not row["sector"] and row["asset_type"] == "etf":
        row["sector"] = "index"
    if not row["complexity"]:
        row["complexity"] = "beginner" if row["asset_type"] == "etf" else "standard"
    if not row["tags"] and row["asset_type"] == "etf":
        row["tags"] = "low_cost"

    row["metadata_source"] = row["metadata_source"] or source_name
    row["metadata_as_of"] = row["metadata_as_of"] or as_of.isoformat()
    row["metadata_updated_at"] = row["metadata_updated_at"] or updated_at.isoformat()
    _apply_reliability_statuses(row, source_name=source_name, as_of=as_of)
    return row, None


def _apply_reliability_statuses(
    row: dict[str, str],
    *,
    source_name: str,
    as_of: date,
) -> None:
    normalized_source = source_name.strip().lower()
    if row.get("is_sbi_supported") in {"true", "false"}:
        is_confirmed = normalized_source.startswith("sbi_")
        row["sbi_tradability_status"] = row.get("sbi_tradability_status") or (
            "confirmed"
            if row["is_sbi_supported"] == "true" and is_confirmed
            else "not_supported" if row["is_sbi_supported"] == "false" else "estimated"
        )
        row["sbi_tradability_verified"] = row.get("sbi_tradability_verified") or (
            "true" if is_confirmed else "false"
        )
        row["sbi_tradability_as_of"] = row.get("sbi_tradability_as_of") or as_of.isoformat()
        row["sbi_tradability_source"] = row.get("sbi_tradability_source") or source_name

    official_nisa_source = normalized_source in {"fsa", "jpx_nisa_growth"}
    category = row.get("nisa_category", "unknown")
    _apply_nisa_status(
        row,
        prefix="nisa_growth",
        eligible=category in {"growth", "both"},
        explicitly_unsupported=category == "none",
        official_source=official_nisa_source,
        source_name=source_name,
        as_of=as_of,
    )
    _apply_nisa_status(
        row,
        prefix="nisa_tsumitate",
        eligible=category in {"tsumitate", "both"},
        explicitly_unsupported=category == "none",
        official_source=official_nisa_source,
        source_name=source_name,
        as_of=as_of,
    )


def _apply_nisa_status(
    row: dict[str, str],
    *,
    prefix: str,
    eligible: bool,
    explicitly_unsupported: bool,
    official_source: bool,
    source_name: str,
    as_of: date,
) -> None:
    if not eligible and not explicitly_unsupported:
        return
    row[f"{prefix}_status"] = row.get(f"{prefix}_status") or (
        "confirmed"
        if eligible and official_source
        else "not_supported" if explicitly_unsupported else "estimated"
    )
    row[f"{prefix}_verified"] = row.get(f"{prefix}_verified") or (
        "true" if official_source else "false"
    )
    row[f"{prefix}_as_of"] = row.get(f"{prefix}_as_of") or as_of.isoformat()
    row[f"{prefix}_source"] = row.get(f"{prefix}_source") or source_name


def _source_value(source_row: dict[str | None, Any], column: str) -> str:
    value = source_row.get(column)
    if value is None or not str(value).strip():
        for alias in SYMBOL_UNIVERSE_SOURCE_ALIASES.get(column, ()):
            value = source_row.get(alias)
            if value is not None and str(value).strip():
                break
    return "" if value is None else str(value).strip()


def _apply_defaults(row: dict[str, str], defaults: SymbolUniverseImportDefaults) -> None:
    if not row["market"] and defaults.market:
        row["market"] = defaults.market
    if not row["asset_type"] and defaults.asset_type:
        row["asset_type"] = defaults.asset_type
    if not row["currency"] and defaults.currency:
        row["currency"] = defaults.currency
    for column, value in defaults.column_defaults.items():
        if column in row and not row[column] and value:
            row[column] = value


def _local_symbol_from_provider_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    for suffix in (".T", ".HK", ".KS", ".KQ", ".VN", ".HM", ".JK", ".SI", ".BK", ".KL"):
        if normalized.endswith(suffix):
            return normalized.removesuffix(suffix)
    return normalized



def _default_yahoo_symbol_status(row: dict[str, str]) -> str:
    reasons = row.get("foreign_data_quality_reasons", "")
    yahoo_symbol = row.get("yahoo_symbol", "").strip()
    symbol = row.get("symbol", "").strip()
    if "yahoo_symbol_unavailable" in reasons:
        return "unavailable"
    if "yahoo_symbol_stale" in reasons:
        return "stale"
    if "yahoo_symbol_requires_review" in reasons:
        return "requires_review"
    if yahoo_symbol and yahoo_symbol != symbol:
        return "confirmed"
    if yahoo_symbol:
        return "generated"
    return "requires_review"

def _apply_foreign_operational_defaults(row: dict[str, str]) -> None:
    currency = row.get("currency", "").strip().upper()
    market = row.get("market", "").strip()
    if not row.get("trading_currency", ""):
        row["trading_currency"] = currency
    if not row.get("settlement_currency", ""):
        row["settlement_currency"] = currency
    if not row.get("quote_currency", ""):
        row["quote_currency"] = currency
    if not row.get("fx_pair_to_jpy", "") and currency not in {"", "JPY"}:
        row["fx_pair_to_jpy"] = f"{currency}JPY"
    if row.get("sbi_foreign_tradability") == "tradable":
        row["sbi_foreign_tradability_as_of"] = row.get("sbi_foreign_tradability_as_of") or row.get("metadata_as_of", "")
        row["sbi_foreign_tradability_source"] = row.get("sbi_foreign_tradability_source") or row.get("metadata_source", "")
    if not row.get("foreign_market_group", ""):
        row["foreign_market_group"] = {
            "jp": "japan",
            "us": "us",
            "hong_kong": "china_hk",
            "china": "china_hk",
            "korea": "korea",
            "vietnam": "asean",
            "indonesia": "asean",
            "singapore": "asean",
            "thailand": "asean",
            "malaysia": "asean",
            "russia": "other_global",
        }.get(market, "unknown")


def _normalize_symbol(symbol: str, *, suffix: str = "") -> str:
    normalized_symbol = symbol.strip().upper()
    normalized_suffix = suffix.strip().upper()
    if (
        normalized_symbol
        and normalized_suffix
        and "." not in normalized_symbol
        and not normalized_symbol.endswith(normalized_suffix)
    ):
        return f"{normalized_symbol}{normalized_suffix}"
    return normalized_symbol


def _operational_metadata_columns() -> set[str]:
    return {"metadata_source", "metadata_as_of", "metadata_updated_at"}


def _manifest_symbol_sample(symbols: Sequence[str]) -> list[str]:
    return list(symbols[:MANIFEST_SYMBOL_SAMPLE_LIMIT])


def _manifest_symbol_list_truncated(symbols: Sequence[str]) -> bool:
    return len(symbols) > MANIFEST_SYMBOL_SAMPLE_LIMIT
