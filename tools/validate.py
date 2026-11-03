"""Check sets/sets.json and data/cards against the schemas and each other. Exits 1 on any problem.

    uv run python tools/validate.py [--online [--images]]

--online fetches the gallery again and reports any printing whose gallery entry is gone, and any gallery entry
the data lacks, and asks TCGCSV whether every TCGplayer product id still exists in category 89. --images also
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

import gallery
import rbjson
import tcgcsv

IMAGE_WORKERS = 6
IMAGE_TRIES = 3


def online_errors(sets: list[dict], files: dict[str, dict], images: bool = False) -> list[str]:
    printings = rbjson.flatten(sets, files)["printings"]
    by_gallery = {p["identifiers"]["galleryId"]: pid for pid, p in printings.items()}
    live = {e["id"] for e in gallery.cards(gallery.fetch("en-us"))}
    errors = [f"printing {pid}: gallery entry {gid} is gone" for gid, pid in by_gallery.items() if gid not in live]
    errors += [f"gallery entry {gid} is not in the data: run tools/import_gallery.py" for gid in sorted(live - by_gallery.keys())]
    errors += product_errors(printings)
    if images:
        errors += image_errors(printings)
    return errors


def product_errors(printings: dict[str, dict]) -> list[str]:
    """Each TCGplayer product id the data names that category 89 no longer sells."""
    import tempfile
    from pathlib import Path

    cache = Path(tempfile.mkdtemp(prefix="rbjson-online-"))
    sold = {p.product_id for g in tcgcsv.groups(cache) for p in tcgcsv.products(g["groupId"], cache)}
    return [f"printing {pid}: TCGplayer product {product_id} is gone from category 89"
            for pid, p in sorted(printings.items())
            for product_id in p.get("identifiers", {}).get("tcgplayerProductIds", []) if product_id not in sold]


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


def image_errors(printings: dict[str, dict], head=head_status) -> list[str]:
    items = sorted(printings.items())
    with ThreadPoolExecutor(IMAGE_WORKERS) as pool:
        statuses = list(pool.map(lambda kv: head(kv[1]["image"]), items))
    return [f"printing {pid}: image answers {status or 'nothing'}" for (pid, _), status in zip(items, statuses) if status is not None]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--images", action="store_true")
    args = ap.parse_args()
    sets, files = rbjson.load_sets(), rbjson.load_cards()
    errors = rbjson.validate(sets, files)
    if not errors and args.online:
        errors = online_errors(sets, files, args.images)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)
    n = sum(len(b["cards"]) for b in files.values())
    m = sum(len(c["printings"]) for b in files.values() for c in b["cards"])
    print(f"ok: {len(sets)} sets, {n} cards, {m} printings")


if __name__ == "__main__":
    main()
