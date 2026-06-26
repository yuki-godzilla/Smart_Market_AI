import json
from datetime import UTC, datetime, timedelta

from ui import favorites
from ui.components import sidemenu


def test_load_favorites_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(favorites, "FAVORITES_FILE_PATH", tmp_path / "favorites.json")

    assert favorites.load_favorites() == []


def test_add_favorite_normalizes_symbol_and_preserves_japanese(tmp_path, monkeypatch):
    path = tmp_path / "data" / "user" / "favorites.json"
    monkeypatch.setattr(favorites, "FAVORITES_FILE_PATH", path)

    favorite = favorites.add_favorite(
        " 7203.t ",
        {
            "name": "トヨタ自動車",
            "market": "jp",
            "asset_type": "stock",
            "currency": "JPY",
            "source_screen": "ranking",
        },
    )
    duplicated = favorites.add_favorite("7203.T", {"name": "ignored"})
    payload = path.read_text(encoding="utf-8")

    assert favorite.symbol == "7203.T"
    assert duplicated == favorite
    assert "トヨタ自動車" in payload
    assert len(json.loads(payload)["favorites"]) == 1


def test_toggle_favorite_adds_then_removes(tmp_path, monkeypatch):
    monkeypatch.setattr(favorites, "FAVORITES_FILE_PATH", tmp_path / "favorites.json")

    assert favorites.toggle_favorite("NVDA", {"name": "NVIDIA"})
    assert favorites.is_favorite("nvda")
    assert not favorites.toggle_favorite("nvda")
    assert not favorites.is_favorite("NVDA")


def test_favorite_symbols_and_update_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(favorites, "FAVORITES_FILE_PATH", tmp_path / "favorites.json")

    favorites.add_favorite("nvda", {"name": "NVIDIA", "tags": ["AI関連"]})
    updated = favorites.update_favorite(
        "NVDA",
        memo="決算後に確認",
        tags=["AI関連", "要注意"],
        last_checked_at="2026-06-27T10:00:00+09:00",
    )

    assert favorites.favorite_symbols() == ["NVDA"]
    assert updated is not None
    assert updated.memo == "決算後に確認"
    assert updated.tags == ("AI関連", "要注意")
    assert updated.last_checked_at == "2026-06-27T10:00:00+09:00"


def test_update_favorite_refresh_metadata_preserves_memo_and_tags(tmp_path, monkeypatch):
    monkeypatch.setattr(favorites, "FAVORITES_FILE_PATH", tmp_path / "favorites.json")
    favorites.add_favorite(
        "7203.T",
        {"memo": "決算後に確認", "tags": ["長期候補"]},
    )

    updated = favorites.update_favorite_refresh_metadata(
        "7203.T",
        refresh_status="stale",
        refresh_error="",
        last_checked_at="2026-06-27T10:00:00+09:00",
        last_price_checked_at="2026-06-27T10:00:00+09:00",
        last_news_checked_at="2026-06-27T10:00:00+09:00",
        last_research_hint_at="2026-06-27T10:00:00+09:00",
    )

    assert updated is not None
    assert updated.refresh_status == "stale"
    assert updated.memo == "決算後に確認"
    assert updated.tags == ("長期候補",)
    payload = json.loads((tmp_path / "favorites.json").read_text(encoding="utf-8"))
    assert payload["favorites"][0]["last_news_checked_at"] == "2026-06-27T10:00:00+09:00"


def test_evaluate_favorite_refresh_status_states():
    now = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)
    stale_time = (now - timedelta(hours=30)).isoformat()
    fresh_time = (now - timedelta(hours=1)).isoformat()

    never_checked = favorites.evaluate_favorite_refresh_status(
        favorites.FavoriteStock(symbol="NVDA"),
        now=now,
    )
    failed = favorites.evaluate_favorite_refresh_status(
        favorites.FavoriteStock(symbol="NVDA", refresh_status="failed"),
        now=now,
    )
    stale = favorites.evaluate_favorite_refresh_status(
        favorites.FavoriteStock(symbol="NVDA", last_checked_at=stale_time),
        now=now,
    )
    needs_attention = favorites.evaluate_favorite_refresh_status(
        favorites.FavoriteStock(symbol="NVDA", last_checked_at=fresh_time),
        now=now,
    )
    fresh = favorites.evaluate_favorite_refresh_status(
        favorites.FavoriteStock(
            symbol="NVDA",
            last_checked_at=fresh_time,
            last_news_checked_at=fresh_time,
            last_research_hint_at=fresh_time,
        ),
        now=now,
    )

    assert never_checked.status == "never_checked"
    assert failed.status == "failed"
    assert stale.status == "stale"
    assert needs_attention.status == "needs_attention"
    assert fresh.status == "fresh"


def test_load_favorites_broken_json_returns_empty(tmp_path, monkeypatch):
    path = tmp_path / "favorites.json"
    path.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(favorites, "FAVORITES_FILE_PATH", path)

    assert favorites.load_favorites() == []


def test_favorite_metadata_from_row_maps_symbol_universe_fields():
    metadata = favorites.favorite_metadata_from_row(
        {
            "name": "トヨタ自動車",
            "market": "jp",
            "asset_type": "stock",
            "currency": "JPY",
        },
        source_screen="cockpit",
    )

    assert metadata == {
        "name": "トヨタ自動車",
        "market": "jp",
        "asset_type": "stock",
        "currency": "JPY",
        "source_screen": "cockpit",
    }


def test_render_favorite_button_toggles_store(tmp_path, monkeypatch):
    class FakeStreamlit:
        def __init__(self) -> None:
            self.toast_message = ""
            self.rerun_called = False

        def button(self, *_args, **_kwargs) -> bool:
            return True

        def toast(self, message: str) -> None:
            self.toast_message = message

        def rerun(self) -> None:
            self.rerun_called = True

    fake_st = FakeStreamlit()
    monkeypatch.setattr(favorites, "FAVORITES_FILE_PATH", tmp_path / "favorites.json")
    monkeypatch.setattr(favorites, "st", fake_st)

    assert favorites.render_favorite_button(" nvda ", name="NVIDIA", source_screen="ranking")
    assert favorites.is_favorite("NVDA")
    assert fake_st.rerun_called
    assert fake_st.toast_message == "Myウォッチリストに追加しました。"


def test_sidemenu_exposes_my_watchlist_page():
    assert sidemenu.SIDEMENU_PAGE_LABELS[sidemenu.SIDEMENU_PAGE_WATCHLIST] == "Myウォッチリスト"

    menu_order = list(sidemenu.SIDEMENU_PAGE_LABELS)
    assert menu_order.index(sidemenu.SIDEMENU_PAGE_NEWS) < menu_order.index(
        sidemenu.SIDEMENU_PAGE_WATCHLIST
    ) < menu_order.index(sidemenu.SIDEMENU_PAGE_COPILOT)
