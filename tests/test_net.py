import json
import urllib.error

import pytest

import net


class _Body:
    def __init__(self, data: bytes):
        self.data = data

    def read(self):
        return self.data

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake(answers, calls):
    def urlopen(req, timeout):
        calls.append((req.get_method(), req.full_url, req.get_header("User-agent")))
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return _Body(answer)
    return urlopen


def _http(code):
    return urllib.error.HTTPError("https://x", code, "err", {}, None)


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(net.time, "sleep", lambda s: None)


def test_get_retries_a_5xx_and_a_dropped_connection_then_returns_the_body(monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(net.urllib.request, "urlopen",
                        _fake([_http(503), urllib.error.URLError("reset"), b"ok"], calls))
    assert net.get("https://x/a") == b"ok"
    assert len(calls) == 3
    assert all(ua == net.USER_AGENT for _, _, ua in calls)


def test_get_raises_a_4xx_at_once(monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(net.urllib.request, "urlopen", _fake([_http(404)], calls))
    with pytest.raises(urllib.error.HTTPError):
        net.get("https://x/a")
    assert len(calls) == 1


def test_get_raises_the_last_5xx_when_every_try_fails(monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(net.urllib.request, "urlopen", _fake([_http(502)] * net.TRIES, calls))
    with pytest.raises(urllib.error.HTTPError):
        net.get("https://x/a")
    assert len(calls) == net.TRIES


def test_head_status_says_0_when_nothing_ever_answers(monkeypatch, no_sleep):
    monkeypatch.setattr(net.urllib.request, "urlopen", _fake([urllib.error.URLError("down")] * net.TRIES, []))
    assert net.head_status("https://x/a.png") == 0


def test_the_user_agent_names_the_project_version():
    assert net.USER_AGENT.startswith(f"rbjson/{net.VERSION} ")


def test_cached_fetches_once_and_reads_the_kept_document_after(tmp_path):
    fetched = []
    path = tmp_path / "doc.json"
    fetch = lambda: fetched.append(1) or {"n": len(fetched)}  # noqa: E731
    assert net.cached(path, False, fetch) == {"n": 1}
    assert net.cached(path, False, fetch) == {"n": 1}
    assert fetched == [1]


def test_cached_with_refresh_fetches_again(tmp_path):
    path = tmp_path / "doc.json"
    net.cached(path, False, lambda: {"v": "old"})
    assert net.cached(path, True, lambda: {"v": "new"}) == {"v": "new"}
    assert json.loads(path.read_text(encoding="utf-8")) == {"v": "new"}


def test_a_failed_fetch_leaves_the_kept_document_whole(tmp_path):
    path = tmp_path / "doc.json"
    net.cached(path, False, lambda: {"v": "old"})

    def broken():
        raise urllib.error.URLError("down")
    with pytest.raises(urllib.error.URLError):
        net.cached(path, True, broken)
    assert json.loads(path.read_text(encoding="utf-8")) == {"v": "old"}


def test_write_atomic_leaves_no_temporary_file(tmp_path):
    net.write_atomic(tmp_path / "sub" / "a.json", "{}")
    assert [p.name for p in (tmp_path / "sub").iterdir()] == ["a.json"]
