import json

import pytest

import import_tcgcsv
from tcgcsv import Product


@pytest.mark.parametrize("set_code, number, expected", [
    ("OGN", "119/298", "OGN-119"), ("OGN", "119a/298", "OGN-119a"), ("OGN", "304*/298", "OGN-304*"),
    ("RAD", "SP1/005", "RAD-SP1"), ("RAD", "R04a", "RAD-R04a"), ("UNL", "R04b", "UNL-R04b"), ("UNL", "T01", "UNL-T01"),
    ("UNL", "T01 // T02", "UNL-T01+T02"), ("OGN", "", None), ("OGN", "119a~ko/298", None),
])
def test_plan_product_names_the_printing_in_a_base_set(set_code, number, expected):
    product = Product(1, 1, "Ahri", {"Number": number, "Rarity": "Epic"})
    plan = import_tcgcsv.plan_product(product, {"id": set_code, "type": "booster"}, {}, {})
    assert (plan.printing_id if plan else None) == expected


def test_product_finishes_keep_what_an_earlier_run_saw_and_add_todays_subtypes():
    recorded = {"1": ["foil"]}
    rows = [{"productId": 1, "subTypeName": "Normal"}, {"productId": 2, "subTypeName": "Foil"},
            {"productId": 2, "subTypeName": "Special"}, {"subTypeName": "Normal"}]
    assert import_tcgcsv.product_finishes(recorded, rows) == {1: {"foil", "nonfoil"}, 2: {"foil"}}
    assert import_tcgcsv.finish_record_text({2: {"foil"}, 1: {"nonfoil", "foil"}}) == \
        '{\n  "1": ["foil", "nonfoil"],\n  "2": ["foil"]\n}\n'


import copy  # noqa: E402


def _printing(pid, **extra):
    return {"id": pid, "collectorNumber": 1, "rarity": "common", "image": "https://x/a.png", "source": "riot-gallery",
            "identifiers": {"galleryId": pid.lower(), "publicCode": pid}, **extra}


def _files():
    return {"OGN": {"cards": [{"number": "OGN-119", "name": "Ahri", "printings": [_printing("OGN-119"), _printing("OGN-119a")]}]}}


GROUPS = [{"groupId": 1, "name": "Origins", "abbreviation": "OGN"}, {"groupId": 2, "name": "Promos", "abbreviation": "PR"}]
PRODUCTS = {
    1: [Product(10, 1, "Ahri", {"Number": "119/298", "Rarity": "Epic"}),
        Product(11, 1, "Ahri (Alt)", {"Number": "119a/298", "Rarity": "Showcase"}),
        Product(12, 1, "Origins Booster Box", {}),
        Product(13, 1, "Teemo", {"Number": "197/298", "Rarity": "Common"})],
    2: [Product(20, 2, "Ahri (Launch)", {"Number": "066/298", "Rarity": "Promo"})],
}


def test_apply_matches_by_set_and_number_and_records_the_rest():
    files, sets = _files(), [{"id": "OGN", "type": "booster"}]
    result = import_tcgcsv.apply(files, sets, GROUPS, lambda gid: PRODUCTS[gid], {10: {"nonfoil", "foil"}, 11: {"foil"}})
    base, alt = files["OGN"]["cards"][0]["printings"]
    assert base["identifiers"]["tcgplayerProductIds"] == [10] and base["finishes"] == ["foil", "nonfoil"]
    assert base["tcgplayer"] == {"name": "Ahri", "match": "number"}
    assert alt["identifiers"]["tcgplayerProductIds"] == [11] and alt["finishes"] == ["foil"]
    assert sets[0]["tcgplayerGroupIds"] == [1]
    assert result["counts"] == {"matched": 3, "minted": 1, "sealed": 1, "unmatched_group_singles": 1,
                                "finishes_inferred": 0, "printings_with_product": 3, "printings_with_finishes": 2}
    assert result["review"]["unmatched"] == []
    teemo = next(c for c in files["OGN"]["cards"] if c["number"] == "OGN-197")
    assert teemo["name"] == "Teemo" and teemo["printings"][0]["source"] == "tcgplayer"
    assert teemo["printings"][0]["tcgplayer"]["match"] == "minted" and teemo["printings"][0]["rarity"] == "common"
    assert result["review"]["unmatched_groups"] == [{"groupId": 2, "name": "Promos", "abbreviation": "PR", "singles": 1}]


def test_apply_starts_from_a_clean_slate_so_a_product_that_moved_is_not_kept():
    files = _files()
    files["OGN"]["cards"][0]["printings"][0].update(
        {"identifiers": {"galleryId": "ogn-119", "publicCode": "OGN-119", "tcgplayerProductIds": [99]},
         "tcgplayer": {"name": "old", "match": "number"}, "finishes": ["foil"]})
    import_tcgcsv.apply(files, [{"id": "OGN", "type": "booster"}], GROUPS[:1], lambda gid: PRODUCTS[gid], {})
    base = files["OGN"]["cards"][0]["printings"][0]
    assert base["identifiers"]["tcgplayerProductIds"] == [10] and "finishes" not in base


def test_a_korean_printing_is_never_matched_and_keeps_its_fields():
    files = _files()
    ko = _printing("OGN-119a~ko", language="ko")
    files["OGN"]["cards"][0]["printings"].append(ko)
    before = json.loads(json.dumps(ko))
    # a product number can only name an English id: no number maps to a key with a language mark
    sets = [{"id": "OGN", "type": "booster", "collectorNumberMax": 298, "releases": []}]
    result = import_tcgcsv.apply(files, sets, GROUPS, lambda gid: PRODUCTS[gid], {})
    assert ko == before and result["counts"]["matched"] == 3
    english = files["OGN"]["cards"][0]["printings"]
    assert all("tcgplayer" in p for p in english[:2])


PROMO_SETS = [{"id": "OGN", "type": "booster", "collectorNumberMax": 298,
               "releases": [{"language": "en", "name": "Origins"}]},
              {"id": "VEN", "type": "booster", "collectorNumberMax": 166,
               "releases": [{"language": "en", "name": "Vendetta"}]},
              {"id": "OPP", "type": "promo", "releases": [{"language": "en", "name": "Organized Play"}]}]
PROMO_GROUPS = [{"groupId": 2, "name": "Organized Play", "abbreviation": "OPP"}]


def _promo_run(products, finishes=None, files=None):
    files = files if files is not None else {"OGN": {"cards": [
        {"number": "OGN-269", "name": "Sett", "subtitle": "The Boss", "type": "unit",
         "printings": [_printing("OGN-269", rarity="epic")]}]}}
    sets = copy.deepcopy(PROMO_SETS)
    result = import_tcgcsv.apply(files, sets, PROMO_GROUPS, lambda gid: products, finishes or {})
    return files, {p["id"]: p for b in files.values() for c in b["cards"] for p in c["printings"]}, result


def test_promo_stamps_of_one_number_get_their_own_printings_on_one_card_with_the_base_cards_facts():
    products = [Product(1, 2, "Sett, The Boss", {"Number": "269/298", "Rarity": "Promo"}),
                Product(2, 2, "Sett, The Boss (Metal) (Best Of)", {"Number": "269/298", "Rarity": "Promo"}),
                Product(3, 2, "Sett, The Boss (Metal) (Prize Wall)", {"Number": "269/298", "Rarity": "Promo"})]
    files, printings, _ = _promo_run(products, {1: {"foil"}, 2: {"foil"}, 3: {"nonfoil"}})
    assert {"OPP-OGN269", "OPP-OGN269.metal-best-of", "OPP-OGN269.metal-prize-wall"} <= set(printings)
    card = next(c for c in files["OPP"]["cards"] if c["number"] == "OPP-OGN269")
    assert (card["name"], card["subtitle"], card["type"]) == ("Sett", "The Boss", "unit")
    assert printings["OPP-OGN269.metal-best-of"]["variant"] == "metal-best-of"
    assert printings["OPP-OGN269"]["rarity"] == "epic" and printings["OPP-OGN269"]["collectorNumber"] == 269


def test_a_rune_that_names_its_set_is_that_sets_printing():
    products = [Product(1, 2, "Calm Rune (Vendetta)", {"Number": "R02b", "Rarity": "Promo"}),
                Product(2, 2, "Calm Rune (R02c)", {"Number": "R02c", "Rarity": "Promo"})]
    _, printings, _ = _promo_run(products)
    assert printings["VEN-R02b"]["suffix"] == "b" and printings["OPP-R02c"]["suffix"] == "c"


def test_a_promo_whose_size_is_no_set_or_an_oversized_card_goes_to_review():
    products = [Product(1, 2, "Odd", {"Number": "001/999", "Rarity": "Promo"}),
                Product(2, 2, "Sett, The Boss (Oversized)", {"Number": "269/298", "Rarity": "Promo"}),
                Product(3, 2, "Buff", {"Rarity": "Promo"})]
    _, _, result = _promo_run(products)
    assert {r["productId"] for r in result["review"]["unmatched"]} == {1, 2, 3}


def test_two_names_on_one_minted_id_keep_the_first_and_review_the_second():
    products = [Product(1, 2, "Jarvan IV, Exemplar", {"Number": "179*/166", "Rarity": "Promo"}),
                Product(2, 2, "Aphelios, Exalted", {"Number": "179*/166", "Rarity": "Promo"})]
    _, printings, result = _promo_run(products)
    assert printings["OPP-VEN179*"]["identifiers"]["tcgplayerProductIds"] == [1]
    assert [r["productId"] for r in result["review"]["unmatched"]] == [2]


def test_an_unpriced_stamp_takes_the_finish_all_priced_copies_agree_on():
    products = [Product(1, 2, "A, X (Metal) (Best Of)", {"Number": "001/298", "Rarity": "Promo"}),
                Product(2, 2, "B, Y (Metal) (Best Of)", {"Number": "002/298", "Rarity": "Promo"}),
                Product(3, 2, "C, Z (Top 8)", {"Number": "003/298", "Rarity": "Promo"})]
    _, printings, result = _promo_run(products, {1: {"foil"}})
    assert printings["OPP-OGN002.metal-best-of"]["finishes"] == ["foil"]
    assert "finishes" not in printings["OPP-OGN003.top-8"] and result["counts"]["finishes_inferred"] == 1


def test_metal_best_of_is_foil_with_no_price_at_all_and_a_token_pair_sorts_its_numbers():
    products = [Product(1, 2, "A, X (Metal) (Best Of)", {"Number": "001/298", "Rarity": "Promo"}),
                Product(2, 2, "Sprite // Buff", {"Number": "T07 // T04", "Rarity": "Common"})]
    _, printings, _ = _promo_run(products)
    assert printings["OPP-OGN001.metal-best-of"]["finishes"] == ["foil"] and "OPP-T04+T07" in printings


def test_a_double_sided_token_is_one_printing_with_both_finishes():
    products = [Product(1, 2, "Mech // Recruit", {"Number": "T06 // T07", "Rarity": "Common"}),
                Product(2, 2, "Mech // Recruit (Full Art)", {"Number": "T06 // T07", "Rarity": "Common"})]
    files, printings, _ = _promo_run(products, {1: {"nonfoil"}, 2: {"foil"}})
    token = printings["OPP-T06+T07.full-art"]
    assert printings["OPP-T06+T07"]["finishes"] == ["nonfoil"] and token["finishes"] == ["foil"]
    assert next(c for c in files["OPP"]["cards"] if c["number"] == "OPP-T06+T07")["name"] == "Mech // Recruit"


def test_a_rerun_mints_the_same_printings_and_keeps_the_gallery_ones():
    products = [Product(1, 2, "Sett, The Boss", {"Number": "269/298", "Rarity": "Promo"})]
    files, first, _ = _promo_run(products)
    snapshot = copy.deepcopy(files)
    _, again, _ = _promo_run(products, files=files)
    assert files == snapshot and set(first) == set(again) and "OGN-269" in again
