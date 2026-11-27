"""Write dist/AllSets.json, AllCards.json, AllPrintings.json and AllProducts.json. Refuses to build invalid data.

    uv run python tools/build.py --version 0.4.0 [--date 2026-11-27]

meta.date is the date of the data, not of the build: by default the day of the last commit that changed sets/ or
data/, so building one commit twice writes the same files.
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys

import rbjson
import uuids

DIST = rbjson.ROOT / "dist"


def data_date() -> str:
    """The day of the last commit that changed sets/ or data/; today when git cannot say."""
    try:
        shown = subprocess.run(["git", "log", "-1", "--format=%cs", "--", "sets", "data"], cwd=rbjson.ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        shown = ""
    return shown or datetime.date.today().isoformat()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="0.0.0-dev")
    ap.add_argument("--date", type=datetime.date.fromisoformat, help="meta.date; default: the day sets/ or data/ last changed")
    args = ap.parse_args()
    sets, files, sealed = rbjson.load_sets(), rbjson.load_cards(), rbjson.load_sealed()
    errors = rbjson.validate(sets, files, sealed) or uuids.errors(files, sealed, uuids.load())
    if errors:
        sys.exit("refusing to build:\n" + "\n".join(errors))
    meta = {"version": args.version, "date": args.date.isoformat() if args.date else data_date()}
    flat = rbjson.flatten(sets, files, sealed)
    DIST.mkdir(exist_ok=True)
    for name, key in (("AllSets", "sets"), ("AllCards", "cards"), ("AllPrintings", "printings"),
                      ("AllProducts", "products")):
        (DIST / f"{name}.json").write_text(json.dumps({"meta": meta, "data": flat[key]}, ensure_ascii=False,
                                                      sort_keys=True), encoding="utf-8")
    print(f"dist/ written: {len(flat['sets'])} sets, {len(flat['cards'])} cards, {len(flat['printings'])} printings, "
          f"{len(flat['products'])} sealed products")


if __name__ == "__main__":
    main()
