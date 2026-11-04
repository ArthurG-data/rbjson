import urllib.error

import validate


class _Answer:
    def close(self):
        pass


def _urlopen(answers, calls):
    def fake(req, timeout):
        calls.append(req.full_url)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return _Answer()
    return fake


def _http(code):
    return urllib.error.HTTPError("https://x", code, "err", {}, None)


def test_a_5xx_is_retried_and_a_later_answer_passes(monkeypatch):
    calls = []
    monkeypatch.setattr(validate.urllib.request, "urlopen", _urlopen([_http(502), _http(503), "ok"], calls))
    monkeypatch.setattr(validate.time, "sleep", lambda s: None)
    assert validate.head_status("https://x/a.png") is None
    assert len(calls) == 3


def test_a_4xx_is_final_without_a_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(validate.urllib.request, "urlopen", _urlopen([_http(404)], calls))
    assert validate.head_status("https://x/a.png") == 404
    assert len(calls) == 1


def test_image_errors_names_each_failure():
    printings = {"OGN-001": {"image": "https://r/1.png"}, "OGN-002": {"image": "https://r/2.png"},
                 "OGN-003": {"image": "https://r/3.png"}}
    statuses = {"https://r/1.png": 404, "https://r/2.png": None, "https://r/3.png": 0}
    assert validate.image_errors(printings, head=statuses.get) == [
        "printing OGN-001: image answers 404", "printing OGN-003: image answers nothing"]


def test_online_errors_reports_gone_and_missing_entries(monkeypatch):
    sets = [{"id": "OGN"}]
    files = {"OGN": {"cards": [{"number": "OGN-001", "name": "x", "printings": [
        {"id": "OGN-001", "collectorNumber": 1, "rarity": "common", "image": "https://r/1.png", "source": "riot-gallery",
         "identifiers": {"galleryId": "ogn-001-298", "publicCode": "OGN-001/298"}}]}]}}
    monkeypatch.setattr(validate.gallery, "fetch", lambda locale: {"cards": {"items": [{"id": "ogn-002-298"}]}})
    assert validate.online_errors(sets, files) == [
        "printing OGN-001: gallery entry ogn-001-298 is gone",
        "gallery entry ogn-002-298 is not in the data: run tools/import_gallery.py"]


def test_set_art_errors_names_a_missing_key_art_and_logo():
    art = {"url": "https://cdn/ogn.jpg", "source": "https://s/ogn", "size": [1920, 1080]}
    sets = [{"id": "OGN", "releases": [{"language": "en", "keyArt": art, "logo": {"url": "https://cdn/logo.png", "source": "https://s"}}]},
            {"id": "SFD", "releases": [{"language": "en", "keyArt": {**art, "url": "https://cdn/sfd.jpg"}}]},
            {"id": "OGS", "releases": [{"language": "en"}]}]
    statuses = {"https://cdn/ogn.jpg": 404, "https://cdn/logo.png": 0, "https://cdn/sfd.jpg": None}
    assert validate.set_art_errors(sets, head=statuses.get) == [
        "set OGN key art: answers 404", "set OGN logo: answers nothing"]
