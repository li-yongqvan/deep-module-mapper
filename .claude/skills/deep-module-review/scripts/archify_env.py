"""Archify dependency probing and the UTF-8 subprocess wrapper.

#24 v2 design §15 (V2-D10 / review F5): archify is an optional external
enhancement invoked as a *process*, never an import.  Detection order:

1. ``ARCHIFY_DIR`` environment variable (if set and non-empty)
2. ``~/.claude/skills/archify``
3. AND ``node --version`` must run -- a directory without a node runtime is a
   *degraded* environment, not a working one (no "probe ok -> child fails"
   undefined path).

Any miss means "archify mode off" -> the skill falls back to the v1 four
artefacts; degradation is a normal outcome (exit code 0), not an error.

Every node invocation in the skill goes through :func:`run_node`, which pins
``encoding="utf-8", errors="replace"`` -- Windows GBK consoles otherwise
mangle archify's Chinese output (#24 §13.2 lesson, unit-test pinned).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ARCHIFY_ENTRY = "bin/archify.mjs"


def default_archify_dir(home: Path | None = None) -> Path:
    home = home or Path.home()
    return home / ".claude" / "skills" / "archify"


def run_node(args: list[str], *, cwd: Path | None = None, timeout: float = 120) -> subprocess.CompletedProcess:
    """Run node with the GBK-safe encoding pinned (§13.2, review F8)."""
    return subprocess.run(
        ["node", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd else None,
        timeout=timeout,
    )


def probe(
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    """Return ``{"available": bool, "dir": str|None, "node": bool, "reason": str|None}``.

    Injectable ``env``/``home`` keep this unit-testable without touching the
    real machine state.
    """
    env = os.environ if env is None else env
    override = (env.get("ARCHIFY_DIR") or "").strip()
    archify_dir = Path(override) if override else default_archify_dir(home)

    if not (archify_dir / ARCHIFY_ENTRY).is_file():
        return {
            "available": False,
            "dir": str(archify_dir),
            "node": False,
            "reason": f"archify not found at {archify_dir} ({ARCHIFY_ENTRY} missing)"
                      + (" (ARCHIFY_DIR)" if override else ""),
        }

    try:
        version = run_node(["--version"], timeout=15)
        node_ok = version.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        node_ok = False
    if not node_ok:
        return {
            "available": False,
            "dir": str(archify_dir),
            "node": False,
            "reason": "node runtime not usable (`node --version` failed); "
                      "archify directory exists but cannot render",
        }

    return {"available": True, "dir": str(archify_dir), "node": True, "reason": None}


def run_archify(
    archify_dir: Path,
    subcommand: str,
    *args: str,
    quality: str | None = None,
    timeout: float = 120,
) -> dict[str, Any]:
    """``node archify.mjs <sub> <args...> [--quality q] --json`` -> parsed JSON.

    Returns ``{"ok": False, "raw": ..., "err": ...}`` instead of raising when
    the child prints anything unparsable, so callers always get a dict.
    """
    cmd = [str(archify_dir / ARCHIFY_ENTRY), subcommand, *args]
    if quality:
        cmd += ["--quality", quality]
    cmd.append("--json")
    result = run_node(cmd, cwd=archify_dir, timeout=timeout)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "raw": result.stdout[-500:],
            "err": result.stderr[-500:],
        }
