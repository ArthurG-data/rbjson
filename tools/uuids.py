"""A UUID for every card, printing and sealed product: given once, kept for good, the same however often it is run.

    uv run python tools/uuids.py

The ids rbjson builds (OGN-119a, OPP-OGN269.metal-best-of, origins-booster-display) say what a record is, and some
of them are built from names another site chooses: a promo's variant and a sealed product's id come from TCGplayer's
product names. A UUID is the key a catalogue can hold on to instead. data/uuids.json records which UUID each id has,
and the importers stamp it on the records they write:

- A record seen for the first time gets ``uuid5(NAMESPACE, "<kind>:<id>")``, so a rebuild from nothing gives every
  record the UUID it had.
- A record whose id the registry knows keeps its UUID.
- A record with a new id takes the UUID of the record it replaces, when that record left and they share a TCGplayer
  product (a promo whose product TCGplayer renamed), or, for a card, when its printings were the left card's
  printings. The old id stays in ``retired`` with the UUID, so either id finds it.
- A record that leaves moves to ``retired`` with its UUID, and gets it back if it returns.

So a UUID is never reused for another record and an id never changes UUID. ``history_errors`` checks that between
two versions of the registry, and validate.py --since runs it in CI.
"""
from __future__ import annotations

import collections
import json
import uuid
from collections.abc import Callable
from pathlib import Path

import rbjson

NAMESPACE = rbjson.NAMESPACE
REGISTRY = rbjson.ROOT / "data" / "uuids.json"
KINDS = ("cards", "printings", "products")


class Conflict(Exception):
    """An id returns whose UUID another record now holds. A person decides which record it is."""


def empty() -> dict:
    return {**{k: {} for k in KINDS}, "retired": {k: {} for k in KINDS}, "tcgplayer": {}}


def load(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else empty()


def save(registry: dict, path: Path = REGISTRY) -> None:
    """Keys sorted, so a run that changes nothing leaves the file as it was."""
    body = {k: dict(sorted(registry[k].items())) for k in KINDS}
    body["retired"] = {k: dict(sorted(registry["retired"][k].items())) for k in KINDS}
    body["tcgplayer"] = dict(sorted(registry["tcgplayer"].items(), key=lambda kv: int(kv[0])))
    rbjson.dump(path, body)


def first(kind: str, key: str, used: set[str]) -> str:
    """The UUID a record gets when it is first seen: uuid5 of its kind and id, or of ``<kind>:<id>#2`` and on in the
    rare case that UUID went to another record before."""
    n = 1
    while True:
        u = str(uuid.uuid5(NAMESPACE, f"{kind}:{key}" + (f"#{n}" if n > 1 else "")))
        if u not in used:
            return u
        n += 1


def _assign(registry: dict, kind: str, records: dict[str, dict],
            candidates: Callable[[str, dict], list[str]]) -> dict[str, str]:
    """{id: UUID} for the live ``records``; updates the registry's current and retired ids of ``kind``.
    ``candidates(id, record)`` names the UUIDs a new id may take over."""
    current, retired = registry[kind], registry["retired"][kind]
    used = set(current.values()) | set(retired.values())
    out: dict[str, str] = {}
    held: dict[str, str] = {}  # UUID -> the live id that holds it
    new: list[str] = []
    for key in sorted(records):
        if key in current:
            out[key] = current[key]
            held[current[key]] = key
        else:
            new.append(key)
    for key in new:
        u = retired.get(key)
        if u is not None and u in held:
            raise Conflict(f"{kind} {key} is back, and its UUID {u} is now on {held[u]}")
        if u is None:
            free = sorted({c for c in candidates(key, records[key]) if c and c not in held})
            u = free[0] if len(free) == 1 else first(kind, key, used)
        out[key] = u
        held[u] = key
        used.add(u)
    for key in [k for k in current if k not in records]:
        retired[key] = current.pop(key)
    for key, u in out.items():
        retired.pop(key, None)
        current[key] = u
    return out


def _anchors(registry: dict, record: dict) -> list[str]:
    """The UUIDs the record's TCGplayer products were on in the last run."""
    return [registry["tcgplayer"].get(str(pid)) for pid in record.get("identifiers", {}).get("tcgplayerProductIds", [])]


def _note_anchors(registry: dict, records: dict[str, dict], out: dict[str, str]) -> None:
    for key, record in records.items():
        for pid in record.get("identifiers", {}).get("tcgplayerProductIds", []):
            registry["tcgplayer"][str(pid)] = out[key]


def _stamp(record: dict, after: str, u: str) -> None:
    """Put ``uuid`` right after the record's id field, in place."""
    rest = {k: v for k, v in record.items() if k != "uuid"}
    record.clear()
    for k, v in rest.items():
        record[k] = v
        if k == after:
            record["uuid"] = u


def assign_cards(files: dict[str, dict], registry: dict) -> None:
    """Stamp a UUID on every card and printing of ``files`` (all the card files, so that a record missing from them
    counts as gone), and record them in ``registry``."""
    printings = {p["id"]: p for body in files.values() for c in body["cards"] for p in c["printings"]}
    was_on = {u: pid for pid, u in registry["printings"].items()}  # UUID -> printing id, before this run
    out = _assign(registry, "printings", printings, lambda key, p: _anchors(registry, p))
    _note_anchors(registry, printings, out)
    for pid, p in printings.items():
        _stamp(p, "id", out[pid])

    cards = {c["number"]: c for body in files.values() for c in body["cards"]}
    card_uuid = {**registry["retired"]["cards"], **registry["cards"]}

    def left_card(key: str, card: dict) -> list[str]:
        # the cards that held this card's printings before; one of them, if it left, is this card renumbered
        before = {rbjson.split_id(was_on[p["uuid"]])[1] for p in card["printings"] if p["uuid"] in was_on}
        return [card_uuid.get(n) for n in before if n not in cards]

    out = _assign(registry, "cards", cards, left_card)
    for number, card in cards.items():
        _stamp(card, "number", out[number])


def assign_products(sealed: dict[str, dict], registry: dict) -> None:
    """Stamp a UUID on every sealed product, and record them in ``registry``."""
    products = {p["id"]: p for body in sealed.values() for p in body["products"]}
    out = _assign(registry, "products", products, lambda key, p: _anchors(registry, p))
    _note_anchors(registry, products, out)
    for key, p in products.items():
        _stamp(p, "id", out[key])


def errors(files: dict[str, dict], sealed: dict[str, dict], registry: dict) -> list[str]:
    """The records whose UUID is missing or is not the registry's, the registry's ids that are no record, and any
    UUID two records share."""
    live = {"cards": {c["number"]: c for body in files.values() for c in body["cards"]},
            "printings": {p["id"]: p for body in files.values() for c in body["cards"] for p in c["printings"]},
            "products": {p["id"]: p for body in sealed.values() for p in body["products"]}}
    found: list[str] = []
    every: collections.Counter = collections.Counter()
    for kind in KINDS:
        known = registry[kind]
        for key, record in sorted(live[kind].items()):
            if "uuid" not in record:
                found.append(f"{kind[:-1]} {key} has no uuid: run tools/uuids.py")
            elif known.get(key) != record["uuid"]:
                found.append(f"{kind[:-1]} {key}: uuid {record['uuid']} is not data/uuids.json's {known.get(key)}")
        found += [f"data/uuids.json: {kind[:-1]} {key} is no longer in the data: run tools/uuids.py"
                  for key in sorted(known.keys() - live[kind].keys())]
        every.update(known.values())
        retired_on_live = set(registry["retired"][kind]) & set(known)
        found += [f"data/uuids.json: {kind[:-1]} {key} is both live and retired" for key in sorted(retired_on_live)]
    found += [f"data/uuids.json: uuid {u} is on {n} live records" for u, n in every.items() if n > 1]
    return found


def history_errors(before: dict, after: dict) -> list[str]:
    """What breaks the promise between two versions of the registry: an id whose UUID changed or was dropped."""
    found = []
    for kind in KINDS:
        then = {**before["retired"][kind], **before[kind]}
        now = {**after["retired"][kind], **after[kind]}
        for key, u in sorted(then.items()):
            if key not in now:
                found.append(f"{kind[:-1]} {key}: its uuid {u} was dropped from data/uuids.json")
            elif now[key] != u:
                found.append(f"{kind[:-1]} {key}: its uuid changed from {u} to {now[key]}")
    return found


def main() -> None:
    registry = load()
    files, sealed = rbjson.load_cards(), rbjson.load_sealed()
    assign_cards(files, registry)
    assign_products(sealed, registry)
    for stem, body in files.items():
        rbjson.dump(rbjson.CARDS / f"{stem}.json", body)
    for stem, body in sealed.items():
        rbjson.dump(rbjson.SEALED / f"{stem}.json", body)
    save(registry)
    counts = {k: len(registry[k]) for k in KINDS}
    retired = sum(len(v) for v in registry["retired"].values())
    print(f"uuids: {counts['cards']} cards, {counts['printings']} printings, {counts['products']} products; "
          f"{retired} retired")


if __name__ == "__main__":
    main()
