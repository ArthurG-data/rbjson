"""Put TCGplayer's product ids and finishes on the printings, from TCGCSV category 89.

    uv run python tools/import_tcgcsv.py [--refresh]

TCGplayer sells one product per printed code, and its groups are the sets: a group's abbreviation is the set
code (OGN) and a product's Number is the printed code without it (119a/298, R04a, T01 // T02). So a product
joins its printing by set code and number, with no image comparison. A product is matched in a group whose
abbreviation is a set in sets/sets.json.

A product whose number the gallery does not list is minted as a printing with source tcgplayer, so runes, signatures
and double-sided tokens exist. Riot's gallery omits them, and it omits the promotional groups (PR, OPP, JDG), which
sell stamped copies. A promo product's number repeats across sets and across stamps, so its printing id names both:
Sett, The Boss (Metal) (Best Of) at 269/298 in OPP is OPP-OGN269.metal-best-of, on card OPP-OGN269. A rune that names
its set ("Calm Rune (Vendetta)", R02b) is that set's printing, VEN-R02b. A minted card copies its facts from the card
it reprints: the number it names, else another card with its name and subtitle. A rerun removes every minted printing
first and mints them again, so this tool owns them outright. Two products of different names on one minted id go to
review, and so does a product whose name is not the card already at its number: TCGplayer lists Jarvan IV at 179*/167,
which is Aphelios's number, so Jarvan IV's product goes to review and Aphelios keeps the printing. A stamped
printing TCGplayer has never priced takes the finish every priced printing of that stamp has, and STAMP_FINISHES states
it for a stamp TCGplayer has never priced at all.

A printing's finishes are the price sub-types TCGplayer has ever priced its product in (Normal is nonfoil, Foil
is foil). TCGplayer drops a sub-type's price row while it has no price, so data/tcgplayer_finishes.json records
every finish seen per product, and a finish stays once seen.

What could not be settled goes to review/tcgplayer-89.json: a single with no number or an oversized one, a promo whose
number has no set to name, and the products of the groups that were not matched.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import NamedTuple

import rbjson
import tcgcsv

CACHE = rbjson.ROOT / ".cache" / "tcgcsv"
FINISH_RECORD = rbjson.ROOT / "data" / "tcgplayer_finishes.json"
REVIEW = rbjson.ROOT / "review" / "tcgplayer-89.json"
MATCH = "number"
MINTED = "minted"
SOURCE = "tcgplayer"
RARITIES = frozenset({"common", "uncommon", "rare", "epic", "showcase"})
FALLBACK_RARITY = "showcase"
# TCGplayer lists all 37 Metal Best Of products and has priced none. Face to Face Games sells them as Foil, and its
# non-foil Metal listings are the Prize Wall copies, which TCGplayer prices as Normal.
STAMP_FINISHES = {"metal-best-of": {"foil"}}

_NUMBER = re.compile(r"^(?P<core>[0-9]{3}|SP[0-9]+|R[0-9]{2}|T[0-9]{2})(?P<suffix>[a-z*]?)(?:/(?P<total>[0-9]+))?$")
_TOKEN_PAIR = re.compile(r"^(T[0-9]{2}) // (T[0-9]{2})$")
_TAG = re.compile(r"\s*\(([^()]*)\)")
_SLUG = re.compile(r"[^a-z0-9]+")
# Tags that say nothing about which printing this is: the number's own suffix already tells an alternate art apart.
_NOTE_TAGS = frozenset({"alternate art"})
_REFUSED_TAG = "oversized"


class Plan(NamedTuple):
    """Where one product belongs: its printing id, the card number that holds it, and what a minted printing needs."""
    printing_id: str
    card_number: str
    set_code: str
    collector_number: int
    suffix: str
    variant: str
    base_number: str | None
    name: str


def _folded(text: str) -> str:
    return _SLUG.sub("", text.replace("\u2019", "'").casefold())


def _digits(core: str) -> int:
    return int(re.sub(r"[^0-9]", "", core.split("+")[0]))


def plan_product(product, set_entry: dict, set_of_size: dict[int, str], set_of_name: dict[str, str]) -> Plan | None:
    """The printing a product names, or None when its number or tags do not say (no number, oversized, a promo whose
    total is no set's size)."""
    number = (product.number or "").strip()
    pair = _TOKEN_PAIR.match(number)
    m = _NUMBER.match(number)
    if not pair and not m:
        return None
    core = "+".join(sorted(pair.groups())) if pair else m["core"]
    suffix = "" if pair else m["suffix"]
    tags = _TAG.findall(product.name)
    if any(t.casefold() == _REFUSED_TAG for t in tags):
        return None
    name = _TAG.sub("", product.name).strip()
    code, prefix, variant, base = set_entry["id"], "", "", None
    if set_entry["type"] == "promo":
        named = [set_of_name[t] for t in tags if t in set_of_name]
        total = int(m["total"]) if m and m["total"] else None
        if named and core.startswith("R"):
            # "Calm Rune (Vendetta) (Metal)" is a stamp on the rune, which is not the set's own printing.
            if [t for t in tags if t not in set_of_name and t != f"{core}{suffix}"]:
                return None
            code = named[0]
        else:
            if total is not None:
                if total not in set_of_size:
                    return None
                prefix = set_of_size[total]
                base = f"{prefix}-{core}"
            elif core[0].isdigit():
                return None
            kept = [t for t in tags if t.casefold() not in _NOTE_TAGS and t != f"{core}{suffix}" and t not in set_of_name]
            variant = _SLUG.sub("-", " ".join(kept).casefold()).strip("-")
    tail = f".{variant}" if variant else ""
    return Plan(f"{code}-{prefix}{core}{suffix}{tail}", f"{code}-{prefix}{core}", code, _digits(core), suffix, variant, base, name)


def _split_name(name: str) -> tuple[str, str | None]:
    """ "Sett, The Boss" is the card Sett with the subtitle The Boss. A double-sided token keeps its whole name."""
    if "//" in name or ", " not in name:
        return name, None
    head, _, tail = name.partition(", ")
    return head, tail


def _infer_stamp_finishes(printings: dict[str, dict]) -> int:
    """Give an unpriced stamped printing the finish of its stamp, when every priced printing of the stamp agrees.
    Returns how many printings gained one."""
    seen: dict[str, set[str]] = collections.defaultdict(set, {k: set(v) for k, v in STAMP_FINISHES.items()})
    for p in printings.values():
        if p.get("variant") and p.get("finishes"):
            seen[p["variant"]].update(p["finishes"])
    inferred = 0
    for p in printings.values():
        found = seen.get(p.get("variant", ""), set())
        if p.get("variant") and not p.get("finishes") and len(found) == 1:
            p["finishes"] = sorted(found)
            inferred += 1
    return inferred


def _remove_minted(files: dict[str, dict]) -> None:
    """Drop the printings an earlier run minted, and any card or file left with none."""
    for stem in list(files):
        body = files[stem]
        for card in body["cards"]:
            card["printings"] = [p for p in card["printings"] if p.get("source") != SOURCE]
        body["cards"] = [c for c in body["cards"] if c["printings"]]
        if not body["cards"]:
            del files[stem]


class Minter:
    """Adds printings for products the gallery does not list, and the cards that hold them."""

    def __init__(self, files: dict[str, dict]):
        self.files = files
        self.cards = {c["number"]: c for body in files.values() for c in body["cards"]}
        self.by_name: dict[tuple[str, str | None], dict] = {}
        for card in self.cards.values():
            self.by_name.setdefault((card["name"], card.get("subtitle")), card)

    def names_the_card(self, plan: Plan) -> bool:
        """False when the plan's card number already holds a card this product's name is not. "Jarvan IV, Exemplar of
        Demacia" is not RAD-179, Aphelios, Exalted. A signature is listed under its champion or its subtitle, so either
        part of the product's name may be the card's name."""
        card = self.cards.get(plan.card_number)
        if card is None:
            return True
        parts = {_folded(p) for p in plan.name.split(", ")} | {_folded(plan.name)}
        known = {_folded(card["name"]), _folded(card.get("subtitle") or ""),
                 _folded(f"{card['name']}, {card.get('subtitle') or ''}")} - {""}
        known |= {_folded(t) for t in card.get("tags", [])}
        return bool(parts & known)

    def _card(self, plan: Plan) -> dict:
        found = self.cards.get(plan.card_number)
        if found is not None:
            return found
        name, subtitle = _split_name(plan.name)
        source = self.cards.get(plan.base_number) if plan.base_number else None
        source = source or self.by_name.get((name, subtitle))
        facts = {k: v for k, v in (source or {}).items() if k not in ("number", "printings", "names", "subtitles")}
        if not source:
            facts = {"name": name, **({"subtitle": subtitle} if subtitle else {})}
        card = {"number": plan.card_number, **facts, "printings": []}
        self.cards[plan.card_number] = card
        self.files.setdefault(plan.set_code, {"cards": []})["cards"].append(card)
        return card

    def _rarity(self, plan: Plan, product) -> str:
        rarity = (product.rarity or "").casefold()
        if rarity in RARITIES:
            return rarity
        base = self.cards.get(plan.base_number) if plan.base_number else None
        return base["printings"][0]["rarity"] if base else FALLBACK_RARITY

    def mint(self, plan: Plan, product) -> dict:
        card = self._card(plan)
        printing: dict = {"id": plan.printing_id, "collectorNumber": plan.collector_number}
        if plan.suffix:
            printing["suffix"] = plan.suffix
        if plan.variant:
            printing["variant"] = plan.variant
        printing.update({"rarity": self._rarity(plan, product), "source": SOURCE, "identifiers": {}})
        card["printings"].append(printing)
        return printing

    def sort(self) -> None:
        for body in self.files.values():
            for card in body["cards"]:
                card["printings"].sort(key=lambda p: (p.get("source") == SOURCE, p["id"]))
            minted = [c for c in body["cards"] if all(p.get("source") == SOURCE for p in c["printings"])]
            gallery = [c for c in body["cards"] if c not in minted]
            body["cards"] = gallery + sorted(minted, key=lambda c: c["number"])


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
    _remove_minted(files)
    # English printings only: TCGplayer sells no other language, and a ~ko id is not a key a product can name
    by_key = {p["id"]: p for body in files.values() for c in body["cards"] for p in c["printings"]
              if rbjson.language(p) == "en"}
    set_codes = {s["id"]: s for s in sets}
    sizes = collections.Counter(s.get("collectorNumberMax") for s in sets)
    # A size two sets share cannot place a promo, so it is left out and the promo goes to review.
    set_of_size = {s["collectorNumberMax"]: s["id"] for s in sets
                   if "collectorNumberMax" in s and sizes[s["collectorNumberMax"]] == 1}
    set_of_name = {r["name"]: s["id"] for s in sets for r in s.get("releases", []) if r.get("language", "en") == "en"}
    minter = Minter(files)
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
            plan = plan_product(product, set_entry, set_of_size, set_of_name)
            if plan is None:
                counts["unmatched"] += 1
                review["unmatched"].append({"productId": product.product_id, "group": set_entry["id"],
                                            "name": product.name, "number": product.number})
                continue
            printing = by_key.get(plan.printing_id)
            match = MATCH
            if printing is None:
                if not minter.names_the_card(plan):
                    counts["unmatched"] += 1
                    review["unmatched"].append({"productId": product.product_id, "group": set_entry["id"],
                                                "name": product.name, "number": product.number})
                    continue
                printing = by_key[plan.printing_id] = minter.mint(plan, product)
                counts["minted"] += 1
            if printing.get("source") == SOURCE:
                match = MINTED
                held = printing.get("tcgplayer", {}).get("name")
                if held and _TAG.sub("", held).strip() != plan.name:
                    counts["unmatched"] += 1
                    review["unmatched"].append({"productId": product.product_id, "group": set_entry["id"],
                                                "name": product.name, "number": product.number})
                    continue
            ids = printing.setdefault("identifiers", {}).setdefault("tcgplayerProductIds", [])
            if product.product_id not in ids:
                ids.append(product.product_id)
            printing["tcgplayer"] = {"name": product.name, "match": match}
            found = finishes.get(product.product_id, set())
            if found:
                printing["finishes"] = sorted(set(printing.get("finishes", [])) | found)
            counts["matched"] += 1
    counts["finishes_inferred"] = _infer_stamp_finishes(by_key)
    minter.sort()
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
