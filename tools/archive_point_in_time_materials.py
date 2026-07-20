from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    from backend.llm_factor.material_archive import (
        DEFAULT_MATERIAL_ARCHIVE_PATH,
        archive_material_records,
        material_record_from_external_payload,
        material_records_from_news_snapshot,
    )
    from backend.news import (
        build_standard_news_dashboard_snapshot,
        load_cached_news_dashboard_snapshot,
    )
    from backend.research.external_adapters import DefaultExternalResearchAdapter
    from backend.research.external_contracts import ExternalResearchFetchRequest

    parser = argparse.ArgumentParser(
        description=(
            "Archive live-observed news/IR metadata for future point-in-time LLM shadow evaluation."
        )
    )
    parser.add_argument("--archive", default=str(DEFAULT_MATERIAL_ARCHIVE_PATH))
    parser.add_argument(
        "--fetch-live-news",
        action="store_true",
        help="Explicitly fetch the current bounded Google News dashboard before archiving.",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="Explicitly fetch targeted EDINET/TDnet/company IR/news/provider sources; repeatable.",
    )
    parser.add_argument("--company-name", default=None)
    args = parser.parse_args(argv)

    records = []
    snapshot = load_cached_news_dashboard_snapshot()
    if args.fetch_live_news:
        snapshot = build_standard_news_dashboard_snapshot(
            allow_network=True,
            fallback_to_demo=False,
        )
    if snapshot is not None:
        records.extend(material_records_from_news_snapshot(snapshot))

    source_counts: dict[str, int] = {}
    traces: list[str] = []
    for symbol in _normalized_symbols(args.symbol):
        adapter = DefaultExternalResearchAdapter()
        payloads = adapter.fetch_sources(
            ExternalResearchFetchRequest(
                symbol=symbol,
                company_name=args.company_name,
                provider=adapter.provider,
                allow_network=True,
            )
        )
        records.extend(material_record_from_external_payload(payload) for payload in payloads)
        for payload in payloads:
            source_counts[payload.provider] = source_counts.get(payload.provider, 0) + 1
        traces.extend(
            f"{trace.provider}:{trace.status}:{trace.result_count}"
            for trace in adapter.last_source_traces
        )

    if not records:
        print("No timestamped live material was available; archive was not changed.")
        if traces:
            print("provider traces: " + ", ".join(traces))
        return 1
    result = archive_material_records(records, path=Path(args.archive))
    print(f"archive: {result.path}")
    print(
        "records: "
        f"input={result.input_count} inserted={result.inserted_count} "
        f"updated={result.updated_count} total={result.total_count}"
    )
    if source_counts:
        print(
            "source counts: "
            + ", ".join(f"{name}={count}" for name, count in sorted(source_counts.items()))
        )
    if traces:
        print("provider traces: " + ", ".join(traces))
    print(
        "Historical warning: first_archived_at is the actual SMAI observation time; "
        "these records cannot be injected into older forecast origins."
    )
    return 0


def _normalized_symbols(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip().upper() for value in values if value.strip()))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
