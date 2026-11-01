# rbjson

An open dataset of Riftbound sets, cards and printings, built from Riot's official card gallery. Every gallery
entry is one printing, every printing carries the gallery id and public code it came from, and the variants of
one collector number (OGN-119/298 and its alternate art OGN-119a/298) are one card with two printings.

Release 0.1.0 holds 6 sets, 1,237 cards and 1,408 printings, in English.

rbjson is the Riftbound sibling of [opjson](https://github.com/ArthurG-data/opjson),
[ygjson](https://github.com/ArthurG-data/ygjson) and [pkmjson](https://github.com/ArthurG-data/pkmjson), and
follows their layout, file shapes and release scheme.

## Using the data

Each tagged release attaches three files to a GitHub release:

```
https://github.com/ArthurG-data/rbjson/releases/latest/download/AllSets.json
https://github.com/ArthurG-data/rbjson/releases/latest/download/AllCards.json
https://github.com/ArthurG-data/rbjson/releases/latest/download/AllPrintings.json
```

Every file is `{"meta": {"version": "0.1.0", "date": "2026-11-01"}, "data": {...}}`. All three come from one
build, so a reader that downloads them separately can check that the versions agree.

| File | Keyed by | Holds |
|---|---|---|
| `AllSets.json` | set code (`OGN`) | type, set size, and per release (`en`) the name, date and source page |
| `AllCards.json` | card number (`OGN-119`) | the facts every printing of the card shares, and the ids of its printings |
| `AllPrintings.json` | printing id (`OGN-119a`) | set, card number, language, collector number, suffix, rarity, image link, artists, gallery identifiers |

## Identity

Riot prints `{SET}-{NUMBER}{suffix}/{set size}` on every card. rbjson keeps the left half as the printing id
and drops the suffix for the card number:

| Printed | Card | Printing | Meaning |
|---|---|---|---|
| `OGN-119/298` | `OGN-119` | `OGN-119` | the base printing |
| `OGN-119a/298` | `OGN-119` | `OGN-119a` | an alternate art of the same card |
| `OGN-304*/298` | `OGN-304` | `OGN-304*` | a further variant of an overnumbered card (304 > 298) |
| `RAD-SP1/005` | `RAD-SP1` | `RAD-SP1` | a promo numbered in its own SP series |
| `RAD-R04a` | `RAD-R04` | `RAD-R04a` | a rune; runes are numbered R01 to R06 and have no set size |
| `UNL-T01` | `UNL-T01` | `UNL-T01` | a token |

A card above the set size is an overnumbered variant. The gallery gives most of them the rarity `showcase`.
Finishes are not in the data yet: the gallery does not state them, and the rule that ties finish to rarity is
not confirmed, so they wait for the TCGCSV step, whose products carry Normal and Foil sub-types.

## Layout

- `sets/sets.json` lists every set the gallery knows, with its type and set size. A new set is added here by
  hand before the importer will file its cards, because the gallery does not say what kind of product it is.
- `data/cards/<set>.json` holds the cards by set, each with every printing of it. A card holds the facts the
  gallery gives every printing: name, subtitle, type, super types, domains, energy, power, might, might bonus
  and tags. No ability text, flavour text or art is copied; images are links to Riot's CDN.
- `review/gallery.json` lists the variants whose gallery entry disagrees with their base entry on a card fact.
  Today that is 21 alternate arts tagged differently from their base. The base entry's facts win.
- `schema/` holds the JSON Schemas `sets.schema.json` and `cards.schema.json`.

A few gallery entries have no card type or domain (13 in Radiance, 2 in Unleashed, all unreleased cards at the
time of writing). The fields are simply absent on those cards until the gallery fills them in.

## Tools

```
uv sync --group dev
uv run python tools/import_gallery.py        # rebuild data/cards from the gallery (cached in .cache/)
uv run python tools/validate.py [--online [--images]]
uv run python tools/build.py --version 0.1.0 # write dist/
uv run pytest -q
```

`import_gallery.py` reads the gallery page to find the current Next.js build id, then downloads
`/_next/data/<build id>/<locale>/card-gallery.json`. It takes `--locale` (`en-us` by default; the gallery also
serves `fr-fr`, `de-de`, `ja-jp` and `ko-kr`) and marks the printings of a non-English locale with their
language. Only English is imported today.

`validate.py --online` fetches the gallery again and reports any printing whose entry is gone and any entry the
data lacks. `--images` also checks that every card image is still served; CI runs it only for a release tag.

## Releasing

Tag `vX.Y.Z` on `main`. CI validates, builds `dist/` and attaches the three files to a GitHub release.

## Licence

The tools are MIT (`LICENSE`). The data is CC BY 4.0 (`LICENSE-DATA`). See `NOTICE` for what the data does
and does not copy from Riot.
