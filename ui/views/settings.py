from __future__ import annotations

from datetime import date

import streamlit as st

from backend.research import ResearchDocumentError
from ui.rebalance_app import runtime_settings_summary, symbol_reference_rows
from ui.research_state import (
    register_uploaded_research_document,
    research_document_summary_rows,
)
from ui.symbol_universe import (
    symbol_universe_csv_metadata_summary,
    symbol_universe_csv_rows,
    symbol_universe_csv_validation_issues,
)


def render_settings_page() -> None:
    """Render runtime and local data reference information."""

    st.subheader("設定 / データ情報")
    st.caption("実行設定、ローカルデータ、銘柄候補を確認します。")

    settings = runtime_settings_summary()
    col_provider, col_config, col_scenarios = st.columns([1.0, 1.2, 2.0])
    col_provider.metric("Provider", settings["provider"])
    col_config.write("Config")
    col_config.code(settings["config_file"], language=None)
    col_scenarios.write("Scenario directory")
    col_scenarios.code(settings["scenario_dir"], language=None)
    if settings["provider"] == "csv":
        st.write("CSV data")
        st.code(settings["csv_data_dir"], language=None)

    with st.expander("サンプル銘柄", expanded=True):
        st.dataframe(symbol_reference_rows(), hide_index=True, use_container_width=True)

    with st.expander("ランキング銘柄候補", expanded=False):
        metadata_summary = symbol_universe_csv_metadata_summary()
        validation_issues = symbol_universe_csv_validation_issues()
        col_count, col_source, col_period, col_status = st.columns([0.8, 1.3, 1.2, 1.0])
        col_count.metric("候補数", metadata_summary["total_rows"])
        col_source.metric("出所", metadata_summary["source_summary"])
        col_period.metric("基準日", metadata_summary["metadata_period"])
        col_status.metric("形式確認", metadata_summary["validation_summary"])
        st.caption(
            "metadata未設定: "
            f"{metadata_summary['missing_metadata_count']}件 / "
            f"古いmetadata: {metadata_summary['stale_metadata_count']}件"
        )
        if validation_issues:
            st.warning("銘柄候補CSVに確認が必要な行があります。")
            st.dataframe(validation_issues, hide_index=True, use_container_width=True)
        else:
            st.caption("銘柄候補CSVの形式確認: OK")
        st.dataframe(symbol_universe_csv_rows(), hide_index=True, use_container_width=True)

    with st.expander("Research RAG / 根拠資料", expanded=False):
        st.caption(
            "ローカル資料を登録し、銘柄コックピットとDecision Reportで根拠表示に使います。"
            "Phase 20ではUTF-8のMarkdown/Text/CSVを対象にします。"
        )
        symbol = st.text_input("銘柄コード", key="research_upload_symbol", placeholder="7203.T")
        title = st.text_input("資料タイトル", key="research_upload_title")
        source_type = st.selectbox(
            "資料種別",
            [
                "user_note",
                "earnings_report",
                "earnings_presentation",
                "annual_report",
                "medium_term_plan",
                "integrated_report",
                "tdnet",
                "news",
            ],
            key="research_upload_source_type",
        )
        published_at = st.date_input(
            "公開日",
            value=None,
            key="research_upload_published_at",
        )
        uploaded_file = st.file_uploader(
            "資料ファイル",
            type=["md", "txt", "csv"],
            key="research_upload_file",
        )
        if st.button("Research資料を登録", key="research_upload_register"):
            if not symbol.strip() or not title.strip() or uploaded_file is None:
                st.warning("銘柄コード、資料タイトル、資料ファイルを指定してください。")
            else:
                try:
                    document_id, chunk_count = register_uploaded_research_document(
                        symbol=symbol,
                        title=title,
                        content=uploaded_file.getvalue(),
                        file_name=uploaded_file.name,
                        source_type=source_type,
                        published_at=published_at if isinstance(published_at, date) else None,
                    )
                except (ResearchDocumentError, UnicodeDecodeError) as exc:
                    st.error(f"Research資料を登録できませんでした: {exc}")
                else:
                    st.success(f"登録しました: {document_id} / chunks: {chunk_count}")

        rows = research_document_summary_rows()
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.info("登録済みResearch資料はまだありません。")
