"""Golden tests: the v2 ``intra`` extension must not change the 5 existing keys.

#24 design §14 contract-sync item 4 / §16.2 / §17.1.  Baselines were captured
by ``capture_golden.py`` *before* the extension touched the parser and pin the
scanned content (sample_pkg fixture directly; the whole repo via a pinned
commit extracted with ``git archive``).  Both tests re-scan that content with
the *current* parser and require the serialized 5 keys to be byte-identical --
"pure additive pass" stops being a claim and becomes an assertion.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest

from parser import scan_codebase

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIVE_KEYS = ["modules", "ports", "edges", "externalModules", "diagnostics"]


def _serialize(graph: dict) -> str:
    """Must match capture_golden.py exactly (json.dumps default key order)."""
    return json.dumps(graph, ensure_ascii=False, indent=2)


def _five(graph: dict) -> dict:
    return {k: graph[k] for k in FIVE_KEYS}


def _load_golden(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def test_golden_sample_pkg_five_keys_byte_identical():
    golden = _load_golden("sample_pkg_5keys.json")
    graph = scan_codebase(FIXTURES / "sample_pkg")
    assert _serialize(_five(graph)) == _serialize(golden["graph"])


def test_golden_repo_pin_five_keys_byte_identical():
    golden = next(
        (GOLDEN_DIR / name for name in sorted(GOLDEN_DIR.iterdir())
         if name.name.startswith("repo_at_")),
        None,
    )
    assert golden is not None, "repo golden fixture missing -- run capture_golden.py"
    meta = json.loads(golden.read_text(encoding="utf-8"))
    sha = meta["commit"]

    git = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--verify", sha],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if git.returncode != 0:
        pytest.skip(f"pinned commit {sha[:12]} not available in this clone")
    archive = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "archive", "--format=zip", sha],
        capture_output=True,
    )
    if archive.returncode != 0:
        pytest.skip("git archive unavailable")

    with tempfile.TemporaryDirectory(prefix="dmm-golden-") as tmp:
        with zipfile.ZipFile(__import__("io").BytesIO(archive.stdout)) as zf:
            zf.extractall(tmp)
        graph = scan_codebase(Path(tmp))

    assert _serialize(_five(graph)) == _serialize(meta["graph"])
