# rbjson

An open dataset of [Riftbound](https://playriftbound.com) sets, cards and printings, built from Riot's
official card gallery. Riftbound is Riot Games' League of Legends trading card game, launched in English on
31 October 2025. The gallery serves the whole catalogue as one JSON document, including sets ahead of their
street date, and rbjson turns that document into stable, versioned files a program can rely on.

Every gallery entry is one printing. The variants of one collector number (`OGN-119/298` and its alternate art
`OGN-119a/298`) are one card with two printings, and every printing keeps the gallery id and printed code it
came from, so a reader can always get back to Riot's own record.

Release 0.3.0 holds 6 sets, 1,237 cards and 1,408 printings, in English. 1,399 printings carry the TCGplayer product
that sells them and the finishes it is sold in. The starter set names its parent, and each booster set carries its
key art.

rbjson is the Riftbound sibling of [opjson](https://github.com/ArthurG-data/opjson) (One Piece),
[ygjson](https://github.com/ArthurG-data/ygjson) (Yu-Gi-Oh!) and [pkmjson](https://github.com/ArthurG-data/pkmjson)
(Pokémon sealed products). The four share one layout, one file shape and one release scheme, so a reader
written for one needs little change for another.

## Using the data

Each tagged release attaches three files to a GitHub release:

```
https://github.com/ArthurG-data/rbjson/releases/latest/download/AllSets.json
https://github.com/ArthurG-data/rbjson/releases/latest/download/AllCards.json
https://github.com/ArthurG-data/rbjson/releases/latest/download/AllPrintings.json
```

Every file is `{"meta": {"version": "0.3.0", "date": "2026-11-04"}, "data": {...}}`. All three come from one
build, so a reader that downloads them separately can check that the versions agree.

| File | Keyed by | Holds |
|---|---|---|
| `AllSets.json` | set code (`OGN`) | type, set size, parent set, TCGplayer group ids, and per release (`en`) the name, date, source page and key art |
| `AllCards.json` | card number (`OGN-119`) | the facts every printing of the card shares, its set, and the ids of its printings |
| `AllPrintings.json` | printing id (`OGN-119a`) | set, card number, language, collector number, suffix, rarity, image link, artists, finishes, gallery and TCGplayer identifiers |

The files are also what the repository's `data/` folder holds, flattened: a reader that wants the cards of one
set can read `data/cards/<set>.json` straight from a checkout instead.

## The sets

| Code | Name | Type | Set size | Cards | Printings |
|---|---|---|---|---|---|
| OGN | Origins | booster | 298 | 310 | 352 |
| OGS | Origins: Proving Grounds | starter | 24 | 24 | 24 |
| SFD | Spiritforged | booster | 221 | 252 | 288 |
| UNL | Unleashed | booster | 219 | 246 | 288 |
| VEN | Vendetta | booster | 166 | 210 | 237 |
| RAD | Radiance | booster | 167 | 195 | 219 |

A set holds more cards than its set size because overnumbered showcase cards, promos, runes and tokens sit
above or outside the numbered run. Vendetta and Radiance are in the gallery ahead of release, and a few of their
cards still lack a type or domain (see [Known gaps](#known-gaps)).

Proving Grounds ships with Origins, so `OGS` carries `parent: OGN`.

## Identity

Riot prints `{SET}-{NUMBER}{suffix}/{set size}` on every card. rbjson keeps the left half as the printing id
and drops the suffix for the card number:

| Printed | Card | Printing | Meaning |
|---|---|---|---|
| `OGN-119/298` | `OGN-119` | `OGN-119` | the base printing |
| `OGN-119a/298` | `OGN-119` | `OGN-119a` | an alternate art of the same card |
| `OGN-304*/298` | `OGN-304` | `OGN-304*` | a further variant of an overnumbered card (304 > 298) |
| `RAD-SP1/005` | `RAD-SP1` | `RAD-SP1` | a promo numbered in its own SP series |
| `RAD-R04a` | `RAD-R04` | `RAD-R04a` | a rune; runes are numbered R01 to R06 and carry no set size |
| `UNL-T01` | `UNL-T01` | `UNL-T01` | a token |

A card numbered above the set size is an overnumbered variant, and the gallery gives nearly all of them the
rarity `showcase`. The gallery's own entry id (`ogn-119a-298`) and printed code (`OGN-119a/298`) travel with
every printing under `identifiers`, so anything keyed on Riot's ids joins without a lookup table.

The same champion appears in several sets with different subtitles (Ahri, Inquisitive in Origins; Ahri,
Confident in Radiance). Each is its own card, because each has its own number, cost and stats. rbjson does
not yet link a reprint to the card it reprints.

## Cards and printings

```json
{
  "number": "OGN-119",
  "name": "Ahri",
  "subtitle": "Inquisitive",
  "type": "unit",
  "superTypes": ["champion"],
  "domains": ["mind"],
  "energy": 3,
  "power": 1,
  "might": 3,
  "tags": ["Ahri", "Ionia"],
  "printings": [
    {"id": "OGN-119", "collectorNumber": 119, "rarity": "epic", "source": "riot-gallery",
     "image": "https://cmsassets.rgpub.io/sanity/images/dsfx7636/game_data_live/cfa28e1a...-744x1039.png?accountingTag=RB",
     "artists": ["Six More Vodka"],
     "identifiers": {"galleryId": "ogn-119-298", "publicCode": "OGN-119/298"}},
    {"id": "OGN-119a", "collectorNumber": 119, "suffix": "a", "rarity": "showcase", "source": "riot-gallery",
     "image": "https://cmsassets.rgpub.io/sanity/images/dsfx7636/game_data_live/7adc5aa8...-744x1039.png?accountingTag=RB",
     "artists": ["Kudos Productions"],
     "identifiers": {"galleryId": "ogn-119a-298", "publicCode": "OGN-119a/298"}}
  ]
}
```

A card holds the facts every printing shares. All but `number`, `name` and `printings` are optional, and a
field is absent rather than null when the gallery gives nothing.

| Field | Meaning |
|---|---|
| `number` | Set code and collector number, without any variant suffix |
| `name` | The card's name as printed |
| `subtitle` | The epithet under a champion's name (Ahri, *Inquisitive*). One champion has one card per subtitle |
| `type` | `unit`, `spell`, `gear`, `battlefield`, `legend` or `rune` |
| `superTypes` | Any of `champion`, `signature`, `token`, `basic` |
| `domains` | The card's domains: `fury`, `calm`, `mind`, `body`, `order`, `chaos`, or `colorless` |
| `energy` | The energy cost |
| `power` | The power cost, paid in rune power |
| `might` | A unit's might |
| `mightBonus` | The might bonus a gear or spell grants |
| `tags` | The tags printed on the card: regions (Ionia), champions (Ahri), tribes (Poro) |

A printing holds what sets one physical card apart from another with the same number.

| Field | Meaning |
|---|---|
| `id` | The printed code before the slash: `OGN-119`, `OGN-119a`, `OGN-304*` |
| `language` | `en`, `fr`, `de`, `ja` or `ko`. Absent means `en` |
| `collectorNumber` | The number as an integer, as the gallery sorts by it |
| `suffix` | `a` or `*`, the variant mark printed after the number. Absent on the base printing |
| `rarity` | `common`, `uncommon`, `rare`, `epic` or `showcase` |
| `image` | A link to the card image on Riot's content delivery network. Not a copy |
| `artists` | The illustrators the gallery credits |
| `source` | `riot-gallery`, the only source today |
| `identifiers.galleryId` | The gallery entry's id (`ogn-119a-298`) |
| `identifiers.publicCode` | The code as the gallery prints it (`OGN-119a/298`) |
| `identifiers.tcgplayerProductIds` | The TCGplayer products that sell the printing (see [TCGplayer products](#tcgplayer-products)) |
| `finishes` | `nonfoil` and/or `foil`: the finishes TCGplayer has priced the product in. Absent on a printing it has never priced |
| `tcgplayer` | How the product was tied to the printing: its `name` and the `match` (`number`) |

No ability text, flavour text or artwork is copied into the data; see `NOTICE` for what is and is not taken
from Riot.

## Where the data comes from

The card gallery at `playriftbound.com/<locale>/card-gallery` is a Next.js page whose data lives at
`/_next/data/<build id>/<locale>/card-gallery.json`. The build id changes with every deploy of the site, so
`tools/gallery.py` reads it from the page on each run and never stores it. The JSON holds the gallery's set
list and every card entry, with its type, domains, costs, stats, tags, rarity, artist and image.

`tools/import_gallery.py` turns that document into `data/cards/<set>.json`:

1. Each entry's printed code is parsed into set, number and suffix.
2. Entries that share a number become one card. The entry without a suffix is the base; the card's facts come
   from it, and the variants become further printings.
3. A variant whose entry disagrees with the base on a card fact is recorded in `review/gallery.json` and takes
   the base's facts. The gallery tags 21 alternate arts differently from their base card today, and nothing
   else differs.
4. A set the gallery lists that `sets/sets.json` does not is reported and its cards are skipped, because the
   gallery does not say what kind of product a set is. Adding the set by hand, with its type, is the one
   manual step a new set needs.

### Set art

A release's `keyArt` is the hero image of the set's announcement on playriftbound.com. It is hotlinked from
Riot's CDN, with the article as `source` and the image's pixel size as `size`. Riot serves no standalone set
logos, so `logo` stays empty. `OGS` has no announcement of its own and has no key art. `tools/validate.py --online`
checks that each key art URL is still served.

### TCGplayer products

`tools/import_tcgcsv.py` reads TCGplayer's Riftbound catalogue as [TCGCSV](https://tcgcsv.com) mirrors it
(category 89). TCGplayer's groups are the sets, and a group's abbreviation is the set code, so a product joins its
printing by set code and the number TCGplayer prints (`119a/298` in the Origins group is `OGN-119a`), with no
image comparison. Each matched printing gets the product under `identifiers.tcgplayerProductIds`, the product's
name under `tcgplayer`, and its `finishes`; each set gets its `tcgplayerGroupIds`.

A printing's finishes are the price sub-types TCGplayer has ever priced its product in: `Normal` is `nonfoil`,
`Foil` is `foil`. TCGplayer drops a sub-type's price row while it has no price, so `data/tcgplayer_finishes.json`
records every finish seen per product across runs, and a finish stays once seen. Origins: Proving Grounds is
sold in Normal only; every other set in both.

Not matched, and listed in `review/tcgplayer-89.json`: the oversized battlefields and the Spiritforged runes and
tokens TCGplayer sells that the gallery does not list, double-sided token products (`T01 // T02`), and the
promotional groups (PR, OPP, JDG, the bundles), whose stamped copies of base cards are a later step.

Riot also publishes a licensed [Content API](https://developer.riotgames.com/apis#riftbound-content-v1). It is
in beta and English only, and rbjson does not use it yet. When it leaves beta it is the better source, and
the gallery import stays as the cross-check.

## Known gaps

- **Finishes** come from TCGplayer's price sub-types, so a printing TCGplayer has never priced has none, and a
  finish the rule of rarity would predict but TCGplayer has never priced is not claimed.
- **Promotional printings.** TCGplayer's promotional groups sell stamped copies of base cards (a launch promo of
  OGN-066, judge and organized-play promos) that the gallery does not list. They are counted in the review file
  and not yet printings of their own.
- **Untyped cards.** 13 Radiance and 2 Unleashed entries carry no type or domain in the gallery at the time of
  writing. Their `type` and `domains` are absent until Riot fills them in.
- **English only.** The gallery serves `fr-fr`, `de-de`, `ja-jp` and `ko-kr` too, and the importer takes a
  `--locale`, but only English is imported so far.
- **No sealed products, no legality.** Booster boxes, starter decks and format legality are not covered.
- **No reprint links.** A champion reprinted with the same subtitle in a later set is a separate card.

## Layout

- `sets/sets.json` lists every set, with its type, set size, parent and releases (with their key art). Hand-kept.
- `data/cards/<set>.json` holds the cards of one set, each with every printing of it. Written by the importer.
- `review/gallery.json` lists the variants whose gallery entry disagrees with their base. Written by the importer.
- `review/tcgplayer-89.json` lists the TCGplayer singles no printing matched and the groups that were not matched.
- `data/tcgplayer_finishes.json` records every finish TCGplayer has priced each product in, across runs.
- `schema/sets.schema.json` and `schema/cards.schema.json` define the two file shapes.
- `tools/` holds the two importers, the validator, the build script, and the gallery and TCGCSV fetchers.
- `tests/` checks the tools against a small gallery fixture and the committed data against the schemas.

## Building

```
uv sync --group dev
uv run python tools/import_gallery.py          # rebuild data/cards from the gallery, cached in .cache/
uv run python tools/import_tcgcsv.py           # TCGplayer product ids and finishes, cached in .cache/tcgcsv
uv run python tools/validate.py [--online [--images]]
uv run python tools/build.py --version 0.3.0   # write dist/AllSets.json, AllCards.json, AllPrintings.json
uv run pytest -q
```

`validate.py` checks the schemas and the cross-references: every printing is filed under its own number, no
id or gallery entry appears twice, every printing's language has a release, a TCGplayer product sits on one
printing. `--online` fetches the gallery again and reports any printing whose entry is gone and any entry the
data lacks, and asks TCGCSV whether every TCGplayer product id still exists. `--images` also asks Riot whether
every card image is still served, about 1,400 requests, so CI runs it only for a release tag.

`build.py` refuses to write `dist/` while the data is invalid.

## Releasing

Tag `vX.Y.Z` on `main`. CI validates the data, builds `dist/` and attaches the three files to a GitHub release
named after the tag. Readers follow `releases/latest/download/<file>`, so a new tag is all a release takes.

## Adding a set or refreshing the data

1. Run `uv run python tools/import_gallery.py`. If it names a new set, add it to `sets/sets.json` with its
   code, type, set size and English name, then run the importer again.
2. Run `uv run python tools/import_tcgcsv.py --refresh` to pick up new products and finishes.
3. Read `review/gallery.json` and `review/tcgplayer-89.json` for anything new.
4. Run `uv run python tools/validate.py --online` and `uv run pytest -q`.
5. Commit `sets/`, `data/` and `review/` together, so a release never mixes two snapshots.

## Licence

The tools are MIT (`LICENSE`). The data is CC BY 4.0 (`LICENSE-DATA`). rbjson is not endorsed by Riot Games;
see `NOTICE`.
