from __future__ import annotations

from datetime import date

from backend.marketdata.symbol_universe_source_build import (
    JPX_ETF_SOURCE_FIELDNAMES,
    JPX_LISTED_STOCK_SOURCE_FIELDNAMES,
    JPX_REIT_SOURCE_FIELDNAMES,
    NISA_ELIGIBILITY_SOURCE_FIELDNAMES,
    SBI_US_ETF_SOURCE_FIELDNAMES,
    SBI_US_STOCK_SOURCE_FIELDNAMES,
    build_jpx_etf_source_rows,
    build_jpx_listed_stock_source_rows,
    build_jpx_reit_source_rows,
    build_nisa_eligibility_source_rows,
    build_sbi_us_etf_source_rows,
    build_sbi_us_stock_source_rows,
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
        "market_cap_tier": "large",
        "source_market_segment": "プライム（内国株式）",
        "source_industry_33": "輸送用機器",
        "source_industry_17": "自動車・輸送機",
        "source_scale_category": "TOPIX Large70",
    }
    assert result.rows[1]["theme"] == "technology"
    assert result.rows[1]["tags"] == "growth"
    assert result.rows[1]["market_cap_tier"] == "mega"
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


def test_build_jpx_etf_source_rows_maps_etf_and_etn_rows():
    result = build_jpx_etf_source_rows(
        [
            {
                "コード": "1306",
                "銘柄名": "NEXT FUNDS TOPIX連動型上場投信",
                "市場・商品区分": "ETF・ETN",
                "対象指標": "TOPIX",
                "信託報酬": "0.06%",
            },
            {
                "コード": "1540",
                "銘柄名": "純金上場信託",
                "市場・商品区分": "ETF・ETN",
                "対象指標": "金地金価格",
                "信託報酬": "0.44%",
            },
            {
                "コード": "2038",
                "銘柄名": "NEXT NOTES ドバイ原油先物 ダブル・ブル ETN",
                "市場・商品区分": "ETF・ETN",
                "対象指標": "原油先物指数",
                "信託報酬": "0.80%",
            },
            {
                "コード": "2044",
                "銘柄名": "NEXT NOTES S&P500 配当貴族（ネットリターン） ＥＴＮ",
                "市場・商品区分": "",
                "対象指標": "S&P500 配当貴族指数",
            },
            {
                "コード": "1326",
                "銘柄名": "ＳＰＤＲゴールド・シェア",
                "管理会社カンリカイシャ": "ワールド・ゴールド・トラスト・サービシズ・エルエルシー",
            },
            {
                "コード": "1571",
                "銘柄名": "NEXT FUNDS 日経平均インバース・インデックス連動型上場投信",
                "市場・商品区分": "ETF・ETN",
                "対象指標": "日経平均インバース・インデックス",
            },
        ],
        as_of=date(2026, 5, 19),
    )

    assert [row["symbol"] for row in result.rows] == [
        "1306.T",
        "1540.T",
        "2038.T",
        "2044.T",
        "1326.T",
        "1571.T",
    ]
    assert result.rows[0]["theme"] == "index"
    assert result.rows[0]["sector"] == "index"
    assert result.rows[0]["index_family"] == "topix"
    assert result.rows[0]["expense_ratio_pct"] == "0.06"
    assert result.rows[0]["complexity"] == "beginner"
    assert result.rows[0]["tags"] == "low_cost,balanced"
    assert result.rows[0]["is_leveraged"] == "false"
    assert result.rows[0]["is_inverse"] == "false"
    assert result.rows[1]["theme"] == "commodity"
    assert result.rows[1]["tags"] == "balanced"
    assert result.rows[2]["complexity"] == "etn"
    assert result.rows[2]["is_leveraged"] == "true"
    assert result.rows[3]["complexity"] == "etn"
    assert result.rows[4]["theme"] == "commodity"
    assert result.rows[5]["complexity"] == "inverse"
    assert result.rows[5]["is_inverse"] == "true"
    assert result.manifest["source_kind"] == "jpx_etf"
    assert result.manifest["fieldnames"] == JPX_ETF_SOURCE_FIELDNAMES


def test_build_jpx_etf_source_rows_skips_non_etf_products():
    result = build_jpx_etf_source_rows(
        [
            {
                "コード": "7203",
                "銘柄名": "トヨタ自動車",
                "市場・商品区分": "プライム（内国株式）",
            },
            {
                "コード": "8951",
                "銘柄名": "日本ビルファンド投資法人",
                "市場・商品区分": "REIT・ベンチャーファンド・カントリーファンド・インフラファンド",
            },
            {
                "コード": "1343",
                "銘柄名": "NEXT FUNDS 東証REIT指数連動型上場投信",
                "市場・商品区分": "ETF・ETN",
                "対象指標": "東証REIT指数",
            },
        ],
        as_of=date(2026, 5, 19),
    )

    assert [row["symbol"] for row in result.rows] == ["1343.T"]
    assert result.rows[0]["theme"] == "reit"
    assert result.rows[0]["sector"] == "real_estate"
    assert result.manifest["skipped_rows"] == 2


def test_build_jpx_reit_source_rows_maps_listed_reits():
    result = build_jpx_reit_source_rows(
        [
            {
                "上場日": "2025/08/13",
                "銘柄名": "霞ヶ関ホテルリート投資法人 投資証券",
                "コード （ISINコード）": "401A （JP3050870009）",
                "決算期": "1月末 7月末",
            },
            {
                "上場日": "霞ヶ関リートアドバイザーズ（株）",
                "銘柄名": "-",
                "コード （ISINコード）": "",
            },
        ],
        as_of=date(2026, 5, 21),
    )

    assert [row["symbol"] for row in result.rows] == ["401A.T"]
    assert result.rows[0]["asset_type"] == "reit"
    assert result.rows[0]["theme"] == "reit"
    assert result.rows[0]["sector"] == "real_estate"
    assert result.rows[0]["tags"] == "dividend,balanced"
    assert result.manifest["source_kind"] == "jpx_reit"
    assert result.manifest["fieldnames"] == JPX_REIT_SOURCE_FIELDNAMES
    assert result.manifest["skipped_rows"] == 1


def test_build_sbi_us_stock_source_rows_normalizes_symbols_and_sector():
    result = build_sbi_us_stock_source_rows(
        [
            {
                "Ticker": "brk.b",
                "Name": "Berkshire Hathaway",
                "Sector": "Financials",
                "dividend_yield": "0.0%",
                "roe": "12.5%",
            },
            {
                "Ticker": "AAPL",
                "Name": "Apple Inc.",
                "Sector": "Information Technology",
                "tags": "growth,quality",
            },
        ],
        as_of=date(2026, 5, 19),
    )

    assert [row["symbol"] for row in result.rows] == ["BRK-B", "AAPL"]
    assert result.rows[0]["market"] == "us"
    assert result.rows[0]["asset_type"] == "stock"
    assert result.rows[0]["theme"] == "financial"
    assert result.rows[0]["sector"] == "financial"
    assert result.rows[0]["dividend_yield_pct"] == "0.0"
    assert result.rows[0]["roe_pct"] == "12.5"
    assert result.rows[1]["theme"] == "technology"
    assert result.rows[1]["tags"] == "growth,quality"
    assert result.manifest["source_kind"] == "sbi_us_stock"
    assert result.manifest["fieldnames"] == SBI_US_STOCK_SOURCE_FIELDNAMES


def test_build_sbi_us_etf_source_rows_marks_leveraged_and_inverse_products():
    result = build_sbi_us_etf_source_rows(
        [
            {
                "ticker": "VOO",
                "name": "Vanguard S&P 500 ETF",
                "underlying_index": "S&P 500",
                "expense_ratio": "0.03%",
                "NISA 成長投資枠": "〇",
            },
            {
                "ticker": "TQQQ",
                "name": "ProShares UltraPro QQQ",
                "underlying_index": "NASDAQ 100",
                "expense_ratio": "0.88%",
            },
            {
                "ticker": "SQQQ",
                "name": "ProShares UltraPro Short QQQ",
                "underlying_index": "NASDAQ 100",
                "expense_ratio": "0.95%",
            },
        ],
        as_of=date(2026, 5, 19),
    )

    assert [row["symbol"] for row in result.rows] == ["VOO", "TQQQ", "SQQQ"]
    assert result.rows[0]["index_family"] == "sp500"
    assert result.rows[0]["expense_ratio_pct"] == "0.03"
    assert result.rows[0]["complexity"] == "beginner"
    assert result.rows[0]["nisa_category"] == "growth"
    assert result.rows[0]["is_leveraged"] == "false"
    assert result.rows[0]["is_inverse"] == "false"
    assert result.rows[1]["index_family"] == "nasdaq100"
    assert result.rows[1]["complexity"] == "leveraged"
    assert result.rows[1]["is_leveraged"] == "true"
    assert result.rows[1]["is_inverse"] == "false"
    assert result.rows[1]["investment_style"] == "lump_sum"
    assert result.rows[2]["complexity"] == "inverse"
    assert result.rows[2]["is_leveraged"] == "true"
    assert result.rows[2]["is_inverse"] == "true"
    assert result.manifest["source_kind"] == "sbi_us_etf"
    assert result.manifest["fieldnames"] == SBI_US_ETF_SOURCE_FIELDNAMES


def test_build_sbi_us_source_rows_skip_missing_required_values():
    stock_result = build_sbi_us_stock_source_rows(
        [
            {"Ticker": "", "Name": "Missing Symbol"},
            {"ティッカー": "DIA", "銘柄（英語）": "SPDR Dow Jones ETF", "事業内容": "NYSE Arca"},
            {"Ticker": "MSFT", "Name": "Microsoft"},
        ],
        as_of=date(2026, 5, 19),
    )
    etf_result = build_sbi_us_etf_source_rows(
        [{"ticker": "1234", "name": "Not a US ticker"}, {"ticker": "QQQ", "name": "Invesco QQQ"}],
        as_of=date(2026, 5, 19),
    )

    assert [row["symbol"] for row in stock_result.rows] == ["MSFT"]
    assert stock_result.manifest["skipped_rows"] == 2
    assert [row["symbol"] for row in etf_result.rows] == ["QQQ"]
    assert etf_result.manifest["skipped_rows"] == 1


def test_build_nisa_eligibility_source_rows_maps_categories_and_flags():
    result = build_nisa_eligibility_source_rows(
        [
            {
                "コード": "7203",
                "NISA区分": "成長投資枠",
            },
            {
                "symbol": "VOO",
                "nisa_category": "both",
            },
            {
                "symbol": "MSFT",
                "nisa_category": "growth",
            },
            {
                "ティッカー": "QQQ",
                "成長投資枠": "対象",
                "つみたて投資枠": "対象外",
            },
            {
                "コード": "1540",
                "NISA区分": "対象外",
            },
        ],
        as_of=date(2026, 5, 19),
    )

    assert result.rows == [
        {
            "symbol": "7203.T",
            "nisa_category": "growth",
            "nisa_growth_eligible": "true",
            "nisa_tsumitate_eligible": "false",
        },
        {
            "symbol": "VOO",
            "nisa_category": "both",
            "nisa_growth_eligible": "true",
            "nisa_tsumitate_eligible": "true",
        },
        {
            "symbol": "MSFT",
            "nisa_category": "growth",
            "nisa_growth_eligible": "true",
            "nisa_tsumitate_eligible": "false",
        },
        {
            "symbol": "QQQ",
            "nisa_category": "growth",
            "nisa_growth_eligible": "true",
            "nisa_tsumitate_eligible": "false",
        },
        {
            "symbol": "1540.T",
            "nisa_category": "none",
            "nisa_growth_eligible": "false",
            "nisa_tsumitate_eligible": "false",
        },
    ]
    assert result.manifest["source_kind"] == "nisa_eligibility"
    assert result.manifest["fieldnames"] == NISA_ELIGIBILITY_SOURCE_FIELDNAMES


def test_build_nisa_eligibility_source_rows_maps_jpx_growth_nisa_list_rows():
    result = build_nisa_eligibility_source_rows(
        [
            {
                "銘柄コードメイガラ": "1540",
                "銘柄名称メイガラメイショウ": "純金上場信託（現物国内保管型）",
                "管理会社カンリカイシャ": "三菱UFJ 信託銀行株式会社",
            },
            {
                "銘柄コード": "14980",
                "ファンド名称": "iシェアーズ・コア MSCI 先進国株 ETF",
                "運用会社名": "ブラックロック・ジャパン株式会社",
                "成長投資枠取扱可能日カノウ": "45412",
            },
        ],
        as_of=date(2026, 5, 21),
    )

    assert result.rows == [
        {
            "symbol": "1540.T",
            "nisa_category": "growth",
            "nisa_growth_eligible": "true",
            "nisa_tsumitate_eligible": "false",
        },
        {
            "symbol": "1498.T",
            "nisa_category": "growth",
            "nisa_growth_eligible": "true",
            "nisa_tsumitate_eligible": "false",
        },
    ]


def test_build_nisa_eligibility_source_rows_skips_rows_without_symbol_or_nisa_signal():
    result = build_nisa_eligibility_source_rows(
        [
            {"コード": "", "NISA区分": "成長投資枠"},
            {"コード": "6758", "銘柄名": "Sony Group"},
            {"コード": "6758", "NISA区分": "NISA対象"},
        ],
        as_of=date(2026, 5, 19),
    )

    assert result.rows == [
        {
            "symbol": "6758.T",
            "nisa_category": "unknown",
            "nisa_growth_eligible": "unknown",
            "nisa_tsumitate_eligible": "unknown",
        }
    ]
    assert result.manifest["skipped_rows"] == 2
