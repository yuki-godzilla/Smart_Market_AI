"""Create the 14 SMAI investment-candidate comparison exports sequentially."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.investment_candidates import export_investment_candidates  # noqa: E402
from ui.ranking_export_policy import create_ranking_export_policy  # noqa: E402
from ui.symbol_universe import symbol_universe_csv_rows  # noqa: E402


def _runner(symbols, start, end, provider, progress):
    from ui.app import _execute_market_data_ranking_job

    return _execute_market_data_ranking_job(
        cache_key=f"candidate-export|{provider}|{start}|{end}|{','.join(symbols)}",
        ranking_symbols=symbols,
        start=start,
        end=end,
        provider=provider,
        progress_callback=progress,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export SMAI NISA growth-investment candidate rankings.")
    parser.add_argument("--output-dir", type=Path, default=Path("exports/investment_candidates"))
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument(
        "--fetch-limit",
        type=int,
        default=300,
        help="各ランキングの最大評価銘柄数（既定: 300）",
    )
    parser.add_argument(
        "--all-symbols",
        action="store_true",
        help="各条件に適合する全銘柄を評価する（長時間実行）",
    )
    args = parser.parse_args()
    if args.fetch_limit < 1:
        parser.error("--fetch-limit は1以上を指定してください。全件実行には --all-symbols を使います。")
    summary = export_investment_candidates(
        output_root=args.output_dir,
        universe_rows=symbol_universe_csv_rows(),
        runner=_runner,
        ranking_policy=create_ranking_export_policy(),
        top_n=max(1, args.top_n),
        fetch_limit=None if args.all_symbols else args.fetch_limit,
    )
    print(summary["zip_file"])
    print(
        "ChatGPTへアップロード後: 安定・インカム枠2〜3銘柄と中長期成長枠2〜3銘柄へ、"
        "重複・財務・リスク・分散を総合評価してください。"
    )


if __name__ == "__main__":
    main()
