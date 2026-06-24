from __future__ import annotations

from datetime import date

from tools.fetch_sbi_overseas_etf_symbol_universe_source import (
    _normalize_source_row,
    parse_sbi_overseas_etf_html,
)


def test_parse_us_etf_rows() -> None:
    html = """
    <h3>米国ETF</h3>
    <table><thead><tr><th>銘柄コード</th><th>名称</th><th>概要</th><th>市場</th><th>経費率(年)</th><th>ファクトシート等</th><th>運用会社</th><th>NISA<br>成長投資枠</th></tr></thead>
    <tbody><tr><td>AAPU</td><td>Direxion デイリー AAPL 株 ブル 2 倍 ETF</td><td>アップル・インク (NASDAQ: AAPL) の普通株式の日々のパフォーマンスの150％の日々の投資成果を追求する。</td><td>NASDAQ</td><td>0.95%</td><td>-</td><td>Direxion Investments</td><td>〇</td></tr></tbody></table>
    """
    rows = parse_sbi_overseas_etf_html(html, as_of=date(2026, 6, 23), source_url="https://example.test")
    assert len(rows) == 1
    row = rows[0]
    assert row["symbol"] == "AAPU"
    assert row["market"] == "us"
    assert row["exchange"] == "NASDAQ"
    assert row["asset_type"] == "etf"
    assert row["is_leveraged"] == "true"
    assert row["complexity"] == "advanced"
    assert row["risk_band"] == "HIGH"
    assert row["nisa_growth_status"] == "confirmed"
    assert row["nisa_growth_eligible"] == "true"
    assert row["nisa_tsumitate_status"] == "not_supported"
    assert row["nisa_tsumitate_eligible"] == "false"


def test_parse_china_korea_singapore_etfs() -> None:
    html = """
    <h3>中国ETF</h3>
    <table><tr><th>銘柄コード</th><th>名称</th><th>概要</th><th>市場</th><th>経費率(年)</th><th>ファクトシート等</th><th>運用会社</th><th>NISA 成長投資枠</th></tr>
    <tr><td>02800</td><td>トラッカー ファンド オブ ホンコン</td><td>香港ハンセン指数と連動する運用成果を目指します。</td><td>香港市場</td><td>0.08%</td><td>-</td><td>ハンセン</td><td>〇</td></tr></table>
    <h3>韓国ETF</h3>
    <table><tr><th>銘柄コード</th><th>名称</th><th>概要</th><th>市場</th><th>経費率(年)</th><th>ファクトシート等</th><th>運用会社</th><th>NISA 成長投資枠</th></tr>
    <tr><td>069500</td><td>サムスンKODEX200 ETF</td><td>KOSPI 200のパフォーマンスに連動した成果を目指す。</td><td>KOSPI</td><td>0.16%</td><td>-</td><td>サムスン</td><td>〇</td></tr></table>
    <h3>シンガポールETF</h3>
    <table><tr><th>銘柄コード</th><th>名称</th><th>概要</th><th>市場</th><th>経費率(年)</th><th>ファクトシート等</th><th>運用会社</th><th>NISA 成長投資枠</th></tr>
    <tr><td>AMOG</td><td>アモーヴァ シンガポール STI ETF</td><td>FTSEストレーツタイムズ指数にほぼ連動する投資成果を目指す。</td><td>SGX</td><td>0.25%</td><td>-</td><td>アモーヴァ</td><td>〇</td></tr></table>
    """
    rows = parse_sbi_overseas_etf_html(html, as_of=date(2026, 6, 23), source_url="https://example.test")
    symbols = {row["symbol"]: row for row in rows}
    assert symbols["02800.HK"]["yahoo_symbol"] == "2800.HK"
    assert symbols["02800.HK"]["market"] == "hong_kong"
    assert symbols["069500.KS"]["market"] == "korea"
    assert symbols["AMOG.SI"]["market"] == "singapore"
    assert symbols["AMOG.SI"]["yahoo_symbol"] == "A35.SI"
    assert symbols["AMOG.SI"]["yahoo_symbol_status"] == "generated"


def test_parse_reit_and_bond_classification() -> None:
    html = """
    <h3>シンガポールETF</h3>
    <table><tr><th>銘柄コード</th><th>名称</th><th>概要</th><th>市場</th><th>経費率(年)</th><th>運用会社</th><th>NISA 成長投資枠</th></tr>
    <tr><td>CSOP</td><td>CSOP iEdge S-REITリーダーズインデックスETF</td><td>S-REITにアクセスするETF。</td><td>SGX</td><td>0.68%</td><td>CSOP</td><td>〇</td></tr>
    <tr><td>DCSX</td><td>シンガポール国債UCITS ETF</td><td>iBoxx ABF シンガポール国債指数への連動を目指す。</td><td>SGX</td><td>0.20%</td><td>ドイチェ</td><td>〇</td></tr></table>
    """
    rows = parse_sbi_overseas_etf_html(html, as_of=date(2026, 6, 23), source_url="https://example.test")
    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["CSOP.SI"]["asset_class"] == "reit"
    assert by_symbol["CSOP.SI"]["index_family"] == "reit"
    assert by_symbol["DCSX.SI"]["asset_class"] == "bond"
    assert by_symbol["DCSX.SI"]["risk_band"] == "LOW"


def test_income_etf_uses_schema_safe_theme() -> None:
    row = _normalize_source_row(
        {
            "code": "PCEF",
            "name": "Invesco CEF Income Composite ETF",
            "description": "income ETF",
            "source_market": "NASDAQ",
            "expense_ratio_pct": "1.99%",
            "nisa_growth": "",
        },
        section="米国ETF",
        as_of=date(2026, 6, 23),
        source_url="https://example.invalid",
    )
    assert row is not None
    assert row["theme"] == "balanced"
    assert "dividend" in row["tags"]
    assert row["dividend_category"] == "dividend"
