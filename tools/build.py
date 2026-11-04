"""Write dist/AllSets.json, AllCards.json, AllPrintings.json and AllProducts.json. Refuses to build invalid data.

    uv run python tools/build.py --version 0.4.0
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys

import rbjson

DIST = rbjson.ROOT / "dist"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="0.0.0-dev")
    args = ap.parse_args()
    sets, files, sealed = rbjson.load_sets(), rbjson.load_cards(), rbjson.load_sealed()
    errors = rbjson.validate(sets, files, sealed)
    if errors:
        sys.exit("refusing to build:\n" + "\n".join(errors))
    meta = {"version": args.version, "date": datetime.date.today().isoformat()}
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
