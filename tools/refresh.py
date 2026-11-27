"""Rebuild the whole dataset: every importer in the order each needs, then the validator.

    uv run python tools/refresh.py [--refresh] [--online]

The importers share data/cards, so the order matters: import_gallery rebuilds the gallery's sets from scratch (no
TCGplayer or Cardmarket ids, no minted printings), import_tcgcsv adds TCGplayer's products and mints what the gallery
lacks, import_sealed needs the group ids import_tcgcsv writes into sets.json, and import_cardmarket puts its ids on
the result. Running one alone leaves the data half rebuilt; this runs them all, then writes the README's counts
(readme.py). --refresh fetches every source again instead of reading .cache/. It stops at the first step that fails.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
STEPS = ("import_gallery", "import_tcgcsv", "import_sealed", "import_cardmarket")


def commands(refresh: bool, online: bool) -> list[list[str]]:
    flag = ["--refresh"] if refresh else []
    steps = [[sys.executable, str(TOOLS / f"{step}.py"), *flag] for step in STEPS]
    return steps + [[sys.executable, str(TOOLS / "readme.py")],
                    [sys.executable, str(TOOLS / "validate.py"), *(["--online"] if online else [])]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="fetch every source again instead of reading .cache/")
    ap.add_argument("--online", action="store_true", help="validate against the live sources at the end")
    args = ap.parse_args()
    for command in commands(args.refresh, args.online):
        print(f"== {Path(command[1]).stem}", flush=True)
        done = subprocess.run(command, cwd=TOOLS.parent)
        if done.returncode != 0:
            sys.exit(f"{Path(command[1]).stem} failed (exit {done.returncode}); the steps after it did not run")


if __name__ == "__main__":
    main()
