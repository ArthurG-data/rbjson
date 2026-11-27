"""Cardmarket's Riftbound product catalogue (game 22), cached under .cache/cardmarket."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import net

CATALOGUE = "https://downloads.s3.cardmarket.com/productCatalog/productList"
GAME = 22


@dataclass(frozen=True)
class Product:
    product_id: int
    expansion_id: int
    name: str


def _get(url: str, cache: Path, refresh: bool) -> dict:
    return net.cached(cache / url.rsplit("/", 1)[1], refresh, lambda: net.get_json(url))


def singles(cache: Path, refresh: bool = False) -> list[Product]:
    """Every single card Cardmarket lists for Riftbound. The file has no collector number."""
    rows = _get(f"{CATALOGUE}/products_singles_{GAME}.json", cache, refresh)["products"]
    return [Product(r["idProduct"], r["idExpansion"], r["name"]) for r in rows]
