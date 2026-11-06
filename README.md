# rbjson

An open dataset of [Riftbound](https://playriftbound.com) sets, cards, printings and sealed products, built from Riot's
official card gallery. Riftbound is Riot Games' League of Legends trading card game, launched in English on
31 October 2025 and in Korea on 18 September 2026. The gallery serves the whole catalogue as one JSON document, including sets ahead of their
street date, and rbjson turns that document into stable, versioned files a program can rely on.

Every gallery entry is one printing. The variants of one collector number (`OGN-119/298` and its alternate art
`OGN-119a/298`) are one card with two printings, and every printing keeps the gallery id and printed code it
came from, so a reader can always get back to Riot's own record.

Release 0.4.0 holds 6 sets, 1,237 cards, 1,783 printings and 65 sealed products. 1,408 printings are English and
375 are the Korean printings of Origins and Proving Grounds, each beside its English twin on the same card, which
carries its Korean name. 1,399 English printings carry the TCGplayer product that sells them and the finishes it is
sold in, and 941 carry the Cardmarket product that sells them. The starter set names its parent, and each booster set carries its key art.

rbjson is the Riftbound sibling of [opjson](https://github.com/ArthurG-data/opjson) (One Piece),
[ygjson](https://github.com/ArthurG-data/ygjson) (Yu-Gi-Oh!) and [pkmjson](https://github.com/ArthurG-data/pkmjson)
(Pokémon sealed products). The four share one layout, one file shape and one release scheme, so a reader
written for one needs little change for another.

## Using the data

Each tagged release attaches four files to a GitHub release:

```
https://github.com/ArthurG-data/rbjson/releases/latest/download/AllSets.json
https://github.com/ArthurG-data/rbjson/releases/latest/download/AllCards.json
https://github.com/ArthurG-data/rbjson/releases/latest/download/AllPrintings.json
https://github.com/ArthurG-data/rbjson/releases/latest/download/AllProducts.json
```

Every file is `{"meta": {"version": "0.4.0", "date": "2026-11-04"}, "data": {...}}`. All four come from one
build, so a reader that downloads them separately can check that the versions agree.

| File | Keyed by | Holds |
|---|---|---|
| `AllSets.json` | set code (`OGN`) | type, set size, parent set, TCGplayer group ids (`tcgplayerGroupIds`), Cardmarket expansion ids (`cardmarketExpansionIds`), and per release (`en`, and `ko` for Origins and Proving Grounds) the name, date, source page and key art |
| `AllCards.json` | card number (`OGN-119`) | the facts every printing of the card shares, its name and subtitle in each language it has printings in, its set, and the ids of its printings |
| `AllPrintings.json` | printing id (`OGN-119a`, `OGN-119a~ko`) | set, card number, language, collector number, suffix, rarity, image link, artists, finishes, gallery, TCGplayer and Cardmarket (`cardmarketProductIds`) identifiers |
| `AllProducts.json` | product id (`origins-booster-display`) | the sealed products: set, category, name, release date, TCGplayer product id, and what the product holds |

The files are also what the repository's `data/` folder holds, flattened: a reader that wants the cards of one
set can read `data/cards/<set>.json` straight from a checkout instead.

## The sets

| Code | Name | Type | Set size | Cards | Printings |
|---|---|---|---|---|---|
| OGN | Origins | booster | 298 | 310 | 703 |
| OGS | Origins: Proving Grounds | starter | 24 | 24 | 48 |
| SFD | Spiritforged | booster | 221 | 252 | 288 |
| UNL | Unleashed | booster | 219 | 246 | 288 |
| VEN | Vendetta | booster | 166 | 210 | 237 |
| RAD | Radiance | booster | 167 | 195 | 219 |

Origins and Proving Grounds count their Korean printings (351 and 24); the other sets are English only.
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
| `name` | The card's English name as printed |
| `names` | The name in each language the card has printings in, keyed by language: `{"en": "Ahri", "ko": "아리"}`. Present on a card with a non-English printing |
| `subtitle` | The epithet under a champion's name (Ahri, *Inquisitive*). One champion has one card per subtitle |
| `subtitles` | The subtitle in each language, in the same shape as `names`, on a card that has a subtitle and a non-English printing |
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
| `id` | The printed code before the slash: `OGN-119`, `OGN-119a`, `OGN-304*`. A printing in another language adds `~` and its language to the English twin's id: `OGN-119a~ko` |
| `language` | `en`, `fr`, `de`, `ja` or `ko`. Absent means `en`; only `en` and `ko` are used today. A `ko` printing has the same number, suffix and rarity as its English twin, its own image, artists and gallery entry, and no TCGplayer data |
| `collectorNumber` | The number as an integer, as the gallery sorts by it |
| `suffix` | `a` or `*`, the variant mark printed after the number. Absent on the base printing |
| `rarity` | `common`, `uncommon`, `rare`, `epic` or `showcase` |
| `image` | A link to the card image on Riot's content delivery network. Not a copy |
| `artists` | The illustrators the gallery credits |
| `source` | `riot-gallery`, the only source today |
| `identifiers.galleryId` | The gallery entry's id (`ogn-119a-298`). A Korean printing has its English twin's id, because the Korean gallery numbers its entries the same way |
| `identifiers.publicCode` | The code as the gallery prints it (`OGN-119a/298`) |
| `identifiers.tcgplayerProductIds` | The TCGplayer products that sell the printing (see [TCGplayer products](#tcgplayer-products)) |
| `identifiers.cardmarketProductIds` | The Cardmarket product that sells the printing, on an English printing whose name fits one card and one product (see [Cardmarket products](#cardmarket-products)) |
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
4. Each locale in `LOCALES` (`ko-kr` today) is fetched and its entries are matched to the English ones by gallery
   id. An entry whose card image differs from the English entry's is a printing in that language: it joins the
   English card as `<English id>~ko`, with the same collector number, suffix and rarity, the Korean image,
   artists and identifiers, and no TCGplayer data. The card gains the entry's name in `names` and its subtitle
   in `subtitles`. An entry the locale has that English lacks is reported and not written.
5. A set the gallery lists that `sets/sets.json` does not is reported and its cards are skipped, because the
   gallery does not say what kind of product a set is. Adding the set by hand, with its type, is the one
   manual step a new set needs.

Which locales are imported was measured on 2026-11-04. The gallery serves `fr-fr`, `de-de`, `es-es`, `it-it`,
`ja-jp`, `ko-kr` and `zh-cn` with the same 1,408 entry ids as `en-us`. In `fr-fr`, `de-de`, `es-es`, `it-it` and
`ja-jp` every card image and name equals English: the page is translated, the cards are not, so they hold no
printings and are not imported. In `ko-kr` 375 entries (351 of Origins' 352, and all 24 of Proving Grounds) have
a Korean image and name, and those are the Korean printings; the one Origins entry that still shows the English
image is OGN-246a. `zh-cn` is the Chinese release, a different card pool, and is not covered. Riot's
announcement of the Korean launch (`playriftbound.com/en-us/news/announcements/koreas-rift-opens-on-september-18/`)
dates Origins on 18 September 2026, which is the `ko` release date of `OGN`. It dates no other set, so the
`OGS` release has none. Spiritforged follows in Korea in December and has no Korean gallery images yet.

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

A product whose number the gallery does not list is minted as a printing with `source: "tcgplayer"`: the runes and
signatures the gallery leaves out, double-sided tokens (`T01 // T02` is `UNL-T01+T02`), and the promotional groups
`OPP`, `PR` and `JDG`, which are sets of type `promo` with no set size. A promo's number repeats across sets and
stamps, so its id names both. Sett, The Boss (Metal) (Best Of), sold at `269/298` in `OPP`, is
`OPP-OGN269.metal-best-of` on the card `OPP-OGN269`. A rune that names its set, `Calm Rune (Vendetta)` at `R02b`, is
`VEN-R02b`. A minted card copies its type, domains and tags from the card it reprints, or from another card with its
name and subtitle, and a minted printing has no image and no gallery id.

A stamped printing TCGplayer has never priced takes the finish every priced printing of that stamp has. TCGplayer has
priced none of the 37 Metal Best Of products, so `STAMP_FINISHES` states them as foil, as Face to Face Games lists them.
A double-sided token's two numbers are sorted: TCGplayer's `T07 // T04` is `UNL-T04+T07`.

Listed in `review/tcgplayer-89.json`: oversized cards, singles with no number, a promo whose size is no set's, a second
product with another name on a minted id (TCGplayer lists Jarvan IV and Aphelios both at `179*/167`), and the groups
that are not sets (the bundles, Legacy, Secret Garden).

### Cardmarket products

`tools/import_cardmarket.py` reads Cardmarket's public product list for Riftbound (game 22),
`products_singles_22.json` under `downloads.s3.cardmarket.com/productCatalog/productList`, cached in
`.cache/cardmarket`. A product has an id, a name and an expansion, and no collector number, so it joins a card by
name alone. Each set lists its Cardmarket expansions in `cardmarketExpansionIds`; that field is kept by hand
(paired by name overlap and Riftcodex's set records), where the importer writes `tcgplayerGroupIds`.

A card's candidate names are `<name>, <subtitle>` and `<name>`, and for a Legend `<champion>, <name>` for each tag
that is a champion's name. Names compare casefolded, without accents or punctuation other than commas and
apostrophes. A product gets its card when exactly one card of the set has that name among its candidates and the
set's expansions list that name once; the id goes on the card's English printing without a suffix, under
`identifiers.cardmarketProductIds`. Korean printings get none.

Cardmarket lists an alternate art or an overnumbered print under its base card's name (Origins has two `Ahri,
Inquisitive`), and nothing on the product says which is which. Rather than order or guess them, every product of
such a name stays unmatched, as does a name two cards share (the runes). `review/cardmarket-22.json` lists these
by name with their products and cards (`ambiguous_name`), the products no card carries (`no_print`), and the
promotional expansions the data does not cover, with their product counts.

### Sealed products

`tools/import_sealed.py` writes `data/sealed/<set>.json` from the products TCGplayer sells in category 89 that are
not singles (no card number and no rarity), filed under the set whose `tcgplayerGroupIds` hold the product's
group. The shape is opjson's: `{"products": [...]}`, each with `id`, `set`, `category`, `name`, `releaseDate`,
`identifiers.tcgplayerProductIds`, `contentsStatus`, `contents` and `sources`. The id is the name lowercased and
joined with hyphens (`origins-booster-display`), unique across the dataset. `releaseDate` is TCGplayer's own date
for the product, else its group's `publishedOn`.

The `category` comes from the name, by ordered rules where the first match wins:

| Name | Category |
|---|---|
| ends in `Case` | `case` |
| ends in `Booster Display` | `booster_box` (the 24-pack box) |
| `[Set of 3]` or `(Set of 3)` | `display` (the sleeved booster pack art bundle) |
| ends in `Display` | `display` (Champion Deck and Showdown Decks displays) |
| `Sleeved Booster Pack` | `sleeved_booster_pack` |
| `Champion Deck`, `Showdown Decks`, `Box Set` | `starter_deck` |
| `Pre-Rift Event Kit` | `tournament_kit` |
| `Nexus Night Promo Pack` | `promo_pack` |
| `Vault Bundle`, `Pre-Rift Kit` | `collection` |
| `Booster Pack` | `booster_pack` |
| anything else | `other` (Bulk Runes) |

`contents` is written only where the product's own name or set states it, and never with counts, so
`contentsStatus` is `partial` or `unknown`, never `complete`:

- a booster pack or sleeved booster pack has a `pool`: its set, with no odds;
- a booster display and a vault bundle hold the set's booster pack;
- a case holds the product its name prefixes (`Origins - Booster Display Case` holds `origins-booster-display`);
- a Champion Deck display or Showdown Decks display holds the deck of the same name;
- a sleeved art bundle holds the set's sleeved booster pack;
- everything else is `unknown` with empty `contents`.

The products of a group that is not a set (the promotional group, the Worlds bundles, Secret Garden, and a set
rbjson does not list yet) are not written. `review/sealed.json` lists them with their group and name.

Riot also publishes a licensed [Content API](https://developer.riotgames.com/apis#riftbound-content-v1). It is
in beta and English only, and rbjson does not use it yet. When it leaves beta it is the better source, and
the gallery import stays as the cross-check.

## Known gaps

- **Finishes** come from TCGplayer's price sub-types, so a printing TCGplayer has never priced has none, and a
  finish the rule of rarity would predict but TCGplayer has never priced is not claimed.
- **Minted printings.** A printing the gallery omits comes from TCGplayer's product list, so it has no image, no
  artist and no gallery id, and its rarity is TCGplayer's or the reprinted card's.
- **Untyped cards.** 13 Radiance and 2 Unleashed entries carry no type or domain in the gallery at the time of
  writing. Their `type` and `domains` are absent until Riot fills them in.
- **Korean for Origins and Proving Grounds only.** Korean printings have no TCGplayer data, because TCGplayer
  sells the English cards, and no finishes. Other sets have no Korean printings until the Korean gallery shows
  Korean images for them. The Korean overnumbered Ahri that Riot's launch article announces is not in the
  gallery and is not in the data. No other language is imported (see [Where the data comes from](#where-the-data-comes-from)).
- **Cardmarket ids.** Alternate arts and overnumbered prints have no Cardmarket id, because Cardmarket lists them
  under the base card's name and the base card's own product is left unmatched with them. Cardmarket's promotional
  expansions are not covered. Cardmarket's sealed products are not imported.
- **Sealed contents.** Deck lists and counts are not stated: a case or display names what it holds without how many, and a deck has no card list. Format legality is not covered.
- **No reprint links.** A champion reprinted with the same subtitle in a later set is a separate card.

## Layout

- `sets/sets.json` lists every set, with its type, set size, parent and releases (with their key art). Hand-kept.
- `data/cards/<set>.json` holds the cards of one set, each with every printing of it. Written by the importer.
- `review/gallery.json` lists the variants whose gallery entry disagrees with their base. Written by the importer.
- `review/tcgplayer-89.json` lists the TCGplayer singles no printing matched and the groups that were not matched.
- `review/cardmarket-22.json` lists the Cardmarket products left unmatched and the expansions no set claims. Written by `tools/import_cardmarket.py`.
- `data/sealed/<set>.json` holds the sealed products of a set. Written by `tools/import_sealed.py`.
- `review/sealed.json` lists the sealed products of groups that are not a set. Written by the same importer.
- `data/tcgplayer_finishes.json` records every finish TCGplayer has priced each product in, across runs.
- `schema/sets.schema.json`, `schema/cards.schema.json` and `schema/sealed.schema.json` define the file shapes.
- `tools/` holds the importers (gallery, TCGCSV, sealed, Cardmarket), the validator, the build script, and the gallery, TCGCSV and Cardmarket fetchers.
- `tests/` checks the tools against a small gallery fixture and the committed data against the schemas.

## Building

```
uv sync --group dev
uv run python tools/import_gallery.py          # rebuild data/cards from the gallery (English, then ko-kr), cached in .cache/
uv run python tools/import_tcgcsv.py           # TCGplayer product ids and finishes, cached in .cache/tcgcsv
uv run python tools/import_sealed.py           # sealed products, after import_tcgcsv
uv run python tools/import_cardmarket.py       # Cardmarket product ids, cached in .cache/cardmarket
uv run python tools/validate.py [--online [--images]]
uv run python tools/build.py --version 0.4.0   # write dist/AllSets.json, AllCards.json, AllPrintings.json, AllProducts.json
uv run pytest -q
```

`validate.py` checks the schemas and the cross-references: every printing is filed under its own number, no
id or gallery entry appears twice, every printing's language has a release, a `~ko` printing has an English twin, `names` and `subtitles` only name languages the card has printings in, a TCGplayer product sits on one
printing or sealed product, a Cardmarket product sits on one English printing, a Cardmarket expansion on one set, and a sealed product's contents name products, sets and printings that exist. `--online` fetches the gallery again (and the Korean one, for the Korean printings) and reports any printing whose entry is gone and any entry the
data lacks, and asks TCGCSV whether every TCGplayer product id, on a printing or a sealed product, still exists, and Cardmarket whether every Cardmarket product id is still in its singles list. `--images` also asks Riot whether
every card image is still served, about 1,800 requests, so CI runs it only for a release tag.

`build.py` refuses to write `dist/` while the data is invalid.

## Releasing

Tag `vX.Y.Z` on `main`. CI validates the data, builds `dist/` and attaches the four files to a GitHub release
named after the tag. Readers follow `releases/latest/download/<file>`, so a new tag is all a release takes.

You can also publish a release from the GitHub web or app: choose a new tag `vX.Y.Z` on `main` and publish it.
CI runs the same checks and attaches the four files to that release, usually within ten minutes. If a check
fails, CI turns the release back into a draft, so readers keep getting the previous one.

## Adding a set or refreshing the data

1. Run `uv run python tools/import_gallery.py`. If it names a new set, add it to `sets/sets.json` with its
   code, type, set size and English name, then run the importer again.
2. Run `uv run python tools/import_tcgcsv.py --refresh` to pick up new products and finishes.
3. Run `uv run python tools/import_sealed.py --refresh`.
4. Run `uv run python tools/import_cardmarket.py --refresh`. A new set needs its `cardmarketExpansionIds` in `sets/sets.json` first.
5. Read `review/gallery.json`, `review/tcgplayer-89.json`, `review/cardmarket-22.json` and `review/sealed.json` for anything new.
6. Run `uv run python tools/validate.py --online` and `uv run pytest -q`.
7. Commit `sets/`, `data/` and `review/` together, so a release never mixes two snapshots.

## Licence

The tools are MIT (`LICENSE`). The data is CC BY 4.0 (`LICENSE-DATA`). rbjson is not endorsed by Riot Games;
see `NOTICE`.
