"""Put Cardmarket's product ids on the English printings, from Cardmarket's public Riftbound product list.

    uv run python tools/import_cardmarket.py [--refresh]

Cardmarket's list (game 22) has a name and an expansion for each single and no collector number, so a product
joins a card by name alone. sets/sets.json names each set's expansions in ``cardmarketExpansionIds``; that field
is kept by hand: Cardmarket's expansions carry no set code, so they were paired by name overlap and by Riftcodex's
set records. (``tcgplayerGroupIds`` is written by import_tcgcsv.py from the group abbreviations.)

A card's candidate names are "<name>, <subtitle>", "<name>", and for a Legend "<champion>, <name>" for each of its
tags that is a champion's name. A product matches a card when exactly one card of the set has its name among its
candidates and the set's expansions list that name once. A name held by several products (an alternate art or an
overnumbered print is listed under the base name) or by several cards is left unmatched, never ordered or guessed.
The id goes on the card's base English printing.

Unmatched products and the expansions no set claims go to review/cardmarket-22.json.
"""
from __future__ import annotations

import argparse
import collections
import re
import unicodedata

import cardmarket
import rbjson

CACHE = rbjson.ROOT / ".cache" / "cardmarket"
REVIEW = rbjson.ROOT / "review" / "cardmarket-22.json"

_FOLDED = re.compile(r"[^\w,' ]")


def fold(name: str) -> str:
    """A name as it is compared: casefolded, accents removed, punctuation other than commas and apostrophes
    dropped (a hyphen is a space)."""
    s = unicodedata.normalize("NFKD", name.replace("’", "'").replace("-", " "))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(_FOLDED.sub("", s.casefold()).split())


def champions(files: dict[str, dict]) -> set[str]:
    """The folded names of the cards whose super types hold ``champion``."""
    return {fold(c["name"]) for body in files.values() for c in body["cards"] if "champion" in c.get("superTypes", [])}


def candidates(card: dict, champion_names: set[str]) -> set[str]:
    """The folded names Cardmarket may sell the card under."""
    names = {fold(card["name"])}
    if card.get("subtitle"):
        names.add(fold(f"{card['name']}, {card['subtitle']}"))
    if card.get("type") == "legend":
        names |= {fold(f"{tag}, {card['name']}") for tag in card.get("tags", []) if fold(tag) in champion_names}
    return names


def base_printing(card: dict) -> dict | None:
    """The card's English printing that carries the id: the one without a suffix, else the only English one."""
    english = [p for p in card["printings"] if rbjson.language(p) == "en"]
    plain = [p for p in english if not p.get("suffix")]
    return plain[0] if plain else english[0] if len(english) == 1 else None


def apply(files: dict[str, dict], sets: list[dict], products: list[cardmarket.Product]) -> dict:
    """Write the product ids into ``files`` in place; returns the review document and counts."""
    for body in files.values():
        for card in body["cards"]:
            for p in card["printings"]:
                p.get("identifiers", {}).pop("cardmarketProductIds", None)
    champion_names = champions(files)
    claimed = {e for s in sets for e in s.get("cardmarketExpansionIds", [])}
    review: dict = {"ambiguous_name": [], "no_print": [], "promo_expansions": []}
    counts: collections.Counter = collections.Counter()
    per_set: dict[str, collections.Counter] = {}
    for s in sets:
        if s["id"] not in files or not s.get("cardmarketExpansionIds"):
            continue
        tally = per_set[s["id"]] = collections.Counter()
        by_name: dict[str, list[dict]] = collections.defaultdict(list)
        for card in files[s["id"]]["cards"]:
            for name in candidates(card, champion_names):
                by_name[name].append(card)
        sold = [p for p in products if p.expansion_id in s["cardmarketExpansionIds"]]
        of_name: dict[str, list[cardmarket.Product]] = collections.defaultdict(list)
        for p in sold:
            of_name[fold(p.name)].append(p)
        wins: dict[str, list[cardmarket.Product]] = collections.defaultdict(list)  # card number -> products
        for name, group in sorted(of_name.items()):
            cards = by_name.get(name, [])
            if not cards:
                review["no_print"].append({"set": s["id"], "name": group[0].name,
                                           "products": [p.product_id for p in group]})
                tally["no_print"] += len(group)
            elif len(cards) == 1 and len(group) == 1:
                wins[cards[0]["number"]].append(group[0])
            else:
                review["ambiguous_name"].append({"set": s["id"], "name": group[0].name,
                                                 "products": [p.product_id for p in group],
                                                 "prints": [c["number"] for c in cards]})
                tally["ambiguous"] += len(group)
        by_number = {c["number"]: c for c in files[s["id"]]["cards"]}
        for number, won in sorted(wins.items()):
            printing = base_printing(by_number[number])
            if len(won) == 1 and printing is not None:
                printing.setdefault("identifiers", {})["cardmarketProductIds"] = [won[0].product_id]
                tally["matched"] += 1
                continue
            # a card two differently named products claim, or one with no English printing to carry the id
            review["ambiguous_name"].append({"set": s["id"], "name": ", ".join(p.name for p in won),
                                             "products": [p.product_id for p in won], "prints": [number]})
            tally["ambiguous"] += len(won)
        tally["products"] = len(sold)
        english = [p for c in files[s["id"]]["cards"] for p in c["printings"] if rbjson.language(p) == "en"]
        tally["english"] = len(english)
        tally["with_id"] = sum(1 for p in english if p.get("identifiers", {}).get("cardmarketProductIds"))
    for expansion, n in sorted(collections.Counter(p.expansion_id for p in products if p.expansion_id not in claimed).items()):
        review["promo_expansions"].append({"expansionId": expansion, "products": n})
    for tally in per_set.values():
        counts.update(tally)
    return {"review": review, "counts": dict(counts), "per_set": {k: dict(v) for k, v in per_set.items()}}


def summary(result: dict) -> str:
    def line(label: str, c: dict) -> str:
        share = 100 * c.get("with_id", 0) / c["english"] if c.get("english") else 0
        return (f"{label}: products={c.get('products', 0)} matched={c.get('matched', 0)} "
                f"ambiguous={c.get('ambiguous', 0)} no_print={c.get('no_print', 0)} "
                f"english printings with an id={c.get('with_id', 0)}/{c.get('english', 0)} ({share:.1f}%)")
    return "\n".join([line(k, v) for k, v in result["per_set"].items()] + [line("all", result["counts"])])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="fetch Cardmarket's list again instead of reading .cache/cardmarket")
    args = ap.parse_args()
    sets, files = rbjson.load_sets(), rbjson.load_cards()
    result = apply(files, sets, cardmarket.singles(CACHE, args.refresh))
    for stem, body in files.items():
        rbjson.dump(rbjson.CARDS / f"{stem}.json", body)
    rbjson.dump(REVIEW, result["review"])
    print(summary(result))


if __name__ == "__main__":
    main()
