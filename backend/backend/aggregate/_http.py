"""Single network touchpoint for the aggregation package (issue #11).

Everything that goes over the wire funnels through :func:`post_json`, so tests
monkeypatch one function instead of the whole transport. stdlib ``urllib``
only — no new runtime dependency (R3).

Error taxonomy (S2 decides retry-vs-fatal from these):
- :class:`TransportError` — connection refused / timeout / DNS / reset / a
  200 response that is not valid JSON (all retryable).
- :class:`HttpError` — an HTTP error status; ``.status`` lets the retry policy
  treat 429/5xx as retryable and other 4xx as fatal.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class TransportError(Exception):
    """Connection-level or malformed-response failure. Retryable."""


class BadResponseError(TransportError):
    """An HTTP 200 whose body could not be decoded as JSON."""


class HttpError(Exception):
    """An HTTP error response with a status code."""

    def __init__(self, status: int, body: str = "") -> None:
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body


def _build_opener() -> urllib.request.OpenerDirector:
    # Explicit ProxyHandler (F8): honors http_proxy/https_proxy/no_proxy env
    # vars (and the Windows-registry fallback) for remote endpoints; localhost
    # (Ollama) is auto-bypassed via proxy_bypass.
    return urllib.request.build_opener(urllib.request.ProxyHandler())


def post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    """POST ``payload`` as JSON and return the parsed JSON response body.

    Raises :class:`TransportError` (incl. :class:`BadResponseError`) for
    connection/timeout/malformed-body failures and :class:`HttpError` for
    non-2xx HTTP statuses.
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers=headers, method="POST"
    )
    try:
        with _build_opener().open(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:  # must precede URLError (subclass)
        body = exc.read().decode("utf-8", errors="replace")
        raise HttpError(exc.code, body) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TransportError(str(exc)) from exc

    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BadResponseError(f"响应体不是合法 JSON: {exc}") from exc
