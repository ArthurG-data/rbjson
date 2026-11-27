"""A UUID for every card, printing and sealed product: given once, kept for good, the same however often it is run.

    uv run python tools/uuids.py

A UUID belongs to what a record is, which is not always its id. A gallery printing is its printed code (OGN-119a)
and a card its number (OGN-119), but a printing rbjson minted from TCGplayer and a sealed product are a TCGplayer
product: their ids (OPP-OGN269.metal-best-of, origins-booster-display) are built from product names, which TCGplayer
may change, and a sealed id can pass to another product when the one holding it is delisted. So each record has one
identity key, and data/uuids.json maps each identity key ever seen to its UUID, per kind:

- ``id:<printed code>`` for a gallery printing, ``tcgplayer:<lowest product id>`` for a minted printing or a sealed
  product, ``id:<number>`` for a card.
- An identity key seen for the first time gets ``uuid5(NAMESPACE, "<kind>:<id>")``, so a rebuild from nothing gives
  the same UUIDs. If the record replaces one that left, it takes that record's UUID instead: a record's alias keys
  (its id, its TCGplayer products, for a card the UUIDs of its printings) name what each was last on, in
  ``bridges``. A rune TCGplayer sold before the gallery listed it keeps its UUID when the gallery starts listing it,
  and a card renumbered with its printings keeps its UUID.
- A known identity key keeps its UUID. A record that leaves keeps its key, so it gets its UUID back if it returns.
- A new TCGplayer product with the id of one that left (a sealed product relisted under its old name) is taken to be
  that product and gets its UUID; a product whose own key is known keeps its own, whatever id it now has.

``keys`` only grows and never changes a value: that is the whole promise, and ``history_errors`` checks it between
two versions of the registry (validate.py --since, run in CI).
"""
from __future__ import annotations

import collections
import json
import uuid
from pathlib import Path

import rbjson

NAMESPACE = rbjson.NAMESPACE
REGISTRY = rbjson.ROOT / "data" / "uuids.json"
KINDS = ("cards", "printings", "products")


class Conflict(Exception):
    """Two live records whose identity keys hold one UUID: a record that came back while the one that took its UUID
    is still here. A person decides which is which."""


def empty() -> dict:
    return {k: {"keys": {}, "bridges": {}} for k in KINDS}


def load(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else empty()


def save(registry: dict, path: Path = REGISTRY) -> None:
    """Keys sorted, so a run that changes nothing leaves the file as it was."""
    rbjson.dump(path, {k: {part: dict(sorted(registry[k][part].items())) for part in ("keys", "bridges")} for k in KINDS})


def first(kind: str, key: str, used: set[str]) -> str:
    """The UUID of a record first seen: uuid5 of its kind and id, or of ``<kind>:<id>#2`` and on in the rare case that
    UUID is taken."""
    n = 1
    while True:
        u = str(uuid.uuid5(NAMESPACE, f"{kind}:{key}" + (f"#{n}" if n > 1 else "")))
        if u not in used:
            return u
        n += 1


def _products(record: dict) -> list[int]:
    return sorted(record.get("identifiers", {}).get("tcgplayerProductIds", []))


def identity(kind: str, record: dict) -> str:
    """The key a record's UUID belongs to: what the record is, which outlives its id."""
    if kind == "cards":
        return f"id:{record['number']}"
    products = _products(record)
    if products and (kind == "products" or record.get("source") == "tcgplayer"):
        return f"tcgplayer:{products[0]}"
    return f"id:{record['id']}"


def _aliases(kind: str, record: dict) -> list[str]:
    """Every key the record answers to: its identity, its id, its TCGplayer products, a card's printings."""
    if kind == "cards":
        return [f"id:{record['number']}", *sorted(f"printing:{p['uuid']}" for p in record["printings"])]
    return list(dict.fromkeys([identity(kind, record), f"id:{record['id']}",
                               *(f"tcgplayer:{pid}" for pid in _products(record))]))


def _assign(registry: dict, kind: str, records: dict[str, dict]) -> dict[str, str]:
    """{record id: UUID} for the live ``records`` of ``kind``; records new identity keys and the bridges in
    ``registry``. Nothing is written into the registry unless every record gets a UUID."""
    keys, bridges = registry[kind]["keys"], registry[kind]["bridges"]
    ident = {rid: identity(kind, r) for rid, r in records.items()}
    out: dict[str, str] = {}
    held: dict[str, str] = {}  # UUID -> the live record id holding it
    for rid in sorted(records, key=lambda r: ident[r]):
        u = keys.get(ident[rid])
        if u is None:
            continue
        if u in held:
            raise Conflict(f"{kind[:-1]} {rid} ({ident[rid]}) and {held[u]} both hold {u}: one of them came back "
                           f"after the other took its UUID")
        out[rid], held[u] = u, rid
    used = set(keys.values()) | set(bridges.values())
    for rid in sorted((r for r in records if r not in out), key=lambda r: ident[r]):
        # a record that left, named by one of this record's keys: the first alias that names a free UUID
        u = next((h for a in _aliases(kind, records[rid]) if (h := keys.get(a) or bridges.get(a)) and h not in held), None)
        u = u or first(kind, rid, used)
        out[rid], held[u] = u, rid
        used.add(u)
    for rid, record in records.items():
        keys.setdefault(ident[rid], out[rid])
        for alias in _aliases(kind, record):
            if alias != ident[rid]:
                bridges[alias] = out[rid]
    return out


def _stamp(record: dict, after: str, u: str) -> None:
    """Put ``uuid`` right after the record's id field, in place."""
    rest = {k: v for k, v in record.items() if k != "uuid"}
    record.clear()
    for k, v in rest.items():
        record[k] = v
        if k == after:
            record["uuid"] = u


def _run(registry: dict, kind: str, records: dict[str, dict], after: str) -> None:
    out = _assign(registry, kind, records)
    for rid, record in records.items():
        _stamp(record, after, out[rid])


def assign_cards(files: dict[str, dict], registry: dict) -> None:
    """Stamp a UUID on every card and printing of ``files``, and record them in ``registry``. The printings go first:
    a card's alias keys are its printings' UUIDs."""
    _run(registry, "printings", {p["id"]: p for b in files.values() for c in b["cards"] for p in c["printings"]}, "id")
    _run(registry, "cards", {c["number"]: c for b in files.values() for c in b["cards"]}, "number")


def assign_products(sealed: dict[str, dict], registry: dict) -> None:
    """Stamp a UUID on every sealed product, and record them in ``registry``."""
    _run(registry, "products", {p["id"]: p for b in sealed.values() for p in b["products"]}, "id")


def _live(files: dict[str, dict], sealed: dict[str, dict]) -> dict[str, dict[str, dict]]:
    return {"cards": {c["number"]: c for b in files.values() for c in b["cards"]},
            "printings": {p["id"]: p for b in files.values() for c in b["cards"] for p in c["printings"]},
            "products": {p["id"]: p for b in sealed.values() for p in b["products"]}}


def errors(files: dict[str, dict], sealed: dict[str, dict], registry: dict) -> list[str]:
    """The records whose UUID is missing or is not the one data/uuids.json gives their identity, and any UUID two
    records share."""
    found: list[str] = []
    every: collections.Counter = collections.Counter()
    for kind, records in _live(files, sealed).items():
        keys = registry[kind]["keys"]
        for rid, record in sorted(records.items()):
            key = identity(kind, record)
            if "uuid" not in record:
                found.append(f"{kind[:-1]} {rid} has no uuid: run tools/uuids.py")
                continue
            if keys.get(key) != record["uuid"]:
                found.append(f"{kind[:-1]} {rid}: uuid {record['uuid']} is not the one data/uuids.json gives {key}, "
                             f"{keys.get(key)}: run tools/uuids.py")
            every[record["uuid"]] += 1
    found += [f"uuid {u} is on {n} records" for u, n in sorted(every.items()) if n > 1]
    return found


def history_errors(before: dict, after: dict) -> list[str]:
    """What breaks the promise between two versions of the registry: an identity key dropped or given another UUID."""
    found = []
    for kind in KINDS:
        now = after[kind]["keys"]
        for key, u in sorted(before[kind]["keys"].items()):
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
    live = _live(files, sealed)
    retired = {k: len(set(registry[k]["keys"].values()) - {r["uuid"] for r in live[k].values()}) for k in KINDS}
    print("uuids: " + ", ".join(f"{len(live[k])} {k} ({retired[k]} retired)" for k in KINDS))


if __name__ == "__main__":
    main()
