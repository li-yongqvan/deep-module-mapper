"""Tests for the aggregate CLI failure semantics (S1).

Only external behavior is tested — exit codes and stderr text — never internals
(S1 Testing Decisions). The happy path (manifest written, exit 0) lands with
S5.
"""

from __future__ import annotations

from backend.backend.aggregate import (
    EXIT_AGGREGATION_FAILED,
    EXIT_FATAL,
    RETRYABLE_MESSAGE,
)
from backend.backend.aggregate.__main__ import main


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


def test_valid_input_hits_skeleton_failure_exit_2_with_retry_message(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_API_BASE", "https://api.example.com/v1")

    assert main([str(tmp_path)]) == EXIT_AGGREGATION_FAILED
    err = capsys.readouterr().err
    assert RETRYABLE_MESSAGE in err  # U5/D13: explicit, non-silent
    assert "尚未实现" in err  # S1 skeleton marker, replaced by real flow in S5


def test_invalid_timeout_env_is_fatal_exit_1(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_TIMEOUT", "not-a-number")

    assert main([str(tmp_path)]) == EXIT_FATAL
    assert "配置错误" in capsys.readouterr().err


def test_recognized_cli_flags_parse(monkeypatch, capsys, tmp_path):
    """S1 accepts the full flag surface; they are wired to the runner in S5."""
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    code = main(
        [
            str(tmp_path),
            "--output",
            str(tmp_path / "manifest.json"),
            "--compare",
            str(tmp_path / "gt.json"),
            "--report",
            str(tmp_path / "report.json"),
            "--training-log",
            str(tmp_path / "train.jsonl"),
            "--dry-run",
            "--skip-local",
        ]
    )
    # Flags parse without argparse errors; the skeleton still fails with exit 2.
    assert code == EXIT_AGGREGATION_FAILED
