from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = PROJECT_ROOT / "ui"
REPORT_PATH = PROJECT_ROOT / "logs/server_ops/ui_delivery_diagnostics.md"
TARGETS = {
    "初期ユーザー選択": ("ui/notification_center.py",),
    "ランキング": ("ui/ranking.py", "ui/app.py"),
    "銘柄コックピット": ("ui/views/cockpit.py", "ui/app.py"),
    "Watchlist": ("ui/app.py",),
    "投資レーダー": ("ui/views/news.py",),
    "SMAIアシスタント": ("ui/views/copilot.py",),
}


@dataclass(frozen=True, slots=True)
class SourceMetrics:
    files: int
    source_bytes: int
    base64_references: int
    data_uri_links: int
    dataframe_calls: int
    session_state_references: int
    expander_calls: int


def analyze_paths(paths: tuple[str, ...]) -> SourceMetrics:
    texts: list[str] = []
    for relative in paths:
        path = PROJECT_ROOT / relative
        if path.is_file():
            texts.append(path.read_text(encoding="utf-8"))
    source = "\n".join(texts)
    return SourceMetrics(
        files=len(texts),
        source_bytes=len(source.encode("utf-8")),
        base64_references=len(re.findall(r"base64", source, flags=re.IGNORECASE)),
        data_uri_links=len(re.findall(r'href=[\'"]data:', source, flags=re.IGNORECASE)),
        dataframe_calls=len(re.findall(r"\bst\.(?:dataframe|data_editor)\s*\(", source)),
        session_state_references=len(re.findall(r"\bst\.session_state\b", source)),
        expander_calls=len(re.findall(r"\bst\.expander\s*\(", source)),
    )


def static_asset_metrics() -> tuple[int, int]:
    assets = [path for path in (UI_ROOT / "static/assets").rglob("*") if path.is_file()]
    return len(assets), sum(path.stat().st_size for path in assets)


def write_report() -> Path:
    asset_count, asset_bytes = static_asset_metrics()
    lines = [
        "# UI delivery diagnostics",
        "",
        "This is a deterministic source/static-asset baseline. Runtime render time, rerun count, "
        "and session-state size are measured from the in-app external connection diagnostics.",
        "",
        f"- Optimized static assets: {asset_count}",
        f"- Optimized static asset bytes: {asset_bytes:,}",
        "",
        "| Screen | Source bytes | base64 refs | data URI links | dataframe/editor | "
        "session_state refs | expanders |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, paths in TARGETS.items():
        metric = analyze_paths(paths)
        lines.append(
            f"| {label} | {metric.source_bytes:,} | {metric.base64_references} | "
            f"{metric.data_uri_links} | {metric.dataframe_calls} | "
            f"{metric.session_state_references} | {metric.expander_calls} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Generated-file data URI links in the target UI source should remain zero.",
            "- Static image URLs keep image bytes out of rerun HTML and allow browser caching.",
            "- Source counts locate review hotspots; they are not network-byte measurements.",
            "- Use the settings-page diagnostic snapshot for actual session key/byte estimates.",
        ]
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return REPORT_PATH


if __name__ == "__main__":
    print(write_report())
