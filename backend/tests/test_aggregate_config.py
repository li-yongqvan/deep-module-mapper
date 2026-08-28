"""Tests for aggregate.config — env-only configuration (S1)."""

from __future__ import annotations

import pytest

from backend.backend.aggregate.config import (
    DEFAULT_LLM_API_BASE,
    DEFAULT_LLM_MODEL,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    ConfigError,
    EnvConfig,
    load_env_config,
)


def test_empty_env_yields_defaults_and_no_api_key():
    cfg = load_env_config({})
    assert cfg.llm_api_base == DEFAULT_LLM_API_BASE
    assert cfg.llm_model == DEFAULT_LLM_MODEL
    assert cfg.ollama_host == DEFAULT_OLLAMA_HOST
    assert cfg.ollama_model == DEFAULT_OLLAMA_MODEL
    assert cfg.llm_timeout_s == 60
    assert cfg.ollama_timeout_s == 300
    assert cfg.llm_api_key is None
    assert cfg.has_api_key is False  # INV11: missing key is detectable


def test_env_overrides():
    cfg = load_env_config(
        {
            "LLM_API_BASE": "https://api.example.com/v1",
            "LLM_API_KEY": "sk-test",
            "LLM_MODEL": "my-cloud-model",
            "OLLAMA_HOST": "http://10.0.0.5:11434",
            "OLLAMA_MODEL": "local-model",
            "LLM_TIMEOUT": "90",
            "OLLAMA_TIMEOUT": "150",
        }
    )
    assert cfg.llm_api_base == "https://api.example.com/v1"
    assert cfg.llm_api_key == "sk-test"
    assert cfg.has_api_key is True
    assert cfg.llm_model == "my-cloud-model"
    assert cfg.ollama_host == "http://10.0.0.5:11434"
    assert cfg.ollama_model == "local-model"
    assert cfg.llm_timeout_s == 90
    assert cfg.ollama_timeout_s == 150


def test_blank_values_fall_back_to_defaults():
    cfg = load_env_config(
        {
            "LLM_API_BASE": "   ",
            "LLM_MODEL": "",
            "OLLAMA_HOST": "",
            "LLM_API_KEY": "",
        }
    )
    assert cfg.llm_api_base == DEFAULT_LLM_API_BASE
    assert cfg.llm_model == DEFAULT_LLM_MODEL
    assert cfg.ollama_host == DEFAULT_OLLAMA_HOST
    assert cfg.llm_api_key is None


def test_non_integer_timeout_is_a_config_error():
    with pytest.raises(ConfigError):
        load_env_config({"LLM_TIMEOUT": "not-a-number"})
