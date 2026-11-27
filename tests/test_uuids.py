import copy
import uuid

import pytest

import uuids


def _printing(pid, products=(), source="riot-gallery"):
    p = {"id": pid, "collectorNumber": 1, "rarity": "common", "source": source, "identifiers": {}}
    if products:
        p["identifiers"]["tcgplayerProductIds"] = list(products)
    return p


def _minted(pid, *products):
    return _printing(pid, products, "tcgplayer")


def _files(*cards):
    """{set: {"cards": [...]}} from (number, [printing, ...]) pairs."""
    files = {}
    for number, printings in cards:
        files.setdefault(number.split("-")[0], {"cards": []})["cards"].append(
            {"number": number, "name": number, "printings": printings})
    return files


def _run(files, registry):
    uuids.assign_cards(files, registry)
    return {p["id"]: p["uuid"] for b in files.values() for c in b["cards"] for p in c["printings"]}


def _cards(files):
    return {c["number"]: c["uuid"] for b in files.values() for c in b["cards"]}


def _sealed(*products):
    return {"OGN": {"products": [{"id": i, "identifiers": {"tcgplayerProductIds": [pid]}} for i, pid in products]}}


def _products(sealed, registry):
    uuids.assign_products(sealed, registry)
    return {p["id"]: p["uuid"] for p in sealed["OGN"]["products"]}


def test_a_record_seen_first_gets_uuid5_of_its_kind_and_id():
    files = _files(("OGN-001", [_printing("OGN-001")]))
    assert _run(files, uuids.empty()) == {"OGN-001": str(uuid.uuid5(uuids.NAMESPACE, "printings:OGN-001"))}
    assert _cards(files) == {"OGN-001": str(uuid.uuid5(uuids.NAMESPACE, "cards:OGN-001"))}


def test_a_rebuild_from_nothing_gives_every_record_the_uuid_it_had():
    def build():
        return _files(("OGN-001", [_printing("OGN-001"), _printing("OGN-001a")]), ("OPP-OGN001", [_minted("OPP-OGN001.x", 7)]))
    one, two = build(), build()
    _run(one, uuids.empty())
    _run(two, uuids.empty())
    assert one == two


def test_a_second_run_changes_nothing():
    registry = uuids.empty()
    files = _files(("OGN-001", [_printing("OGN-001", [5])]), ("OPP-OGN001", [_minted("OPP-OGN001.x", 7)]))
    _run(files, registry)
    before = copy.deepcopy((files, registry))
    _run(files, registry)
    assert (files, registry) == before


def test_the_uuid_sits_right_after_the_id():
    files = _files(("OGN-001", [_printing("OGN-001")]))
    _run(files, uuids.empty())
    card = files["OGN"]["cards"][0]
    assert list(card)[:2] == ["number", "uuid"]
    assert list(card["printings"][0])[:2] == ["id", "uuid"]


def test_a_minted_printing_whose_id_changes_keeps_its_uuid_through_its_tcgplayer_product():
    registry = uuids.empty()
    u = _run(_files(("OPP-OGN269", [_minted("OPP-OGN269.metal-best-of", 7)])), registry)["OPP-OGN269.metal-best-of"]
    after = _run(_files(("OPP-OGN269", [_minted("OPP-OGN269.metal-best-of-2026", 7)])), registry)
    assert after["OPP-OGN269.metal-best-of-2026"] == u


def test_two_minted_printings_whose_names_swap_keep_the_uuid_of_their_own_product():
    registry = uuids.empty()
    before = _run(_files(("OPP-OGN269", [_minted("OPP-OGN269.a", 7), _minted("OPP-OGN269.b", 8)])), registry)
    after = _run(_files(("OPP-OGN269", [_minted("OPP-OGN269.a", 8), _minted("OPP-OGN269.b", 7)])), registry)
    assert after == {"OPP-OGN269.a": before["OPP-OGN269.b"], "OPP-OGN269.b": before["OPP-OGN269.a"]}


def test_a_sealed_id_that_passes_to_another_product_does_not_take_the_first_products_uuid():
    registry = uuids.empty()
    before = _products(_sealed(("x", 100), ("x-200", 200)), registry)
    # TCGplayer delists product 100, so product 200 is now plain x
    after = _products(_sealed(("x", 200)), registry)
    assert after == {"x": before["x-200"]}
    # and product 100 gets its own back when it returns
    assert _products(_sealed(("x", 100), ("x-200", 200)), registry) == before


def test_a_new_product_relisted_under_a_left_products_id_takes_its_uuid():
    registry = uuids.empty()
    u = _products(_sealed(("origins-booster-display", 100)), registry)["origins-booster-display"]
    assert _products(_sealed(("origins-booster-display", 300)), registry) == {"origins-booster-display": u}


def test_a_minted_printing_the_gallery_starts_listing_keeps_its_uuid():
    registry = uuids.empty()
    u = _run(_files(("OGN-R01", [_minted("OGN-R01", 7)])), registry)["OGN-R01"]
    assert _run(_files(("OGN-R01", [_printing("OGN-R01", [7])])), registry) == {"OGN-R01": u}


def test_a_gallery_printing_keeps_its_uuid_when_tcgplayer_moves_its_product_to_another():
    registry = uuids.empty()
    before = _run(_files(("OGN-001", [_printing("OGN-001", [7]), _printing("OGN-001a")])), registry)
    after = _run(_files(("OGN-001", [_printing("OGN-001"), _printing("OGN-001a", [7])])), registry)
    assert after == before


def test_minted_printings_dropped_by_a_gallery_rebuild_get_their_uuids_back_from_the_next_tcgcsv_run():
    registry = uuids.empty()
    whole = _files(("OGN-001", [_printing("OGN-001", [5]), _minted("OGN-001.metal", 7)]))
    before = _run(copy.deepcopy(whole), registry)
    _run(_files(("OGN-001", [_printing("OGN-001")])), registry)  # import_gallery alone: no products, no minted
    assert _run(copy.deepcopy(whole), registry) == before


def test_a_card_whose_number_changes_keeps_its_uuid_through_its_printings():
    registry = uuids.empty()
    before = _files(("OPP-OGN269", [_minted("OPP-OGN269", 7)]))
    _run(before, registry)
    after = _files(("OPP-SFD269", [_minted("OPP-SFD269", 7)]))
    _run(after, registry)
    assert _cards(after) == {"OPP-SFD269": _cards(before)["OPP-OGN269"]}


def test_a_new_card_does_not_take_the_uuid_of_a_card_still_in_the_data():
    registry = uuids.empty()
    before = _files(("OGN-001", [_printing("OGN-001"), _printing("OGN-001a")]))
    _run(before, registry)
    after = _files(("OGN-001", [_printing("OGN-001")]), ("OGN-002", [_printing("OGN-001a")]))
    _run(after, registry)
    assert _cards(after)["OGN-001"] == _cards(before)["OGN-001"]
    assert _cards(after)["OGN-002"] != _cards(before)["OGN-001"]


def test_printings_and_products_do_not_share_tcgplayer_keys():
    registry = uuids.empty()
    printing = _run(_files(("OGN-R01", [_minted("OGN-R01", 7)])), registry)["OGN-R01"]
    assert _products(_sealed(("bulk-runes", 7)), registry)["bulk-runes"] != printing


def test_two_live_records_on_one_uuid_are_a_conflict():
    registry = uuids.empty()
    _run(_files(("OGN-R01", [_minted("OGN-R01", 7, 8)])), registry)
    with pytest.raises(uuids.Conflict):
        # the printing's two products split into two printings that each name the old UUID
        registry["printings"]["keys"]["tcgplayer:8"] = registry["printings"]["keys"]["tcgplayer:7"]
        _run(_files(("OGN-R01", [_minted("OGN-R01", 7), _minted("OGN-R01a", 8)])), registry)


def test_errors_names_a_missing_uuid_a_wrong_one_and_a_shared_one():
    registry = uuids.empty()
    files = _files(("OGN-001", [_printing("OGN-001")]), ("OGN-002", [_printing("OGN-002")]))
    _run(files, registry)
    assert uuids.errors(files, {}, registry) == []
    cards = files["OGN"]["cards"]
    del cards[0]["printings"][0]["uuid"]
    cards[1]["printings"][0]["uuid"] = cards[1]["uuid"] = str(uuid.uuid4())
    found = uuids.errors(files, {}, registry)
    assert any(e.startswith("printing OGN-001 has no uuid") for e in found)
    assert any(e.startswith("printing OGN-002: uuid") for e in found)
    assert any(e.endswith("is on 2 records") for e in found)


def test_history_allows_new_and_left_records_and_refuses_a_changed_or_dropped_key():
    before = uuids.empty()
    _run(_files(("OGN-001", [_printing("OGN-001")]), ("OGN-002", [_printing("OGN-002")])), before)
    after = copy.deepcopy(before)
    _run(_files(("OGN-001", [_printing("OGN-001")]), ("OGN-003", [_printing("OGN-003")])), after)
    assert uuids.history_errors(before, after) == []
    changed = copy.deepcopy(after)
    keys = changed["printings"]["keys"]
    keys["id:OGN-001"] = str(uuid.uuid4())
    del keys["id:OGN-002"]
    old = before["printings"]["keys"]
    assert uuids.history_errors(before, changed) == [
        f"printing id:OGN-001: its uuid changed from {old['id:OGN-001']} to {keys['id:OGN-001']}",
        f"printing id:OGN-002: its uuid {old['id:OGN-002']} was dropped from data/uuids.json"]
