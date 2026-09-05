"""Inline-SVG architecture diagram for the ``/deep-module-review`` skill.

Grid layout reusing the constants of the deleted ``frontend/src/lib/layout.ts``
(COLUMNS=6 / GAP_X=40 / GAP_Y=40).  Node fill/stroke encode depth score
(D7 traffic-light semantics: deep=green, moderate=amber, shallow=red), a left
strip encodes a cycle/orphan finding, and arrows are the aggregated
production-to-production module edges (v1 never draws external-dependency
nodes -- #24 D7).  Output is a self-contained, theme-aware SVG that is also
safe to inline into ``template.html``.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

# layout.ts constants
COLUMNS = 6
GAP_X = 40
GAP_Y = 40
NODE_W = 200
NODE_H = 72

_DEPTH_STROKE = {
    "deep": "#34d399",  # green  --good
    "moderate": "#fbbf24",  # amber  --mid
    "shallow": "#f87171",  # red    --warn
}
_FINDING_FILL = {
    "cycle/scc": "#ef4444",
    "orphan/isolated": "#9ca3af",
    "orphan/third-party-only": "#818cf8",
}


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _short_id(module_id: str, max_chars: int = 30) -> str:
    if len(module_id) <= max_chars:
        return module_id
    return "…" + module_id[-(max_chars - 1):]


def _dir_key(module_id: str) -> str:
    return str(PurePosixPath(module_id).parent)


def _layout(ids: list[str]) -> dict[str, tuple[int, int]]:
    """Order modules by (directory, id) then tile into a COLUMNS-wide grid."""
    ordered = sorted(ids, key=lambda mid: (_dir_key(mid), mid))
    pos: dict[str, tuple[int, int]] = {}
    for index, mid in enumerate(ordered):
        pos[mid] = (index % COLUMNS, index // COLUMNS)
    return pos


def build_svg(metrics: dict[str, Any], *, repo_name: str | None = None) -> str:
    """Render the architecture SVG from a ``metrics.compute_metrics`` payload."""
    rows = metrics["modules"]
    by_id = {r["id"]: r for r in rows}
    ids = [r["id"] for r in rows]
    pos = _layout(ids)

    cols = min(COLUMNS, max(1, len(ids)))
    grid_w = max(cols * (NODE_W + GAP_X) - GAP_X, NODE_W)
    grid_h = max((max(pos.values(), default=(0, 0))[1] + 1) * (NODE_H + GAP_Y) - GAP_Y, NODE_H)
    margin = 16
    width = grid_w + margin * 2
    height = grid_h + margin * 2

    def cell(mid: str) -> tuple[float, float, float, float]:
        col, row = pos[mid]
        x = margin + col * (NODE_W + GAP_X)
        y = margin + row * (NODE_H + GAP_Y)
        return x, y, x + NODE_W, y + NODE_H

    # --- edges (drawn first, nodes cover their ends) --------------------------
    edge_svg: list[str] = []
    for e in metrics.get("aggregatedEdges") or []:
        src, tgt = e["source"], e["target"]
        if src not in pos or tgt not in pos or src == tgt:
            continue
        sx, sy, sxe, sye = cell(src)
        tx, ty, txe, tye = cell(tgt)
        x1, y1 = sxe, (sy + sye) / 2
        x2, y2 = tx, (ty + tye) / 2
        kinds = ", ".join(e["kinds"])
        title = f"{src} → {tgt}  [{kinds}] ×{e['weight']}"
        edge_svg.append(
            f'<line class="edge" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'marker-end="url(#dmmr-arrow)"><title>{_esc(title)}</title></line>'
        )

    # --- nodes ----------------------------------------------------------------
    node_svg: list[str] = []
    for mid in ids:
        row = by_id[mid]
        level = row["depthScore"] or "shallow"
        x, y, x2, y2 = cell(mid)
        stroke = _DEPTH_STROKE[level]
        ratio = row["ratio"]
        ratio_txt = f"{ratio:.1f}" if ratio is not None else "—"
        ports = row["ports"]
        external = f" · ext {len(row['externalDeps'])}" if row["externalDeps"] else ""
        finding = row["finding"]
        lines = [
            _short_id(mid),
            f"ports {ports} · ratio {ratio_txt}",
            f"fan-in {row['fanIn']} · fan-out {row['fanOut']}{external}",
        ]
        texts = "".join(
            f'<text x="{x + 10}" y="{y + 16 + i * 14}">{_esc(t)}</text>' for i, t in enumerate(lines)
        )
        title_txt = mid
        if finding:
            title_txt += f" · {finding}"
        strip = ""
        if finding and finding in _FINDING_FILL:
            strip = (
                f'<rect x="{x}" y="{y}" width="5" height="{NODE_H}" rx="2" '
                f'fill="{_FINDING_FILL[finding]}"/>'
            )
        node_svg.append(
            f'<g class="node" transform="translate(0,0)">'
            f"<title>{_esc(title_txt)}</title>"
            f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="8" '
            f'fill="{stroke}" fill-opacity="0.13" stroke="{stroke}" stroke-width="2"/>'
            f"{strip}"
            f'{texts}</g>'
        )

    caption = _esc(repo_name or metrics.get("repo") or "repo")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = (
        f'<text class="caption" x="{margin}" y="12">{caption}</text>'
        f'<text class="muted caption" x="{margin}" y="26">generated {generated}</text>'
    )

    style = """\
    <style>
      .dmm-svg{--text:#111827;--muted:#6b7280;--line:#94a3b8}
      .dmm-svg .edge{stroke:var(--line);stroke-width:1.6}
      .dmm-svg .node text{fill:var(--text);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px}
      .dmm-svg .node text.muted{fill:var(--muted)}
      .dmm-svg .caption{font-family:system-ui,sans-serif;font-size:11px}
      .dmm-svg text.muted{fill:var(--muted)}
      @media (prefers-color-scheme: dark){
        .dmm-svg{--text:#e5e7eb;--muted:#94a3b8;--line:#475569}
      }
    </style>"""

    svg = f"""\
<svg class="dmm-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-label="module architecture map">
{style}
  <defs>
    <marker id="dmmr-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--line)"/>
    </marker>
  </defs>
  <g class="dmm-svg-content">
{chr(10).join('    ' + l for l in edge_svg)}
{chr(10).join('    ' + l for l in node_svg)}
  </g>
  {title}
</svg>"""
    return svg
