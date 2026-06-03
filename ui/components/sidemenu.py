from __future__ import annotations

from typing import Literal, cast

import streamlit as st

from ui.components.mascot import render_mascot_panel

SideMenuPage = Literal["cockpit", "ranking", "news", "rebalance", "settings"]

SIDEMENU_PAGE_COCKPIT: SideMenuPage = "cockpit"
SIDEMENU_PAGE_RANKING: SideMenuPage = "ranking"
SIDEMENU_PAGE_NEWS: SideMenuPage = "news"
SIDEMENU_PAGE_REBALANCE: SideMenuPage = "rebalance"
SIDEMENU_PAGE_SETTINGS: SideMenuPage = "settings"

SIDEMENU_PAGE_LABELS: dict[SideMenuPage, str] = {
    SIDEMENU_PAGE_COCKPIT: "銘柄コックピット",
    SIDEMENU_PAGE_RANKING: "銘柄ランキング",
    SIDEMENU_PAGE_NEWS: "投資レーダー",
    SIDEMENU_PAGE_REBALANCE: "リバランス",
    SIDEMENU_PAGE_SETTINGS: "設定 / データ情報",
}
SIDEMENU_STATE_KEY = "sidemenu_page"


def _current_sidemenu_page() -> SideMenuPage:
    page = st.session_state.get(SIDEMENU_STATE_KEY, SIDEMENU_PAGE_COCKPIT)
    if page not in SIDEMENU_PAGE_LABELS:
        page = SIDEMENU_PAGE_COCKPIT
        st.session_state[SIDEMENU_STATE_KEY] = page
    return cast(SideMenuPage, page)


def _set_sidemenu_page(page: SideMenuPage) -> None:
    st.session_state[SIDEMENU_STATE_KEY] = page


def render_sidemenu(runtime_settings: dict[str, str]) -> SideMenuPage:
    """Render the compact app side menu and return the selected page key."""

    selected_page = _current_sidemenu_page()

    with st.sidebar:
        st.caption("Smart Market AI")
        render_mascot_panel(
            "brand",
            message=_sidebar_mascot_message(selected_page),
            layout="sidebar",
        )
        st.markdown("#### メニュー")

        for page_key, label in SIDEMENU_PAGE_LABELS.items():
            st.button(
                label,
                key=f"sidemenu_button_{page_key}",
                type="primary" if selected_page == page_key else "secondary",
                use_container_width=True,
                on_click=_set_sidemenu_page,
                args=(page_key,),
            )

        with st.expander("実行環境", expanded=False):
            st.write(f"データ取得元: `{runtime_settings['provider']}`")
            st.write(f"設定ファイル: `{runtime_settings['config_file']}`")
            st.write(f"シナリオ保存先: `{runtime_settings['scenario_dir']}`")
            if runtime_settings["provider"] == "csv":
                st.write(f"CSVデータ: `{runtime_settings['csv_data_dir']}`")

        st.caption("分析結果は投資判断の補助であり、売買推奨ではありません。")

    return _current_sidemenu_page()


def _sidebar_mascot_message(page: SideMenuPage) -> str:
    messages = {
        SIDEMENU_PAGE_COCKPIT: "1銘柄の確認ポイントを一緒に整理します。",
        SIDEMENU_PAGE_RANKING: "深掘り候補をスコアとリスク確認で見比べます。",
        SIDEMENU_PAGE_NEWS: "市場ニュースから確認すべきテーマと関連銘柄を整理します。",
        SIDEMENU_PAGE_REBALANCE: "配分のズレと見直し候補を確認します。",
        SIDEMENU_PAGE_SETTINGS: "データ設定と取得元を確認します。",
    }
    return messages[page]
