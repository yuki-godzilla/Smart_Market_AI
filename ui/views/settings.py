from __future__ import annotations

from datetime import date

import streamlit as st

from backend.research import ResearchDocumentError
from ui.content.common_texts import user_facing_table_rows
from ui.rebalance_app import runtime_settings_summary, symbol_reference_rows
from ui.research_state import (
    external_research_fetch_last_summary,
    register_uploaded_research_document,
    research_document_summary_rows,
)
from ui.symbol_universe import (
    symbol_universe_csv_metadata_summary,
    symbol_universe_csv_rows,
    symbol_universe_csv_validation_issues,
)

RESEARCH_SOURCE_TYPE_LABELS = {
    "user_note": "ユーザーメモ",
    "earnings_report": "決算短信",
    "earnings_presentation": "決算説明資料",
    "annual_report": "有価証券報告書",
    "medium_term_plan": "中期経営計画",
    "integrated_report": "統合報告書",
    "tdnet": "TDnet",
    "news": "ニュース",
}


def render_settings_page() -> None:
    """Render runtime and local data reference information."""

    st.subheader("設定 / データ情報")
    st.caption("実行設定、ローカルデータ、銘柄候補を確認します。")

    settings = runtime_settings_summary()
    col_provider, col_profile, col_config, col_scenarios = st.columns([1.0, 1.0, 1.2, 2.0])
    col_provider.metric("データ取得元", settings["provider"])
    col_profile.metric("性能profile", settings["performance_profile"])
    col_profile.caption(
        "外部取得: "
        f"{settings['external_fetch_max_workers']} workers / "
        f"{settings['external_fetch_timeout_sec']}秒"
    )
    col_profile.caption(f"LLM並列: {settings['llm_workers']} worker")
    if settings["performance_fallback_used"] == "True":
        col_profile.warning("指定されたprofileが見つからないため既定値で動作中です。")
    col_config.write("設定ファイル")
    col_config.code(settings["config_file"], language=None)
    col_scenarios.write("シナリオ保存先")
    col_scenarios.code(settings["scenario_dir"], language=None)
    if settings["provider"] == "csv":
        st.write("CSVデータ")
        st.code(settings["csv_data_dir"], language=None)

    last_fetch_summary = external_research_fetch_last_summary()
    if last_fetch_summary:
        with st.expander("直近のAI調査 外部取得", expanded=False):
            st.dataframe(
                user_facing_table_rows(
                    [
                        {"field": key, "value": str(value)}
                        for key, value in last_fetch_summary.items()
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )

    with st.expander("サンプル銘柄", expanded=True):
        st.dataframe(
            user_facing_table_rows(symbol_reference_rows()),
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("ランキング銘柄候補", expanded=False):
        metadata_summary = symbol_universe_csv_metadata_summary()
        validation_issues = symbol_universe_csv_validation_issues()
        col_count, col_source, col_period, col_status = st.columns([0.8, 1.3, 1.2, 1.0])
        col_count.metric("候補数", metadata_summary["total_rows"])
        col_source.metric("出所", metadata_summary["source_summary"])
        col_period.metric("基準日", metadata_summary["metadata_period"])
        col_status.metric("形式確認", metadata_summary["validation_summary"])
        st.caption(
            "取得元情報未設定: "
            f"{metadata_summary['missing_metadata_count']}件 / "
            f"古い取得元情報: {metadata_summary['stale_metadata_count']}件"
        )
        if validation_issues:
            st.warning("銘柄候補CSVに確認が必要な行があります。")
            st.dataframe(
                user_facing_table_rows(validation_issues),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption("銘柄候補CSVの形式確認: OK")
        st.dataframe(
            user_facing_table_rows(symbol_universe_csv_rows()),
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("AI調査 / 根拠資料", expanded=False):
        st.caption(
            "ローカル資料を登録し、銘柄コックピットと投資判断レポートで根拠表示に使います。"
            "Phase 20ではUTF-8のMarkdown/Text/CSVを対象にします。"
        )
        symbol = st.text_input("銘柄コード", key="research_upload_symbol", placeholder="7203.T")
        title = st.text_input("資料タイトル", key="research_upload_title")
        source_type = st.selectbox(
            "資料種別",
            list(RESEARCH_SOURCE_TYPE_LABELS),
            format_func=lambda value: RESEARCH_SOURCE_TYPE_LABELS.get(value, value),
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
        if st.button("根拠資料を登録", key="research_upload_register", type="primary"):
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
                    st.error(f"根拠資料を登録できませんでした: {exc}")
                else:
                    st.success(f"登録しました: {document_id} / チャンク数: {chunk_count}")

        rows = research_document_summary_rows()
        if rows:
            st.dataframe(
                user_facing_table_rows(rows),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("登録済みの根拠資料はまだありません。")
