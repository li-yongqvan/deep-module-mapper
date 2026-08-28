"""Tests for the aggregate CLI (S1 failure semantics, S5 real flow).

S5 wires the full pipeline, so ``main`` needs a fake API provider injected via
``runner.get_api_provider`` (the one-place swap, D7). Only external behavior is
asserted — exit codes, stderr text, files written.
"""

from __future__ import annotations

import json

from backend.backend.aggregate import (
    EXIT_AGGREGATION_FAILED,
    EXIT_FATAL,
    EXIT_OK,
    RETRYABLE_MESSAGE,
)
from backend.backend.aggregate import runner
from backend.backend.aggregate.__main__ import main
from backend.backend.aggregate.providers import ProviderResult

VALID_MANIFEST = json.dumps(
    {
        "atoms": [
            {"id": "core", "name": "核心", "description": "核心功能", "files": ["alpha.py", "beta.py"]}
        ]
    },
    ensure_ascii=False,
)


class FakeProvider:
    name = "fake"

    def __init__(self, result: ProviderResult) -> None:
        self.result = result

    def generate(self, system, user, *, temperature=0.1) -> ProviderResult:
        return self.result


def _write_repo(tmp_path) -> None:
    (tmp_path / "alpha.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("from alpha import f\n", encoding="utf-8")


def _install_fake_api(monkeypatch, result: ProviderResult) -> None:
    monkeypatch.setattr(runner, "get_api_provider", lambda config: FakeProvider(result))


def test_missing_api_key_is_fatal_exit_1(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_BASE", "https://api.example.com/v1")

    assert main([str(tmp_path)]) == EXIT_FATAL
    err = capsys.readouterr().err
    assert "LLM_API_KEY" in err  # INV11: surfaced, never silently skipped
    assert "AI 聚合失败，可重试" not in err  # exit 1 is fatal, not retryable


def test_bad_repo_path_is_fatal_exit_1(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    missing = str(tmp_path / "does-not-exist")

    assert main([missing]) == EXIT_FATAL
    assert "仓库路径不存在" in capsys.readouterr().err


def test_valid_input_with_successful_api_writes_manifest_exit_0(
    monkeypatch, capsys, tmp_path
):
    _write_repo(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    _install_fake_api(monkeypatch, ProviderResult(text=VALID_MANIFEST, ok=True))
    out = tmp_path / "out.json"

    assert main([str(tmp_path), "--output", str(out), "--skip-local"]) == EXIT_OK
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(VALID_MANIFEST)
    assert "已写入" in capsys.readouterr().out


def test_api_failure_exit_2_with_retry_message_and_no_manifest(monkeypatch, capsys, tmp_path):
    _write_repo(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    _install_fake_api(
        monkeypatch, ProviderResult(text=None, ok=False, error="http 400: bad request", retryable=False)
    )
    out = tmp_path / "out.json"

    assert main([str(tmp_path), "--output", str(out)]) == EXIT_AGGREGATION_FAILED
    err = capsys.readouterr().err
    assert RETRYABLE_MESSAGE in err  # U5/D13: explicit, non-silent
    assert not out.exists()  # INV5: no manifest written on AI failure


def test_invalid_timeout_env_is_fatal_exit_1(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_TIMEOUT", "not-a-number")

    assert main([str(tmp_path)]) == EXIT_FATAL
    assert "配置错误" in capsys.readouterr().err


def test_recognized_cli_flags_parse(monkeypatch, capsys, tmp_path):
    """All flags are wired to the runner; dry-run writes nothing."""
    _write_repo(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    _install_fake_api(monkeypatch, ProviderResult(text=VALID_MANIFEST, ok=True))

    code = main(
        [
            str(tmp_path),
            "--output",
            str(tmp_path / "m.json"),
            "--compare",
            str(tmp_path / "gt.json"),
            "--report",
            str(tmp_path / "r.json"),
            "--training-log",
            str(tmp_path / "train.jsonl"),
            "--dry-run",
            "--skip-local",
        ]
    )
    assert code == EXIT_OK
    assert not (tmp_path / "m.json").exists()  # dry-run: no writes
