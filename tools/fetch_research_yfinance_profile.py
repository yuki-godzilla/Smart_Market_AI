from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "research_docs"


PROFILE_FIELDS = [
    ("longName", "Company Name"),
    ("symbol", "Provider Symbol"),
    ("quoteType", "Quote Type"),
    ("exchange", "Exchange"),
    ("currency", "Currency"),
    ("sector", "Sector"),
    ("industry", "Industry"),
    ("country", "Country"),
    ("website", "Website"),
    ("marketCap", "Market Cap"),
    ("trailingPE", "Trailing PE"),
    ("priceToBook", "Price To Book"),
    ("returnOnEquity", "Return On Equity"),
    ("dividendYield", "Dividend Yield"),
    ("payoutRatio", "Payout Ratio"),
    ("beta", "Beta"),
    ("fiftyTwoWeekLow", "52 Week Low"),
    ("fiftyTwoWeekHigh", "52 Week High"),
    ("averageVolume", "Average Volume"),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch a real Yahoo Finance company profile into a local Research RAG Markdown file."
    )
    parser.add_argument("--symbol", required=True, help="Yahoo-compatible symbol, e.g. 7203.T")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--write", action="store_true", help="Write the Markdown file.")
    args = parser.parse_args()

    symbol = args.symbol.strip().upper()
    fetched_at = datetime.now(UTC)
    ticker = yf.Ticker(symbol)
    info = ticker.get_info()
    if not isinstance(info, dict) or not info:
        raise RuntimeError(f"No Yahoo Finance profile data returned for {symbol}.")

    markdown = build_markdown(symbol=symbol, info=info, fetched_at=fetched_at)
    output_dir = Path(args.output_dir)
    output_path = output_dir / f"{safe_symbol(symbol)}_yfinance_profile_{fetched_at:%Y%m%d}.md"

    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(str(output_path.relative_to(PROJECT_ROOT)))
    else:
        print(markdown)
    return 0


def build_markdown(*, symbol: str, info: dict[str, Any], fetched_at: datetime) -> str:
    company_name = _value(info.get("longName")) or symbol
    lines = [
        f"# {company_name} Research Profile",
        "",
        "## Source",
        "",
        "- Provider: Yahoo Finance via yfinance",
        f"- Symbol: {symbol}",
        f"- Fetched at: {fetched_at.isoformat()}",
        "- Usage: Local Research RAG evidence only; not a buy/sell recommendation.",
        "",
        "## Company Profile",
        "",
    ]
    for key, label in PROFILE_FIELDS:
        value = _value(info.get(key))
        if value:
            lines.append(f"- {label}: {value}")

    summary = _value(info.get("longBusinessSummary"))
    if summary:
        lines.extend(["", "## Business Summary", "", summary])

    risks = [
        "This provider profile is a market-data provider snapshot, not an audited filing.",
        "Confirm important facts against official IR, annual report, or regulatory filings.",
        "Treat missing fields as unknown rather than negative evidence.",
    ]
    lines.extend(["", "## Data Quality Notes", ""])
    lines.extend(f"- {risk}" for risk in risks)
    return "\n".join(lines) + "\n"


def safe_symbol(symbol: str) -> str:
    return symbol.replace(".", "_").replace("-", "_")


def _value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
