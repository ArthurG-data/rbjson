"""HTTP for the fetchers: one User-Agent, retries on a 5xx or a dropped connection, and a cache written atomically.

Named net, not http, because tools/ is on sys.path and a tools/http.py would shadow the standard library's http,
which urllib itself imports.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
USER_AGENT = f"rbjson/{VERSION} (+https://github.com/ArthurG-data/rbjson)"
TRIES = 3


def _retried(call: Callable[[], object], tries: int) -> object:
    """call(), tried again after a 5xx or a dropped connection, waiting 1 s, 2 s, ... between tries. A 4xx is
    final. The last failure is raised."""
    for attempt in range(tries):
        try:
            return call()
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == tries - 1:
                raise
        time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def get(url: str, timeout: int = 60, tries: int = TRIES) -> bytes:
    def call() -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    return _retried(call, tries)


def get_json(url: str, timeout: int = 60) -> object:
    return json.loads(get(url, timeout).decode("utf-8"))


def head_status(url: str, timeout: int = 30, tries: int = TRIES) -> int | None:
    """The HTTP status a HEAD of url fails with, 0 when nothing answers, None when it is served."""
    def call() -> None:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        urllib.request.urlopen(req, timeout=timeout).close()
    try:
        _retried(call, tries)
        return None
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return 0


def write_atomic(path: Path, text: str) -> None:
    """Write text to path so that a reader sees the old file or the whole new one, never a part: an interrupted
    run leaves no truncated cache behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def cached(path: Path, refresh: bool, fetch: Callable[[], object]) -> object:
    """The JSON document kept at path, else ``fetch()``, kept at path for the next call. With refresh, fetch
    again whatever is kept."""
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetch()
    write_atomic(path, json.dumps(data, ensure_ascii=False))
    return data
