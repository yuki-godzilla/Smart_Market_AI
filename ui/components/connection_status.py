from __future__ import annotations

import ipaddress
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / ".streamlit/config.toml"
DIAGNOSTIC_LOG_PATH = PROJECT_ROOT / "logs/server_ops/external_connection_diagnostics.log"


@dataclass(frozen=True, slots=True)
class ConnectionDiagnostic:
    connection_type: str
    client_address: str
    lightweight_mode: bool
    static_serving: bool
    websocket_compression: bool
    optimized_asset_count: int
    optimized_asset_bytes: int
    session_key_count: int
    estimated_session_bytes: int


def infer_connection_type(client_address: str | None) -> str:
    value = str(client_address or "").strip().split("%", 1)[0]
    if not value:
        return "不明"
    if value.lower() == "localhost":
        return "localhost"
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return "不明"
    if address.is_loopback:
        return "localhost"
    if isinstance(address, ipaddress.IPv4Address) and address in ipaddress.ip_network(
        "100.64.0.0/10"
    ):
        return "Tailscale"
    if address.is_private or address.is_link_local:
        return "LAN"
    return "不明"


@lru_cache(maxsize=1)
def _config_values() -> dict[str, Any]:
    """Read the server configuration once for the rerun-driven diagnostic view.

    Streamlit applies its server configuration at process start.  Keeping this
    diagnostic aligned with that lifecycle avoids a disk read on each Settings
    rerun without hiding a configuration change that the running server could
    not apply anyway.
    """
    try:
        import tomllib

        payload = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    server = payload.get("server")
    return server if isinstance(server, dict) else {}


@lru_cache(maxsize=1)
def _optimized_asset_stats() -> tuple[int, int]:
    """Return static-asset totals once per server process.

    The diagnostic panel is rendered on every Settings rerun.  Its asset
    inventory is deployment metadata, so repeatedly walking the same static
    directory only adds filesystem work and does not make the diagnosis more
    accurate during a running server.
    """

    optimized_files = tuple(
        path for path in (PROJECT_ROOT / "ui/static/assets").rglob("*") if path.is_file()
    )
    return len(optimized_files), sum(path.stat().st_size for path in optimized_files)


def estimate_session_state_size(state: Mapping[str, Any]) -> tuple[int, int]:
    total = 0
    for value in state.values():
        try:
            total += len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))
        except (TypeError, ValueError, RecursionError):
            total += len(repr(type(value)).encode("utf-8"))
    return len(state), total


def build_connection_diagnostic(
    *,
    client_address: str | None,
    session_state: Mapping[str, Any],
) -> ConnectionDiagnostic:
    config = _config_values()
    optimized_asset_count, optimized_asset_bytes = _optimized_asset_stats()
    key_count, estimated_bytes = estimate_session_state_size(session_state)
    return ConnectionDiagnostic(
        connection_type=infer_connection_type(client_address),
        client_address=str(client_address or "取得できません"),
        lightweight_mode=os.getenv("SMAI_LIGHTWEIGHT_MODE", "0") == "1",
        static_serving=bool(config.get("enableStaticServing", False)),
        websocket_compression=bool(config.get("enableWebsocketCompression", False)),
        optimized_asset_count=optimized_asset_count,
        optimized_asset_bytes=optimized_asset_bytes,
        session_key_count=key_count,
        estimated_session_bytes=estimated_bytes,
    )


def write_connection_diagnostic_log(diagnostic: ConnectionDiagnostic) -> Path:
    DIAGNOSTIC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "recorded_at": datetime.now(UTC).isoformat(),
        **asdict(diagnostic),
    }
    with DIAGNOSTIC_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return DIAGNOSTIC_LOG_PATH


def _streamlit_client_address() -> str | None:
    context = getattr(st, "context", None)
    value = getattr(context, "ip_address", None) if context is not None else None
    return str(value) if value else None


def render_connection_status() -> None:
    session_snapshot = {str(key): st.session_state[key] for key in st.session_state.keys()}
    diagnostic = build_connection_diagnostic(
        client_address=_streamlit_client_address(),
        session_state=session_snapshot,
    )
    st.caption(
        "接続状態と画面セッションの概算です。投資データや入力内容そのものはログへ保存しません。"
    )
    first, second, third, fourth = st.columns(4)
    first.metric("接続種別", diagnostic.connection_type)
    second.metric("軽量モード", "ON" if diagnostic.lightweight_mode else "OFF")
    third.metric("最適化画像", f"{diagnostic.optimized_asset_count}件")
    fourth.metric("画像総量", f"{diagnostic.optimized_asset_bytes / 1024:.0f}KB")
    st.table(
        [
            {"項目": "アクセス元", "状態": diagnostic.client_address},
            {
                "項目": "static配信 / WebSocket圧縮",
                "状態": f"{diagnostic.static_serving} / {diagnostic.websocket_compression}",
            },
            {
                "項目": "session_state概算",
                "状態": (
                    f"{diagnostic.session_key_count}キー / "
                    f"{diagnostic.estimated_session_bytes / 1024:.1f}KB"
                ),
            },
        ]
    )
    if st.button("診断スナップショットをログへ保存", key="save_connection_diagnostic"):
        try:
            path = write_connection_diagnostic_log(diagnostic)
        except OSError as exc:
            st.error(f"診断ログを保存できませんでした: {exc}")
        else:
            st.success(f"診断ログを保存しました: {path.relative_to(PROJECT_ROOT)}")
