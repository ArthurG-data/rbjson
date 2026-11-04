"""Cardmarket's Riftbound product catalogue (game 22), cached under .cache/cardmarket."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CATALOGUE = "https://downloads.s3.cardmarket.com/productCatalog/productList"
GAME = 22
USER_AGENT = "rbjson (+https://github.com/ArthurG-data/rbjson)"


@dataclass(frozen=True)
class Product:
    product_id: int
    expansion_id: int
    name: str


def _get(url: str, cache: Path, refresh: bool) -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / url.rsplit("/", 1)[1]
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def singles(cache: Path, refresh: bool = False) -> list[Product]:
    """Every single card Cardmarket lists for Riftbound. The file has no collector number."""
    rows = _get(f"{CATALOGUE}/products_singles_{GAME}.json", cache, refresh)["products"]
    return [Product(r["idProduct"], r["idExpansion"], r["name"]) for r in rows]
