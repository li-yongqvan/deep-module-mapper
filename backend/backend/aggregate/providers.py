"""Provider abstraction + retry/repair (S2, issue #11).

The backend had zero AI code before this ticket (T5); this module is the new
swap point (D7). Two concrete providers go through the single network
touchpoint ``_http.post_json``:

- :class:`OpenAICompatProvider` — DeepSeek, the **sole authority** for the
  manifest (D1). OpenAI-compatible ``/chat/completions`` protocol.
- :class:`OllamaProvider` — the local **learning role** only (D5); its output
  never becomes the authoritative manifest.

:func:`retry_with_repair` implements the D8 policy: transport failures are
retried up to 3 total attempts (1 first + 2 retries, backoff 1s/2s; 4xx beyond
429 is not retried), and one invalid output triggers a single repair pass.
"""

from __future__ import annotations

import dataclasses
import json
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from . import _http
from .config import EnvConfig

# HTTP statuses the retry policy treats as transient (D8): rate-limit and 5xx.
# Other 4xx are client errors — retrying cannot fix them.
RETRYABLE_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})

# Backoff per retry index (0 → 1s, 1 → 2s); attempt 2 has no further retry.
BACKOFF_SECONDS = (1, 2)


class Provider(Protocol):
    """One model-backed endpoint. Both authorities and the learning role
    implement this so ``retry_with_repair`` / the runner can treat them alike.
    """

    name: str

    def generate(
        self, system: str, user: str, *, temperature: float = 0.1
    ) -> ProviderResult: ...


@dataclass
class ProviderResult:
    """Outcome of a model call (or of :func:`retry_with_repair`).

    ``ok=True`` means usable text was produced. On failure ``text`` is None and
    ``error`` carries the reason. ``retryable`` tells the retry policy whether
    another attempt could plausibly help; ``attempts`` counts total calls.
    """

    text: str | None
    ok: bool
    error: str | None = None
    attempts: int = 0
    retryable: bool = True


def _shape_error(body: object, kind: str) -> ProviderResult:
    return ProviderResult(
        text=None,
        ok=False,
        error=f"unexpected response shape ({kind}): {body!r}"[:200],
        attempts=1,
    )


def _extract(content: object, kind: str) -> ProviderResult:
    if not isinstance(content, str) or not content.strip():
        return ProviderResult(
            text=None, ok=False, error=f"empty response content ({kind})", attempts=1
        )
    return ProviderResult(text=content, ok=True, attempts=1)


class OpenAICompatProvider:
    """DeepSeek via the OpenAI-compatible ``/chat/completions`` protocol."""

    def __init__(
        self, base_url: str, api_key: str, model: str, *, timeout: int = 60
    ) -> None:
        self.name = f"openai-compat:{model}"
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def generate(
        self, system: str, user: str, *, temperature: float = 0.1
    ) -> ProviderResult:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            body = _http.post_json(
                f"{self._base_url}/chat/completions", headers, payload, self._timeout
            )
        except _http.TransportError as exc:
            return ProviderResult(text=None, ok=False, error=f"transport: {exc}", attempts=1)
        except _http.HttpError as exc:
            return ProviderResult(
                text=None,
                ok=False,
                error=f"http {exc.status}: {exc.body[:200]}",
                attempts=1,
                retryable=exc.status in RETRYABLE_HTTP_STATUSES,
            )
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return _shape_error(body, "choices[0].message.content")
        return _extract(content, "deepseek")


class OllamaProvider:
    """Local learning role via Ollama's native ``/api/chat`` protocol."""

    def __init__(self, host: str, model: str, *, timeout: int = 120) -> None:
        self.name = f"ollama:{model}"
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout

    def generate(
        self, system: str, user: str, *, temperature: float = 0.1
    ) -> ProviderResult:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }
        try:
            body = _http.post_json(f"{self._host}/api/chat", {}, payload, self._timeout)
        except _http.TransportError as exc:
            return ProviderResult(text=None, ok=False, error=f"transport: {exc}", attempts=1)
        except _http.HttpError as exc:
            return ProviderResult(
                text=None,
                ok=False,
                error=f"http {exc.status}: {exc.body[:200]}",
                attempts=1,
                retryable=exc.status in RETRYABLE_HTTP_STATUSES,
            )
        try:
            content = body["message"]["content"]
        except (KeyError, TypeError):
            return _shape_error(body, "message.content")
        return _extract(content, "ollama")


# --- retry / repair (D8) -------------------------------------------------

def _is_valid_json(text: str) -> str | None:
    """Default validity check for repair: ``None`` if parseable, else an error
    description. S4/S5 swap in a stronger check (``validate_manifest``)."""
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        return f"输出不是合法 JSON: {exc}"
    return None


def _default_repair_user(raw_output: str, error: str) -> str:
    """Repair prompt fed back to the model (S3 refines via REPAIR_TEMPLATE)."""
    return (
        "你上次的输出不是合法 JSON。请只输出修正后的合法 JSON，不要任何其他文本。\n\n"
        f"错误：{error}\n\n上次输出：\n{raw_output}"
    )


def retry_with_repair(
    provider: Provider,
    system: str,
    user: str,
    *,
    max_transport_attempts: int = 3,
    check: Callable[[str], str | None] = _is_valid_json,
    repair_user: Callable[[str, str], str] = _default_repair_user,
    sleep: Callable[[float], None] = time.sleep,
) -> ProviderResult:
    """Call ``provider.generate`` with the D8 policy and return the outcome.

    Transport failures (connection/timeout/429/5xx) are retried up to
    ``max_transport_attempts`` total calls with backoff; non-retryable 4xx
    returns immediately. If usable text is produced but fails ``check``, a
    single repair pass is attempted. ``attempts`` counts every call made.
    """
    total = 0
    last: ProviderResult | None = None
    for attempt in range(max_transport_attempts):
        total += 1
        last = provider.generate(system, user)
        if last.ok or not last.retryable:
            break
        if attempt < max_transport_attempts - 1:
            sleep(BACKOFF_SECONDS[attempt])
    assert last is not None
    if not last.ok or last.text is None:
        return dataclasses.replace(last, attempts=total)

    error = check(last.text)
    if error is None:
        return dataclasses.replace(last, attempts=total)
    # One repair pass (D8). The repaired output must re-pass ``check``; a
    # still-invalid output is a failure (never a silent pass-through).
    repaired = provider.generate(system, repair_user(last.text, error))
    if not repaired.ok or repaired.text is None:
        return dataclasses.replace(repaired, attempts=total + 1)
    repair_error = check(repaired.text)
    if repair_error is not None:
        return ProviderResult(
            text=None,
            ok=False,
            error=f"repair 后输出仍无效: {repair_error}",
            attempts=total + 1,
        )
    return dataclasses.replace(repaired, attempts=total + 1)


# --- factories (D7: swapping a provider is a one-place change) -----------

def get_api_provider(config: EnvConfig) -> Provider:
    """Build the authoritative (DeepSeek) provider. Callers must have checked
    ``config.has_api_key`` first (INV11 — missing key is fatal, exit 1)."""
    return OpenAICompatProvider(
        config.llm_api_base,
        config.llm_api_key or "",
        config.llm_model,
        timeout=config.llm_timeout_s,
    )


def get_local_provider(config: EnvConfig) -> Provider:
    """Build the local learning-role provider (best-effort, never authority)."""
    return OllamaProvider(
        config.ollama_host,
        config.ollama_model,
        timeout=config.ollama_timeout_s,
    )
