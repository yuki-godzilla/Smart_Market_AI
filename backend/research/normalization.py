from __future__ import annotations


def normalize_symbol(symbol: str) -> str:
    """Return the canonical symbol representation shared by Research services."""

    return symbol.strip().upper()
