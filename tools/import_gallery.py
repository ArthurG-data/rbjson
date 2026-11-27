"""Rebuild data/cards/<set>.json from Riot's card gallery.

    uv run python tools/import_gallery.py [--refresh] [--locale ko-kr ...] [--cache .cache]

The gallery is read from .cache/gallery-<locale>.json when it is there; --refresh fetches it from Riot again.

Every gallery entry is one printing. Entries that share a number (OGN-119/298 and OGN-119a/298) are one card
with two printings; the card's facts come from the entry without a suffix when there is one. A variant whose
entry disagrees with the base on a fact (the gallery tags some alternate arts differently) is listed in
review/gallery.json and takes the base's facts. A set the gallery lists that sets/sets.json does not is reported
and skipped, so a new set is added by hand first, with its type.

English is built first. Then each locale in LOCALES is fetched and its entries are matched to the English ones
by gallery id: an entry whose card image differs from the English entry's is a printing in that language
(``OGN-119a~ko``), filed on the same card, and the card gains the entry's name in ``names`` (and its subtitle
in ``subtitles``). An entry whose image equals the English one is a translated page over English cards and adds
nothing. An entry a locale has that English lacks is reported and not written.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import gallery
import rbjson
import uuids

CODE = re.compile(r"^(?P<set>[A-Z]{3})-(?P<core>[A-Z]*[0-9]+)(?P<suffix>[a*]?)(?:/[0-9]+)?$")
SCALARS = ("energy", "power", "might", "mightBonus")
# Locales merged into the English cards. Riot also serves fr-fr, de-de, es-es, it-it and ja-jp, but in each of
# them every card image and name equals English (measured 2026-11-04), so they hold no printings. zh-cn is the
# Chinese release, a different card pool, and is out of scope. Add a locale here when its images differ.
LOCALES = ("ko-kr",)
# Facts the gallery gets wrong, checked by hand against the printed card. Each names what the gallery says and what
# the card prints, so a correction Riot has since made in the gallery is reported and can be removed.
CORRECTIONS = rbjson.ROOT / "corrections" / "gallery.json"
TAG_REVIEW = rbjson.ROOT / "review" / "gallery-tags.json"


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


def load_corrections(path: Path = CORRECTIONS) -> dict[str, dict[str, dict]]:
    """{card number: {field: correction}} from corrections/gallery.json."""
    if not path.exists():
        return {}
    out: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    for c in json.loads(path.read_text(encoding="utf-8")):
        out[c["card"]][c["field"]] = c
    return dict(out)


def _corrected(facts: dict, fixes: dict[str, dict]) -> dict:
    """``facts`` with each field the gallery states as the correction expects replaced by the printed value."""
    out = dict(facts)
    for field, fix in fixes.items():
        if out.get(field) == fix["gallery"]:
            if fix["printed"] is None:
                out.pop(field, None)
            else:
                out[field] = fix["printed"]
    return out


def correction_notes(entries: list[dict], corrections: dict[str, dict[str, dict]]) -> tuple[list[str], list[str]]:
    """(notes, problems) about the corrections themselves: one the gallery now agrees with is a note (remove it), one
    whose card the gallery now states otherwise, or no longer lists, is a problem (look at the card again)."""
    facts = {}
    for entry in entries:
        _, number, suffix = parse_code(entry["publicCode"])
        if number in corrections and (not suffix or number not in facts):
            facts[number] = card_facts(entry)
    notes, problems = [], []
    for number, fixes in sorted(corrections.items()):
        for field, fix in sorted(fixes.items()):
            if number not in facts:
                problems.append(f"corrections/gallery.json: the gallery no longer lists {number}")
                continue
            said = facts[number].get(field)
            if said == fix["printed"]:
                notes.append(f"corrections/gallery.json: the gallery now gives {number} its printed {field}; remove the correction")
            elif said != fix["gallery"]:
                problems.append(f"corrections/gallery.json: the gallery now gives {number} {field} {said!r}, neither "
                                f"{fix['gallery']!r} nor the printed {fix['printed']!r}: check the card again")
    return notes, problems


def build_files(entries: list[dict], known_sets: set[str], language: str = "en",
                corrections: dict[str, dict[str, dict]] | None = None) -> tuple[dict[str, dict], list[str], list[dict]]:
    """data/cards file bodies by set, the problems met on the way (unknown sets), and the variants that disagree
    with their base entry on a card fact, one record per differing field. ``corrections`` (load_corrections) fix
    what the gallery states wrongly, on every entry of the card."""
    corrections = corrections or {}
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
        fixes = corrections.get(number, {})
        facts = _corrected(card_facts(base), fixes)
        for pid, _, entry in variants:
            if entry is base:
                continue
            other = _corrected(card_facts(entry), fixes)
            for field in sorted(set(facts) | set(other)):
                if facts.get(field) != other.get(field):
                    disagreements.append({"printing": pid, "base": base["publicCode"], "field": field,
                                          "printing_value": other.get(field), "base_value": facts.get(field)})
        card = {"number": number, **facts,
                "printings": [printing(e, pid, suffix, language) for pid, suffix, e in variants]}
        files[number.split("-", 1)[0]]["cards"].append(card)
    return dict(files), problems, disagreements


def merge_locale(files: dict[str, dict], english: list[dict], entries: list[dict], language: str) -> tuple[int, list[str]]:
    """Add one locale's printings to the English ``files`` in place: the entries whose image differs from the
    English entry's. Returns the printings added and the entries English lacks (reported, not written)."""
    live = {e["id"]: e["cardImage"]["url"] for e in english}
    twins = {p["identifiers"]["galleryId"]: (card, p) for body in files.values() for card in body["cards"]
             for p in card["printings"]}
    problems: list[str] = []
    added: dict[str, list[tuple[dict, dict]]] = collections.defaultdict(list)
    for entry in entries:
        if entry["id"] not in live:
            problems.append(f"{entry['publicCode']}: the {language} gallery has entry {entry['id']}, English does not")
            continue
        if entry["id"] not in twins or entry["cardImage"]["url"] == live[entry["id"]]:
            continue
        card, twin = twins[entry["id"]]
        added[card["number"]].append((twin, entry))
    n = 0
    for body in files.values():
        for card in body["cards"]:
            found = added.get(card["number"])
            if not found:
                continue
            for twin, entry in found:
                p = printing(entry, twin["id"] + "~" + language, twin.get("suffix", ""), language)
                p["rarity"], p["collectorNumber"] = twin["rarity"], twin["collectorNumber"]
                card["printings"].append(p)
                n += 1
            # the base printing's entry names the card, else the first variant that has a printing
            entry = next((e for t, e in found if not t.get("suffix")), found[0][1])
            rebuilt = {}
            for key, value in card.items():
                rebuilt[key] = value
                if key == "name":
                    rebuilt["names"] = {**card.get("names", {"en": card["name"]}), language: entry["name"]}
                if key == "subtitle" and entry.get("subtitle"):
                    rebuilt["subtitles"] = {**card.get("subtitles", {"en": card["subtitle"]}), language: entry["subtitle"]}
            card.clear()
            card.update(rebuilt)
    return n, problems


def others(on_disk: dict[str, dict], files: dict[str, dict], listed: set[str]) -> dict[str, dict | None]:
    """The card files this run did not rebuild. A set the gallery no longer lists (``listed`` is the gallery's own set
    list) loses its gallery printings, and the printings import_tcgcsv minted stay for it to manage; None for a file
    left with no card. A set the gallery still lists but sent no entry for is kept as it is: that is a short answer
    from the gallery, not a removal."""
    out: dict[str, dict | None] = {}
    for stem, body in on_disk.items():
        if stem in files:
            continue
        if stem in listed:
            out[stem] = body
            print(f"the gallery lists set {stem} but sent no entry for it: cards/{stem}.json is kept as it is",
                  file=sys.stderr)
            continue
        cards = [{**c, "printings": [p for p in c["printings"] if p["source"] != "riot-gallery"]} for c in body["cards"]]
        cards = [c for c in cards if c["printings"]]
        out[stem] = {**body, "cards": cards} if cards else None
    return out


def reprint_tags(files: dict[str, dict]) -> list[dict]:
    """The cards of one name and subtitle (one oracleId) whose tags differ, each with its tags. The gallery often
    tags a showcase reprint without its region, which the printed card has; a tag checked against the card goes in
    corrections/gallery.json."""
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for body in files.values():
        for card in body["cards"]:
            groups[rbjson.oracle_key(card)].append(card)
    return [{"card": ", ".join(filter(None, (cards[0]["name"], cards[0].get("subtitle")))),
             "tags": {c["number"]: c.get("tags", []) for c in cards}}
            for cards in groups.values() if len({tuple(c.get("tags", [])) for c in cards}) > 1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale", action="append", help="a locale to merge into the English cards (repeatable); default LOCALES")
    ap.add_argument("--cache", type=Path, default=rbjson.ROOT / ".cache")
    ap.add_argument("--refresh", action="store_true", help="fetch the gallery again instead of reading the cache")
    args = ap.parse_args()
    known = {s["id"] for s in rbjson.load_sets()}
    g = gallery.fetch("en-us", args.cache, args.refresh)
    for s in gallery.sets(g):
        if s["id"] not in known:
            print(f"new set {s['id']} ({s['name']}, {s['collectorNumberMax']} cards): add it to sets/sets.json")
    english = gallery.cards(g)
    corrections = load_corrections()
    notes, problems = correction_notes(english, corrections)
    files, unknown, disagreements = build_files(english, known, corrections=corrections)
    problems += unknown
    for locale in args.locale or LOCALES:
        language = locale.split("-")[0]
        added, found = merge_locale(files, english, gallery.cards(gallery.fetch(locale, args.cache, args.refresh)), language)
        print(f"{locale}: {added} {language} printings")
        problems += found
    rest = others(rbjson.load_cards(), files, {s["id"] for s in gallery.sets(g)})
    kept = {stem: body for stem, body in rest.items() if body is not None}
    registry = uuids.load()
    # the files this run does not rebuild (a promo set's) are live too, so their records keep their place
    uuids.assign_cards({**kept, **files}, registry)
    for stem, body in {**kept, **files}.items():
        rbjson.dump(rbjson.CARDS / f"{stem}.json", body)
    for stem in sorted(set(rest) - set(kept)):
        (rbjson.CARDS / f"{stem}.json").unlink()
        print(f"removed cards/{stem}.json: the gallery no longer lists set {stem}")
    uuids.save(registry)
    rbjson.dump(rbjson.ROOT / "review" / "gallery.json", disagreements)
    rbjson.dump(TAG_REVIEW, reprint_tags(files))
    n = sum(len(b["cards"]) for b in files.values())
    m = sum(len(c["printings"]) for b in files.values() for c in b["cards"])
    print(f"wrote {len(files)} files: {n} cards, {m} printings; {len(disagreements)} disagreements in review/gallery.json")
    if notes:
        print("\n".join(notes))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
