import json

import pytest

import import_tcgcsv
from tcgcsv import Product


@pytest.mark.parametrize("set_code, number, expected", [
    ("OGN", "119/298", "OGN-119"), ("OGN", "119a/298", "OGN-119a"), ("SFD", "227*/221", "SFD-227*"),
    ("RAD", "SP1/005", "RAD-SP1"), ("RAD", "R04a", "RAD-R04a"), ("SFD", "T03", "SFD-T03"),
    ("UNL", "T01 // T02", None), ("OGN", "", None),
])
def test_printing_key(set_code, number, expected):
    assert import_tcgcsv.printing_key(set_code, number) == expected


def test_product_finishes_keep_what_an_earlier_run_saw_and_add_todays_subtypes():
    recorded = {"1": ["foil"]}
    rows = [{"productId": 1, "subTypeName": "Normal"}, {"productId": 2, "subTypeName": "Foil"},
            {"productId": 2, "subTypeName": "Special"}, {"subTypeName": "Normal"}]
    assert import_tcgcsv.product_finishes(recorded, rows) == {1: {"foil", "nonfoil"}, 2: {"foil"}}
    assert import_tcgcsv.finish_record_text({2: {"foil"}, 1: {"nonfoil", "foil"}}) == \
        '{\n  "1": ["foil", "nonfoil"],\n  "2": ["foil"]\n}\n'


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
    assert result["counts"] == {"matched": 2, "sealed": 1, "unmatched": 1, "unmatched_group_singles": 1,
                                "printings_with_product": 2, "printings_with_finishes": 2}
    assert result["review"]["unmatched"] == [{"productId": 13, "group": "OGN", "name": "Teemo", "number": "197/298"}]
    assert result["review"]["unmatched_groups"] == [{"groupId": 2, "name": "Promos", "abbreviation": "PR", "singles": 1}]


def test_apply_starts_from_a_clean_slate_so_a_product_that_moved_is_not_kept():
    files = _files()
    files["OGN"]["cards"][0]["printings"][0].update(
        {"identifiers": {"galleryId": "ogn-119", "publicCode": "OGN-119", "tcgplayerProductIds": [99]},
         "tcgplayer": {"name": "old", "match": "number"}, "finishes": ["foil"]})
    import_tcgcsv.apply(files, [{"id": "OGN", "type": "booster"}], GROUPS[:1], lambda gid: PRODUCTS[gid], {})
    base = files["OGN"]["cards"][0]["printings"][0]
    assert base["identifiers"]["tcgplayerProductIds"] == [10] and "finishes" not in base
