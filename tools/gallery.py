"""Fetch Riot's card gallery, the one JSON document behind playriftbound.com/<locale>/card-gallery.

The page is a Next.js build: its HTML names a build id, and the gallery data lives at
/_next/data/<build id>/<locale>/card-gallery.json. The build id changes with every site deploy, so it is read
from the page on each fetch and never kept.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

USER_AGENT = "rbjson/0.1 (+https://github.com/ArthurG-data/rbjson)"
SITE = "https://playriftbound.com"
# The gallery locale that serves each printing language.
LOCALE = {"en": "en-us", "fr": "fr-fr", "de": "de-de", "ja": "ja-jp", "ko": "ko-kr"}
BLADE = "riftboundCardGallery"
BUILD_ID = re.compile(r'"buildId":"([^"]+)"')


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


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


def fetch(locale: str = "en-us", cache: Path | None = None) -> dict:
    """The gallery blade for a locale. With cache, the page document is kept at cache/gallery-<locale>.json and
    read from there on the next call."""
    if cache:
        path = cache / f"gallery-{locale}.json"
        if path.exists():
            return blade(json.loads(path.read_text(encoding="utf-8")))
    html = _get(f"{SITE}/{locale}/card-gallery").decode("utf-8")
    raw = _get(data_url(build_id(html), locale))
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return blade(json.loads(raw))


def sets(gallery: dict) -> list[dict]:
    return gallery["sets"]["items"]


def cards(gallery: dict) -> list[dict]:
    return gallery["cards"]["items"]
