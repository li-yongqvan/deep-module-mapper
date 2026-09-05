"""Capture golden 5-key scan baselines BEFORE the v2 ``intra`` extension.

#24 design §14 contract-sync item 4: the "existing 5 keys keep their content"
claim becomes a verifiable assertion via these fixtures.  Run this script
*before* touching the parser; ``parser/tests/test_golden.py`` then re-scans the
same pinned content with the current parser and requires byte-identical output.

Two baselines:

- ``sample_pkg_5keys.json``   the committed test fixture, scanned directly.
- ``repo_at_<sha>_5keys.json`` this repository pinned at a commit.  Content is
  extracted via ``git archive`` so the baseline never drifts when the repo
  evolves; the golden test re-extracts the same commit.

Both files store ``{"graph": <5 keys>}`` plus capture metadata.  Serialization
is ``json.dumps(graph, ensure_ascii=False, indent=2)`` -- the golden tests
compare that exact text.

Usage::

    python parser/tests/golden/capture_golden.py [--commit HEAD]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = Path(__file__).resolve().parent
FIVE_KEYS = ["modules", "ports", "edges", "externalModules", "diagnostics"]


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _five_keys(graph: dict) -> dict:
    missing = [k for k in FIVE_KEYS if k not in graph]
    if missing:
        raise RuntimeError(f"scan output missing keys: {missing}")
    return {k: graph[k] for k in FIVE_KEYS}


def _serialize(graph: dict) -> str:
    return json.dumps(graph, ensure_ascii=False, indent=2)


def capture_sample_pkg() -> dict:
    from parser import scan_codebase

    fixture = REPO_ROOT / "parser" / "tests" / "fixtures" / "sample_pkg"
    graph = scan_codebase(fixture)
    return {
        "target": "parser/tests/fixtures/sample_pkg",
        "commit": _git("rev-parse", "HEAD"),
        "exclude_dirs": None,
        "graph": _five_keys(graph),
    }


def capture_repo(commit: str) -> dict:
    from parser import scan_codebase

    sha = _git("rev-parse", commit)
    with tempfile.TemporaryDirectory(prefix="dmm-golden-") as tmp:
        archive = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "archive", "--format=zip", sha],
            capture_output=True,
        )
        if archive.returncode != 0:
            raise RuntimeError(f"git archive failed: {archive.stderr.decode(errors='replace')}")
        with zipfile.ZipFile(io_bytes(archive.stdout)) as zf:
            zf.extractall(tmp)
        graph = scan_codebase(Path(tmp))
    return {
        "target": f"repo tree pinned at {sha[:12]}",
        "commit": sha,
        "exclude_dirs": None,
        "graph": _five_keys(graph),
    }


def io_bytes(data: bytes):
    import io

    return io.BytesIO(data)


def main(argv: list[str] | None = None) -> int:
    commit = "HEAD"
    if argv:
        commit = argv[0]
    sys.path.insert(0, str(REPO_ROOT))

    sample = capture_sample_pkg()
    (GOLDEN_DIR / "sample_pkg_5keys.json").write_text(
        _serialize(sample) + "\n", encoding="utf-8"
    )
    print(f"golden: sample_pkg  modules={len(sample['graph']['modules'])} "
          f"edges={len(sample['graph']['edges'])}")

    repo = capture_repo(commit)
    (GOLDEN_DIR / f"repo_at_{repo['commit'][:12]}_5keys.json").write_text(
        _serialize(repo) + "\n", encoding="utf-8"
    )
    print(f"golden: repo @{repo['commit'][:12]}  "
          f"modules={len(repo['graph']['modules'])} edges={len(repo['graph']['edges'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
