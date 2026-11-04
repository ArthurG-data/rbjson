"""Load, validate and flatten rbjson sets and cards."""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SETS = ROOT / "sets" / "sets.json"
CARDS = ROOT / "data" / "cards"
SEALED = ROOT / "data" / "sealed"
SCHEMAS = ROOT / "schema"

NUMBER = re.compile(r"^(?P<set>[A-Z]{3})-(?P<core>[0-9]{3}|SP[0-9]+|R[0-9]{2}|T[0-9]{2})(?P<suffix>[a*]?)$")


def _schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMAS / name).read_text(encoding="utf-8")), format_checker=FormatChecker())


def language(p: dict) -> str:
    """A printing's language. Absent means English."""
    return p.get("language", "en")


def split_id(printing_id: str) -> tuple[str, str, str]:
    """(set, card number, suffix) of a printing id: OGN-119a -> ("OGN", "OGN-119", "a")."""
    m = NUMBER.match(printing_id)
    if not m:
        raise ValueError(f"not a printing id: {printing_id}")
    return m["set"], f"{m['set']}-{m['core']}", m["suffix"]


def load_sets() -> list[dict]:
    return json.loads(SETS.read_text(encoding="utf-8"))


def load_cards() -> dict[str, dict]:
    """The card files by stem (set code), in name order."""
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(CARDS.glob("*.json"))}


def load_sealed(sealed_dir: Path = SEALED) -> dict[str, dict]:
    """{set id: file body}, sorted by set id."""
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(sealed_dir.glob("*.json"))}


def dump(path: Path, body: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(sets: list[dict], files: dict[str, dict], sealed: dict[str, dict] | None = None) -> list[str]:
    """Every problem found offline, one message each. Empty when the data is valid."""
    sealed = sealed or {}
    errors = [f"sets.json: {e.json_path}: {e.message}" for e in _schema("sets.schema.json").iter_errors(sets)]
    card_schema = _schema("cards.schema.json")
    for stem, body in files.items():
        errors += [f"cards/{stem}.json: {e.json_path}: {e.message}" for e in card_schema.iter_errors(body)]
    sealed_schema = _schema("sealed.schema.json")
    for stem, body in sealed.items():
        errors += [f"sealed/{stem}.json: {e.json_path}: {e.message}" for e in sealed_schema.iter_errors(body)]
    if errors:
        return errors  # the checks below assume the documents have the right shape

    set_ids = collections.Counter(s["id"] for s in sets)
    errors += [f"sets.json: set {s} is listed {n} times" for s, n in set_ids.items() if n > 1]
    releases = {s["id"]: {r["language"] for r in s["releases"]} for s in sets}
    for s in sets:
        langs = collections.Counter(r["language"] for r in s["releases"])
        errors += [f"sets.json: set {s['id']} has {n} {lang} releases" for lang, n in langs.items() if n > 1]
        if "parent" in s and (s["parent"] == s["id"] or s["parent"] not in set_ids):
            errors.append(f"sets.json: set {s['id']}: parent {s['parent']} is not a set")

    numbers = collections.Counter()
    printing_ids: dict[str, str] = {}
    gallery_ids: dict[str, str] = {}
    for stem, body in files.items():
        if stem not in set_ids:
            errors.append(f"cards/{stem}.json: {stem} is not a set in sets.json")
        for card in body["cards"]:
            number = card["number"]
            numbers[number] += 1
            if number.split("-", 1)[0] != stem:
                errors.append(f"cards/{stem}.json: card {number} belongs in cards/{number.split('-', 1)[0]}.json")
            for p in card["printings"]:
                pid = p["id"]
                if pid in printing_ids:
                    errors.append(f"printing {pid} is listed twice ({printing_ids[pid]} and {number})")
                printing_ids[pid] = number
                _, owner, suffix = split_id(pid)
                if owner != number:
                    errors.append(f"printing {pid} is filed under card {number}")
                if p.get("suffix", "") != suffix:
                    errors.append(f"printing {pid}: suffix field must be {suffix!r}, not {p.get('suffix', '')!r}")
                lang = language(p)
                if stem in releases and lang not in releases[stem]:
                    errors.append(f"printing {pid}: set {stem} has no {lang} release")
                gid = p["identifiers"]["galleryId"]
                if gid in gallery_ids:
                    errors.append(f"gallery entry {gid} is on {gallery_ids[gid]} and {pid}")
                gallery_ids[gid] = pid
                if p["identifiers"]["publicCode"].split("/")[0] != pid:
                    errors.append(f"printing {pid}: publicCode {p['identifiers']['publicCode']} names another printing")
    errors += [f"card {n} is listed {c} times" for n, c in numbers.items() if c > 1]
    product_owner: dict[int, str] = {}
    for body in files.values():
        for card in body["cards"]:
            for p in card["printings"]:
                for product_id in p.get("identifiers", {}).get("tcgplayerProductIds", []):
                    if product_id in product_owner:
                        errors.append(f"TCGplayer product {product_id} is on {product_owner[product_id]} and {p['id']}")
                    product_owner[product_id] = p["id"]
                if ("tcgplayer" in p) != bool(p.get("identifiers", {}).get("tcgplayerProductIds")):
                    errors.append(f"printing {p['id']}: tcgplayer and identifiers.tcgplayerProductIds come together")
    errors += _sealed_errors(sealed, set_ids, set(printing_ids), product_owner)
    return errors


def _sealed_errors(sealed: dict[str, dict], set_ids, printing_ids: set[str], product_owner: dict[int, str]) -> list[str]:
    errors = []
    products = collections.Counter(p["id"] for body in sealed.values() for p in body["products"])
    errors += [f"sealed product id {i} is used {n} times" for i, n in products.items() if n > 1]
    for stem, body in sealed.items():
        for p in body["products"]:
            where = f"sealed/{stem}.json: {p['id']}"
            if p["set"] != stem:
                errors.append(f"{where}: filed under {stem} but its set is {p['set']}")
            if p["set"] not in set_ids:
                errors.append(f"{where}: set {p['set']} is not in sets.json")
            for product_id in p.get("identifiers", {}).get("tcgplayerProductIds", []):
                if product_id in product_owner:
                    errors.append(f"TCGplayer product {product_id} is on {product_owner[product_id]} and {p['id']}")
                product_owner[product_id] = p["id"]
            contents = p["contents"]
            for item in contents.get("sealed", []):
                if item["product"] not in products or item["product"] == p["id"]:
                    errors.append(f"{where}: holds {item['product']}, which is not another sealed product")
            for item in contents.get("cards", []):
                if item["printing"] not in printing_ids:
                    errors.append(f"{where}: holds printing {item['printing']}, which does not exist")
            for item in contents.get("pool", []):
                if item["set"] not in set_ids:
                    errors.append(f"{where}: pool set {item['set']} is not in sets.json")
            if p["contentsStatus"] == "unknown" and any(contents.values()):
                errors.append(f"{where}: lists contents but says contentsStatus unknown")
            if p["contentsStatus"] == "complete" and any("count" not in i for k in ("sealed", "cards")
                                                       for i in contents.get(k, [])):
                errors.append(f"{where}: complete contents need a count on every item")
    return errors


def flatten(sets: list[dict], files: dict[str, dict], sealed: dict[str, dict] | None = None) -> dict[str, dict]:
    """The release shape: sets, cards, printings and sealed products each keyed by id, every printing carrying
    its set and card."""
    out_sets = {s["id"]: s for s in sets}
    cards: dict[str, dict] = {}
    printings: dict[str, dict] = {}
    for body in files.values():
        for card in body["cards"]:
            facts = {k: v for k, v in card.items() if k != "printings"}
            facts["set"] = card["number"].split("-", 1)[0]
            facts["printings"] = [p["id"] for p in card["printings"]]
            cards[card["number"]] = facts
            for p in card["printings"]:
                printings[p["id"]] = {"number": card["number"], "set": facts["set"], "language": language(p),
                                      **{k: v for k, v in p.items() if k != "language"}}
    products = {p["id"]: p for body in (sealed or {}).values() for p in body["products"]}
    return {"sets": out_sets, "cards": cards, "printings": printings, "products": products}
