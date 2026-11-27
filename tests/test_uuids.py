import copy
import uuid

import pytest

import uuids


def _printing(pid, products=(), source="riot-gallery"):
    p = {"id": pid, "collectorNumber": 1, "rarity": "common", "source": source, "identifiers": {}}
    if products:
        p["identifiers"]["tcgplayerProductIds"] = list(products)
    return p


def _files(*cards):
    """{set: {"cards": [...]}} from (number, [printing, ...]) pairs."""
    files = {}
    for number, printings in cards:
        files.setdefault(number.split("-")[0], {"cards": []})["cards"].append(
            {"number": number, "name": number, "printings": printings})
    return files


def _uuid_of(files, pid):
    return next(p["uuid"] for b in files.values() for c in b["cards"] for p in c["printings"] if p["id"] == pid)


def _card_uuid(files, number):
    return next(c["uuid"] for b in files.values() for c in b["cards"] if c["number"] == number)


def _run(files, registry):
    uuids.assign_cards(files, registry)
    return files


def test_a_record_seen_first_gets_uuid5_of_its_kind_and_id():
    files = _run(_files(("OGN-001", [_printing("OGN-001")])), uuids.empty())
    assert _uuid_of(files, "OGN-001") == str(uuid.uuid5(uuids.NAMESPACE, "printings:OGN-001"))
    assert _card_uuid(files, "OGN-001") == str(uuid.uuid5(uuids.NAMESPACE, "cards:OGN-001"))


def test_a_rebuild_from_nothing_gives_every_record_the_uuid_it_had():
    one = _run(_files(("OGN-001", [_printing("OGN-001"), _printing("OGN-001a")])), uuids.empty())
    two = _run(_files(("OGN-001", [_printing("OGN-001"), _printing("OGN-001a")])), uuids.empty())
    assert one == two


def test_a_second_run_changes_nothing():
    registry = uuids.empty()
    files = _run(_files(("OGN-001", [_printing("OGN-001")]), ("OGN-002", [_printing("OGN-002")])), registry)
    before = copy.deepcopy((files, registry))
    _run(files, registry)
    assert (files, registry) == before


def test_the_uuid_sits_right_after_the_id():
    files = _run(_files(("OGN-001", [_printing("OGN-001")])), uuids.empty())
    card = files["OGN"]["cards"][0]
    assert list(card)[:2] == ["number", "uuid"]
    assert list(card["printings"][0])[:2] == ["id", "uuid"]


def test_a_printing_whose_id_changes_keeps_its_uuid_through_its_tcgplayer_product():
    registry = uuids.empty()
    before = _run(_files(("OPP-OGN269", [_printing("OPP-OGN269.metal-best-of", [7], "tcgplayer")])), registry)
    u = _uuid_of(before, "OPP-OGN269.metal-best-of")
    # TCGplayer renames the product, so the variant in the id changes
    after = _run(_files(("OPP-OGN269", [_printing("OPP-OGN269.metal-best-of-2026", [7], "tcgplayer")])), registry)
    assert _uuid_of(after, "OPP-OGN269.metal-best-of-2026") == u
    assert registry["retired"]["printings"] == {"OPP-OGN269.metal-best-of": u}


def test_a_card_whose_number_changes_keeps_its_uuid_through_its_printings():
    registry = uuids.empty()
    before = _run(_files(("OPP-OGN269", [_printing("OPP-OGN269", [7], "tcgplayer")])), registry)
    card = _card_uuid(before, "OPP-OGN269")
    after = _run(_files(("OPP-SFD269", [_printing("OPP-SFD269", [7], "tcgplayer")])), registry)
    assert _card_uuid(after, "OPP-SFD269") == card
    assert registry["retired"]["cards"] == {"OPP-OGN269": card}


def test_a_minted_printing_the_gallery_starts_listing_keeps_its_uuid():
    registry = uuids.empty()
    u = _uuid_of(_run(_files(("OGN-R01", [_printing("OGN-R01", [7], "tcgplayer")])), registry), "OGN-R01")
    assert _uuid_of(_run(_files(("OGN-R01", [_printing("OGN-R01", [7])])), registry), "OGN-R01") == u


def test_a_record_that_leaves_is_retired_and_gets_its_uuid_back_when_it_returns():
    registry = uuids.empty()
    u = _uuid_of(_run(_files(("OGN-001", [_printing("OGN-001")]), ("OGN-002", [_printing("OGN-002")])), registry),
                 "OGN-002")
    _run(_files(("OGN-001", [_printing("OGN-001")])), registry)
    assert "OGN-002" not in registry["printings"]
    assert registry["retired"]["printings"]["OGN-002"] == u
    back = _run(_files(("OGN-001", [_printing("OGN-001")]), ("OGN-002", [_printing("OGN-002")])), registry)
    assert _uuid_of(back, "OGN-002") == u
    assert registry["retired"]["printings"] == {}


def test_a_new_printing_does_not_take_the_uuid_of_a_printing_still_in_the_data():
    registry = uuids.empty()
    u = _uuid_of(_run(_files(("OGN-001", [_printing("OGN-001", [7])])), registry), "OGN-001")
    # product 7 moves to a new printing while OGN-001 stays
    after = _run(_files(("OGN-001", [_printing("OGN-001"), _printing("OGN-001a", [7])])), registry)
    assert _uuid_of(after, "OGN-001") == u
    assert _uuid_of(after, "OGN-001a") != u


def test_an_id_that_returns_to_a_uuid_another_record_took_is_a_conflict():
    registry = uuids.empty()
    _run(_files(("OPP-OGN269", [_printing("OPP-OGN269.a", [7], "tcgplayer")])), registry)
    _run(_files(("OPP-OGN269", [_printing("OPP-OGN269.b", [7], "tcgplayer")])), registry)  # .b takes .a's uuid
    with pytest.raises(uuids.Conflict):
        _run(_files(("OPP-OGN269", [_printing("OPP-OGN269.a"), _printing("OPP-OGN269.b", [7], "tcgplayer")])), registry)


def test_products_keep_their_uuid_through_their_tcgplayer_product_when_renamed():
    registry = uuids.empty()
    sealed = {"OGN": {"products": [{"id": "origins-booster-box", "identifiers": {"tcgplayerProductIds": [9]}}]}}
    uuids.assign_products(sealed, registry)
    u = sealed["OGN"]["products"][0]["uuid"]
    renamed = {"OGN": {"products": [{"id": "origins-booster-display", "identifiers": {"tcgplayerProductIds": [9]}}]}}
    uuids.assign_products(renamed, registry)
    assert renamed["OGN"]["products"][0]["uuid"] == u


def test_errors_names_a_missing_uuid_a_wrong_one_and_a_registry_id_the_data_lacks():
    registry = uuids.empty()
    files = _run(_files(("OGN-001", [_printing("OGN-001")]), ("OGN-002", [_printing("OGN-002")])), registry)
    assert uuids.errors(files, {}, registry) == []
    del files["OGN"]["cards"][0]["printings"][0]["uuid"]
    files["OGN"]["cards"][1]["uuid"] = str(uuid.uuid4())
    del files["OGN"]["cards"][1]["printings"][0]
    found = uuids.errors(files, {}, registry)
    assert any(e.startswith("printing OGN-001 has no uuid") for e in found)
    assert any(e.startswith("card OGN-002: uuid") for e in found)
    assert any("printing OGN-002 is no longer in the data" in e for e in found)


def test_history_allows_new_and_retired_ids_and_refuses_a_changed_or_dropped_one():
    before = uuids.empty()
    _run(_files(("OGN-001", [_printing("OGN-001")]), ("OGN-002", [_printing("OGN-002")])), before)
    after = copy.deepcopy(before)
    _run(_files(("OGN-001", [_printing("OGN-001")]), ("OGN-003", [_printing("OGN-003")])), after)
    assert uuids.history_errors(before, after) == []
    changed = copy.deepcopy(after)
    changed["printings"]["OGN-001"] = str(uuid.uuid4())
    del changed["retired"]["printings"]["OGN-002"]
    assert uuids.history_errors(before, changed) == [
        f"printing OGN-001: its uuid changed from {before['printings']['OGN-001']} to {changed['printings']['OGN-001']}",
        f"printing OGN-002: its uuid {before['printings']['OGN-002']} was dropped from data/uuids.json"]
