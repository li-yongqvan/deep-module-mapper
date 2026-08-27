"""Tests for aggregate.providers — provider abstraction + retry/repair (S2).

Two seams, both offline: ``_http.post_json`` (monkeypatched for the concrete
providers) and ``provider.generate`` (a scripted fake for
``retry_with_repair``). Only external behavior is asserted.
"""

from __future__ import annotations

from backend.backend.aggregate import _http
from backend.backend.aggregate.config import EnvConfig
from backend.backend.aggregate.providers import (
    OpenAICompatProvider,
    OllamaProvider,
    ProviderResult,
    get_api_provider,
    get_local_provider,
    retry_with_repair,
)

NO_SLEEP = lambda _seconds: None  # noqa: E731  (pytest-style test helper)


def _result(text=None, ok=False, error=None, retryable=True) -> ProviderResult:
    return ProviderResult(text=text, ok=ok, error=error, attempts=1, retryable=retryable)


class FakeProvider:
    """Scripted provider: returns pre-arranged results, records the users."""

    def __init__(self, *results: ProviderResult) -> None:
        self._results = list(results)
        self.users: list[str] = []

    @property
    def name(self) -> str:
        return "fake"

    def generate(self, system: str, user: str, *, temperature: float = 0.1) -> ProviderResult:
        self.users.append(user)
        return self._results.pop(0)


# --- concrete providers: response parsing + error mapping -----------------


def test_deepseek_parses_openai_compatible_response(monkeypatch):
    captured: dict = {}

    def fake_post_json(url, headers, payload, timeout):
        captured.update(url=url, headers=headers, payload=payload, timeout=timeout)
        return {"choices": [{"message": {"content": '{"atoms": []}'}}]}

    monkeypatch.setattr(_http, "post_json", fake_post_json)
    provider = OpenAICompatProvider("https://api.example.com/v1", "sk-test", "deepseek-chat")

    result = provider.generate("sys", "user")

    assert result.ok and result.text == '{"atoms": []}'
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["payload"]["model"] == "deepseek-chat"
    assert captured["payload"]["stream"] is False


def test_ollama_parses_native_response(monkeypatch):
    captured: dict = {}

    def fake_post_json(url, headers, payload, timeout):
        captured.update(url=url, payload=payload)
        return {"message": {"content": "local answer"}}

    monkeypatch.setattr(_http, "post_json", fake_post_json)
    provider = OllamaProvider("http://127.0.0.1:11434", "my-assistant")

    result = provider.generate("sys", "user")

    assert result.ok and result.text == "local answer"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"] == {"temperature": 0.1}


def test_transport_error_is_retryable_failure(monkeypatch):
    def fake_post_json(url, headers, payload, timeout):
        raise _http.TransportError("connection refused")

    monkeypatch.setattr(_http, "post_json", fake_post_json)
    provider = OpenAICompatProvider("https://api.example.com/v1", "sk-test", "m")

    result = provider.generate("s", "u")

    assert not result.ok and result.text is None
    assert result.retryable is True
    assert "transport" in result.error


def test_http_500_is_retryable_and_400_is_not(monkeypatch):
    def fake_500(url, headers, payload, timeout):
        raise _http.HttpError(500, "boom")

    monkeypatch.setattr(_http, "post_json", fake_500)
    provider = OpenAICompatProvider("https://api.example.com/v1", "k", "m")
    assert provider.generate("s", "u").retryable is True

    def fake_400(url, headers, payload, timeout):
        raise _http.HttpError(400, "bad request")

    monkeypatch.setattr(_http, "post_json", fake_400)
    result = provider.generate("s", "u")
    assert result.retryable is False
    assert result.error.startswith("http 400")


def test_unexpected_response_shape_is_retryable(monkeypatch):
    def fake_post_json(url, headers, payload, timeout):
        return {"unexpected": True}

    monkeypatch.setattr(_http, "post_json", fake_post_json)
    provider = OpenAICompatProvider("https://api.example.com/v1", "k", "m")

    result = provider.generate("s", "u")

    assert not result.ok
    assert result.retryable is True
    assert "shape" in result.error


# --- retry_with_repair: the D8 policy ------------------------------------


def test_transport_failures_retry_until_success():
    provider = FakeProvider(
        _result(error="http 500", retryable=True),
        _result(error="http 500", retryable=True),
        _result(text='{"atoms": []}', ok=True),
    )

    out = retry_with_repair(provider, "sys", "user", sleep=NO_SLEEP)

    assert out.ok and out.text == '{"atoms": []}'
    assert out.attempts == 3  # 1 first + 2 retries (D8)
    assert len(provider.users) == 3


def test_non_retryable_4xx_stops_immediately():
    provider = FakeProvider(_result(error="http 400", retryable=False))

    out = retry_with_repair(provider, "sys", "user", sleep=NO_SLEEP)

    assert not out.ok
    assert out.attempts == 1
    assert len(provider.users) == 1


def test_transport_failure_after_retries_is_a_failure():
    provider = FakeProvider(
        _result(error="http 500", retryable=True),
        _result(error="http 500", retryable=True),
        _result(error="http 500", retryable=True),
    )

    out = retry_with_repair(provider, "sys", "user", sleep=NO_SLEEP)

    assert not out.ok
    assert out.attempts == 3
    assert "http 500" in out.error


def test_repair_fixes_invalid_output_once():
    provider = FakeProvider(
        _result(text="not valid json {", ok=True),
        _result(text='{"atoms": []}', ok=True),
    )

    out = retry_with_repair(provider, "sys", "user", sleep=NO_SLEEP)

    assert out.ok and out.text == '{"atoms": []}'
    assert out.attempts == 2
    assert "JSON" in provider.users[1]  # repair prompt mentions the JSON error


def test_repair_that_still_fails_is_a_failure():
    provider = FakeProvider(
        _result(text="not valid json {", ok=True),
        _result(text="still not valid", ok=True),
    )

    out = retry_with_repair(provider, "sys", "user", sleep=NO_SLEEP)

    assert not out.ok
    assert out.attempts == 2
    assert "仍无效" in out.error


# --- factories (D7: one-place swap) --------------------------------------


def test_get_api_provider_builds_openai_compat_from_config():
    cfg = EnvConfig(
        llm_api_base="https://api.example.com/v1",
        llm_api_key="sk-test",
        llm_model="deepseek-chat",
        llm_timeout_s=90,
    )

    provider = get_api_provider(cfg)

    assert isinstance(provider, OpenAICompatProvider)
    assert provider.name == "openai-compat:deepseek-chat"


def test_get_local_provider_builds_ollama_from_config():
    cfg = EnvConfig(
        ollama_host="http://10.0.0.5:11434",
        ollama_model="local-model",
        ollama_timeout_s=150,
    )

    provider = get_local_provider(cfg)

    assert isinstance(provider, OllamaProvider)
    assert provider.name == "ollama:local-model"
