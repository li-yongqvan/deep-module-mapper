"""Make skill scripts importable when pytest runs this tests dir.

Repo layout: <root>/.claude/skills/deep-module-review/{scripts,tests}/.
``python -m pytest <this dir>`` from anywhere therefore needs both the skill's
``scripts/`` and the repo root (for ``parser``) on ``sys.path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
REPO_ROOT = SKILL_DIR.parents[2]  # deep-module-review -> skills -> .claude -> repo root

for _p in (SKILL_DIR / "scripts", REPO_ROOT):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT
