"""Rebuild data/cards/<set>.json from Riot's card gallery.

    uv run python tools/import_gallery.py [--locale en-us] [--cache .cache]

Every gallery entry is one printing. Entries that share a number (OGN-119/298 and OGN-119a/298) are one card
with two printings; the card's facts come from the entry without a suffix when there is one. A variant whose
entry disagrees with the base on a fact (the gallery tags some alternate arts differently) is listed in
review/gallery.json and takes the base's facts. A set the gallery lists that sets/sets.json does not is reported
and skipped, so a new set is added by hand first, with its type.
"""
from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

import gallery
import rbjson

CODE = re.compile(r"^(?P<set>[A-Z]{3})-(?P<core>[A-Z]*[0-9]+)(?P<suffix>[a*]?)(?:/[0-9]+)?$")
SCALARS = ("energy", "power", "might", "mightBonus")


def parse_code(public_code: str) -> tuple[str, str, str]:
    """(set, card number, suffix) of a gallery code: "OGN-119a/298" -> ("OGN", "OGN-119", "a"),
    "RAD-R04a" -> ("RAD", "RAD-R04", "a"), "UNL-T01" -> ("UNL", "UNL-T01", "")."""
    m = CODE.match(public_code)
    if not m:
        raise ValueError(f"unrecognised card code: {public_code}")
    core = m["core"]
    if core.isdigit():
        core = f"{int(core):03d}"
    return m["set"], f"{m['set']}-{core}", m["suffix"]


def _ids(block: dict | None, key: str) -> list[str]:
    return [v["id"] for v in (block or {}).get(key, [])]


def card_facts(entry: dict) -> dict:
    """The facts every printing of a card shares, from one gallery entry."""
    facts: dict = {"name": entry["name"]}
    if entry.get("subtitle"):
        facts["subtitle"] = entry["subtitle"]
    types = _ids(entry.get("cardType"), "type")
    if types:
        facts["type"] = types[0]
    supers = _ids(entry.get("cardType"), "superType")
    if supers:
        facts["superTypes"] = supers
    domains = _ids(entry.get("domain"), "values")
    if domains:
        facts["domains"] = domains
    for key in SCALARS:
        value = (entry.get(key) or {}).get("value")
        if value is not None:
            facts[key] = int(value["id"])
    tags = (entry.get("tags") or {}).get("tags")
    if tags:
        facts["tags"] = tags
    return facts


def printing(entry: dict, printing_id: str, suffix: str, language: str) -> dict:
    p: dict = {"id": printing_id}
    if language != "en":
        p["language"] = language
    p["collectorNumber"] = int(entry["collectorNumber"])
    if suffix:
        p["suffix"] = suffix
    p["rarity"] = entry["rarity"]["value"]["id"]
    p["image"] = entry["cardImage"]["url"]
    artists = [v["label"] for v in (entry.get("illustrator") or {}).get("values", [])]
    if artists:
        p["artists"] = artists
    p["source"] = "riot-gallery"
    p["identifiers"] = {"galleryId": entry["id"], "publicCode": entry["publicCode"]}
    return p


def _sort_key(printing_id: str) -> tuple:
    _, number, suffix = rbjson.split_id(printing_id)
    core = number.split("-", 1)[1]
    kind = 0 if core.isdigit() else {"S": 1, "R": 2, "T": 3}[core[0]]
    return kind, int(re.sub(r"[^0-9]", "", core)), suffix


def build_files(entries: list[dict], known_sets: set[str], language: str = "en") -> tuple[dict[str, dict], list[str], list[dict]]:
    """data/cards file bodies by set, the problems met on the way (unknown sets), and the variants that disagree
    with their base entry on a card fact, one record per differing field."""
    problems: list[str] = []
    disagreements: list[dict] = []
    by_card: dict[str, list[tuple[str, str, dict]]] = collections.defaultdict(list)
    for entry in entries:
        set_id, number, suffix = parse_code(entry["publicCode"])
        if set_id not in known_sets:
            problems.append(f"{entry['publicCode']}: set {set_id} is not in sets/sets.json")
            continue
        by_card[number].append((f"{number}{suffix}", suffix, entry))

    files: dict[str, dict] = collections.defaultdict(lambda: {"cards": []})
    for number in sorted(by_card, key=_sort_key):
        variants = sorted(by_card[number], key=lambda v: _sort_key(v[0]))
        base = next((e for pid, suffix, e in variants if not suffix), variants[0][2])
        facts = card_facts(base)
        for pid, suffix, entry in variants:
            if entry is base:
                continue
            other = card_facts(entry)
            for field in sorted(set(facts) | set(other)):
                if facts.get(field) != other.get(field):
                    disagreements.append({"printing": pid, "base": base["publicCode"], "field": field,
                                          "printing_value": other.get(field), "base_value": facts.get(field)})
        card = {"number": number, **facts,
                "printings": [printing(e, pid, suffix, language) for pid, suffix, e in variants]}
        files[number.split("-", 1)[0]]["cards"].append(card)
    return dict(files), problems, disagreements


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale", default="en-us")
    ap.add_argument("--cache", type=Path, default=rbjson.ROOT / ".cache")
    args = ap.parse_args()
    language = args.locale.split("-")[0]
    known = {s["id"] for s in rbjson.load_sets()}
    g = gallery.fetch(args.locale, args.cache)
    for s in gallery.sets(g):
        if s["id"] not in known:
            print(f"new set {s['id']} ({s['name']}, {s['collectorNumberMax']} cards): add it to sets/sets.json")
    files, problems, disagreements = build_files(gallery.cards(g), known, language)
    for stem, body in files.items():
        rbjson.dump(rbjson.CARDS / f"{stem}.json", body)
    rbjson.dump(rbjson.ROOT / "review" / "gallery.json", disagreements)
    n = sum(len(b["cards"]) for b in files.values())
    m = sum(len(c["printings"]) for b in files.values() for c in b["cards"])
    print(f"wrote {len(files)} files: {n} cards, {m} printings; {len(disagreements)} disagreements in review/gallery.json")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
