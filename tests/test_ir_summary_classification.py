from backend.research.ir_classification import (
    IRDocumentCandidate,
    classify_ir_document_candidates,
)


def _tdnet_matches(title: str) -> dict[str, str]:
    matches = classify_ir_document_candidates(
        [
            IRDocumentCandidate(
                title=title,
                source_type="tdnet",
                source_url=f"https://example.com/{abs(hash(title))}.pdf",
            )
        ]
    )
    return {document_type: match.candidate.title for document_type, match in matches.items()}


def test_rsu_stock_compensation_tdnet_stays_generic_disclosure_only():
    matches = _tdnet_matches(
        "リストリクテッド・ストック・ユニット（RSU）付与制度としての"
        "自己株式処分の払込完了に関するお知らせ"
    )

    assert "適時開示" in matches
    assert "配当・自社株買い" not in matches
    assert "業績予想修正" not in matches


def test_forecast_revision_requires_explicit_earnings_forecast_keywords():
    matches = _tdnet_matches("通期連結業績予想の修正に関するお知らせ")

    assert "業績予想修正" in matches
    assert "配当・自社株買い" not in matches
    assert "適時開示" not in matches


def test_upward_revision_matches_forecast_revision():
    matches = _tdnet_matches("業績予想の上方修正に関するお知らせ")

    assert "業績予想修正" in matches


def test_dividend_forecast_revision_does_not_match_earnings_forecast_revision():
    matches = _tdnet_matches("配当予想の修正に関するお知らせ")

    assert "配当・自社株買い" in matches
    assert "業績予想修正" not in matches


def test_share_buyback_matches_shareholder_return():
    matches = _tdnet_matches("自己株式取得に係る事項の決定に関するお知らせ")

    assert "配当・自社株買い" in matches


def test_stock_disposal_compensation_is_excluded_from_shareholder_return():
    matches = _tdnet_matches("譲渡制限付株式報酬としての自己株式処分に関するお知らせ")

    assert "適時開示" in matches
    assert "配当・自社株買い" not in matches
    assert "業績予想修正" not in matches


def test_earnings_summary_matches_earnings_summary_category():
    matches = _tdnet_matches("2026年3月期 第1四半期決算短信〔日本基準〕（連結）")

    assert "決算短信" in matches


def test_earnings_presentation_does_not_duplicate_earnings_summary():
    matches = _tdnet_matches("2026年3月期 第1四半期決算説明資料")

    assert "決算説明資料" in matches
    assert "決算短信" not in matches


def test_medium_term_plan_matches_medium_term_plan_category():
    matches = _tdnet_matches("新中期経営計画の策定に関するお知らせ")

    assert "中期経営計画" in matches


def test_generic_tdnet_disclosure_does_not_spread_to_specific_categories():
    matches = _tdnet_matches("役員人事に関するお知らせ")

    assert "適時開示" in matches
    assert "配当・自社株買い" not in matches
    assert "業績予想修正" not in matches
    assert "決算短信" not in matches
