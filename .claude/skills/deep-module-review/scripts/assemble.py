"""Assemble ``map.html``: main archify architecture + per-module drill-down panels.

#24 v2 design §15 / §12.  Inputs (all under the last-review dir):

- ``architecture.json`` + ``idmap.json``   from ``to_archify.py``
- ``graph.json``                           parser scan (``intra`` drives panel edges)
- ``panels/<panel_id>.json``               AI lane/promise/interp annotations (SKILL.md protocol)
- ``panels/_summary.json``                 optional AI one-paragraph verdict

Steps: build each panel's workflow IR from its spec + ``intra`` data ->
``archify validate``+``deliver`` every diagram (external node processes through
the UTF-8 wrapper) -> extract each ``<svg>``/``<style>`` -> prefix internal ids
(the ``(?<=\\s)id="..."`` regex from the prototype incident, §13.4-2) -> merge
styles (byte-equal dedupe, concat fallback on mismatch, review F8) -> inject
panel DOM + click JS -> assert the panel-id <-> ``data-node-id`` mapping ->
write ``map.html``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import archify_env

MAP_SIZE_WARN_BYTES = 10 * 1024 * 1024  # §12 scale strategy (threshold TODO by design)
ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")
MODULE_PSEUDO = "<module>"
MODULE_PSEUDO_ID = "top_level"
WORKFLOW_QUALITY = "standard"


class SpecError(Exception):
    """A panel spec is inconsistent with the intra data -- AI must fix it."""


# --- func name -> archify node id -------------------------------------------------

def sanitize_func_id(name: str, taken: set[str]) -> str:
    """``_foo`` -> ``foo``; ``<module>`` -> ``top_level``; collisions are fatal."""
    if name == MODULE_PSEUDO:
        short = MODULE_PSEUDO_ID
    else:
        short = name.lstrip("_")
        short = re.sub(r"[^A-Za-z0-9_-]", "_", short) or "node"
    if not short[0].isalpha():
        short = "f" + short
    if short in taken:
        raise SpecError(f"function id collision after sanitize: {name!r} -> {short!r}")
    taken.add(short)
    return short


# --- spec -> workflow IR ------------------------------------------------------------

def build_workflow_ir(spec: dict[str, Any], intra_entry: dict[str, Any]) -> dict[str, Any]:
    """Turn one AI panel spec + the module's ``intra`` entry into a workflow IR.

    Assertions (fail loud, per design "宁缺勿幻"):
    - every function in ``intra.funcs`` is placed on a lane (missing -> error);
    - no unknown names in ``spec.nodes`` (typo protection);
    - col clamped to <= 5; same lane+col twice -> error (archify would reject).
    """
    funcs = [f["name"] for f in intra_entry.get("funcs") or []]
    raw_calls = intra_entry.get("calls") or []

    lanes = spec.get("lanes") or []
    if not lanes:
        raise SpecError("spec has no lanes")
    lane_ids = set()
    for lane in lanes:
        if not ID_PATTERN.match(lane.get("id") or ""):
            raise SpecError(f"bad lane id {lane.get('id')!r} (must match {ID_PATTERN.pattern})")
        if not (lane.get("label") or "").strip():
            raise SpecError(f"lane {lane['id']!r} has no label")
        lane_ids.add(lane["id"])

    placements = spec.get("nodes") or {}
    unknown = sorted(set(placements) - set(funcs))
    missing = sorted(set(funcs) - set(placements))
    if unknown:
        raise SpecError(f"spec places unknown functions: {unknown}")
    if missing:
        raise SpecError(f"spec must place all intra functions, missing: {missing}")

    taken: set[str] = set()
    fid = {name: sanitize_func_id(name, taken) for name in funcs}
    nodes, seen_cell = [], set()
    for name in funcs:
        lane, col = placements[name][0], placements[name][1]
        sublabel = placements[name][2] if len(placements[name]) > 2 else ""
        if lane not in lane_ids:
            raise SpecError(f"function {name!r} placed on unknown lane {lane!r}")
        col = min(int(col), 5)  # clamp (§17.2); collision checked below
        cell = (lane, col)
        if cell in seen_cell:
            raise SpecError(f"two functions share lane={lane!r} col={col} (after clamp)")
        seen_cell.add(cell)
        node: dict[str, Any] = {
            "id": fid[name], "lane": lane, "col": col,
            "type": "backend", "label": name, "width": 190,
        }
        if sublabel:
            node["sublabel"] = sublabel
        nodes.append(node)

    edges: dict[tuple[str, str], dict[str, Any]] = {}
    for call in raw_calls:
        src, dst = fid.get(call["from"]), fid.get(call["to"])
        if src is None or dst is None or src == dst:
            continue  # self-recursion stays off the lane diagram (design: 其他函数)
        edges.setdefault((src, dst), {})

    for extra in spec.get("extra_edges") or []:
        src, dst = fid.get(extra["from"]), fid.get(extra["to"])
        if src is None or dst is None:
            raise SpecError(
                f"extra_edge {extra['from']!r}->{extra['to']!r} references an unplaced function"
            )
        if src == dst:
            continue
        entry = edges.setdefault((src, dst), {})
        if extra.get("label"):
            entry["label"] = extra["label"]

    # real cycles get a highlighted return edge (V2-D7; honest only when they exist)
    for (src, dst), entry in edges.items():
        if (dst, src) in edges and "label" not in entry:
            entry["label"] = "↻ 循环"
    cycle_pairs = {(a, b) for (a, b) in edges if (b, a) in edges}
    for (src, dst), entry in edges.items():
        if (src, dst) in cycle_pairs:
            entry["variant"] = "emphasis"

    return {
        "schema_version": 2,
        "diagram_type": "workflow",
        "meta": {
            "title": f"{spec.get('title') or spec['module_id']} · 内部函数路线",
            "subtitle": "节点=真实函数，箭头=真实调用，泳道=AI 业务阶段标注",
            "locale": "zh-CN",
            "quality_profile": WORKFLOW_QUALITY,
        },
        "lanes": [{"id": l["id"], "label": l["label"]} for l in lanes],
        "nodes": nodes,
        "edges": [{"from": a, "to": b, **rest} for (a, b), rest in sorted(edges.items())],
    }


# --- deliver + extract ---------------------------------------------------------------

def validate_and_deliver(archify_dir: Path, ir: dict[str, Any], ir_path: Path,
                         out_html: Path, diagram_type: str, quality: str) -> None:
    ir_path.parent.mkdir(parents=True, exist_ok=True)
    ir_path.write_text(json.dumps(ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = archify_env.run_archify(archify_dir, "validate", diagram_type, str(ir_path), quality=quality)
    if not result.get("ok"):
        raise RuntimeError(
            f"archify validate failed for {ir_path.name} ({quality}): "
            + json.dumps((result.get("diagnostics") or [])[:5], ensure_ascii=False)
        )
    delivered = archify_env.run_archify(
        archify_dir, "deliver", diagram_type, str(ir_path), str(out_html), quality=quality
    )
    if not delivered.get("ok"):
        raise RuntimeError(
            f"archify deliver failed for {ir_path.name}: "
            + json.dumps(delivered, ensure_ascii=False)[:400]
        )


def extract_style_blocks(html: str) -> list[str]:
    return re.findall(r"<style>.*?</style>", html, re.S)


def extract_svg(html: str) -> str:
    start, end = html.find("<svg"), html.rfind("</svg>")
    if start < 0 or end < 0:
        raise RuntimeError("deliver HTML contains no <svg>")
    return html[start: end + len("</svg>")]


def unique_ids(svg: str, prefix: str) -> str:
    """Prefix internal ids so multiple SVGs can coexist in one page.

    ``(?<=\\s)`` keeps the rewrite away from attribute tails like
    ``data-node-id="..."`` -- the bare ``id="..."`` regex was the v2 prototype's
    silent-click-failure bug (§13.4-2).
    """
    svg = re.sub(r'(?<=\s)id="([^"]+)"', rf'id="{prefix}-\1"', svg)
    svg = re.sub(r'url\(#([^)]+)\)', rf'url(#{prefix}-\1)', svg)
    svg = re.sub(r'href="#([^"]+)"', rf'href="#{prefix}-\1"', svg)
    svg = re.sub(
        r'aria-labelledby="([^"]+)"',
        lambda m: 'aria-labelledby="' + " ".join(f"{prefix}-{x}" for x in m.group(1).split()) + '"',
        svg,
    )
    return svg


def merge_styles(per_deliver: list[list[str]]) -> tuple[str, str]:
    """Dedupe when every deliver agrees byte-for-byte; otherwise concat (F8)."""
    flat = [s for blocks in per_deliver for s in blocks]
    # Tolerate one stray nesting level (a single-block list where a bare block
    # was expected).  Without this, a list element flows into str.format and is
    # repr'd -- newlines become literal "\n" and the CSS silently breaks (seen
    # as an all-black diagram once the archify theme variables stop resolving).
    flat = [x for s in flat for x in (s if isinstance(s, list) else [s])]
    if not flat or not all(isinstance(s, str) for s in flat):
        raise TypeError(f"merge_styles expected style-block strings, got {flat!r}")
    first = flat[0]
    if all(block == first for block in flat):
        return first, "deduped"
    note = ("<!-- style blocks differed between archify delivers; concatenated in "
            "delivery order (later rules override earlier ones). Assumption noted per "
            "#24 review F8. -->")
    return note + "".join(flat), "concatenated"


# --- page assembly --------------------------------------------------------------------

def _esc(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def panel_section(short_id: str, spec: dict[str, Any], svg: str) -> str:
    title = _esc(spec.get("title") or spec["module_id"])
    file_ = _esc(spec["module_id"])
    promise = spec.get("promise") or ""
    interp = spec.get("interp") or ""
    return f"""
<section class="panel" id="panel-{short_id}" hidden>
  <div class="panel-head">
    <h2>{title} <span class="mono">{file_}</span></h2>
    <p class="promise">{promise}</p>
  </div>
  <div class="wf">{svg}</div>
  <div class="interp"><h3>AI 解读</h3><p>{interp}</p></div>
</section>"""


PAGE_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
{styles}
<style>
  body {{ margin:0; background:#f7f7f5; color:#1c1917; font:15px/1.6 "PingFang SC","Microsoft YaHei",system-ui,sans-serif; }}
  .wrap {{ max-width:1160px; margin:0 auto; padding:24px 20px 80px; }}
  header h1 {{ font-size:24px; margin:0 0 4px; }}
  header .hint {{ color:#6b7280; font-size:13px; margin:0 0 6px; }}
  header .hint b {{ color:#b45309; }}
  .diagram-scroll {{ overflow-x:auto; border:1px solid #e5e4e0; border-radius:12px; background:#fff; margin-top:10px; }}
  #arch g[data-node-id] {{ cursor:pointer; }}
  #arch g[data-node-id]:hover {{ opacity:.85; }}
  .summary {{ margin-top:14px; background:#eef7f4; border:1px solid #d6e8e2; border-radius:10px; padding:12px 16px; font-size:14px; }}
  .panel {{ margin-top:26px; border:1px solid #e5e4e0; border-radius:12px; background:#fff; padding:20px 22px; box-shadow:0 1px 2px rgb(0 0 0/.05); }}
  .panel-head h2 {{ margin:0 0 4px; font-size:18px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .mono {{ font-family:ui-monospace,Menlo,monospace; font-size:12px; background:#f0efed; padding:2px 8px; border-radius:6px; color:#57534e; font-weight:400; }}
  .promise {{ font-size:15px; font-weight:600; margin:6px 0 0; color:#0f766e; }}
  .wf {{ overflow-x:auto; margin-top:14px; border:1px solid #efeeec; border-radius:10px; background:#fdfdfc; }}
  .interp {{ margin-top:14px; background:#f7f6f4; border-radius:10px; padding:12px 16px; }}
  .interp h3 {{ margin:0 0 6px; font-size:13px; color:#78716c; letter-spacing:.06em; }}
  .interp p {{ margin:0; font-size:14px; }}
  .interp code {{ font-family:ui-monospace,Menlo,monospace; font-size:12.5px; background:#e7e5e4; padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
<header>
  <h1>{title}</h1>
  <p class="hint">👆 <b>点任意模块卡片</b> → 下方展开它的「内部功能路线」（真实函数调用泳道图 + AI 解读）。再点其他模块切换。</p>
</header>
<div class="diagram-scroll" id="arch">{main_svg}</div>
{summary}
{panels}
</div>
<script>
document.querySelectorAll('#arch g[data-node-id]').forEach(function(g) {{
  g.addEventListener('click', function() {{
    var id = g.getAttribute('data-node-id');
    document.querySelectorAll('.panel').forEach(function(p) {{ p.hidden = true; }});
    var panel = document.getElementById('panel-' + id);
    if (panel) {{ panel.hidden = false; panel.scrollIntoView({{behavior:'smooth', block:'start'}}); }}
  }});
}});
</script>
</body></html>"""


def assert_panel_mapping(main_svg: str, panel_ids: list[str]) -> None:
    """The §13.4-2 incident guard: every clickable node has its panel, and vice versa."""
    node_ids = set(re.findall(r'data-node-id="([^"]+)"', main_svg))
    panel_set = set(panel_ids)
    if node_ids != panel_set:
        raise RuntimeError(
            f"panel mapping mismatch: nodes without panel={sorted(node_ids - panel_set)}, "
            f"panels without node={sorted(panel_set - node_ids)}"
        )


def run(last_review: Path) -> dict[str, Any]:
    env = archify_env.probe()
    if not env["available"]:
        print(json.dumps({"ok": False, "archify": env}, ensure_ascii=False))
        return {"ok": False, "archify": env}
    archify_dir = Path(env["dir"])

    graph = json.loads((last_review / "graph.json").read_text(encoding="utf-8"))
    idmap: dict[str, str] = json.loads((last_review / "idmap.json").read_text(encoding="utf-8"))
    architecture = json.loads((last_review / "architecture.json").read_text(encoding="utf-8"))
    intra: dict[str, Any] = graph.get("intra") or {}

    panels_dir = last_review / "panels"
    specs = sorted(panels_dir.glob("*.json")) if panels_dir.is_dir() else []
    # Exclude our own intermediates/verdict: re-running assemble must not pick
    # up the *.workflow.json IRs it wrote last time as if they were specs.
    specs = [p for p in specs
             if p.name != "_summary.json" and not p.name.endswith(".workflow.json")]
    if not specs:
        print(json.dumps({"ok": False, "error": f"no panel specs in {panels_dir} "
                          "(SKILL.md step: AI writes panels/*.json first)"}, ensure_ascii=False))
        return {"ok": False, "error": "no panel specs"}

    # coverage: every production module needs exactly one spec
    by_module = {}
    for spec_path in specs:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        by_module.setdefault(spec.get("module_id"), []).append(spec_path.name)
    missing_specs = sorted(set(idmap) - set(by_module))
    unknown_specs = sorted(set(by_module) - set(idmap))
    if missing_specs or unknown_specs:
        print(json.dumps({"ok": False,
                          "error": "panel specs do not cover the production modules",
                          "missing": missing_specs, "unknown": unknown_specs}, ensure_ascii=False))
        return {"ok": False, "error": "spec coverage mismatch"}

    # ---- main diagram ---------------------------------------------------------
    main_html_path = last_review / "architecture.html"
    validate_and_deliver(archify_dir, architecture, last_review / "architecture.json",
                         main_html_path, "architecture",
                         architecture.get("meta", {}).get("quality_profile") or "showcase")
    main_html = main_html_path.read_text(encoding="utf-8")
    all_styles: list[str] = extract_style_blocks(main_html)
    main_svg = unique_ids(extract_svg(main_html), "arch")

    # ---- panels ---------------------------------------------------------------
    comp_order = {c["id"]: (c.get("row", 0), c.get("col", 0))
                  for c in architecture.get("components", [])}
    sections, panel_ids = [], []
    for module_id in sorted(idmap, key=lambda m: comp_order.get(idmap[m], (0, 0))):
        short = idmap[module_id]
        spec = json.loads((panels_dir / by_module[module_id][0]).read_text(encoding="utf-8"))
        try:
            ir = build_workflow_ir(spec, intra.get(module_id) or {})
        except SpecError as exc:
            print(json.dumps({"ok": False, "error": f"{by_module[module_id][0]}: {exc}"},
                             ensure_ascii=False))
            return {"ok": False, "error": str(exc)}
        ir_path = panels_dir / f"{short}.workflow.json"
        out_html = panels_dir / f"{short}.html"
        validate_and_deliver(archify_dir, ir, ir_path, out_html, "workflow", WORKFLOW_QUALITY)
        panel_html = out_html.read_text(encoding="utf-8")
        all_styles.extend(extract_style_blocks(panel_html))
        svg = unique_ids(extract_svg(panel_html), f"w-{short}")
        sections.append(panel_section(short, spec, svg))
        panel_ids.append(short)

    assert_panel_mapping(main_svg, panel_ids)

    merged, style_mode = merge_styles([all_styles])

    summary_html = ""
    summary_path = panels_dir / "_summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if (summary.get("summary_html") or "").strip():
            summary_html = f'<div class="summary">{summary["summary_html"]}</div>'

    title = architecture.get("meta", {}).get("title") or "模块地图"
    html = PAGE_TEMPLATE.format(
        title=_esc(title), styles=merged, main_svg=main_svg,
        summary=summary_html, panels="".join(sections),
    )
    map_path = last_review / "map.html"
    map_path.write_text(html, encoding="utf-8")

    size = map_path.stat().st_size
    result = {
        "ok": True,
        "map": str(map_path),
        "mapSizeBytes": size,
        "styleMode": style_mode,
        "panels": len(panel_ids),
        "archify": env,
    }
    if size > MAP_SIZE_WARN_BYTES:
        result["warning"] = (
            f"map.html is {size} bytes (> 10MB). Panel scale strategy pending (design TODO): "
            "consider restricting panels to deep/moderate modules."
        )
    print(json.dumps(result, ensure_ascii=False))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="assemble", description=__doc__.splitlines()[0])
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
