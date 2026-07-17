"""Create the 14 SMAI investment-candidate comparison exports sequentially."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.investment_candidates import export_investment_candidates  # noqa: E402
from ui.symbol_universe import symbol_universe_csv_rows  # noqa: E402


def _runner(symbols, start, end, provider, progress):
    from ui.app import _execute_market_data_ranking_job
    return _execute_market_data_ranking_job(cache_key=f"candidate-export|{provider}|{start}|{end}|{','.join(symbols)}", ranking_symbols=symbols, start=start, end=end, provider=provider, progress_callback=progress)

def main() -> None:
    parser = argparse.ArgumentParser(description="Export SMAI NISA growth-investment candidate rankings.")
    parser.add_argument("--output-dir", type=Path, default=Path("exports/investment_candidates"))
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--fetch-limit", type=int, default=300)
    args = parser.parse_args()
    summary = export_investment_candidates(output_root=args.output_dir, universe_rows=symbol_universe_csv_rows(), runner=_runner, top_n=max(1, args.top_n), fetch_limit=max(1, args.fetch_limit))
    print(summary["zip_file"])
    print("ChatGPTへアップロード後: 安定・インカム枠2〜3銘柄と中長期成長枠2〜3銘柄へ、重複・財務・リスク・分散を総合評価してください。")
if __name__ == "__main__":
    main()
