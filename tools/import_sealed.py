"""Write data/sealed/<set>.json from TCGplayer's sealed Riftbound products (TCGCSV category 89).

    uv run python tools/import_sealed.py [--refresh]

A product's category comes from its name (ordered rules, first match wins, as opjson's CATEGORY_RULES).
Contents are written only where the product's own name or set states them, and never with counts:
- a booster pack's `pool` is its set (the cards it can hold, with no odds);
- a booster display names the set's booster pack, a vault bundle too;
- a case names the product its name prefixes ("Origins - Booster Display Case" holds "Origins - Booster Display");
- a Champion Deck display or a Showdown Decks display names the deck it shares a name with;
- a sleeved art bundle names the set's sleeved booster pack.
So `contentsStatus` is `partial` or `unknown`, never `complete`: no source in reach gives quantities or deck lists.

A group joins a set through the set's `tcgplayerGroupIds` (written by import_tcgcsv.py). The products of a group
with no set (the promotional groups, the Worlds bundles, a set rbjson does not list yet) are not written; they go
to review/sealed.json.
"""
from __future__ import annotations

import argparse
import collections
import re

import rbjson
import tcgcsv

CACHE = rbjson.ROOT / ".cache" / "tcgcsv"
REVIEW = rbjson.ROOT / "review" / "sealed.json"

# (regex on the product name, category). First match wins, so containers come before what they contain.
CATEGORY_RULES = [
    (r"case$", "case"),
    (r"booster display$", "booster_box"),
    (r"\[set of \d+\]|\(set of \d+\)", "display"),
    (r"display$", "display"),
    (r"sleeved booster pack", "sleeved_booster_pack"),
    (r"champion deck|showdown decks|box set", "starter_deck"),
    (r"pre-rift event kit", "tournament_kit"),
    (r"nexus night promo pack", "promo_pack"),
    (r"vault bundle|pre-rift kit", "collection"),
    (r"booster pack", "booster_pack"),
]
_SLUG = re.compile(r"[^a-z0-9]+")
_CONTAINER = re.compile(r"\s*(case|display)$", re.I)


def classify(name: str) -> str:
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, name, re.I):
            return category
    return "other"


def slug(name: str) -> str:
    return _SLUG.sub("-", name.lower().replace("!!", "")).strip("-")


def release_date(group: dict, released_on: str | None) -> str | None:
    """TCGplayer's own date for the product, else its group's."""
    return released_on or (group.get("publishedOn") or "")[:10] or None


def build(sets: list[dict], groups: list[dict], products_of) -> tuple[dict[str, list[dict]], list[dict]]:
    """({set id: products}, review entries). ``products_of(group_id)`` lists a group's products."""
    set_of_group = {gid: s["id"] for s in sets for gid in s.get("tcgplayerGroupIds", [])}
    by_set: dict[str, list[dict]] = collections.defaultdict(list)
    review = []
    for g in sorted(groups, key=lambda g: g["groupId"]):
        set_id = set_of_group.get(g["groupId"])
        for p in sorted(products_of(g["groupId"]), key=lambda p: p.product_id):
            if p.is_single:
                continue
            if set_id is None:
                review.append({"productId": p.product_id, "groupId": g["groupId"],
                               "group": g.get("abbreviation"), "name": p.name})
                continue
            category = classify(p.name)
            product = {"id": slug(p.name), "set": set_id, "category": category, "name": p.name,
                       "identifiers": {"tcgplayerProductIds": [p.product_id]},
                       "contentsStatus": "unknown", "contents": {},
                       "sources": [f"https://www.tcgplayer.com/product/{p.product_id}"]}
            if released := release_date(g, p.released_on):
                product["releaseDate"] = released
            if category in ("booster_pack", "sleeved_booster_pack"):
                product["contents"]["pool"] = [{"set": set_id}]
                product["contentsStatus"] = "partial"
            by_set[set_id].append(product)
    _dedupe_ids([p for _, ps in sorted(by_set.items()) for p in ps])
    for products in by_set.values():
        products.sort(key=lambda x: x["id"])
        _link_contents(products)
    return dict(by_set), review


def _link_contents(products: list[dict]) -> None:
    """Name the product a container holds, when its name says so. The count stays unstated."""
    by_name = {p["name"].casefold(): p for p in products}
    by_category = {}
    for p in products:
        by_category.setdefault(p["category"], p)  # at most one booster pack and sleeved pack per set
    for p in products:
        held = None
        if p["category"] == "case":
            held = by_name.get(_CONTAINER.sub("", p["name"]).casefold())
        elif p["category"] == "booster_box":
            held = by_category.get("booster_pack")
        elif p["category"] == "display" and re.search(r"set of \d+", p["name"], re.I):
            held = by_category.get("sleeved_booster_pack")
        elif p["category"] == "display":
            held = by_name.get(_CONTAINER.sub("", p["name"]).casefold())
        elif re.search(r"vault bundle$", p["name"], re.I):
            held = by_category.get("booster_pack")
        if held is not None and held is not p:
            p["contents"]["sealed"] = [{"product": held["id"]}]
            p["contentsStatus"] = "partial"


def _dedupe_ids(products: list[dict]) -> None:
    seen = collections.Counter()
    for p in products:
        seen[p["id"]] += 1
        if seen[p["id"]] > 1:
            p["id"] = f"{p['id']}-{p['identifiers']['tcgplayerProductIds'][0]}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="fetch TCGCSV again instead of reading .cache/tcgcsv")
    args = ap.parse_args()
    sets = rbjson.load_sets()
    groups = tcgcsv.groups(CACHE, args.refresh)
    by_set, review = build(sets, groups, lambda gid: tcgcsv.products(gid, CACHE, args.refresh))
    rbjson.SEALED.mkdir(parents=True, exist_ok=True)
    for old in rbjson.SEALED.glob("*.json"):
        old.unlink()
    for set_id, products in sorted(by_set.items()):
        rbjson.dump(rbjson.SEALED / f"{set_id}.json", {"products": products})
    rbjson.dump(REVIEW, {"unmatched": review})
    counts = collections.Counter(p["category"] for ps in by_set.values() for p in ps)
    total = sum(counts.values())
    print(f"{total} sealed products in {len(by_set)} sets; {len(review)} in review; {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    main()
