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


def _entry(gid, code, name, image, subtitle=None, artist="Kudos Productions"):
    e = {"id": gid, "publicCode": code, "name": name, "collectorNumber": int(code.split("-")[1][:3]),
         "rarity": {"value": {"id": "epic"}}, "cardImage": {"url": image},
         "illustrator": {"values": [{"label": artist}]}, "cardType": {"type": [{"id": "unit"}]}}
    if subtitle:
        e["subtitle"] = subtitle
    return e


def _english():
    return [_entry("ogn-119-298", "OGN-119/298", "Ahri", "https://r/en-119.png", "Inquisitive"),
            _entry("ogn-119a-298", "OGN-119a/298", "Ahri", "https://r/en-119a.png", "Inquisitive"),
            _entry("ogn-004-298", "OGN-004/298", "Brazen Buccaneer", "https://r/en-4.png")]


def _merged(korean):
    english = _english()
    files, _, _ = import_gallery.build_files(english, {"OGN"})
    added, problems = import_gallery.merge_locale(files, english, korean, "ko")
    return files, added, problems


def test_a_korean_entry_with_its_own_image_becomes_a_ko_printing_and_names_the_card():
    korean = [_entry("ogn-119-298", "OGN-119/298", "아리", "https://r/ko-119.png", "호기심", artist="Kudos"),
              _entry("ogn-119a-298", "OGN-119a/298", "아리", "https://r/ko-119a.png", "호기심"),
              _entry("ogn-004-298", "OGN-004/298", "무모한 해적", "https://r/ko-4.png")]
    files, added, problems = _merged(korean)
    assert added == 3 and problems == []
    ahri = next(c for c in files["OGN"]["cards"] if c["number"] == "OGN-119")
    assert [p["id"] for p in ahri["printings"]] == ["OGN-119", "OGN-119a", "OGN-119~ko", "OGN-119a~ko"]
    assert ahri["name"] == "Ahri" and ahri["subtitle"] == "Inquisitive"
    assert ahri["names"] == {"en": "Ahri", "ko": "아리"} and ahri["subtitles"] == {"en": "Inquisitive", "ko": "호기심"}
    ko = ahri["printings"][3]
    assert ko["language"] == "ko" and ko["suffix"] == "a" and ko["image"] == "https://r/ko-119a.png"
    assert ko["collectorNumber"] == 119 and ko["rarity"] == "epic" and ko["artists"] == ["Kudos Productions"]
    assert ko["identifiers"] == {"galleryId": "ogn-119a-298", "publicCode": "OGN-119a/298"}
    assert "finishes" not in ko and "tcgplayer" not in ko
    buccaneer = next(c for c in files["OGN"]["cards"] if c["number"] == "OGN-004")
    assert buccaneer["names"]["ko"] == "무모한 해적" and "subtitles" not in buccaneer


def test_a_korean_entry_whose_image_equals_the_english_one_adds_nothing():
    korean = [_entry("ogn-119-298", "OGN-119/298", "아리", "https://r/en-119.png", "호기심"),
              _entry("ogn-119a-298", "OGN-119a/298", "아리", "https://r/en-119a.png", "호기심"),
              _entry("ogn-004-298", "OGN-004/298", "무모한 해적", "https://r/ko-4.png")]
    files, added, _ = _merged(korean)
    assert added == 1
    ahri = next(c for c in files["OGN"]["cards"] if c["number"] == "OGN-119")
    assert len(ahri["printings"]) == 2 and "names" not in ahri and "subtitles" not in ahri


def test_one_translated_variant_names_the_card_from_the_variant_that_differs():
    korean = [_entry("ogn-119-298", "OGN-119/298", "아리", "https://r/en-119.png", "호기심"),
              _entry("ogn-119a-298", "OGN-119a/298", "아리a", "https://r/ko-119a.png", "호기심a")]
    files, added, _ = _merged(korean)
    ahri = files["OGN"]["cards"][1]
    assert added == 1 and [p["id"] for p in ahri["printings"]] == ["OGN-119", "OGN-119a", "OGN-119a~ko"]
    assert ahri["names"]["ko"] == "아리a"


def test_an_entry_english_lacks_is_reported_and_not_written():
    korean = [_entry("ogn-999-298", "OGN-999/298", "없음", "https://r/ko-999.png")]
    files, added, problems = _merged(korean)
    assert added == 0 and len(problems) == 1 and "ogn-999-298" in problems[0]
    assert sum(len(c["printings"]) for c in files["OGN"]["cards"]) == 3


def test_union_pages_keeps_an_entry_one_read_omits():
    import gallery

    def page(*ids):
        return {"pageProps": {"page": {"blades": [{"type": gallery.BLADE, "cards": {"items": [{"id": i} for i in ids]}}]}}}

    merged = gallery.union_pages(page("a", "c"), page("a", "b", "c"))
    assert [e["id"] for e in gallery.cards(gallery.blade(merged))] == ["a", "c", "b"]

    # Any number of reads: an entry is kept once, from the first read that has it.
    merged = gallery.union_pages(page("a"), page("a", "c"), page("b", "c"))
    assert [e["id"] for e in gallery.cards(gallery.blade(merged))] == ["a", "c", "b"]
