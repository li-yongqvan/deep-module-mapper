"""Module-level metrics for the ``/deep-module-review`` skill.

Reuses the semantics of the three frontend TS modules that were deleted in the
#24 migration (see wayfinder/design-doc-deep-module-review-skill.md §5.3):

- ``depthScore.ts``  -> ``depth_score`` + ``score_color``  (DEEP>=50, MODERATE>=15)
- ``aggregateEdges.ts`` -> review edges grouped by (source, target)
- ``recompose/detect.ts`` -> SCC cycle detection + orphan three-way classification

Scope decision (user, 2026-09-03): metrics *and* diagram cover only production
modules -- ``/tests/`` & ``/fixtures/`` files and ``__init__.py`` facades are
excluded from nodes (matching backend ``is_production_module``).  ``digest.py``
keeps its own noise filter for the model-facing text.

Pure functions, no third-party dependencies (invariant: zero-dep skill).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

# --- depth scoring (frontend/src/lib/depthScore.ts:22-24) ---------------------
DEPTH_THRESHOLD_DEEP = 50
DEPTH_THRESHOLD_MODERATE = 15
DEPTH_LEVELS = ("deep", "moderate", "shallow")


def depth_score(ports: list[dict[str, Any]]) -> tuple[str, float | None]:
    """Return (level, ratio) for a module's public ports.

    ratio = max(port.line) / portCount   (portCount > 0)
    Zero-port modules are ``shallow`` with ratio None (TS parity).
    """
    if not ports:
        return "shallow", None
    max_line = max(p["line"] for p in ports if p.get("line"))
    ratio = max_line / len(ports)
    if ratio >= DEPTH_THRESHOLD_DEEP:
        return "deep", ratio
    if ratio >= DEPTH_THRESHOLD_MODERATE:
        return "moderate", ratio
    return "shallow", ratio


def score_color(level: str) -> str:
    """Traffic-light color token for a depth level (depthScore.ts scoreColor)."""
    return {"deep": "#34d399", "moderate": "#fbbf24", "shallow": "#f87171"}[level]


# --- module classification (backend validate.py predicates) -------------------
# A scanned module id is a repo-root-relative posix path, so a top-level test
# dir yields ids like ``tests/x.py`` (no leading ``/``).  Matching on path
# segments ``tests`` / ``fixtures`` at any depth supersedes the backend's
# substring markers (which only fired on nested dirs) so both ``tests/x.py``
# and ``pkg/tests/x.py`` are dropped.  ``__init__.py`` is handled separately.
_NOISE_SEGMENTS = frozenset({"tests", "fixtures"})


def is_noise_module(module_id: str) -> bool:
    return bool(_NOISE_SEGMENTS.intersection(PurePosixPath(module_id).parts))


def is_init_module(module_id: str) -> bool:
    return module_id.endswith("__init__.py")


def is_production_module(module_id: str) -> bool:
    """The set the review (metrics + diagram) covers exactly."""
    return not is_noise_module(module_id) and not is_init_module(module_id)


# --- SCC (Kosaraju, iterative DFS) --------------------------------------------
def _dfs_order(adj: dict[str, list[str]], root: str, seen: set[str], out: list[str]) -> None:
    """Iterative post-order DFS from ``root``; appends vertices to ``out``."""
    stack: list[tuple[str, bool]] = [(root, False)]
    while stack:
        v, done = stack.pop()
        if done:
            out.append(v)
            continue
        if v in seen:
            continue
        seen.add(v)
        stack.append((v, True))
        for w in adj.get(v, []):
            if w not in seen:
                stack.append((w, False))


def strongly_connected_components(adj: dict[str, list[str]]) -> list[list[str]]:
    """Return SCCs of the directed graph ``adj`` (Kosaraju, deterministic).

    A full DFS on the reverse graph yields exactly the same SCC partition as
    the Tarjan used by the old ``recompose/detect.ts``; members are sorted for
    stable output. Iterative so deep module chains never hit the recursion cap.
    """
    seen: set[str] = set()
    order: list[str] = []
    for v in sorted(adj):
        if v not in seen:
            _dfs_order(adj, v, seen, order)

    rev: dict[str, list[str]] = {v: [] for v in adj}
    for v, targets in adj.items():
        for w in targets:
            rev.setdefault(w, []).append(v)

    comps: list[list[str]] = []
    seen2: set[str] = set()
    for v in reversed(order):
        if v in seen2:
            continue
        comp: list[str] = []
        stack = [v]
        seen2.add(v)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for w in rev.get(cur, []):
                if w not in seen2:
                    seen2.add(w)
                    stack.append(w)
        comps.append(sorted(comp))
    return comps


# --- review graph construction ------------------------------------------------
def _init_reexports(graph: dict[str, Any]) -> dict[tuple[str, str], set[str]]:
    """Map (init_id, symbol) -> {producer module ids} for ``__init__`` re-exports.

    A backing edge is ``__init__.py -> producer.py`` with a resolved targetPort
    (``from .producer import Sym``).  Consumers that import a symbol through the
    facade (``from pkg import Sym``) are re-pointed at the producer.
    """
    reexport: dict[tuple[str, str], set[str]] = {}
    for e in graph.get("edges") or []:
        src = e.get("source")
        tgt = e.get("target")
        sym = e.get("targetPort")
        if is_init_module(str(src)) and isinstance(sym, str) and isinstance(tgt, str):
            reexport.setdefault((src, sym), set()).add(tgt)
    return reexport


def build_review_edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Production-to-production edges, resolving ``__init__`` facade targets.

    Input: every ``graph.edges`` whose source is a production module.  Targets
    that are production modules are kept as-is; targets that are ``__init__.py``
    facades are re-pointed at their single re-export producer (unambiguous
    facades only -- otherwise the edge is dropped).  Test/fixture targets and
    third-party targets never become review edges (third-party usage is
    reported separately per module).

    Returns a list of aggregated dicts::
        {source, target, kinds: [...], weight: n, viaFacade: "x/__init__.py" | None}
    """
    reexport = _init_reexports(graph)
    prod_ids = {m["id"] for m in graph["modules"] if is_production_module(m["id"])}

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for e in graph.get("edges") or []:
        src = e.get("source")
        tgt = e.get("target")
        sym = e.get("targetPort")
        if not isinstance(src, str) or not isinstance(tgt, str):
            continue
        if src not in prod_ids:  # edges from tests / __init__ / fixtures are out of scope
            continue
        via_facade: str | None = None
        if tgt in prod_ids:
            resolved = tgt
        elif is_init_module(tgt) and isinstance(sym, str):
            producers = reexport.get((tgt, sym), set()) & prod_ids
            if len(producers) != 1:  # ambiguous / unresolvable facade import
                continue
            resolved = next(iter(producers))
            via_facade = tgt
        else:
            continue  # noise target or third-party (handled via external deps)

        key = (src, resolved)
        agg = by_key.setdefault(
            key,
            {
                "source": src,
                "target": resolved,
                "kinds": set(),
                "weight": 0,
                "viaFacade": None,
            },
        )
        agg["kinds"].add(e.get("kind", "import"))
        agg["weight"] += 1
        if via_facade:
            agg["viaFacade"] = via_facade

    out = []
    for (src, tgt), agg in sorted(by_key.items()):
        out.append(
            {
                "source": src,
                "target": tgt,
                "kinds": sorted(agg["kinds"]),
                "weight": agg["weight"],
                "viaFacade": agg["viaFacade"],
            }
        )
    return out


def _external_deps(graph: dict[str, Any]) -> dict[str, list[str]]:
    """Distinct third-party targets per production module.

    An external dep is an edge whose target is not any scanned module file
    (i.e. not internal and not an ``__init__`` facade -- stdlib is ignored by
    the parser, so this is third-party/unresolved top-level names).
    """
    module_files = {m["id"] for m in graph["modules"]}
    deps: dict[str, set[str]] = {}
    for e in graph.get("edges") or []:
        src, tgt = e.get("source"), e.get("target")
        if isinstance(src, str) and isinstance(tgt, str) and src in module_files:
            if tgt not in module_files:
                deps.setdefault(src, set()).add(tgt)
    return {k: sorted(v) for k, v in deps.items()}


# --- orchestration -------------------------------------------------------------
def compute_metrics(graph: dict[str, Any], repo_name: str) -> dict[str, Any]:
    """Build the full ``metrics.json`` payload for one scan Graph."""
    modules = [
        m for m in graph.get("modules") or [] if is_production_module(str(m.get("id")))
    ]
    modules.sort(key=lambda m: str(m["id"]))
    module_ids = [m["id"] for m in modules]
    external_deps = _external_deps(graph)
    review_edges = build_review_edges(graph)

    # adjacency over aggregated review edges (every production module present)
    adj: dict[str, list[str]] = {mid: [] for mid in module_ids}
    has_module_edge: set[str] = set()
    for re in review_edges:
        adj[re["source"]].append(re["target"])
        has_module_edge.add(re["source"])
        has_module_edge.add(re["target"])

    # facade-exported: producers reachable from an __init__ re-export edge
    # (public API of a package) -- "used" even with no production importer.
    reexport = _init_reexports(graph)
    facade_exported = {t for (_init, _sym), producers in reexport.items() for t in producers}

    sccs = strongly_connected_components(adj)
    cycles: list[dict[str, Any]] = []
    in_cycle: set[str] = set()
    for scc in sccs:
        if len(scc) >= 2:
            members = set(scc)
            in_cycle |= members
            cyc_edges = [
                {
                    "source": re["source"],
                    "target": re["target"],
                    "kinds": re["kinds"],
                }
                for re in review_edges
                if re["source"] in members and re["target"] in members
            ]
            cycles.append({"modules": scc, "edges": cyc_edges})

    # per-module metrics
    by_depth: dict[str, list[str]] = {lv: [] for lv in DEPTH_LEVELS}
    isolated: list[dict[str, str]] = []
    third_party_only: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    for m in modules:
        mid = m["id"]
        ports = m.get("ports") or []
        level, ratio = depth_score(ports)
        by_depth[level].append(mid)
        fan_in = sum(1 for re in review_edges if re["target"] == mid)
        fan_out = sum(1 for re in review_edges if re["source"] == mid)
        ext = external_deps.get(mid, [])
        finding: str | None = None
        if mid in in_cycle:
            finding = "cycle/scc"
        elif mid in has_module_edge:
            finding = None
        elif mid in facade_exported:
            finding = None
        elif ext:
            finding = "orphan/third-party-only"
        else:
            finding = "orphan/isolated"
        row = {
            "id": mid,
            "depthScore": level,
            "ratio": round(ratio, 1) if ratio is not None else None,
            "ports": len(ports),
            "maxLine": max((p.get("line") or 0) for p in ports) if ports else None,
            "fanIn": fan_in,
            "fanOut": fan_out,
            "externalDeps": ext,
            "viaFacade": mid in facade_exported,
            "finding": finding,
        }
        rows.append(row)
        if finding == "orphan/isolated":
            isolated.append({"id": mid, "depthScore": level})
        elif finding == "orphan/third-party-only":
            third_party_only.append({"id": mid, "depthScore": level})

    summary = {
        "modules": len(module_ids),
        "reviewEdges": len(review_edges),
        "cycles": len(cycles),
        "cycleModules": len(in_cycle),
        "isolated": len(isolated),
        "thirdPartyOnly": len(third_party_only),
        "depthDistribution": {lv: len(by_depth[lv]) for lv in DEPTH_LEVELS},
        "thirdPartyModules": len({t for dep in external_deps.values() for t in dep}),
    }
    skipped = {
        "tests": sum(1 for m in graph.get("modules") or [] if is_noise_module(m.get("id", ""))),
        "init": sum(1 for m in graph.get("modules") or [] if is_init_module(m.get("id", ""))),
    }
    return {
        "repo": repo_name,
        "scannedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": {
            "productionModulesOnly": True,
            "excluded": "tests/, fixtures/, __init__.py facades",
            "skipped": skipped,
        },
        "thresholds": {
            "DEEP": DEPTH_THRESHOLD_DEEP,
            "MODERATE": DEPTH_THRESHOLD_MODERATE,
            "formula": "ratio = max(port.line) / portCount",
        },
        "summary": summary,
        "modules": rows,
        "aggregatedEdges": review_edges,
        "cycles": cycles,
        "orphans": {"isolated": isolated, "thirdPartyOnly": third_party_only},
    }


def to_json_file(payload: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
