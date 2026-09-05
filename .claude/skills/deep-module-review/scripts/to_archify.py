"""graph.json + metrics.json -> Archify architecture IR (#24 v2 design §15).

Deterministic pipeline:

1. **id mapping** -- module ids (``parser/_edges.py``) violate archify's id
   pattern, so every path segment is joined with ``__`` and stripped of leading
   underscores (``parser__edges``).  The mapping is asserted collision-free;
   a collision is a hard error, never a silent mislink (review F3).
2. **layout** -- deterministic baseline first (modules ordered by directory
   then id, tiled onto a grid).  An in-process geometric check (component
   overlap with archify's 8px minimum gap, straight-line edge crossings,
   region-frame overlaps) decides whether the fixed-seed hill-climb search
   runs; the search never spawns node subprocesses -- only the *final* layout
   is confirmed by one ``archify validate`` (review F4).
3. **cache** -- the solved layout is written to ``.last-review/layout.json``
   and reused verbatim while the production-module set is unchanged, so two
   runs over the same repo produce the same picture (review F4).

CLI::

    python to_archify.py [--last-review DIR]

Reads ``graph.json`` + ``metrics.json`` from the last-review dir; writes
``architecture.json`` + ``idmap.json`` + ``layout.json``; prints a JSON
summary (including the quality profile that passed validation).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

import archify_env

# Grid geometry: values proven by the accepted v2 prototype (%TEMP%\dmm_v2_demo).
CELL_W = 190.0
CELL_H = 120.0
GAP_X = 110.0
GAP_Y = 100.0
MIN_GAP = 8.0  # archify's component overlap minimum gap (geometry.mjs minGap)

DEPTH_ZH = {"deep": "深", "moderate": "中", "shallow": "浅"}
FANOUT_TAG_THRESHOLD = 5  # prototype rule: fanOut >= 5 -> 扇出偏高 tag

SEED = 42
RESTARTS = 150
MAX_ROUNDS = 40


# --- id mapping (review F3) ---------------------------------------------------

def map_module_id(module_id: str) -> str:
    """``parser/_edges.py`` -> ``parser__edges``.

    Directory segments and the file stem are joined with ``__``; each segment
    is stripped of leading underscores to satisfy archify's
    ``^[a-zA-Z][a-zA-Z0-9_-]*$`` id pattern.  The result is deterministic; the
    caller must run :func:`assert_no_collisions` on the full set.
    """
    parts = module_id.split("/")
    parts[-1] = parts[-1][: -3] if parts[-1].endswith(".py") else parts[-1]
    mapped = "__".join(seg.lstrip("_") for seg in parts)
    if not mapped or not mapped[0].isalpha():
        raise ValueError(f"module id {module_id!r} maps to invalid archify id {mapped!r}")
    return mapped


def assert_no_collisions(mapping: dict[str, str]) -> None:
    """Two modules mapping to one id would mislink panels silently -- die loudly."""
    seen: dict[str, str] = {}
    for module_id, short in mapping.items():
        if short in seen:
            raise ValueError(
                f"archify id collision: {seen[short]!r} and {module_id!r} both map "
                f"to {short!r}; rename one file"
            )
        seen[short] = module_id


# --- in-process geometry (review F4) -------------------------------------------

def _rects_overlap(a: tuple[float, float, float, float],
                   b: tuple[float, float, float, float],
                   min_gap: float = MIN_GAP) -> bool:
    """True when rects ``(x, y, w, h)`` are closer than ``min_gap`` (archify rule)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (
        ax + aw + min_gap <= bx or bx + bw + min_gap <= ax
        or ay + ah + min_gap <= by or by + bh + min_gap <= ay
    )


def _seg_intersect(p1, p2, p3, p4) -> bool:
    """Proper (or touching) segment intersection between p1-p2 and p3-p4."""

    def orient(a, b, c) -> int:
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)

    def on_seg(a, b, c) -> bool:
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])

    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    if d1 != d2 and d3 != d4:
        return True
    if d1 == 0 and on_seg(p3, p4, p1):
        return True
    if d2 == 0 and on_seg(p3, p4, p2):
        return True
    if d3 == 0 and on_seg(p1, p2, p3):
        return True
    if d4 == 0 and on_seg(p1, p2, p4):
        return True
    return False


def _cell_rect(col: int, row: int) -> tuple[float, float, float, float]:
    return (col * (CELL_W + GAP_X), row * (CELL_H + GAP_Y), CELL_W, CELL_H)


def count_crossings(pos: dict[str, tuple[int, int]], edges: list[tuple[str, str]]) -> int:
    """Straight-line crossings between edge segments (shared endpoints excluded)."""
    segs: list[tuple[tuple[float, float], tuple[float, float], tuple[str, str]]] = []
    for src, tgt in edges:
        if src == tgt or src not in pos or tgt not in pos:
            continue
        sc, sr = pos[src]
        tc, tr = pos[tgt]
        segs.append((
            (sc * (CELL_W + GAP_X) + CELL_W / 2, sr * (CELL_H + GAP_Y) + CELL_H / 2),
            (tc * (CELL_W + GAP_X) + CELL_W / 2, tr * (CELL_H + GAP_Y) + CELL_H / 2),
            (src, tgt),
        ))
    crossings = 0
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            (a1, a2, ea), (b1, b2, eb) = segs[i], segs[j]
            if ea[0] in eb or ea[1] in eb:
                continue  # shared endpoint: adjacency, not a crossing
            if _seg_intersect(a1, a2, b1, b2):
                crossings += 1
    return crossings


def total_edge_length(pos: dict[str, tuple[int, int]], edges: list[tuple[str, str]]) -> float:
    total = 0.0
    for src, tgt in edges:
        if src == tgt or src not in pos or tgt not in pos:
            continue
        sc, sr = pos[src]
        tc, tr = pos[tgt]
        total += math.hypot((sc - tc) * (CELL_W + GAP_X), (sr - tr) * (CELL_H + GAP_Y))
    return total


def region_overlaps(groups: dict[str, list[str]], pos: dict[str, tuple[int, int]]) -> int:
    """Distinct region frames must not interleave on the grid (archify boundary rule)."""
    frames: list[tuple[float, float, float, float]] = []
    pad = 30.0
    for members in groups.values():
        cols = [pos[m][0] for m in members if m in pos]
        rows = [pos[m][1] for m in members if m in pos]
        if not cols:
            continue
        x0 = min(cols) * (CELL_W + GAP_X) - pad
        y0 = min(rows) * (CELL_H + GAP_Y) - pad
        x1 = (max(cols) + 1) * (CELL_W + GAP_X) - GAP_X + pad
        y1 = (max(rows) + 1) * (CELL_H + GAP_Y) - GAP_Y + pad
        frames.append((x0, y0, x1 - x0, y1 - y0))
    count = 0
    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            if _rects_overlap(frames[i], frames[j], min_gap=1.0):
                count += 1
    return count


def _edge_polyline(pos: dict[str, tuple[int, int]], src: str, tgt: str):
    """Model archify's orthogonal route for a grid placement.

    Reverse-engineered from validate evidence (#24 implementation notes): a
    rightward edge runs horizontal at the source row to the channel *left of
    the target column*, turns vertical, then horizontal into the target; a
    leftward edge mirrors it (channel right of target); same-column edges use
    the target's left channel too.  One vertical segment per edge -- NOT one
    per traversed channel.  Returns (points, channel_x).
    """
    sc, sr = pos[src]
    tc, tr = pos[tgt]
    sy = sr * (CELL_H + GAP_Y) + CELL_H / 2
    ty = tr * (CELL_H + GAP_Y) + CELL_H / 2
    if tc > sc:  # rightward
        x0 = sc * (CELL_W + GAP_X) + CELL_W
        x1 = tc * (CELL_W + GAP_X)
        vx = tc * (CELL_W + GAP_X) - GAP_X / 2
    elif tc < sc:  # leftward
        x0 = sc * (CELL_W + GAP_X)
        x1 = tc * (CELL_W + GAP_X) + CELL_W
        vx = (tc + 1) * (CELL_W + GAP_X) - GAP_X / 2
    else:  # same column: out the left side, up/down, back in
        x0 = x1 = sc * (CELL_W + GAP_X)
        vx = sc * (CELL_W + GAP_X) - GAP_X / 2
    return [(x0, sy), (vx, sy), (vx, ty), (x1, ty)], vx


def _polylines(pos: dict[str, tuple[int, int]], edges: list[tuple[str, str]]):
    out = []
    for src, tgt in edges:
        if src == tgt or src not in pos or tgt not in pos:
            continue
        pl = _edge_polyline(pos, src, tgt)
        if pl is not None:
            out.append(((src, tgt), pl[0], pl[1]))
    return out


def polyline_crossings(pos: dict[str, tuple[int, int]], edges: list[tuple[str, str]]) -> int:
    """Exact crossings between the modelled orthogonal routes (shared endpoints excluded)."""
    pls = _polylines(pos, edges)
    crossings = 0
    for i in range(len(pls)):
        for j in range(i + 1, len(pls)):
            (ea, pa, _), (eb, pb, _) = pls[i], pls[j]
            if ea[0] in eb or ea[1] in eb:
                continue  # share a node: adjacency, not a crossing
            for k in range(len(pa) - 1):
                for m in range(len(pb) - 1):
                    if _seg_intersect(pa[k], pa[k + 1], pb[m], pb[m + 1]):
                        crossings += 1
    return crossings


def corridor_conflicts(pos: dict[str, tuple[int, int]], edges: list[tuple[str, str]]) -> int:
    """Vertical segments sharing a channel x with overlapping vertical extent.

    This is archify's ``ambiguous-corridor`` showcase check; the channel x is
    exactly the modelled vertical position, so distinct channels never merge.
    """
    verticals: dict[float, list[tuple[float, float]]] = {}
    for (src, tgt), pl, _vx in _polylines(pos, edges):
        sy, ty = pl[0][1], pl[2][1]
        verticals.setdefault(_vx, []).append((min(sy, ty), max(sy, ty)))
    conflicts = 0
    for spans in verticals.values():
        spans.sort()
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                if spans[i][1] > spans[j][0]:
                    conflicts += 1
    return conflicts


def blocked_routes(pos: dict[str, tuple[int, int]], edges: list[tuple[str, str]]) -> int:
    """Edges whose only L-shaped routes pass through unrelated modules' cells.

    Approximates archify's ``edge-through-node`` check: the orthogonal router
    connects two grid cells with an L path; when *both* L variants are blocked
    by unrelated cells the rendered edge squeezes through a component (2px
    clearance) and showcase fails.
    """
    occupied: dict[tuple[int, int], str] = {pos[mid]: mid for mid in pos}
    blocked = 0
    for src, tgt in edges:
        if src == tgt or src not in pos or tgt not in pos:
            continue
        (c1, r1), (c2, r2) = pos[src], pos[tgt]
        if c1 == c2 and r1 == r2:
            continue
        others = (None, src, tgt)

        def path_clear(cells: list[tuple[int, int]]) -> bool:
            return not any(occupied.get(cell, None) not in others for cell in cells)

        cols_between = [(c, r1) for c in range(min(c1, c2) + 1, max(c1, c2))]
        rows_between_v1 = [(c2, r) for r in range(min(r1, r2) + 1, max(r1, r2))]
        rows_between_v2 = [(c1, r) for r in range(min(r1, r2) + 1, max(r1, r2))]
        cols_between_h2 = [(c, r2) for c in range(min(c1, c2) + 1, max(c1, c2))]
        l1_clear = path_clear(cols_between + rows_between_v1)  # across then drop
        l2_clear = path_clear(rows_between_v2 + cols_between_h2)  # drop then across
        if not (l1_clear or l2_clear):
            blocked += 1
    return blocked


def evaluate(pos, edges, groups) -> tuple[int, int, int, int, float]:
    """Lexicographic: weighted sum first, then the parts, then total edge length."""
    cross = polyline_crossings(pos, edges)
    corr = corridor_conflicts(pos, edges)
    rov = region_overlaps(groups, pos)
    blk = blocked_routes(pos, edges)
    return (cross + 10 * corr + 100 * rov + 50 * blk, cross, corr, rov, total_edge_length(pos, edges))


def _dependency_layers(ids: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    """Longest-path layering along dependency direction (sources leftmost).

    Iterative relaxation with a hard iteration cap: acyclic graphs converge,
    cyclic ones terminate deterministically with a best-effort layering.
    """
    layer = {mid: 0 for mid in ids}
    for _ in range(len(ids)):
        changed = False
        for src, tgt in edges:
            if src in layer and tgt in layer and layer[tgt] <= layer[src]:
                layer[tgt] = layer[src] + 1
                changed = True
        if not changed:
            break
    return layer


def _baseline_layout(ids: list[str], edges: list[tuple[str, str]]) -> dict[str, tuple[int, int]]:
    """Layered layout: dependency layers = columns, barycentric ordering = rows.

    Deterministic, and for tree-ish dependency graphs (the common case)
    produces crossing-free, unblocked placements directly -- the "确定性布局
    优先" half of §15; the fixed-seed search only runs when checks fail.
    """
    layer = _dependency_layers(ids, edges)
    by_layer: dict[int, list[str]] = {}
    for mid in ids:
        by_layer.setdefault(layer[mid], []).append(mid)

    pos: dict[str, tuple[int, int]] = {}
    for lvl in sorted(by_layer):
        members = sorted(by_layer[lvl])
        pos.update((mid, (lvl, row)) for row, mid in enumerate(members))

    for _ in range(2):  # barycentric sweeps on rows
        for lvl in sorted(by_layer):
            members = by_layer[lvl]

            def bary(mid: str) -> float:
                rows = [pos[s][1] for s, t in edges if t == mid and s in pos]
                return sum(rows) / len(rows) if rows else 0.0

            members = sorted(members, key=lambda m: (bary(m), m))
            pos.update((mid, (lvl, row)) for row, mid in enumerate(members))
    return pos


def solve_layout(
    ids: list[str],
    edges: list[tuple[str, str]],
    groups: dict[str, list[str]],
    cols: int | None = None,
) -> dict[str, tuple[int, int]]:
    """Deterministic layered baseline; fixed-seed hill-climb only if checks fail.

    Hill-climbing starts from the layered baseline *and* the seeded random
    restarts, so the deterministic candidate always gets local refinement.
    """
    baseline = _baseline_layout(ids, edges)
    if evaluate(baseline, edges, groups)[0] == 0:
        return baseline

    n_cols = max(c for c, _ in baseline.values()) + 1
    n_rows = max(r for _, r in baseline.values()) + 1
    cells = [(c, r) for c in range(n_cols + 1) for r in range(n_rows + 2)]
    ordered = sorted(ids)
    rng = random.Random(SEED)  # fixed seed: same repo -> same search -> same layout
    best, best_score = baseline, evaluate(baseline, edges, groups)

    def hillclimb(pos: dict[str, tuple[int, int]], score) -> tuple[dict, tuple]:
        improved, rounds = True, 0
        while improved and rounds < MAX_ROUNDS and score[0] > 0:
            improved, rounds = False, rounds + 1
            for name in ordered:
                if score[0] == 0:
                    break
                for cell in cells:
                    if cell in [pos[o] for o in ordered if o != name]:
                        continue
                    old = pos[name]
                    pos[name] = cell
                    new_score = evaluate(pos, edges, groups)
                    if new_score < score:
                        score, improved = new_score, True
                    else:
                        pos[name] = old
        return pos, score

    best, best_score = hillclimb(dict(best), best_score)
    for _ in range(RESTARTS):
        pos: dict[str, tuple[int, int]] = {}
        occupied: set[tuple[int, int]] = set()
        for name in ordered:
            while True:
                cell = rng.choice(cells)
                if cell not in occupied:
                    occupied.add(cell)
                    pos[name] = cell
                    break
        pos, score = hillclimb(pos, evaluate(pos, edges, groups))
        if score < best_score:
            best, best_score = dict(pos), score
        if best_score[0] == 0:
            break
    return best


# --- layout cache ---------------------------------------------------------------

def load_cached_layout(path: Path, module_ids: list[str]) -> dict[str, tuple[int, int]] | None:
    """Reuse ``layout.json`` when the module set is unchanged and it passed showcase.

    Layouts that only cleared ``standard`` are re-solved (the cache must not
    pin a degraded layout forever -- the goal is a reproducible *showcase* map).
    """
    if not path.is_file():
        return None
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if meta.get("validatedQuality") != "showcase":
        return None
    if sorted(meta.get("modules") or []) != sorted(module_ids):
        return None
    try:
        return {k: (int(v[0]), int(v[1])) for k, v in meta["positions"].items()}
    except (KeyError, TypeError, ValueError):
        return None


def save_layout_cache(path: Path, module_ids: list[str], pos: dict[str, tuple[int, int]],
                      passed_quality: str | None) -> None:
    path.write_text(json.dumps({
        "modules": sorted(module_ids),
        "positions": {k: list(v) for k, v in pos.items()},
        "validatedQuality": passed_quality,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --- IR assembly -----------------------------------------------------------------

def parent_group(module_id: str) -> str:
    parts = module_id.split("/")
    return parts[-2] if len(parts) > 1 else "(root)"


def build_ir(
    graph: dict[str, Any],
    metrics: dict[str, Any],
    pos: dict[str, tuple[int, int]],
    mapping: dict[str, str],
    repo_name: str,
) -> dict[str, Any]:
    rows = {r["id"]: r for r in metrics["modules"]}
    components = []
    for mid in sorted(rows):
        r = rows[mid]
        short = mapping[mid]
        level = r["depthScore"]
        comp: dict[str, Any] = {
            "id": short,
            "type": "backend",
            "label": mid.rsplit("/", 1)[-1][: -3].lstrip("_"),
            "sublabel": f"{DEPTH_ZH[level]}模块 · {r['ports']} 端口",
            "col": pos[mid][0],
            "row": pos[mid][1],
        }
        if level == "shallow":
            comp["tag"] = "浅"
        if r["fanOut"] >= FANOUT_TAG_THRESHOLD:
            comp["tag"] = "扇出偏高" if "tag" not in comp else comp["tag"]
        components.append(comp)

    boundaries = [
        {"kind": "region", "label": f"{dirname} 包（{len(members)} 模块）", "wraps": [mapping[m] for m in sorted(members)]}
        for dirname, members in sorted(_by_group(rows).items())
    ]
    connections = [
        {"from": mapping[e["source"]], "to": mapping[e["target"]]}
        for e in metrics["aggregatedEdges"]
        if e["source"] in mapping and e["target"] in mapping and e["source"] != e["target"]
    ]

    return {
        "schema_version": 1,
        "diagram_type": "architecture",
        "meta": {
            "title": f"{repo_name} · 模块地图",
            "subtitle": "由 /deep-module-review 扫描生成 · Archify 渲染",
            "locale": "zh-CN",
            "quality_profile": "showcase",
            "legend": {"mode": "auto"},
        },
        "layout": {"mode": "grid", "cols": max(c for c, _ in pos.values()) + 1,
                   "cellW": CELL_W, "cellH": CELL_H, "gapX": GAP_X, "gapY": GAP_Y},
        "components": components,
        "boundaries": boundaries,
        "connections": connections,
    }


def _by_group(rows: dict[str, dict]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for mid in rows:
        groups.setdefault(parent_group(mid), []).append(mid)
    return groups


# --- validation ------------------------------------------------------------------

def validate_ir(archify_dir: Path, ir_path: Path) -> tuple[bool, str | None, list]:
    """One ``archify validate`` per quality step-down: showcase -> standard (§15)."""
    diagnostics: list = []
    for quality in ("showcase", "standard"):
        result = archify_env.run_archify(archify_dir, "validate", "architecture", str(ir_path), quality=quality)
        if result.get("ok"):
            return True, quality, result.get("diagnostics") or []
        diagnostics = result.get("diagnostics") or diagnostics
    return False, None, diagnostics


# --- CLI ---------------------------------------------------------------------------

def run(last_review: Path) -> dict[str, Any]:
    env = archify_env.probe()
    if not env["available"]:
        print(json.dumps({"ok": False, "archify": env}, ensure_ascii=False))
        return {"ok": False, "archify": env}

    graph = json.loads((last_review / "graph.json").read_text(encoding="utf-8"))
    metrics = json.loads((last_review / "metrics.json").read_text(encoding="utf-8"))
    rows = metrics["modules"]
    module_ids = [r["id"] for r in rows]

    mapping = {mid: map_module_id(mid) for mid in module_ids}
    assert_no_collisions(mapping)

    edges = [(e["source"], e["target"]) for e in metrics["aggregatedEdges"]]
    groups = _by_group({mid: {} for mid in module_ids})

    cache = last_review / "layout.json"
    pos = load_cached_layout(cache, module_ids)
    reused = pos is not None
    if pos is None:
        pos = solve_layout(module_ids, edges, groups)
    save_layout_cache(cache, module_ids, pos, None)

    ir = build_ir(graph, metrics, pos, mapping, metrics.get("repo") or "repo")
    ir_path = last_review / "architecture.json"
    ir_path.write_text(json.dumps(ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    passed, quality, diagnostics = validate_ir(Path(env["dir"]), ir_path)
    if not passed:
        print(json.dumps({
            "ok": False,
            "error": "archify validate failed at both showcase and standard",
            "diagnostics": diagnostics[:10],
        }, ensure_ascii=False))
        return {"ok": False, "diagnostics": diagnostics}

    if quality != ir["meta"].get("quality_profile"):
        # Persist the quality that actually passed (§15 single step-down).  The
        # IR is written aiming high ("showcase"); assemble() reads this field to
        # decide the profile it validates AND delivers at -- leaving it at
        # "showcase" would make assemble re-attempt showcase and fail on repos
        # that only clear standard.
        ir["meta"]["quality_profile"] = quality
        ir_path.write_text(json.dumps(ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    save_layout_cache(cache, module_ids, pos, quality)
    idmap_path = last_review / "idmap.json"
    idmap_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "ok": True,
        "architecture": str(ir_path),
        "idmap": str(idmap_path),
        "layout": str(cache),
        "layoutReused": reused,
        "quality": quality,
        "modules": len(module_ids),
        "archify": env,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="to_archify", description=__doc__.splitlines()[0])
    parser.add_argument("--last-review", default=str(Path(__file__).resolve().parent.parent / ".last-review"))
    args = parser.parse_args(argv)
    try:
        result = run(Path(args.last_review).resolve())
    except Exception as exc:  # clean failure, no traceback
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
