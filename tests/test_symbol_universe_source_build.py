from __future__ import annotations

from datetime import date

from backend.marketdata.symbol_universe_source_build import (
    JPX_LISTED_STOCK_SOURCE_FIELDNAMES,
    build_jpx_listed_stock_source_rows,
)


def test_build_jpx_listed_stock_source_rows_maps_jpx_raw_stock_rows():
    result = build_jpx_listed_stock_source_rows(
        [
            {
                "コード": "7203",
                "銘柄名": "トヨタ自動車",
                "市場・商品区分": "プライム（内国株式）",
                "33業種区分": "輸送用機器",
                "17業種区分": "自動車・輸送機",
                "規模区分": "TOPIX Large70",
            },
            {
                "コード": "9984",
                "銘柄名": "ソフトバンクグループ",
                "市場・商品区分": "プライム（内国株式）",
                "33業種区分": "情報・通信業",
                "17業種区分": "情報通信・サービスその他",
                "規模区分": "TOPIX Core30",
            },
        ],
        as_of=date(2026, 5, 19),
    )

    assert [row["code"] for row in result.rows] == ["7203", "9984"]
    assert result.rows[0] == {
        "code": "7203",
        "security_name": "トヨタ自動車",
        "market": "jp",
        "asset_type": "stock",
        "currency": "JPY",
        "theme": "automotive",
        "sector": "industrial",
        "tags": "balanced",
        "aliases": "トヨタ自動車 プライム（内国株式） 輸送用機器 自動車・輸送機",
        "source_market_segment": "プライム（内国株式）",
        "source_industry_33": "輸送用機器",
        "source_industry_17": "自動車・輸送機",
        "source_scale_category": "TOPIX Large70",
    }
    assert result.rows[1]["theme"] == "technology"
    assert result.rows[1]["tags"] == "growth"
    assert result.manifest["source_kind"] == "jpx_listed_stock"
    assert result.manifest["output_rows"] == 2
    assert result.manifest["fieldnames"] == JPX_LISTED_STOCK_SOURCE_FIELDNAMES


def test_build_jpx_listed_stock_source_rows_skips_out_of_scope_products():
    result = build_jpx_listed_stock_source_rows(
        [
            {
                "コード": "1540",
                "銘柄名": "純金上場信託",
                "市場・商品区分": "ETF・ETN",
                "33業種区分": "",
                "17業種区分": "",
            },
            {
                "コード": "8951",
                "銘柄名": "日本ビルファンド投資法人",
                "市場・商品区分": "REIT・ベンチャーファンド・カントリーファンド・インフラファンド",
                "33業種区分": "",
                "17業種区分": "",
            },
            {
                "コード": "1301",
                "銘柄名": "極洋",
                "市場・商品区分": "スタンダード（内国株式）",
                "33業種区分": "水産・農林業",
                "17業種区分": "食品",
            },
        ],
        as_of=date(2026, 5, 19),
    )

    assert [row["code"] for row in result.rows] == ["1301"]
    assert result.rows[0]["theme"] == "consumer"
    assert result.manifest["input_rows"] == 3
    assert result.manifest["output_rows"] == 1
    assert result.manifest["skipped_rows"] == 2
