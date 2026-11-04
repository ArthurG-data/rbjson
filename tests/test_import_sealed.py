import json
from pathlib import Path

import pytest

import import_sealed
import rbjson
from tcgcsv import Product

SCANS_SOURCE = ("tests/fixtures/",)
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sealed_sample.json").read_text(encoding="utf-8"))


def _products_of(group_id):
    return [Product(r["productId"], group_id, r["name"], {e["name"]: e["value"] for e in r["extendedData"]},
                    ((r.get("presaleInfo") or {}).get("releasedOn") or "")[:10] or None)
            for r in FIXTURE["products"][str(group_id)]]


def _build():
    return import_sealed.build(FIXTURE["sets"], FIXTURE["groups"], _products_of)


@pytest.mark.parametrize("name, category", [
    ("Origins - Booster Display Case", "case"),
    ("Origins - Booster Display", "booster_box"),
    ("Origins - Sleeved Booster Pack Art Bundle [Set of 3]", "display"),
    ("Radiance - Sleeved Booster Pack Art Bundle (Set of 3)", "display"),
    ("Origins - Champion Deck (Jinx) Display", "display"),
    ("Origins - Sleeved Booster Pack", "sleeved_booster_pack"),
    ("Origins - Champion Deck (Jinx)", "starter_deck"),
    ("Vendetta - Showdown Decks: Zed vs Shen", "starter_deck"),
    ("Origins - Proving Grounds Box Set", "starter_deck"),
    ("Spiritforged - Pre-Rift Event Kit", "tournament_kit"),
    ("Unleashed - Nexus Night Promo Pack", "promo_pack"),
    ("Unleashed - Vault Bundle", "collection"),
    ("Unleashed - Pre-Rift Kit", "collection"),
    ("Origins - Booster Pack", "booster_pack"),
    ("Riftbound: Bulk Runes", "other"),
])
def test_classify_one_name_per_rule(name, category):
    assert import_sealed.classify(name) == category


def test_slug():
    assert import_sealed.slug("Origins - Booster Display") == "origins-booster-display"
    assert import_sealed.slug("Origins - Sleeved Booster Pack Art Bundle [Set of 3]") == \
        "origins-sleeved-booster-pack-art-bundle-set-of-3"


def test_a_pack_holds_its_set_as_a_pool_and_keeps_tcgplayers_date():
    pack = {p["id"]: p for p in _build()[0]["OGN"]}["origins-booster-pack"]
    assert pack["contents"] == {"pool": [{"set": "OGN"}]} and pack["contentsStatus"] == "partial"
    assert pack["releaseDate"] == "2025-10-31"
    assert pack["identifiers"] == {"tcgplayerProductIds": [11]}
    assert pack["sources"] == ["https://www.tcgplayer.com/product/11"]


def test_the_group_date_stands_in_when_the_product_has_none():
    box = {p["id"]: p for p in _build()[0]["OGN"]}["origins-booster-display"]
    assert box["releaseDate"] == "2025-10-01"


def test_a_display_a_case_and_a_vault_bundle_name_what_they_hold():
    by_id = {p["id"]: p for p in _build()[0]["OGN"]}
    assert by_id["origins-booster-display"]["contents"] == {"sealed": [{"product": "origins-booster-pack"}]}
    assert by_id["origins-booster-display-case"]["contents"] == {"sealed": [{"product": "origins-booster-display"}]}
    assert by_id["origins-champion-deck-jinx-display"]["contents"] == {
        "sealed": [{"product": "origins-champion-deck-jinx"}]}
    art = by_id["origins-sleeved-booster-pack-art-bundle-set-of-3"]
    assert art["contents"] == {"sealed": [{"product": "origins-sleeved-booster-pack"}]}
    assert by_id["origins-vault-bundle"]["contents"] == {"sealed": [{"product": "origins-booster-pack"}]}


def test_a_deck_and_a_kit_have_unknown_contents():
    by_id = {p["id"]: p for p in _build()[0]["OGN"]}
    for pid in ("origins-champion-deck-viktor", "origins-pre-rift-event-kit", "riftbound-bulk-runes"):
        assert by_id[pid]["contents"] == {} and by_id[pid]["contentsStatus"] == "unknown"


def test_a_group_with_no_set_goes_to_review_and_singles_are_skipped():
    by_set, review = _build()
    assert set(by_set) == {"OGN"} and len(by_set["OGN"]) == 11
    assert review == [{"productId": 30, "groupId": 2, "group": "PR", "name": "Riftbound: League of Legends Arcane Box Set"}]


def test_the_built_products_validate_against_the_schema():
    sets, files = rbjson.load_sets(), rbjson.load_cards()
    by_set, _ = _build()
    assert rbjson.validate(sets, files, {"OGN": {"products": by_set["OGN"]}}) == []


def test_a_repeated_name_gets_its_product_id_so_ids_stay_unique():
    products = [{"id": "a", "identifiers": {"tcgplayerProductIds": [1]}},
                {"id": "a", "identifiers": {"tcgplayerProductIds": [2]}}]
    import_sealed._dedupe_ids(products)
    assert [p["id"] for p in products] == ["a", "a-2"]
