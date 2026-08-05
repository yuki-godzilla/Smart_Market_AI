from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def _allowed(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        normalized == "data/marketdata/symbol_universe.csv"
        or normalized.startswith("data/marketdata/symbol_universe_sources/")
        or (normalized.startswith("data/marketdata/") and "manifest" in Path(normalized).name)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Commit and optionally push only approved symbol-universe artifacts."
    )
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--message", default="chore: refresh symbol universe artifacts")
    args = parser.parse_args()
    status = _run("git", "status", "--porcelain", "--", "data/marketdata")
    paths = [
        line[3:] for line in status.stdout.splitlines() if len(line) >= 4 and line[0:2].strip()
    ]
    unsafe = [path for path in paths if not _allowed(path)]
    if unsafe:
        print("[ERROR] Refusing automatic commit; unexpected marketdata paths:", file=sys.stderr)
        print("\n".join(unsafe), file=sys.stderr)
        return 2
    if not paths:
        print("[SMAI] No approved symbol artifacts changed.")
        return 0
    add = _run("git", "add", "--", *paths)
    if add.returncode:
        print(add.stderr, file=sys.stderr)
        return add.returncode
    commit = _run("git", "commit", "-m", args.message)
    if commit.returncode:
        print(commit.stdout + commit.stderr, file=sys.stderr)
        return commit.returncode
    print(commit.stdout, end="")
    if args.push:
        push = _run("git", "push")
        print(push.stdout, end="")
        if push.returncode:
            print(push.stderr, file=sys.stderr)
            return push.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
