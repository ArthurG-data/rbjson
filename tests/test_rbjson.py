import copy

import pytest

import rbjson


def _data():
    return rbjson.load_sets(), rbjson.load_cards()


def test_the_committed_data_is_valid():
    assert rbjson.validate(*_data()) == []


def test_every_set_file_has_cards_and_every_set_has_a_file():
    sets, files = _data()
    assert set(files) == {s["id"] for s in sets}
    assert all(body["cards"] for body in files.values())


def test_flatten_keys_every_printing_by_id_with_its_set_and_card():
    flat = rbjson.flatten(*_data())
    p = flat["printings"]["OGN-119a"]
    assert p["set"] == "OGN" and p["number"] == "OGN-119" and p["language"] == "en"
    assert "OGN-119a" in flat["cards"]["OGN-119"]["printings"]


@pytest.mark.parametrize("pid, expected", [
    ("OGN-119", ("OGN", "OGN-119", "")),
    ("OGN-304*", ("OGN", "OGN-304", "*")),
    ("RAD-R04a", ("RAD", "RAD-R04", "a")),
])
def test_split_id(pid, expected):
    assert rbjson.split_id(pid) == expected


def test_validate_names_a_misfiled_and_a_duplicated_printing():
    sets, files = _data()
    files = copy.deepcopy(files)
    ahri = next(c for c in files["OGN"]["cards"] if c["number"] == "OGN-119")
    stray = copy.deepcopy(ahri["printings"][0])
    stray["id"] = "OGN-120"
    stray["identifiers"]["galleryId"] = "ogn-120-298-x"
    stray["identifiers"]["publicCode"] = "OGN-120/298"
    ahri["printings"].append(stray)
    errors = rbjson.validate(sets, files)
    assert any("OGN-120 is filed under card OGN-119" in e for e in errors)


def test_validate_rejects_a_card_in_the_wrong_file():
    sets, files = _data()
    files = copy.deepcopy(files)
    files["OGN"]["cards"].append(files["SFD"]["cards"][0])
    errors = rbjson.validate(sets, files)
    assert any("belongs in cards/SFD.json" in e for e in errors)
    assert any("is listed 2 times" in e for e in errors)


def test_a_parent_outside_the_file_or_the_set_itself_fails_validation():
    sets, files = _data()
    for parent in ("XXX", "OGS"):
        bad = copy.deepcopy(sets)
        next(s for s in bad if s["id"] == "OGS")["parent"] = parent
        assert rbjson.validate(bad, files) == [f"sets.json: set OGS: parent {parent} is not a set"]


def test_the_committed_parents_and_key_art_validate():
    sets, files = _data()
    by_id = {s["id"]: s for s in sets}
    assert by_id["OGS"]["parent"] == "OGN"
    for code in ("OGN", "SFD", "UNL", "VEN", "RAD"):
        art = by_id[code]["releases"][0]["keyArt"]
        assert len(art["size"]) == 2 and art["source"].startswith("https://playriftbound.com/")
    assert "keyArt" not in by_id["OGS"]["releases"][0]
    assert rbjson.validate(sets, files) == []


def _sealed(**over):
    product = {"id": "origins-booster-pack", "set": "OGN", "category": "booster_pack", "name": "Origins - Booster Pack",
               "identifiers": {"tcgplayerProductIds": [635366]}, "contentsStatus": "partial",
               "contents": {"pool": [{"set": "OGN"}]}, "sources": ["https://www.tcgplayer.com/product/635366"]}
    return {"OGN": {"products": [{**product, **over}]}}


def test_the_committed_sealed_products_are_in_the_flat_release_shape():
    sets, files = _data()
    sealed = rbjson.load_sealed()
    assert rbjson.validate(sets, files, sealed) == []
    products = rbjson.flatten(sets, files, sealed)["products"]
    assert products["origins-booster-display"]["category"] == "booster_box"
    assert len(products) == sum(len(b["products"]) for b in sealed.values())


@pytest.mark.parametrize("over, message", [
    ({"category": "pack"}, "sealed/OGN.json: $.products[0].category"),
    ({"set": "SFD"}, "filed under OGN but its set is SFD"),
    ({"set": "ZZZ"}, "set ZZZ is not in sets.json"),
    ({"contents": {"pool": [{"set": "ZZZ"}]}}, "pool set ZZZ is not in sets.json"),
    ({"contents": {"sealed": [{"product": "nothing"}]}}, "holds nothing, which is not another sealed product"),
    ({"contents": {"sealed": [{"product": "origins-booster-pack"}]}}, "holds origins-booster-pack"),
    ({"contents": {"cards": [{"printing": "OGN-999"}]}}, "holds printing OGN-999, which does not exist"),
    ({"contentsStatus": "unknown"}, "lists contents but says contentsStatus unknown"),
    ({"contentsStatus": "complete", "contents": {"cards": [{"printing": "OGN-119"}]}}, "complete contents need a count"),
])
def test_validate_names_each_sealed_problem(over, message):
    sets, files = _data()
    errors = rbjson.validate(sets, files, _sealed(**over))
    assert any(message in e for e in errors), errors


def test_a_sealed_id_and_a_tcgplayer_product_used_twice_are_named():
    sets, files = _data()
    sealed = _sealed()
    sealed["OGN"]["products"].append(dict(sealed["OGN"]["products"][0]))
    errors = rbjson.validate(sets, files, sealed)
    assert any("sealed product id origins-booster-pack is used 2 times" in e for e in errors)
    assert any("TCGplayer product 635366 is on origins-booster-pack" in e for e in errors)
