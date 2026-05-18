from __future__ import annotations

import streamlit as st

from ui.rebalance_app import runtime_settings_summary, symbol_reference_rows
from ui.symbol_universe import symbol_universe_csv_rows


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

    with st.expander("Sample Symbols", expanded=True):
        st.dataframe(symbol_reference_rows(), hide_index=True, use_container_width=True)

    with st.expander("Ranking Symbol Universe", expanded=False):
        st.dataframe(symbol_universe_csv_rows(), hide_index=True, use_container_width=True)
