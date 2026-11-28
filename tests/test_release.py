import copy
import json

import pytest
from jsonschema import Draft202012Validator, FormatChecker

import build
import rbjson
import release_schema
import uuids

META = {"version": "1.0.0", "date": "2026-11-27"}


@pytest.fixture(scope="module")
def release():
    flat = rbjson.flatten(rbjson.load_sets(), rbjson.load_cards(), rbjson.load_sealed())
    flat["uuids"] = uuids.load()
    return {name: {"meta": META, "data": flat[key]} for name, key in
            build.FILES}


def _errors(name, doc):
    validator = Draft202012Validator(release_schema.schemas()[name], format_checker=FormatChecker())
    return [e.message for e in validator.iter_errors(doc)]


def test_the_committed_data_builds_release_files_their_schemas_describe(release):
    for name, doc in release.items():
        assert _errors(name, doc) == [], name


@pytest.mark.parametrize("name,key,change", [
    ("AllPrintings", "OGN-119a", lambda r: r.pop("uuid")),
    ("AllPrintings", "OGN-119a", lambda r: r.pop("language")),
    ("AllCards", "OGN-119", lambda r: r.pop("oracleId")),
    ("AllPrintings", "OGN-119a", lambda r: r.pop("finishesKnown")),
    ("AllCards", "OGN-119", lambda r: r.update(printings=[{"id": "OGN-119"}])),
    ("AllCards", "OGN-119", lambda r: r.update(uuid="not-a-uuid")),
    ("AllProducts", "origins-booster-display", lambda r: r.update(price=1)),
])
def test_a_release_record_its_schema_does_not_describe_is_refused(release, name, key, change):
    doc = copy.deepcopy(release[name])
    change(doc["data"][key])
    assert _errors(name, doc)


def test_a_reprint_shares_its_cards_oracle_id_and_keeps_its_own_uuid(release):
    cards = release["AllCards"]["data"]
    assert cards["OPP-OGN269"]["oracleId"] == cards["OGN-269"]["oracleId"]
    assert cards["OPP-OGN269"]["uuid"] != cards["OGN-269"]["uuid"]
    # one champion, two subtitles: two cards with two oracleIds
    ahri = {c["oracleId"] for c in cards.values() if c["name"] == "Ahri" and c.get("type") == "unit"}
    assert len(ahri) == len({c.get("subtitle") for c in cards.values() if c["name"] == "Ahri" and c.get("type") == "unit"})


def test_cards_of_one_name_and_subtitle_that_disagree_on_a_rule_fact_are_refused():
    sets, files = rbjson.load_sets(), rbjson.load_cards()
    files = copy.deepcopy(files)
    card = next(c for c in files["OPP"]["cards"] if c["number"] == "OPP-OGN269")
    assert card["domains"]
    card["domains"] = ["colorless"] if card["domains"] != ["colorless"] else ["fury"]
    assert any("OPP-OGN269: shares its oracleId" in e for e in rbjson.validate(sets, files, rbjson.load_sealed()))


def test_finishes_known_says_whether_a_printing_has_finishes_and_never_that_it_has_none(release):
    printings = release["AllPrintings"]["data"]
    assert all(p["finishesKnown"] == ("finishes" in p) for p in printings.values())
    korean = next(p for p in printings.values() if p["language"] == "ko")
    assert korean["finishesKnown"] is False
    inferred = [p for p in printings.values() if p.get("finishesInferred")]
    assert inferred and all(p["finishesKnown"] for p in inferred)


def test_the_release_carries_the_registry_as_a_document(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "DIST", tmp_path)
    monkeypatch.setattr("sys.argv", ["build.py", "--version", "0.0.0-test", "--date", "2026-11-27"])
    build.main()
    doc = json.loads((tmp_path / "AllUuids.json").read_text(encoding="utf-8"))
    assert set(doc) == {"meta", "data"}
    assert set(doc["data"]) == {"cards", "printings", "products", "oracles"}
    printings = doc["data"]["printings"]
    assert printings["bridges"]["id:OPP-OGN007b"] == printings["keys"]["tcgplayer:662900"]
    assert (tmp_path / "AllUuids.schema.json").exists()
    assert not (tmp_path / "uuids.json").exists()


def test_the_registry_schema_refuses_a_value_that_is_not_a_uuid():
    bad = {"meta": META, "data": {k: {"keys": {}, "bridges": {}} for k in uuids.KINDS}}
    assert _errors("AllUuids", bad) == []
    bad["data"]["cards"]["keys"]["id:OGN-001"] = "nope"
    assert _errors("AllUuids", bad)
