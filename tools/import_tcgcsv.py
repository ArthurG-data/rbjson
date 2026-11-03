"""Put TCGplayer's product ids and finishes on the printings, from TCGCSV category 89.

    uv run python tools/import_tcgcsv.py [--refresh]

TCGplayer sells one product per printed code, and its groups are the sets: a group's abbreviation is the set
code (OGN) and a product's Number is the printed code without it (119a/298, R04a, T01 // T02). So a product
joins its printing by set code and number, with no image comparison. A product is matched in a group whose
abbreviation is a set in sets/sets.json; the promotional groups (PR, OPP, JDG) sell stamped copies the gallery
does not list, so their products are counted and left for a later step, not matched to a base print.

A printing's finishes are the price sub-types TCGplayer has ever priced its product in (Normal is nonfoil, Foil
is foil). TCGplayer drops a sub-type's price row while it has no price, so data/tcgplayer_finishes.json records
every finish seen per product, and a finish stays once seen.

What could not be settled goes to review/tcgplayer-89.json: a single in a matched group whose number names no
printing, and the products of the groups that were not matched.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

import rbjson
import tcgcsv

CACHE = rbjson.ROOT / ".cache" / "tcgcsv"
FINISH_RECORD = rbjson.ROOT / "data" / "tcgplayer_finishes.json"
REVIEW = rbjson.ROOT / "review" / "tcgplayer-89.json"
MATCH = "number"

_NUMBER = re.compile(r"^(?P<code>([0-9]{3}|SP[0-9]+|R[0-9]{2}|T[0-9]{2})[a*]?)(?:/[0-9]+)?$")


def printing_key(set_code: str, number: str) -> str | None:
    """The printing id a TCGplayer number names in a set: ``119a/298`` in OGN is ``OGN-119a``; a number of
    another shape (``T01 // T02``, a double-sided token product) is None."""
    m = _NUMBER.match(number.strip())
    return f"{set_code}-{m['code']}" if m else None


def product_finishes(recorded: dict[str, list[str]], rows) -> dict[int, set[str]]:
    """Each product's finishes: those an earlier run recorded, plus one for each of today's price rows."""
    finishes: dict[int, set[str]] = collections.defaultdict(set)
    for product_id, found in recorded.items():
        finishes[int(product_id)].update(found)
    for row in rows:
        finish = tcgcsv.FINISHES.get(row.get("subTypeName"))
        if finish and row.get("productId") is not None:
            finishes[int(row["productId"])].add(finish)
    return finishes


def finish_record_text(finishes: dict[int, set[str]]) -> str:
    lines = [f'  "{pid}": {json.dumps(sorted(found))}' for pid, found in sorted(finishes.items()) if found]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def apply(files: dict[str, dict], sets: list[dict], groups: list[dict], products_of, finishes: dict[int, set[str]]) -> dict:
    """Write the product ids, finishes and group ids into ``files`` and ``sets`` in place; returns the review
    document and counts. ``products_of(group_id)`` lists a group's products."""
    by_key = {p["id"]: p for body in files.values() for c in body["cards"] for p in c["printings"]}
    set_codes = {s["id"]: s for s in sets}
    counts: collections.Counter = collections.Counter()
    review: dict = {"unmatched": [], "unmatched_groups": []}
    for p in by_key.values():
        p.get("identifiers", {}).pop("tcgplayerProductIds", None)
        p.pop("tcgplayer", None)
        p.pop("finishes", None)
    for s in sets:
        s.pop("tcgplayerGroupIds", None)
    for group in sorted(groups, key=lambda g: g["groupId"]):
        set_entry = set_codes.get(group.get("abbreviation") or "")
        if set_entry is None:
            products = products_of(group["groupId"])
            review["unmatched_groups"].append({
                "groupId": group["groupId"], "name": group["name"], "abbreviation": group.get("abbreviation"),
                "singles": sum(1 for p in products if p.is_single)})
            counts["unmatched_group_singles"] += sum(1 for p in products if p.is_single)
            continue
        set_entry.setdefault("tcgplayerGroupIds", []).append(group["groupId"])
        for product in sorted(products_of(group["groupId"]), key=lambda p: p.product_id):
            if not product.is_single:
                counts["sealed"] += 1
                continue
            key = printing_key(set_entry["id"], product.number or "")
            printing = by_key.get(key) if key else None
            if printing is None:
                counts["unmatched"] += 1
                review["unmatched"].append({"productId": product.product_id, "group": set_entry["id"],
                                            "name": product.name, "number": product.number})
                continue
            ids = printing.setdefault("identifiers", {}).setdefault("tcgplayerProductIds", [])
            if product.product_id not in ids:
                ids.append(product.product_id)
            printing["tcgplayer"] = {"name": product.name, "match": MATCH}
            found = finishes.get(product.product_id, set())
            if found:
                printing["finishes"] = sorted(set(printing.get("finishes", [])) | found)
            counts["matched"] += 1
    counts["printings_with_product"] = sum(1 for p in by_key.values() if p.get("identifiers", {}).get("tcgplayerProductIds"))
    counts["printings_with_finishes"] = sum(1 for p in by_key.values() if p.get("finishes"))
    return {"review": review, "counts": dict(counts)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="fetch TCGCSV again instead of reading .cache/tcgcsv")
    args = ap.parse_args()
    sets, files = rbjson.load_sets(), rbjson.load_cards()
    groups = tcgcsv.groups(CACHE, args.refresh)
    recorded = json.loads(FINISH_RECORD.read_text(encoding="utf-8")) if FINISH_RECORD.exists() else {}
    finishes = product_finishes(recorded, (row for g in groups for row in tcgcsv.prices(g["groupId"], CACHE, args.refresh)))
    result = apply(files, sets, groups, lambda gid: tcgcsv.products(gid, CACHE, args.refresh), finishes)
    for stem, body in files.items():
        rbjson.dump(rbjson.CARDS / f"{stem}.json", body)
    rbjson.dump(rbjson.SETS, sets)
    FINISH_RECORD.write_text(finish_record_text(finishes), encoding="utf-8")
    rbjson.dump(REVIEW, result["review"])
    print(" ".join(f"{k}={v}" for k, v in sorted(result["counts"].items())))


if __name__ == "__main__":
    main()
