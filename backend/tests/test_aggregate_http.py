"""Tests for aggregate._http — the single network touchpoint (S1).

All tests monkeypatch ``_build_opener`` so nothing leaves the process.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from backend.backend.aggregate import _http


class FakeResponse:
    """Context-manager response the fake opener hands back."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def read(self) -> bytes:
        return self.body


class FakeOpener:
    """Stand-in for an ``OpenerDirector``: returns a result or raises."""

    def __init__(self, result: FakeResponse | Exception) -> None:
        self.result = result
        self.last_request = None
        self.last_timeout = None

    def open(self, request, timeout=None):
        self.last_request = request
        self.last_timeout = timeout
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _install_opener(monkeypatch, result):
    opener = FakeOpener(result)
    monkeypatch.setattr(_http, "_build_opener", lambda: opener)
    return opener


def test_post_json_returns_parsed_json_and_passes_payload_headers_timeout(monkeypatch):
    opener = _install_opener(monkeypatch, FakeResponse(b'{"ok": true, "n": 1}'))

    result = _http.post_json(
        "https://api.example.com/v1/chat/completions",
        headers={"Authorization": "Bearer sk-test", "Content-Type": "application/json"},
        payload={"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]},
        timeout=60,
    )

    assert result == {"ok": True, "n": 1}
    assert opener.last_timeout == 60
    assert opener.last_request.method == "POST"
    sent = json.loads(opener.last_request.data.decode("utf-8"))
    assert sent["model"] == "deepseek-chat"
    assert opener.last_request.headers["Authorization"] == "Bearer sk-test"


def test_http_error_status_is_surfaced(monkeypatch):
    err = urllib.error.HTTPError(
        "https://api.example.com", 500, "Internal Server Error", {}, io.BytesIO(b"boom")
    )
    _install_opener(monkeypatch, err)

    with pytest.raises(_http.HttpError) as excinfo:
        _http.post_json("https://api.example.com", {}, {"x": 1}, timeout=10)
    assert excinfo.value.status == 500
    assert excinfo.value.body == "boom"


def test_four_xx_http_error_is_surfaced(monkeypatch):
    err = urllib.error.HTTPError(
        "https://api.example.com", 400, "Bad Request", {}, io.BytesIO(b"bad")
    )
    _install_opener(monkeypatch, err)

    with pytest.raises(_http.HttpError) as excinfo:
        _http.post_json("https://api.example.com", {}, {"x": 1}, timeout=10)
    assert excinfo.value.status == 400  # S2 decides: 4xx is not retryable


def test_connection_refused_is_transport_error(monkeypatch):
    err = urllib.error.URLError("Connection refused")
    _install_opener(monkeypatch, err)

    with pytest.raises(_http.TransportError):
        _http.post_json("http://127.0.0.1:11434/api/chat", {}, {"x": 1}, timeout=10)


def test_oserror_is_transport_error(monkeypatch):
    _install_opener(monkeypatch, OSError("network is unreachable"))

    with pytest.raises(_http.TransportError):
        _http.post_json("http://127.0.0.1:11434/api/chat", {}, {"x": 1}, timeout=10)


def test_non_json_body_is_bad_response(monkeypatch):
    _install_opener(monkeypatch, FakeResponse(b"<html>not json</html>"))

    with pytest.raises(_http.BadResponseError):
        _http.post_json("https://api.example.com", {}, {"x": 1}, timeout=10)
