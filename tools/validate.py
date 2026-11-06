"""Check sets/sets.json and data/cards against the schemas and each other. Exits 1 on any problem.

    uv run python tools/validate.py [--online [--images]]

--online fetches the gallery again (English, and each other language the data has printings in) and reports any
printing whose gallery entry is gone, and any gallery entry the data lacks (in another language, one whose image
differs from English), and asks TCGCSV whether every TCGplayer product id, on a printing or a sealed product, still exists in category 89, and Cardmarket whether every Cardmarket product id is still in its singles list. It also asks whether each
set's key art and logo are still served. --images also
asks Riot whether every card image is still served: about 1,400 requests, so CI runs it only for a release tag. They go IMAGE_WORKERS at a time, and a 5xx or a dropped connection is retried
before it counts.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import cardmarket
import gallery
import rbjson
import tcgcsv

IMAGE_WORKERS = 6
IMAGE_TRIES = 3


def online_errors(sets: list[dict], files: dict[str, dict], images: bool = False,
                  sealed: dict[str, dict] | None = None) -> list[str]:
    printings = rbjson.flatten(sets, files)["printings"]
    errors: list[str] = []
    english = {e["id"]: e for e in gallery.cards(gallery.fetch("en-us"))}
    for lang in sorted({p["language"] for p in printings.values()}):
        tag = "" if lang == "en" else f"{lang} "
        by_gallery = {p["identifiers"]["galleryId"]: pid for pid, p in printings.items()
                      if p["language"] == lang and p["source"] == "riot-gallery"}
        entries = english if lang == "en" else {e["id"]: e for e in gallery.cards(gallery.fetch(gallery.LOCALE[lang]))}
        errors += [f"printing {pid}: {tag}gallery entry {gid} is gone" for gid, pid in by_gallery.items() if gid not in entries]
        # English lists every entry as a printing; another language only the entries whose image differs
        wanted = {gid for gid, e in entries.items()
                  if lang == "en" or (gid in english and e["cardImage"]["url"] != english[gid]["cardImage"]["url"])}
        errors += [f"{tag}gallery entry {gid} is not in the data: run tools/import_gallery.py" for gid in sorted(wanted - by_gallery.keys())]
    errors += product_errors(printings, rbjson.flatten(sets, files, sealed)["products"])
    errors += cardmarket_errors(printings)
    errors += set_art_errors(sets)
    if images:
        errors += image_errors(printings)
    return errors


def product_errors(printings: dict[str, dict], products: dict[str, dict] | None = None) -> list[str]:
    """Each TCGplayer product id the data names, on a printing or a sealed product, that category 89 no longer sells."""
    import tempfile
    from pathlib import Path

    cache = Path(tempfile.mkdtemp(prefix="rbjson-online-"))
    sold = {p.product_id for g in tcgcsv.groups(cache) for p in tcgcsv.products(g["groupId"], cache)}
    return [f"{kind} {key}: TCGplayer product {product_id} is gone from category 89"
            for kind, items in (("printing", printings), ("sealed product", products or {}))
            for key, p in sorted(items.items())
            for product_id in p.get("identifiers", {}).get("tcgplayerProductIds", []) if product_id not in sold]


def cardmarket_errors(printings: dict[str, dict]) -> list[str]:
    """Each Cardmarket product id the data names that Cardmarket's singles list no longer holds."""
    import tempfile
    from pathlib import Path

    sold = {p.product_id for p in cardmarket.singles(Path(tempfile.mkdtemp(prefix="rbjson-online-")))}
    return [f"printing {key}: Cardmarket product {product_id} is gone from the singles list"
            for key, p in sorted(printings.items())
            for product_id in p.get("identifiers", {}).get("cardmarketProductIds", []) if product_id not in sold]


def head_status(url: str) -> int | None:
    """The HTTP status a HEAD of url fails with, None when it is served. A 5xx or a dropped connection is tried
    IMAGE_TRIES times; a 4xx is final."""
    status = 0
    for attempt in range(IMAGE_TRIES):
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": gallery.USER_AGENT})
        try:
            urllib.request.urlopen(req, timeout=30).close()
            return None
        except urllib.error.HTTPError as e:
            status = e.code
            if status < 500:
                return status
        except urllib.error.URLError:
            status = 0
        time.sleep(2 ** attempt)
    return status


def set_art_errors(sets: list[dict], head=head_status) -> list[str]:
    """Each release's key art and logo that Riot's CDN no longer serves."""
    items = [(f"set {s['id']} {label}", r[field]["url"])
             for s in sets for r in s.get("releases", [])
             for field, label in (("keyArt", "key art"), ("logo", "logo")) if field in r]
    with ThreadPoolExecutor(IMAGE_WORKERS) as pool:
        statuses = list(pool.map(lambda item: head(item[1]), items))
    return [f"{what}: answers {status or 'nothing'}" for (what, _), status in zip(items, statuses) if status is not None]


def image_errors(printings: dict[str, dict], head=head_status) -> list[str]:
    items = sorted((pid, p) for pid, p in printings.items() if "image" in p)
    with ThreadPoolExecutor(IMAGE_WORKERS) as pool:
        statuses = list(pool.map(lambda kv: head(kv[1]["image"]), items))
    return [f"printing {pid}: image answers {status or 'nothing'}" for (pid, _), status in zip(items, statuses) if status is not None]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--images", action="store_true")
    args = ap.parse_args()
    sets, files, sealed = rbjson.load_sets(), rbjson.load_cards(), rbjson.load_sealed()
    errors = rbjson.validate(sets, files, sealed)
    if not errors and args.online:
        errors = online_errors(sets, files, args.images, sealed)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)
    n = sum(len(b["cards"]) for b in files.values())
    m = sum(len(c["printings"]) for b in files.values() for c in b["cards"])
    k = sum(len(b["products"]) for b in sealed.values())
    print(f"ok: {len(sets)} sets, {n} cards, {m} printings, {k} sealed products")


if __name__ == "__main__":
    main()
