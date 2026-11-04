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


def _with_korean_ahri():
    sets, files = _data()
    sets, files = copy.deepcopy(sets), copy.deepcopy(files)
    ahri = next(c for c in files["OGN"]["cards"] if c["number"] == "OGN-119")
    ahri["printings"] = [p for p in ahri["printings"] if p.get("language", "en") == "en"]
    ahri.pop("names", None), ahri.pop("subtitles", None)
    twin = ahri["printings"][1]
    ko = {"id": "OGN-119a~ko", "language": "ko", "collectorNumber": twin["collectorNumber"], "suffix": "a",
          "rarity": twin["rarity"], "image": "https://r/ko.png", "source": "riot-gallery",
          "identifiers": {k: v for k, v in twin["identifiers"].items() if k != "tcgplayerProductIds"}}
    ahri["printings"].append(ko)
    return sets, files, ahri, ko


def test_a_valid_korean_printing_passes_and_flattens_with_its_names():
    sets, files, ahri, ko = _with_korean_ahri()
    ahri["names"], ahri["subtitles"] = {"en": ahri["name"], "ko": "아리"}, {"en": ahri["subtitle"], "ko": "호기심"}
    for s in sets:
        if s["id"] == "OGN":
            assert any(r["language"] == "ko" for r in s["releases"])
    assert rbjson.validate(sets, files) == []
    flat = rbjson.flatten(sets, files)
    assert flat["printings"]["OGN-119a~ko"]["language"] == "ko" and flat["printings"]["OGN-119a~ko"]["number"] == "OGN-119"
    assert flat["cards"]["OGN-119"]["names"]["ko"] == "아리" and flat["cards"]["OGN-119"]["subtitles"]["ko"] == "호기심"
    assert "OGN-119a~ko" in flat["cards"]["OGN-119"]["printings"]


def test_a_korean_printing_needs_a_ko_release_on_its_set():
    sets, files, _, _ = _with_korean_ahri()
    next(s for s in sets if s["id"] == "OGN")["releases"] = [r for r in next(s for s in sets if s["id"] == "OGN")["releases"]
                                                              if r["language"] != "ko"]
    assert any("printing OGN-119a~ko: set OGN has no ko release" in e for e in rbjson.validate(sets, files))


def test_a_korean_printing_needs_its_english_twin():
    sets, files, ahri, ko = _with_korean_ahri()
    ko["id"], ko["identifiers"]["galleryId"] = "OGN-119~ko", "ogn-119-298-ko"
    ahri["printings"] = [p for p in ahri["printings"] if p["id"] != "OGN-119"]
    errors = rbjson.validate(sets, files)
    assert any("OGN-119~ko: its English printing OGN-119 does not exist" in e for e in errors)


def test_the_ko_mark_and_the_language_go_together():
    sets, files, _, ko = _with_korean_ahri()
    del ko["language"]
    assert any("a printing in en has the id mark ~en" in e for e in rbjson.validate(sets, files))


def test_names_and_subtitles_only_name_languages_the_card_has_printings_in():
    sets, files, ahri, ko = _with_korean_ahri()
    ahri["printings"].remove(ko)
    ahri["names"], ahri["subtitles"] = {"en": ahri["name"], "ko": "아리"}, {"ko": "호기심"}
    errors = rbjson.validate(sets, files)
    assert any("card OGN-119: names has a ko entry but no printing in ko" in e for e in errors)
    assert any("card OGN-119: subtitles has a ko entry but no printing in ko" in e for e in errors)


def test_a_korean_printing_carries_no_tcgplayer_data():
    sets, files, _, ko = _with_korean_ahri()
    ko["finishes"] = ["foil"]
    assert any("a ko printing has no TCGplayer data" in e for e in rbjson.validate(sets, files))


def test_the_same_gallery_entry_may_sit_on_an_english_and_a_korean_printing_but_not_twice_in_one_language():
    sets, files, ahri, ko = _with_korean_ahri()
    assert rbjson.validate(sets, files) == []
    dup = copy.deepcopy(ko)
    dup["id"] = "OGN-119~ko"
    ahri["printings"].append(dup)
    assert any("gallery entry ogn-119a-298 is on OGN-119a~ko and OGN-119~ko" in e for e in rbjson.validate(sets, files))


def test_a_korean_printing_carries_no_cardmarket_product():
    sets, files, _, ko = _with_korean_ahri()
    ko["identifiers"]["cardmarketProductIds"] = [5]
    assert any("a ko printing has none" in e for e in rbjson.validate(sets, files))


def test_a_cardmarket_product_on_two_printings_and_an_expansion_on_two_sets_are_named():
    sets, files = _data()
    sets, files = copy.deepcopy(sets), copy.deepcopy(files)
    one, two = files["OGN"]["cards"][0]["printings"][0], files["OGN"]["cards"][1]["printings"][0]
    one["identifiers"]["cardmarketProductIds"] = two["identifiers"]["cardmarketProductIds"] = [7]
    sets[1]["cardmarketExpansionIds"] = list(sets[0]["cardmarketExpansionIds"])
    errors = rbjson.validate(sets, files)
    assert any(f"Cardmarket product 7 is on {one['id']} and {two['id']}" in e for e in errors)
    assert any(f"Cardmarket expansion {sets[0]['cardmarketExpansionIds'][0]} is on OGN and OGS" in e for e in errors)


def test_a_non_integer_cardmarket_expansion_id_fails_the_schema():
    sets, files = _data()
    sets = copy.deepcopy(sets)
    sets[0]["cardmarketExpansionIds"] = ["6286"]
    assert any("cardmarketExpansionIds" in e for e in rbjson.validate(sets, files))
