from __future__ import annotations

from typing import Literal, cast

import streamlit as st
import streamlit.components.v1 as components

from ui.components.mascot import render_mascot_panel

SideMenuPage = Literal[
    "cockpit", "ranking", "news", "watchlist", "copilot", "rebalance", "settings"
]

SIDEMENU_PAGE_COCKPIT: SideMenuPage = "cockpit"
SIDEMENU_PAGE_RANKING: SideMenuPage = "ranking"
SIDEMENU_PAGE_NEWS: SideMenuPage = "news"
SIDEMENU_PAGE_WATCHLIST: SideMenuPage = "watchlist"
SIDEMENU_PAGE_COPILOT: SideMenuPage = "copilot"
SIDEMENU_PAGE_REBALANCE: SideMenuPage = "rebalance"
SIDEMENU_PAGE_SETTINGS: SideMenuPage = "settings"

SIDEMENU_PAGE_LABELS: dict[SideMenuPage, str] = {
    SIDEMENU_PAGE_COCKPIT: "銘柄コックピット",
    SIDEMENU_PAGE_RANKING: "銘柄ランキング",
    SIDEMENU_PAGE_NEWS: "投資レーダー",
    SIDEMENU_PAGE_WATCHLIST: "Myウォッチリスト",
    SIDEMENU_PAGE_COPILOT: "SMAIアシスタント",
    SIDEMENU_PAGE_REBALANCE: "リバランス",
    SIDEMENU_PAGE_SETTINGS: "設定 / データ情報",
}
SIDEMENU_STATE_KEY = "sidemenu_page"
SIDEMENU_RENDERED_PAGE_STATE_KEY = "_smai_sidemenu_rendered_page"


def sidemenu_scroll_to_top_html() -> str:
    """Return the small bridge used to reset Streamlit's main scroll container."""

    return """
<script>
(() => {
  const resetMainScroll = () => {
    const main = window.parent.document.querySelector("section.stAppViewMain");
    if (main) {
      main.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
  };
  window.parent.requestAnimationFrame(() => {
    resetMainScroll();
    window.parent.requestAnimationFrame(resetMainScroll);
  });
  window.parent.setTimeout(resetMainScroll, 120);
  window.parent.setTimeout(resetMainScroll, 320);
})();
</script>
""".strip()


def render_sidemenu_scroll_reset(selected_page: SideMenuPage) -> None:
    """Reset the main viewport after the newly selected page finishes rendering."""

    previous_page = st.session_state.get(SIDEMENU_RENDERED_PAGE_STATE_KEY)
    st.session_state[SIDEMENU_RENDERED_PAGE_STATE_KEY] = selected_page
    if previous_page is None or previous_page == selected_page:
        return
    components.html(sidemenu_scroll_to_top_html(), height=0, width=0)


def _current_sidemenu_page() -> SideMenuPage:
    page = st.session_state.get(SIDEMENU_STATE_KEY, SIDEMENU_PAGE_COCKPIT)
    if page not in SIDEMENU_PAGE_LABELS:
        page = SIDEMENU_PAGE_COCKPIT
    if st.session_state.get(SIDEMENU_STATE_KEY) != page:
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

        st.caption("個人用の分析ツール。データ更新日時と根拠も見比べます。")

    return _current_sidemenu_page()


def _sidebar_mascot_message(page: SideMenuPage) -> str:
    messages = {
        SIDEMENU_PAGE_WATCHLIST: "気になる銘柄をまとめます。",
        SIDEMENU_PAGE_COCKPIT: "1銘柄を深掘りします。",
        SIDEMENU_PAGE_RANKING: "注目候補を見比べます。",
        SIDEMENU_PAGE_NEWS: "市場テーマと関連銘柄を追います。",
        SIDEMENU_PAGE_COPILOT: "気になる点をすぐ聞けます。",
        SIDEMENU_PAGE_REBALANCE: "配分のズレを見ます。",
        SIDEMENU_PAGE_SETTINGS: "データ取得の設定です。",
    }
    return messages[page]
