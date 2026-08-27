"""CLI entry point: ``python -m backend.backend.aggregate <repo_path>``.

Mirrors ``parser/__main__.py`` (T9): argparse + ``--output``, ``main`` returns
an int exit code. Aggregation is pure AI: on failure the CLI prints an explicit
retry message and never falls back to the hand-maintained manifest (U1/D5/D9).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (
    EXIT_AGGREGATION_FAILED,
    EXIT_FATAL,
    EXIT_OK,
    RETRYABLE_MESSAGE,
    AggregationFailed,
    FatalError,
    run_aggregation,
)
from .config import ConfigError, load_env_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.backend.aggregate",
        description="AI-aggregate a codebase into a functional-atom manifest (issue #11).",
    )
    parser.add_argument(
        "repo_path",
        type=Path,
        help="Path to the codebase root to aggregate",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the manifest to this file (default: <repo>/frontend/src/manifest/feature-atoms.json)",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        default=None,
        help="Ground-truth manifest to compare against (default: the existing --output content)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the manifest and quality comparison; do not write any file",
    )
    parser.add_argument(
        "--skip-local",
        action="store_true",
        help="Skip the local-model learning step (no sidecar, no learn reflection)",
    )
    parser.add_argument(
        "--training-log",
        type=Path,
        default=None,
        help="Append training JSONL records (role=api/local/learn, one run_id per run)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the report JSON to this file (default: next to --output)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_env_config()
    except ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return EXIT_FATAL

    try:
        return run_aggregation(args.repo_path, config)
    except FatalError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return EXIT_FATAL
    except AggregationFailed as exc:
        print(f"AI 聚合失败：{exc}", file=sys.stderr)
        print(RETRYABLE_MESSAGE, file=sys.stderr)
        return EXIT_AGGREGATION_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
