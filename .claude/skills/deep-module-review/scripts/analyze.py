"""CLI entry point for the ``/deep-module-review`` skill.

Usage (from anywhere)::

    python .claude/skills/deep-module-review/scripts/analyze.py [repo]

``repo`` defaults to the current working directory.  Locates the ``parser``
package by walking up from this script's location, adds that repo root to
``sys.path``, scans ``repo`` (excluding tooling directories), computes metrics,
digest and the architecture SVG, and writes them under
``.claude/skills/deep-module-review/.last-review/``:

    graph.json   raw parser scan graph (5-key schema)
    metrics.json depth / edge / cycle / orphan metrics
    digest.json  model-facing module+port digest (truncation ladder)
    diagram.svg  inline-SVG architecture map

Prints a JSON mapping of the written result paths to stdout so the skill
(Claude) knows what to read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling scripts
from digest import API_TOTAL_DIGEST_CHARS, build_digest  # noqa: E402
from diagram import build_svg  # noqa: E402
from metrics import compute_metrics  # noqa: E402

# #24 design §5.3: exclude tooling/transient dirs so a self-scan has no noise.
EXCLUDE_DIRS = {
    ".git",
    ".claude",
    ".dagr",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
}

OUTPUT_DIR = Path(__file__).resolve().parent.parent / ".last-review"


def _find_repo_root(start: Path) -> Path:
    """Walk up from ``start`` to the directory that owns ``parser/``."""
    for candidate in [start, *start.parents]:
        if (candidate / "parser" / "_scanner.py").is_file():
            return candidate
    raise RuntimeError(
        "Could not locate the deep-module-mapper repo root (parser/_scanner.py) "
        "above " + str(start)
    )


def _repo_name(scan_path: Path) -> str:
    resolved = scan_path.resolve()
    return resolved.name or resolved.anchor


def run(scan_path: str | Path, repo_root: Path) -> dict[str, str]:
    """Scan ``scan_path`` and write the four review artefacts.

    ``repo_root`` (the deep-module-mapper root owning ``parser/``) must already
    be on ``sys.path``.  Returns {kind: absolute output path}.
    """
    from parser import scan_codebase

    path = Path(scan_path).resolve()
    repo_name = _repo_name(path)

    graph = scan_codebase(path, exclude_dirs=set(EXCLUDE_DIRS))

    metrics = compute_metrics(graph, repo_name)
    digest = build_digest(graph, root=path, total_chars=API_TOTAL_DIGEST_CHARS)
    svg = build_svg(metrics, repo_name=repo_name)

    digest_payload = json.loads(digest.text)
    digest_payload["meta"] = {
        "truncation": digest.truncation,
        "chars": len(digest.text),
        "budget": API_TOTAL_DIGEST_CHARS,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    written["graph"] = OUTPUT_DIR / "graph.json"
    written["metrics"] = OUTPUT_DIR / "metrics.json"
    written["digest"] = OUTPUT_DIR / "digest.json"
    written["diagram"] = OUTPUT_DIR / "diagram.svg"

    written["graph"].write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    written["metrics"].write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    written["digest"].write_text(json.dumps(digest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    written["diagram"].write_text(svg, encoding="utf-8")

    return {k: str(v) for k, v in written.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="analyze",
        description="Scan a Python codebase and emit /deep-module-review artefacts.",
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Python codebase root to review (default: current directory)",
    )
    args = parser.parse_args(argv)

    repo_root = _find_repo_root(Path(__file__).resolve().parent)
    sys.path.insert(0, str(repo_root))
    try:
        paths = run(args.repo_path, repo_root)
    except Exception as exc:  # surface a clean failure instead of a traceback
        print(f"analyze: error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(paths, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
