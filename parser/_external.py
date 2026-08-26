"""Classify import targets as local / stdlib / third-party.

D10: stdlib whitelist (``sys.stdlib_module_names``) + internal path matching.
D17: stdlib is ignored entirely — no node, no edge (Q3/F7).
"""

from __future__ import annotations

import sys
from pathlib import Path

_STDLIB = frozenset(sys.stdlib_module_names)

# D21 (F6): directories that are never scanned.
EXCLUDED_DIRS = frozenset(
    {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build"}
)


def is_stdlib(name: str) -> bool:
    return name in _STDLIB


def build_module_index(files: list[Path], root: Path) -> dict[str, str]:
    """Map dotted module name -> module id (relative path, posix separators).

    ``sample_pkg/core.py``  -> ``sample_pkg.core``
    ``sample_pkg/__init__.py`` -> ``sample_pkg``
    """
    index: dict[str, str] = {}
    for rel in files:
        posix = rel.as_posix()
        if posix.endswith("__init__.py"):
            dotted = posix[: -len("__init__.py")].rstrip("/")
        else:
            dotted = posix[: -3]
        if dotted:
            index[dotted.replace("/", ".")] = posix
    return index


def classify(name: str, index: dict[str, str]) -> tuple[str, str | None]:
    """Return ``(kind, module_id)`` where kind is local | stdlib | third_party.

    - exact module match, or longest package-prefix match -> local
    - stdlib whitelist -> stdlib (ignored, module_id None)
    - otherwise -> third_party (module_id is the import name itself)
    """
    if name in index:
        return "local", index[name]
    parts = name.split(".")
    for i in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in index:
            return "local", index[prefix]
    if is_stdlib(name):
        return "stdlib", None
    return "third_party", name
