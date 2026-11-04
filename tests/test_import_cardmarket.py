import import_cardmarket as im
from cardmarket import Product


def _printing(pid, **extra):
    return {"id": pid, "collectorNumber": 1, "rarity": "common", "image": "https://x/a.png", "source": "riot-gallery",
            "identifiers": {"galleryId": pid.lower(), "publicCode": pid}, **extra}


def _card(number, name, subtitle=None, type="unit", super_types=(), tags=(), suffixes=("",)):
    card = {"number": number, "name": name, "type": type, "superTypes": list(super_types), "tags": list(tags),
            "printings": [_printing(number + s, **({"suffix": s} if s else {})) for s in suffixes]}
    if subtitle:
        card["subtitle"] = subtitle
    return card


SETS = [{"id": "OGN", "cardmarketExpansionIds": [1]}]


def _run(cards, products):
    files = {"OGN": {"cards": cards}}
    result = im.apply(files, SETS, products)
    ids = {p["id"]: p["identifiers"].get("cardmarketProductIds") for c in cards for p in c["printings"]}
    return result, ids


def test_fold_ignores_case_accents_and_punctuation_but_keeps_commas_and_apostrophes():
    assert im.fold("LeBlanc, Deceiver") == im.fold("Leblanc, Deceiver")
    assert im.fold("Kai’Sa, Survivor") == "kai'sa, survivor"
    assert im.fold("Fox-Fire (Alt)") == "fox fire alt"
    assert im.fold("Rek’Saí") == "rek'sai"


def test_a_card_is_found_by_name_with_or_without_its_subtitle():
    cards = [_card("OGN-001", "Darius", "Trifarian"), _card("OGN-002", "Teemo")]
    _, ids = _run(cards, [Product(10, 1, "Darius, Trifarian"), Product(11, 1, "TEEMO")])
    assert ids == {"OGN-001": [10], "OGN-002": [11]}


def test_a_legend_is_found_under_its_champion_and_a_signature_spell_under_its_name():
    cards = [_card("OGN-001", "Ahri", "Inquisitive", super_types=["champion"]),
             _card("OGN-002", "Ahri", "Nine-Tailed Fox", type="legend", tags=["Ahri", "Ionia"]),
             _card("OGN-003", "Fox-Fire", "Ahri", type="spell", super_types=["signature"], tags=["Ahri"])]
    products = [Product(10, 1, "Ahri, Inquisitive"), Product(11, 1, "Ahri, Nine-Tailed Fox"), Product(12, 1, "Fox-Fire")]
    _, ids = _run(cards, products)
    assert ids == {"OGN-001": [10], "OGN-002": [11], "OGN-003": [12]}


def test_a_tag_that_is_no_champion_names_nothing():
    cards = [_card("OGN-001", "Fox", type="legend", tags=["Ionia"])]
    assert im.candidates(cards[0], im.champions({"OGN": {"cards": cards}})) == {"fox"}


def test_two_products_of_one_name_stay_unmatched_and_are_listed():
    cards = [_card("OGN-001", "Ahri", "Inquisitive", suffixes=("", "a"))]
    result, ids = _run(cards, [Product(10, 1, "Ahri, Inquisitive"), Product(11, 1, "Ahri, Inquisitive")])
    assert ids == {"OGN-001": None, "OGN-001a": None}
    assert result["review"]["ambiguous_name"] == [
        {"set": "OGN", "name": "Ahri, Inquisitive", "products": [10, 11], "prints": ["OGN-001"]}]
    assert result["counts"]["ambiguous"] == 2


def test_two_prints_of_one_name_stay_unmatched():
    cards = [_card("OGN-001", "Fury Rune", type="rune"), _card("OGN-002", "Fury Rune", type="rune")]
    result, ids = _run(cards, [Product(10, 1, "Fury Rune")])
    assert ids == {"OGN-001": None, "OGN-002": None}
    assert result["review"]["ambiguous_name"][0]["prints"] == ["OGN-001", "OGN-002"]


def test_a_product_no_print_carries_is_no_print_and_a_foreign_expansion_is_promo():
    result, ids = _run([_card("OGN-001", "Teemo")],
                       [Product(10, 1, "Bird"), Product(11, 1, "Teemo"), Product(12, 9, "Teemo")])
    assert ids == {"OGN-001": [11]}
    assert result["review"]["no_print"] == [{"set": "OGN", "name": "Bird", "products": [10]}]
    assert result["review"]["promo_expansions"] == [{"expansionId": 9, "products": 1}]
    assert result["counts"]["no_print"] == 1 and "ambiguous" not in result["counts"]


def test_the_id_goes_on_the_english_base_printing_only_and_a_rerun_starts_clean():
    korean = _printing("OGN-001~ko", language="ko")
    card = _card("OGN-001", "Teemo", suffixes=("", "a"))
    card["printings"].append(korean)
    card["printings"][1]["identifiers"]["cardmarketProductIds"] = [99]  # stale
    _, ids = _run([card], [Product(10, 1, "Teemo")])
    assert ids == {"OGN-001": [10], "OGN-001a": None, "OGN-001~ko": None}
