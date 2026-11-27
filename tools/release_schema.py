"""The JSON schemas of the release files, dist/All*.json, built from the schemas of the files in data/.

A release file is ``{"meta": {"version", "date"}, "data": {id: record}}``, and its records are the data/ records
flattened (rbjson.flatten): a card carries its set and oracleId and lists its printings by id, and a printing
carries its card number, set and language. Building these from schema/ keeps the two from drifting apart. build.py
checks each file against its schema and writes the schemas next to the files, for a reader to check its download.
"""
from __future__ import annotations

import copy
import json

import rbjson

BASE = "https://github.com/ArthurG-data/rbjson/schema/release"
UUID = {"type": "string", "format": "uuid"}


def _source(name: str) -> dict:
    return json.loads((rbjson.SCHEMAS / name).read_text(encoding="utf-8"))


def _release(name: str, title: str, record: dict, defs: dict | None = None) -> dict:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{BASE}/{name}.schema.json",
        "title": title,
        "type": "object",
        "additionalProperties": False,
        "required": ["meta", "data"],
        "properties": {
            "meta": {"type": "object", "additionalProperties": False, "required": ["version", "date"],
                     "properties": {"version": {"type": "string", "minLength": 1},
                                    "date": {"type": "string", "format": "date"}}},
            "data": {"type": "object", "additionalProperties": record},
        },
    }
    if defs:
        schema["$defs"] = defs
    return schema


def _with(record: dict, required: list[str], **properties: dict) -> dict:
    out = copy.deepcopy(record)
    out["properties"].update(properties)
    out["required"] = list(dict.fromkeys([*out.get("required", []), *required]))
    return out


def schemas() -> dict[str, dict]:
    """{release file name: its schema}."""
    sets = _source("sets.schema.json")["items"]
    cards = _source("cards.schema.json")
    sealed = _source("sealed.schema.json")["properties"]["products"]["items"]
    defs = cards["$defs"]
    set_code = {"type": "string", "pattern": "^[A-Z]{2,3}$"}

    card = _with(cards["properties"]["cards"]["items"], ["set", "oracleId", "uuid"],
                 set=set_code, oracleId={**UUID, "description": "Shared by every card with this name and subtitle: "
                                                                "a reprint has its own number and the same oracleId."},
                 printings={"type": "array", "minItems": 1, "items": defs["printing"]["properties"]["id"]})
    printing = _with(defs["printing"], ["number", "set", "language", "uuid", "finishesKnown"],
                     number=cards["properties"]["cards"]["items"]["properties"]["number"], set=set_code,
                     finishesKnown={"type": "boolean", "description": "Whether the printing's finishes are known: "
                                    "false means unknown (never priced by TCGplayer, or a Korean printing), never "
                                    "that it has no finish. True with finishesInferred when they were inferred."})
    return {
        "AllSets": _release("AllSets", "rbjson sets", sets),
        "AllCards": _release("AllCards", "rbjson cards", card, {"byLanguage": defs["byLanguage"]}),
        "AllPrintings": _release("AllPrintings", "rbjson printings", printing),
        "AllProducts": _release("AllProducts", "rbjson sealed products", _with(sealed, ["uuid"])),
    }
