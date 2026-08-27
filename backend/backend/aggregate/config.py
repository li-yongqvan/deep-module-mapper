"""Environment-based configuration for the AI aggregation CLI.

All configuration flows through environment variables (backend convention,
mirroring ``BACKEND_CORS_ORIGINS``). No config files, no CLI flags for values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Defaults (§5.8 of design-doc-issue-11-ai-aggregation.md). DeepSeek is the
# sole authority for aggregation (D1); Ollama is the learning role only (D5).
DEFAULT_LLM_API_BASE = "https://api.deepseek.com/v1"
DEFAULT_LLM_MODEL = "deepseek-chat"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "my-assistant"
DEFAULT_LLM_TIMEOUT_S = 60
DEFAULT_OLLAMA_TIMEOUT_S = 120


class ConfigError(Exception):
    """Raised when the environment is missing required configuration."""


@dataclass(frozen=True)
class EnvConfig:
    """Resolved configuration for one aggregation run (env-only)."""

    llm_api_base: str = DEFAULT_LLM_API_BASE
    llm_api_key: str | None = None
    llm_model: str = DEFAULT_LLM_MODEL
    llm_timeout_s: int = DEFAULT_LLM_TIMEOUT_S
    ollama_host: str = DEFAULT_OLLAMA_HOST
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_timeout_s: int = DEFAULT_OLLAMA_TIMEOUT_S

    @property
    def has_api_key(self) -> bool:
        """Whether the API key is present (missing key is fatal, INV11)."""
        return bool(self.llm_api_key)


def _env_int(environ: dict[str, str], name: str, default: int) -> int:
    raw = environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:  # non-numeric timeout is a config error
        raise ConfigError(f"环境变量 {name} 不是有效整数: {raw!r}") from exc


def load_env_config(environ: dict[str, str] | None = None) -> EnvConfig:
    """Build an :class:`EnvConfig` from ``os.environ`` (injectable for tests).

    ``LLM_API_KEY`` has no default: a missing key must be surfaced as a
    config error (exit 1), never silently skipped (D9/U1, INV11).
    """
    env = os.environ if environ is None else environ
    return EnvConfig(
        llm_api_base=env.get("LLM_API_BASE", DEFAULT_LLM_API_BASE).strip()
        or DEFAULT_LLM_API_BASE,
        llm_api_key=env.get("LLM_API_KEY") or None,
        llm_model=env.get("LLM_MODEL", DEFAULT_LLM_MODEL).strip()
        or DEFAULT_LLM_MODEL,
        llm_timeout_s=_env_int(env, "LLM_TIMEOUT", DEFAULT_LLM_TIMEOUT_S),
        ollama_host=env.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST).strip()
        or DEFAULT_OLLAMA_HOST,
        ollama_model=env.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()
        or DEFAULT_OLLAMA_MODEL,
        ollama_timeout_s=_env_int(env, "OLLAMA_TIMEOUT", DEFAULT_OLLAMA_TIMEOUT_S),
    )
