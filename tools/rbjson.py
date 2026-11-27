"""Load, validate and flatten rbjson sets and cards."""
from __future__ import annotations

import collections
import json
import re
import unicodedata
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SETS = ROOT / "sets" / "sets.json"
CARDS = ROOT / "data" / "cards"
SEALED = ROOT / "data" / "sealed"
SCHEMAS = ROOT / "schema"

# A promo set's number names the set it reprints (OPP-VEN134 is 134/166), and a stamped version adds a variant
# (OPP-OGN269.metal-best-of). T06+T07 is a double-sided token.
NUMBER = re.compile(r"^(?P<set>[A-Z]{2,3})-(?P<core>(?:[A-Z]{3})?[0-9]{3}|(?:[A-Z]{3})?SP[0-9]+|R[0-9]{2}|T[0-9]{2}(?:\+T[0-9]{2})?)"
                    r"(?P<suffix>[a-z*]?)(?:\.(?P<variant>[a-z0-9-]+))?(?:~(?P<lang>[a-z]{2}))?$")


_NOT_SLUG = re.compile(r"[^a-z0-9]+")
_NOT_FOLDED = re.compile(r"[^\w,' ]")


def slug(text: str) -> str:
    """Lowercase letters and digits, each run of anything else a hyphen: "Origins - Booster Display" ->
    "origins-booster-display", "Metal Best Of" -> "metal-best-of"."""
    return _NOT_SLUG.sub("-", text.casefold()).strip("-")


def fold(name: str) -> str:
    """A name as names are compared across sources: casefolded, accents removed, a hyphen a space, punctuation other
    than commas and apostrophes dropped. "Rek’Saí" -> "rek'sai"."""
    s = unicodedata.normalize("NFKD", name.replace("’", "'").replace("-", " "))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(_NOT_FOLDED.sub("", s.casefold()).split())


def _schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMAS / name).read_text(encoding="utf-8")), format_checker=FormatChecker())


def language(p: dict) -> str:
    """A printing's language. Absent means English."""
    return p.get("language", "en")


def split_id(printing_id: str) -> tuple[str, str, str]:
    """(set, card number, suffix) of a printing id: OGN-119a -> ("OGN", "OGN-119", "a"). A language mark
    (OGN-119a~ko) is ignored."""
    m = NUMBER.match(printing_id)
    if not m:
        raise ValueError(f"not a printing id: {printing_id}")
    return m["set"], f"{m['set']}-{m['core']}", m["suffix"]


def variant_of(printing_id: str) -> str:
    """The variant in a printing id: OPP-OGN269.metal-best-of -> "metal-best-of", OGN-119a -> ""."""
    m = NUMBER.match(printing_id)
    if not m:
        raise ValueError(f"not a printing id: {printing_id}")
    return m["variant"] or ""


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
    errors = _schema_errors(sets, files, sealed)
    if errors:
        return errors  # the checks below assume the documents have the right shape
    set_ids = collections.Counter(s["id"] for s in sets)
    releases = {s["id"]: {r["language"] for r in s["releases"]} for s in sets}
    printing_ids: dict[str, str] = {}
    product_owner: dict[int, str] = {}
    errors += _set_errors(sets, set_ids)
    errors += _card_errors(files, set_ids)
    errors += _printing_errors(files, releases, printing_ids)
    errors += _owner_errors(files, sets, product_owner)
    errors += _sealed_errors(sealed, set_ids, set(printing_ids), product_owner)
    return errors


def _cards(files: dict[str, dict]):
    """(file stem, card) for every card, in file order."""
    for stem, body in files.items():
        for card in body["cards"]:
            yield stem, card


def _schema_errors(sets: list[dict], files: dict[str, dict], sealed: dict[str, dict]) -> list[str]:
    errors = [f"sets.json: {e.json_path}: {e.message}" for e in _schema("sets.schema.json").iter_errors(sets)]
    for folder, schema, bodies in (("cards", "cards.schema.json", files), ("sealed", "sealed.schema.json", sealed)):
        validator = _schema(schema)
        for stem, body in bodies.items():
            errors += [f"{folder}/{stem}.json: {e.json_path}: {e.message}" for e in validator.iter_errors(body)]
    return errors


def _set_errors(sets: list[dict], set_ids: collections.Counter) -> list[str]:
    errors = [f"sets.json: set {s} is listed {n} times" for s, n in set_ids.items() if n > 1]
    for s in sets:
        langs = collections.Counter(r["language"] for r in s["releases"])
        errors += [f"sets.json: set {s['id']} has {n} {lang} releases" for lang, n in langs.items() if n > 1]
        if s["type"] != "promo" and "collectorNumberMax" not in s:
            errors.append(f"sets.json: set {s['id']} needs collectorNumberMax: only a promo set has no size of its own")
        if "parent" in s and (s["parent"] == s["id"] or s["parent"] not in set_ids):
            errors.append(f"sets.json: set {s['id']}: parent {s['parent']} is not a set")
    return errors


def _card_errors(files: dict[str, dict], set_ids: collections.Counter) -> list[str]:
    """Where each card is filed, and its names and subtitles in each language."""
    errors = [f"cards/{stem}.json: {stem} is not a set in sets.json" for stem in files if stem not in set_ids]
    numbers = collections.Counter()
    for stem, card in _cards(files):
        number = card["number"]
        numbers[number] += 1
        if number.split("-", 1)[0] != stem:
            errors.append(f"cards/{stem}.json: card {number} belongs in cards/{number.split('-', 1)[0]}.json")
        card_langs = {language(p) for p in card["printings"]}
        for field in ("names", "subtitles"):
            for lang in card.get(field, {}):
                if lang not in card_langs:
                    errors.append(f"card {number}: {field} has a {lang} entry but no printing in {lang}")
        if "names" in card and card["names"].get("en", card["name"]) != card["name"]:
            errors.append(f"card {number}: names.en must be the card's name")
        if "subtitles" in card and card["subtitles"].get("en", card.get("subtitle")) != card.get("subtitle"):
            errors.append(f"card {number}: subtitles.en must be the card's subtitle")
    return errors + [f"card {n} is listed {c} times" for n, c in numbers.items() if c > 1]


def _printing_errors(files: dict[str, dict], releases: dict[str, set[str]], printing_ids: dict[str, str]) -> list[str]:
    """Each printing's id against its fields, its card and its language. Fills ``printing_ids`` with {printing id:
    card number}."""
    errors: list[str] = []
    gallery_ids: dict[tuple[str, str], str] = {}
    for stem, card in _cards(files):
        number = card["number"]
        ids_of_card = {p["id"] for p in card["printings"]}
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
            if p.get("variant", "") != variant_of(pid):
                errors.append(f"printing {pid}: variant field must be {variant_of(pid)!r}")
            lang = language(p)
            if pid.partition("~")[2] != ("" if lang == "en" else lang):
                errors.append(f"printing {pid}: a printing in {lang} has the id mark ~{lang}, and English has none")
            elif lang != "en" and pid.partition("~")[0] not in ids_of_card:
                errors.append(f"printing {pid}: its English printing {pid.partition('~')[0]} does not exist")
            if stem in releases and lang not in releases[stem]:
                errors.append(f"printing {pid}: set {stem} has no {lang} release")
            if lang != "en" and p["identifiers"].get("cardmarketProductIds"):
                errors.append(f"printing {pid}: Cardmarket products are matched to English printings, so a {lang} printing has none")
            if lang != "en" and ("tcgplayer" in p or "finishes" in p or p["identifiers"].get("tcgplayerProductIds")):
                errors.append(f"printing {pid}: TCGplayer sells English cards, so a {lang} printing has no TCGplayer data")
            if ("tcgplayer" in p) != bool(p["identifiers"].get("tcgplayerProductIds")):
                errors.append(f"printing {pid}: tcgplayer and identifiers.tcgplayerProductIds come together")
            if p["source"] != "riot-gallery":
                if not p["identifiers"].get("tcgplayerProductIds"):
                    errors.append(f"printing {pid}: a printing the gallery does not list needs its TCGplayer product")
                continue
            gid = p["identifiers"]["galleryId"]
            if (lang, gid) in gallery_ids:
                errors.append(f"gallery entry {gid} is on {gallery_ids[lang, gid]} and {pid}")
            gallery_ids[lang, gid] = pid
            if p["identifiers"]["publicCode"].split("/")[0] != pid.partition("~")[0]:
                errors.append(f"printing {pid}: publicCode {p['identifiers']['publicCode']} names another printing")
    return errors


def _owner_errors(files: dict[str, dict], sets: list[dict], product_owner: dict[int, str]) -> list[str]:
    """A TCGplayer or Cardmarket product on one printing only, and a Cardmarket expansion on one set. Fills
    ``product_owner`` with {TCGplayer product id: printing id}, for the sealed check."""
    errors: list[str] = []
    cardmarket_owner: dict[int, str] = {}
    for _, card in _cards(files):
        for p in card["printings"]:
            for owners, key, shop in ((product_owner, "tcgplayerProductIds", "TCGplayer"),
                                      (cardmarket_owner, "cardmarketProductIds", "Cardmarket")):
                for product_id in p["identifiers"].get(key, []):
                    if product_id in owners:
                        errors.append(f"{shop} product {product_id} is on {owners[product_id]} and {p['id']}")
                    owners[product_id] = p["id"]
    expansion_owner: dict[int, str] = {}
    for s in sets:
        for expansion in s.get("cardmarketExpansionIds", []):
            if expansion in expansion_owner:
                errors.append(f"sets.json: Cardmarket expansion {expansion} is on {expansion_owner[expansion]} and {s['id']}")
            expansion_owner[expansion] = s["id"]
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
