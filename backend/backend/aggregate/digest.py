"""Lightweight input digest for AI aggregation (S3, D12/U3).

Only *path + imports + ports* are fed to the model — never full-text excerpts.
The digest is derived entirely from a scan Graph (module ids, import edges,
port signatures), so no filesystem reads happen here. Defensive parsing keeps a
malformed/partial graph from crashing (INV9).

Budget & truncation ladder (deterministic, INV8/INV12):
  1. ``no-docstrings`` — drop every port's ``docstring``
  2. ``no-params``     — drop every port's ``params`` (keep ``signature``)
  3. ``bare-ports``    — ports reduced to ``{kind, name}``
  4. ``dropped-ports`` — drop the longest port entries until within budget

``id`` and ``imports`` are never dropped. The active level is reported so the
runner can surface it in the report (INV14).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .validate import is_noise_module

# Budgets (§5.3). Local is conservative for a ~16K context (U3); the API — the
# sole authority (D1) — gets a far larger budget so the local 8B model's window
# never limits the authoritative path (R2/F3).
TOTAL_DIGEST_CHARS = 12000
API_TOTAL_DIGEST_CHARS = 40000

# Truncation levels, in the order the ladder applies them.
TRUNCATION_NONE = "none"
TRUNCATION_NO_DOCSTRINGS = "no-docstrings"
TRUNCATION_NO_PARAMS = "no-params"
TRUNCATION_BARE_PORTS = "bare-ports"
TRUNCATION_DROPPED_PORTS = "dropped-ports"

# Edge kinds that express "this module imports something" (T16). Other kinds
# (call / annotation / inheritance / decorator) are NOT imports.
_IMPORT_KINDS = frozenset({"import", "from_import"})


@dataclass(frozen=True)
class Digest:
    """The rendered digest plus which truncation level is in effect."""

    text: str
    truncation: str


def _collect(
    graph: dict[str, Any],
) -> tuple[list[str], dict[str, list[str]], dict[str, list[dict[str, Any]]]]:
    """Extract, in graph order: kept module ids, imports per module, ports per
    module. Noise modules are dropped (the model cannot name them); import
    edges are deduped preserving order; external targets are kept (T16).
    """
    modules = graph.get("modules") or []
    ids = [
        m["id"]
        for m in modules
        if isinstance(m, dict) and isinstance(m.get("id"), str) and not is_noise_module(m["id"])
    ]
    kept = set(ids)

    imports: dict[str, list[str]] = {}
    for edge in graph.get("edges") or []:
        if not isinstance(edge, dict) or edge.get("kind") not in _IMPORT_KINDS:
            continue
        src, target = edge.get("source"), edge.get("target")
        if not isinstance(src, str) or not isinstance(target, str) or src == target:
            continue
        bucket = imports.setdefault(src, [])
        if target not in bucket:  # dedupe, preserve first-seen order
            bucket.append(target)

    ports: dict[str, list[dict[str, Any]]] = {}
    for port in graph.get("ports") or []:
        if not isinstance(port, dict):
            continue
        mid = port.get("moduleId")
        if isinstance(mid, str) and mid in kept:
            ports.setdefault(mid, []).append(port)

    return ids, imports, ports


def _port_dict(port: dict[str, Any], level: int) -> dict[str, Any]:
    """Render one port at ladder ``level`` (0=full … 3=bare)."""
    d: dict[str, Any] = {}
    for key in ("kind", "name", "signature"):
        if port.get(key):
            d[key] = port[key]
    if level < 1 and port.get("docstring"):
        d["docstring"] = port["docstring"]
    if level < 2 and port.get("params"):
        d["params"] = port["params"]
    return d


def _entry(
    module_id: str,
    imports: dict[str, list[str]],
    port_list: list[dict[str, Any]],
    level: int,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"id": module_id}
    if imports.get(module_id):
        entry["imports"] = imports[module_id]
    if port_list:
        entry["ports"] = (
            [
                {"kind": p.get("kind"), "name": p.get("name")}
                for p in port_list
                if p.get("kind") and p.get("name")
            ]
            if level >= 3
            else [_port_dict(p, level) for p in port_list]
        )
    return entry


def _serialize(repo_name: str, entries: list[dict[str, Any]]) -> str:
    return json.dumps(
        {"repo": repo_name, "modules": entries}, ensure_ascii=False, indent=2
    )


def _drop_longest_ports(
    repo_name: str,
    ids: list[str],
    imports: dict[str, list[str]],
    ports: dict[str, list[dict[str, Any]]],
    total_chars: int,
) -> str:
    """Ladder level 4: start from bare ports and drop the longest port entries
    (ranked by their *original* serialized length — the most verbose ones go
    first) until within budget. id/imports are never dropped."""
    entries = [_entry(mid, imports, ports.get(mid, []), 3) for mid in ids]
    lengths = [
        [len(json.dumps(p, ensure_ascii=False)) for p in ports.get(mid, [])] for mid in ids
    ]
    while True:
        text = _serialize(repo_name, entries)
        if len(text) <= total_chars:
            return text
        best: tuple[int, int, int] | None = None  # (length, module_idx, port_idx)
        for i, entry in enumerate(entries):
            for j, _port in enumerate(entry.get("ports", [])):
                length = lengths[i][j]
                key = (length, i, j)
                if best is None or (length > best[0]) or (length == best[0] and (i, j) < (best[1], best[2])):
                    best = key
        if best is None:
            return text  # no ports left; accept over-budget (id+imports kept)
        _length, i, j = best
        entries[i]["ports"].pop(j)
        lengths[i].pop(j)


_LEVEL_NAMES = (
    TRUNCATION_NONE,
    TRUNCATION_NO_DOCSTRINGS,
    TRUNCATION_NO_PARAMS,
    TRUNCATION_BARE_PORTS,
)


def build_digest(
    graph: dict[str, Any],
    root: str | Path | None = None,
    *,
    total_chars: int = API_TOTAL_DIGEST_CHARS,
) -> Digest:
    """Build the deterministic lightweight digest for ``graph``.

    Walks the truncation ladder until the rendered text fits ``total_chars``;
    ``Digest.truncation`` reports the level reached (``"none"`` if it already
    fits). ``root`` only contributes the repo name shown to the model.
    """
    repo_name = Path(root).name if root else "repo"
    ids, imports, ports = _collect(graph)

    for level, name in enumerate(_LEVEL_NAMES):
        entries = [_entry(mid, imports, ports.get(mid, []), level) for mid in ids]
        text = _serialize(repo_name, entries)
        if len(text) <= total_chars:
            return Digest(text=text, truncation=name)

    text = _drop_longest_ports(repo_name, ids, imports, ports, total_chars)
    return Digest(text=text, truncation=TRUNCATION_DROPPED_PORTS)
