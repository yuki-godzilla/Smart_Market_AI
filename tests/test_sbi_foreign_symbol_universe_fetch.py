from __future__ import annotations

from datetime import date

from tools.fetch_sbi_foreign_symbol_universe_sources import parse_sbi_foreign_list_html


def test_parse_hk_official_table_builds_yahoo_symbol_and_sector() -> None:
    html = """
    <html><body>
      <h3>普通株式一覧</h3>
      <table>
        <tr><th>コード</th><th>銘柄名（カナ）</th><th>銘柄名（漢字）</th><th>会社概要</th><th>市場</th><th>業種</th></tr>
        <tr><td>00700</td><td>テンセント</td><td>騰訊控股</td><td>インターネットサービス</td><td>メインボード</td><td>通信・技術</td></tr>
        <tr><td>00005</td><td>HSBC</td><td>匯豊控股</td><td>総合金融グループ</td><td>メインボード</td><td>銀行</td></tr>
      </table>
    </body></html>
    """
    rows = parse_sbi_foreign_list_html(
        html,
        source_kind="sbi_hk_stock",
        as_of=date(2026, 6, 23),
        source_url="https://example.test/hk.html",
    )

    assert [row["symbol"] for row in rows] == ["00700.HK", "00005.HK"]
    assert [row["yahoo_symbol"] for row in rows] == ["0700.HK", "0005.HK"]
    assert rows[0]["sector"] == "technology"
    assert rows[1]["sector"] == "financial"
    assert rows[0]["sbi_tradability_status"] == "confirmed"
    assert rows[0]["risk_band"] == "MEDIUM"
    assert rows[0]["complexity"] == "standard"
    assert rows[0]["tags"] == "technology"
    assert rows[0]["market_cap_tier"] == ""


def test_parse_korea_kosdaq_uses_kq_suffix() -> None:
    html = """
    <html><body>
      <h3>韓国株式一覧</h3>
      <table>
        <tr><th>コード</th><th>銘柄</th><th>会社概要</th><th>市場</th></tr>
        <tr><td>005930</td><td>サムスン電子</td><td>総合電機メーカー</td><td>KOSPI</td></tr>
        <tr><td>950170</td><td>ジェイティーシー</td><td>免税店を運営</td><td>KOSDAQ</td></tr>
      </table>
    </body></html>
    """
    rows = parse_sbi_foreign_list_html(
        html,
        source_kind="sbi_korea_stock",
        as_of=date(2026, 6, 23),
        source_url="https://example.test/kr.html",
    )

    assert rows[0]["symbol"] == "005930.KS"
    assert rows[0]["yahoo_symbol"] == "005930.KS"
    assert rows[1]["symbol"] == "950170.KQ"
    assert rows[1]["yahoo_symbol"] == "950170.KQ"


def test_parse_singapore_etf_section_marks_etf_and_review_yahoo() -> None:
    html = """
    <html><body>
      <h3>ETF銘柄一覧</h3>
      <table>
        <tr><th>コード</th><th>（取引所コード）</th><th>銘柄</th><th>連動指数</th><th>市場</th></tr>
        <tr><td>AMOE</td><td>（G3B）</td><td>Amova Singapore STI ETF</td><td>FTSEストレーツタイムズ指数に連動</td><td>メインボード</td></tr>
      </table>
    </body></html>
    """
    rows = parse_sbi_foreign_list_html(
        html,
        source_kind="sbi_singapore_stock",
        as_of=date(2026, 6, 23),
        source_url="https://example.test/sg.html",
    )

    assert rows[0]["asset_type"] == "etf"
    assert rows[0]["sector"] == "index"
    assert rows[0]["theme"] == "index"
    assert rows[0]["index_family"] == "singapore_equity"
    assert rows[0]["tags"] == "index"
    assert rows[0]["risk_band"] == "MEDIUM"
    assert rows[0]["yahoo_symbol"] == "G3B.SI"
    assert rows[0]["yahoo_symbol_status"] == "generated"


def test_ranking_tags_use_comma_separator() -> None:
    from tools.fetch_sbi_foreign_symbol_universe_sources import _normalize_ranking_tags

    assert _normalize_ranking_tags("reit;real_estate") == "reit,real_estate"
    assert _normalize_ranking_tags("foreign_etf;msci") == "index"


def test_reit_detection_does_not_match_concrete_or_street() -> None:
    from tools.fetch_sbi_foreign_symbol_universe_sources import _asset_type_for_section

    assert (
        _asset_type_for_section(
            "ベトナム株式一覧", "Hoa Cam Concrete JSC", "コンクリートなどの建設資材メーカー"
        )
        == "stock"
    )
    assert (
        _asset_type_for_section("ベトナム株式一覧", "Wall Street Securities JSC", "証券会社")
        == "stock"
    )
    assert (
        _asset_type_for_section("REIT銘柄一覧", "リンク リート", "REIT（不動産投資信託）") == "reit"
    )
