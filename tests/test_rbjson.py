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
