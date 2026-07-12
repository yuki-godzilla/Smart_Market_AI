"""Network-free cross-screen regression checks for the UI quality sprint."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

import pytest
from streamlit.testing.v1 import AppTest

SCREEN_CASES = (
    ("cockpit", "銘柄コックピット", ("データを取得", "データ取得元")),
    ("ranking", "銘柄ランキング", ("ランキングを作成", "ランキング作成")),
    ("news", "投資レーダー", ("ニュース表示を更新", "Watchlist")),
    ("watchlist", "Myウォッチリスト", ("銘柄ランキングで探す", "投資レーダーを見る")),
    ("copilot", "SMAIアシスタント", ("新しい会話", "メッセージ")),
    ("rebalance", "リバランス", ("配分見直しを確認", "シナリオ")),
    ("settings", "設定 / データ情報", ("根拠資料を登録", "サンプル銘柄")),
)


def _page_text(app: AppTest) -> str:
    groups: tuple[Iterable[object], ...] = (
        cast(Iterable[object], app.caption),
        cast(Iterable[object], app.markdown),
        cast(Iterable[object], app.subheader),
        cast(Iterable[object], app.button),
        cast(Iterable[object], app.selectbox),
        cast(Iterable[object], app.text_input),
        cast(Iterable[object], app.multiselect),
        cast(Iterable[object], app.checkbox),
        cast(Iterable[object], app.radio),
        cast(Iterable[object], app.slider),
    )
    values: list[str] = []
    for group in groups:
        for element in group:
            value = getattr(element, "value", None)
            label = getattr(element, "label", None)
            if value is not None:
                values.append(str(value))
            if label is not None:
                values.append(str(label))
    return "\n".join(values)


def _button_by_label(app: AppTest, label: str):
    return next(button for button in app.button if button.label == label)


@pytest.mark.parametrize(("page", "heading", "controls"), SCREEN_CASES)
def test_week_1_each_primary_screen_renders_with_a_core_control(
    monkeypatch: pytest.MonkeyPatch,
    page: str,
    heading: str,
    controls: tuple[str, str],
) -> None:
    """Week 1: page transition and the first usable operation stay available."""

    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=30)
    app.session_state["sidemenu_page"] = page
    app.session_state["smai_current_user_id"] = "default"

    app.run()

    assert not app.exception
    rendered_text = _page_text(app)
    assert heading in rendered_text
    assert any(control in rendered_text for control in controls)


def test_week_1_rebalance_primary_operation_produces_a_risk_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Week 1: exercise a deterministic primary action, not only initial rendering."""

    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=30)
    app.session_state["sidemenu_page"] = "rebalance"
    app.session_state["smai_current_user_id"] = "default"

    app.run()
    _button_by_label(app, "配分見直しを確認").click().run()

    assert not app.exception
    rendered_text = _page_text(app)
    assert "サマリー" in rendered_text
    assert "リスク判定" in rendered_text
