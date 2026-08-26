"""CLI entry point: ``python -m parser <repo_path> [--output graph.json]``.

Thin wrapper over the single public API (F15); never touches private modules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import scan_codebase


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="parser", description="Scan a codebase and emit a module-dependency graph (Deep Module Mapper)."
    )
    parser.add_argument("repo_path", type=Path, help="Path to the codebase root to scan")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON to this file instead of stdout")
    args = parser.parse_args(argv)

    graph = scan_codebase(args.repo_path)
    text = json.dumps(graph, indent=2, ensure_ascii=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
