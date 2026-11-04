"""TCGplayer's Riftbound catalogue as mirrored by TCGCSV (category 89), cached under .cache/tcgcsv."""
from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

TCGCSV = "https://tcgcsv.com/tcgplayer"
CATEGORY = 89
USER_AGENT = "rbjson/0.2 (+https://github.com/ArthurG-data/rbjson)"
FETCH_DELAY_S = 0.5
# TCGplayer's price sub-types, as the finish each names.
FINISHES = {"Normal": "nonfoil", "Foil": "foil"}


@dataclass(frozen=True)
class Product:
    product_id: int
    group_id: int
    name: str
    extended: dict
    released_on: str | None = None  # TCGplayer's own release date for the product (presaleInfo), when it gives one

    @property
    def number(self) -> str | None:
        """What TCGplayer prints as the card number: ``119a/298``, ``R04a``, ``T01 // T02``; None on a sealed product."""
        return self.extended.get("Number")

    @property
    def is_single(self) -> bool:
        return bool(self.extended.get("Number") or self.extended.get("Rarity"))


def _get(url: str, cache: Path, refresh: bool) -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (url.removeprefix(TCGCSV + "/").replace("/", "_") + ".json")
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    time.sleep(FETCH_DELAY_S)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("success", True):
        raise RuntimeError(f"{url}: {data.get('errors')}")
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def groups(cache: Path, refresh: bool = False) -> list[dict]:
    return _get(f"{TCGCSV}/{CATEGORY}/groups", cache, refresh)["results"]


def products(group_id: int, cache: Path, refresh: bool = False) -> list[Product]:
    rows = _get(f"{TCGCSV}/{CATEGORY}/{group_id}/products", cache, refresh)["results"]
    return [Product(product_id=r["productId"], group_id=r["groupId"], name=r["name"],
                    extended={e["name"]: e["value"] for e in r.get("extendedData") or []},
                    released_on=((r.get("presaleInfo") or {}).get("releasedOn") or "")[:10] or None)
            for r in rows]


def prices(group_id: int, cache: Path, refresh: bool = False) -> list[dict]:
    return _get(f"{TCGCSV}/{CATEGORY}/{group_id}/prices", cache, refresh)["results"]
