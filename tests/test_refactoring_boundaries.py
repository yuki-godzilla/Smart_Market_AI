from backend.research import ExternalResearchFetchService
from backend.research.external_fetch_service import (
    ExternalResearchFetchService as DirectExternalResearchFetchService,
)
from backend.research.normalization import normalize_symbol
from ui.copilot_streaming import stream_chunks
from ui.ranking_presenter import compact_confidence_summary, full_confirmation_note
from ui.style_components import compact_display_value
from ui.styles import compact_display_value as legacy_compact_display_value


def test_style_component_legacy_import_keeps_the_same_callable() -> None:
    assert legacy_compact_display_value is compact_display_value
    assert compact_display_value("12.30%") == "12.3%"


def test_research_package_keeps_lazy_external_fetch_public_contract() -> None:
    assert ExternalResearchFetchService is DirectExternalResearchFetchService
    assert normalize_symbol(" 7203.t ") == "7203.T"


def test_copilot_streaming_keeps_progressive_final_text() -> None:
    text = "銘柄を確認しました。価格材料を整理します。"
    chunks = stream_chunks(text)
    assert chunks[-1] == text
    assert all(text.startswith(chunk) for chunk in chunks)


def test_ranking_presenter_is_state_free_and_preserves_display_contract() -> None:
    assert (
        compact_confidence_summary(
            {"データ品質": "90", "条件適合度": "80", "DB信頼度": "高", "根拠状態": "確認済み"}
        )
        == "品質90 / 条件80 / DB高 / 確認済み"
    )
    assert full_confirmation_note("予測は上向き", "公式資料を確認します。") == (
        "予測は上向き / 公式資料を確認します。"
    )
