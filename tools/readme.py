"""Write the README's counts from the data: the paragraph that sizes the dataset and the table of sets.

    uv run python tools/readme.py [--check]

The counts change whenever the data does, so they are written, not typed: each sits between a pair of markers
(<!-- counts:start --> ... <!-- counts:end -->, <!-- sets:start --> ... <!-- sets:end -->) and this rewrites what is
between them. refresh.py runs it after the importers. --check only says whether the README is current, and exits 1
when it is not.
"""
from __future__ import annotations

import argparse
import re
import sys

import rbjson

README = rbjson.ROOT / "README.md"


def _n(k: int) -> str:
    return f"{k:,}"


def counts(sets: list[dict], files: dict[str, dict], sealed: dict[str, dict]) -> str:
    cards = [c for body in files.values() for c in body["cards"]]
    printings = [p for c in cards for p in c["printings"]]
    english = [p for p in printings if rbjson.language(p) == "en"]
    minted = [p for p in printings if p["source"] == "tcgplayer"]
    pictured = sum(1 for p in minted if "image" in p)
    other = len(printings) - len(english)
    sold = sum(1 for p in english if p["identifiers"].get("tcgplayerProductIds"))
    cardmarket = sum(1 for p in english if p["identifiers"].get("cardmarketProductIds"))
    products = sum(len(body["products"]) for body in sealed.values())
    return (f"The data holds {len(sets)} sets, {_n(len(cards))} cards, {_n(len(printings))} printings and {products} "
            f"sealed products. {_n(len(english))} printings are English and {_n(other)} are Korean, each beside its "
            f"English twin on the same card, which carries its Korean name. {_n(len(printings) - len(minted))} "
            f"printings come from the gallery and {_n(len(minted))} from TCGplayer's catalogue: the runes, signatures, "
            f"tokens and promos the gallery leaves out, {_n(pictured)} of them with TCGplayer's image. {_n(sold)} "
            f"English printings carry the TCGplayer product that sells them, and {_n(cardmarket)} carry the Cardmarket "
            f"product that sells them. Every card, printing and sealed product has a UUID that never changes.")


def sets_table(sets: list[dict], files: dict[str, dict]) -> str:
    rows = ["| Code | Name | Type | Set size | Cards | Printings |", "|---|---|---|---|---|---|"]
    for s in sets:
        cards = files.get(s["id"], {"cards": []})["cards"]
        name = next(r["name"] for r in s["releases"] if r["language"] == "en")
        rows.append(f"| {s['id']} | {name} | {s['type']} | {s.get('collectorNumberMax', '')} | {len(cards)} | "
                    f"{sum(len(c['printings']) for c in cards)} |")
    return "\n".join(rows)


def update(text: str, sets: list[dict], files: dict[str, dict], sealed: dict[str, dict]) -> str:
    """``text`` with what lies between each pair of markers written from the data."""
    for block, body in (("counts", counts(sets, files, sealed)), ("sets", sets_table(sets, files))):
        pattern = re.compile(rf"(<!-- {block}:start -->\n).*?(\n<!-- {block}:end -->)", re.S)
        if not pattern.search(text):
            raise ValueError(f"README.md has no <!-- {block}:start --> ... <!-- {block}:end --> block")
        text = pattern.sub(lambda m, body=body: m[1] + body + m[2], text)
    return text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 when the README's counts are not the data's")
    args = ap.parse_args()
    text = README.read_text(encoding="utf-8")
    new = update(text, rbjson.load_sets(), rbjson.load_cards(), rbjson.load_sealed())
    if args.check:
        if new != text:
            sys.exit("README.md's counts are not the data's: run tools/readme.py")
        return
    README.write_text(new, encoding="utf-8")
    print("README.md: counts written" if new != text else "README.md: counts already current")


if __name__ == "__main__":
    main()
