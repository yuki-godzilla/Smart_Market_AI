import pandas as pd

from ui.app import RANKING_TABLE_CONFIG, ranking_result_aggrid_options
from ui.ranking_table import RankingTableConfig, build_ranking_aggrid_options


def test_ranking_table_config_is_explicit_and_immutable() -> None:
    assert isinstance(RANKING_TABLE_CONFIG, RankingTableConfig)
    assert RANKING_TABLE_CONFIG.hidden_columns == (
        "確認詳細",
        "並べ替え理由",
        "確認ポイント",
    )


def test_legacy_ranking_table_wrapper_matches_presenter_output() -> None:
    frame = pd.DataFrame(
        [
            {
                "順位": "1",
                "銘柄": "7203.T",
                "銘柄名": "トヨタ自動車",
                "総合スコア": "82.5",
                "下降警戒": "31.0",
                "確認詳細": "公式資料を確認します。",
            }
        ]
    )

    expected = build_ranking_aggrid_options(frame, RANKING_TABLE_CONFIG)
    actual = ranking_result_aggrid_options(frame)

    assert actual == expected
    assert actual["rowHeight"] == 38
    assert actual["headerHeight"] == 38
