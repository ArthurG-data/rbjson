import json
from pathlib import Path

import pytest

import gallery
import import_gallery

FIXTURE = Path(__file__).parent / "fixtures" / "gallery_sample.json"


def _entries():
    return gallery.cards(gallery.blade(json.loads(FIXTURE.read_text(encoding="utf-8"))))


@pytest.mark.parametrize("code, expected", [
    ("OGN-119/298", ("OGN", "OGN-119", "")),
    ("OGN-119a/298", ("OGN", "OGN-119", "a")),
    ("SFD-227*/221", ("SFD", "SFD-227", "*")),
    ("RAD-SP1/005", ("RAD", "RAD-SP1", "")),
    ("RAD-R04a", ("RAD", "RAD-R04", "a")),
    ("UNL-T01", ("UNL", "UNL-T01", "")),
])
def test_parse_code(code, expected):
    assert import_gallery.parse_code(code) == expected


def test_an_unrecognised_code_is_refused():
    with pytest.raises(ValueError):
        import_gallery.parse_code("OGN119")


def test_variants_of_one_number_become_one_card_with_several_printings():
    files, problems, _ = import_gallery.build_files(_entries(), {"OGN", "SFD", "RAD", "UNL"})
    assert problems == []
    ahri = next(c for c in files["OGN"]["cards"] if c["number"] == "OGN-119")
    assert ahri["name"] == "Ahri" and ahri["subtitle"] == "Inquisitive"
    assert ahri["type"] == "unit" and ahri["superTypes"] == ["champion"]
    assert [p["id"] for p in ahri["printings"]] == ["OGN-119", "OGN-119a"]
    assert ahri["printings"][0]["rarity"] == "epic" and ahri["printings"][1]["rarity"] == "showcase"
    assert ahri["printings"][1]["suffix"] == "a" and "suffix" not in ahri["printings"][0]
    assert ahri["printings"][1]["identifiers"] == {"galleryId": "ogn-119a-298", "publicCode": "OGN-119a/298"}


def test_star_variants_runes_tokens_and_promos_keep_their_numbers():
    files, _, _ = import_gallery.build_files(_entries(), {"OGN", "SFD", "RAD", "UNL"})
    ids = {p["id"] for body in files.values() for c in body["cards"] for p in c["printings"]}
    assert {"SFD-227", "SFD-227*", "RAD-SP1", "RAD-R04", "RAD-R04a", "UNL-T01"} <= ids
    rune = next(c for c in files["RAD"]["cards"] if c["number"] == "RAD-R04")
    assert rune["type"] == "rune" and rune["superTypes"] == ["basic"]
    assert [p["id"] for p in rune["printings"]] == ["RAD-R04", "RAD-R04a"]


def test_an_entry_the_gallery_gives_no_type_has_no_type_field():
    entry = {"name": "Mystery", "cardType": {"label": "Card Type", "type": []}, "domain": {"values": []}}
    assert import_gallery.card_facts(entry) == {"name": "Mystery"}


def test_a_variant_that_disagrees_with_its_base_is_reported_and_takes_the_base_facts():
    files, _, disagreements = import_gallery.build_files(_entries(), {"OGN", "SFD", "RAD", "UNL"})
    ahri = next(c for c in files["OGN"]["cards"] if c["number"] == "OGN-119")
    assert ahri["tags"] == ["Ahri", "Ionia"]
    assert disagreements == [{"printing": "OGN-119a", "base": "OGN-119/298", "field": "tags",
                              "printing_value": ["Ahri"], "base_value": ["Ahri", "Ionia"]}]


def test_cards_are_ordered_numbers_then_promos_runes_tokens():
    files, _, _ = import_gallery.build_files(_entries(), {"OGN", "SFD", "RAD", "UNL"})
    assert [c["number"] for c in files["RAD"]["cards"]] == ["RAD-SP1", "RAD-R04"]


def test_an_unknown_set_is_reported_and_skipped():
    files, problems, _ = import_gallery.build_files(_entries(), {"OGN"})
    assert set(files) == {"OGN"}
    assert any("SFD is not in sets/sets.json" in p for p in problems)


def test_a_non_english_locale_marks_its_printings():
    files, _, _ = import_gallery.build_files(_entries(), {"OGN"}, language="fr")
    assert all(p["language"] == "fr" for c in files["OGN"]["cards"] for p in c["printings"])


def test_build_id_is_read_from_the_page():
    assert gallery.build_id('<script>{"buildId":"saXcR0KxRzJ_Rr6squY8u","x":1}</script>') == "saXcR0KxRzJ_Rr6squY8u"
    with pytest.raises(ValueError):
        gallery.build_id("<html></html>")
