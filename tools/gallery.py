"""Fetch Riot's card gallery, the one JSON document behind playriftbound.com/<locale>/card-gallery.

The page is a Next.js build: its HTML names a build id, and the gallery data lives at
/_next/data/<build id>/<locale>/card-gallery.json. The build id changes with every site deploy, so it is read
from the page on each fetch and never kept.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import net

SITE = "https://playriftbound.com"
# The gallery locale that serves each printing language.
LOCALE = {"en": "en-us", "fr": "fr-fr", "de": "de-de", "ja": "ja-jp", "ko": "ko-kr"}
BLADE = "riftboundCardGallery"
BUILD_ID = re.compile(r'"buildId":"([^"]+)"')


def build_id(html: str) -> str:
    m = BUILD_ID.search(html)
    if not m:
        raise ValueError("the gallery page names no Next.js build id")
    return m.group(1)


def data_url(build: str, locale: str) -> str:
    return f"{SITE}/_next/data/{build}/{locale}/card-gallery.json"


def blade(page: dict) -> dict:
    """The gallery blade of the page document: its sets and cards."""
    for b in page["pageProps"]["page"]["blades"]:
        if b.get("type") == BLADE:
            return b
    raise ValueError(f"the page has no {BLADE} blade")


READS = 3


def fetch(locale: str = "en-us", cache: Path | None = None, refresh: bool = False) -> dict:
    """The gallery blade for a locale. With cache, the page document is kept at cache/gallery-<locale>.json and
    read from there on the next call, unless refresh asks for the live gallery again."""
    if cache:
        return blade(net.cached(cache / f"gallery-{locale}.json", refresh, lambda: _page(locale)))
    return blade(_page(locale))


def _page(locale: str) -> dict:
    html = net.get(f"{SITE}/{locale}/card-gallery", timeout=120).decode("utf-8")
    url = data_url(build_id(html), locale)
    # Riot's gallery now and then omits one entry from a response (seen 2026-11-04: 1,407 of 1,408, a different
    # entry each time). Two identical requests were not enough on CI (SFD-119 on 2026-11-04, SFD-054 on 11-05),
    # likely because a cache served the same response twice. So each read gets its own query string, which the
    # data route ignores, and an entry any read has is kept.
    return union_pages(*(json.loads(net.get(f"{url}?read={n}", timeout=120)) for n in range(READS)))


def union_pages(first: dict, *others: dict) -> dict:
    """``first`` with each card entry only a later page holds added after its own, in read order."""
    items = cards(blade(first))
    seen = {e["id"] for e in items}
    for other in others:
        for e in cards(blade(other)):
            if e["id"] not in seen:
                items.append(e)
                seen.add(e["id"])
    return first


def sets(gallery: dict) -> list[dict]:
    return gallery["sets"]["items"]


def cards(gallery: dict) -> list[dict]:
    return gallery["cards"]["items"]
