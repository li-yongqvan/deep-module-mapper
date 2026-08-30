/**
 * Module-level dependency edges (issue #10, hardened for #18).
 *
 * Issue #18 ("画线即校验") flips the canvas to **zero edges by default**:
 * auto-aggregated edges are no longer rendered (D1); a user-drawn edge is only
 * accepted when it matches a real code dependency, and only then does it
 * render — with the real underlying raw edges as evidence (D3). Every function
 * here is pure so the draw-to-verify contract is unit-testable.
 */
import { MarkerType, type Edge as FlowEdge } from '@xyflow/react';
import type { Graph } from '../../api/types';
import type { AggregatedEdgeData } from '../graphToFlow';
import { aggregateEdges } from '../aggregateEdges';
import { THIRD_PARTY_NODE_ID } from '../graphToFeatureFlow';
import { atomForFile } from '../../manifest/featureAtoms';
import type { ModuleEdgeRef, RecomposedDesign } from './types';

/** Canonical key for an ordered module pair (`source->target`). */
export function edgeKey(source: string, target: string): string;
export function edgeKey(ref: ModuleEdgeRef): string;
export function edgeKey(
  a: string | ModuleEdgeRef,
  b?: string,
): string {
  const source = typeof a === 'string' ? a : a.source;
  const target = typeof a === 'string' ? (b as string) : a.target;
  return `${source}->${target}`;
}

export interface ParsedEdgeId {
  source: string;
  target: string;
  /** 'module' = auto-aggregated edge; 'manual' = user-drawn edge. */
  kind: 'module' | 'manual';
}

/** Reverse of the edge id scheme (`module-edge-<s>-><t>` / `manual-edge-<s>-><t>`). */
export function parseEdgeId(id: string): ParsedEdgeId | null {
  const match = /^(module|manual)-edge-(.+?)->(.+)$/.exec(id);
  if (!match) return null;
  return {
    kind: match[1] === 'module' ? 'module' : 'manual',
    source: match[2],
    target: match[3],
  };
}

/** Index aggregated edges by their canonical `source->target` key (D2/D12). */
function indexAggregatedEdges(
  aggregated: FlowEdge<AggregatedEdgeData>[],
): Map<string, FlowEdge<AggregatedEdgeData>> {
  return new Map(aggregated.map((e) => [edgeKey(e.source, e.target), e]));
}

/** Result of a draw-to-verify dependency check (issue #18, D4/D5). */
export interface DependencyCheck {
  status: 'real' | 'reversed' | 'none';
  /**
   * The matching aggregated edge when a dependency exists: the forward edge
   * for `real`, the backward edge for `reversed`. Its `data.rawEdges` is the
   * code evidence (import kind / targetPort / line) shown in the Inspector.
   */
  evidence?: FlowEdge<AggregatedEdgeData>;
}

/**
 * Direction-sensitive check of whether a drawn `source -> target` dependency
 * matches the code facts (aggregated module edges, §2.1 V6/V7):
 * - `real`     = forward pair exists in the aggregated set;
 * - `reversed` = only the backward pair exists (code depends the other way);
 * - `none`     = no dependency between the two modules at all.
 */
export function checkDependency(
  aggregated: FlowEdge<AggregatedEdgeData>[],
  source: string,
  target: string,
): DependencyCheck {
  const byKey = indexAggregatedEdges(aggregated);
  const forward = byKey.get(edgeKey(source, target));
  if (forward) return { status: 'real', evidence: forward };
  const backward = byKey.get(edgeKey(target, source));
  if (backward) return { status: 'reversed', evidence: backward };
  return { status: 'none' };
}

/** Rejection feedback text for a non-real dependency (D4/D5, wording fixed). */
export function rejectionMessage(
  status: 'reversed' | 'none',
  design: RecomposedDesign,
  source: string,
  target: string,
): string {
  const name = (id: string) => design.modules.find((m) => m.id === id)?.name ?? id;
  const src = name(source);
  const tgt = name(target);
  if (status === 'reversed') return `实际是 ${tgt} 依赖 ${src}，方向反了`;
  return `这两个模块之间无任何依赖关系（${src} 的文件里没有任何 import 指向 ${tgt}）`;
}

/** How long one rejection toast stays "fresh" (§9 Q1 one-shot feedback). */
export const REJECTION_FEEDBACK_COOLDOWN_MS = 1800;

/**
 * One-shot gate for rejection feedback. React Flow may call `isValidConnection`
 * many times during a single drag/hover gesture with the same pair; this makes
 * the toast fire only once per (pair, message) per cooldown window.
 */
export function shouldShowFeedback(
  gate: { signature: string; shownAt: number } | null,
  signature: string,
  now: number,
  cooldownMs: number = REJECTION_FEEDBACK_COOLDOWN_MS,
): boolean {
  return !(gate !== null && gate.signature === signature && now - gate.shownAt < cooldownMs);
}

/** Auto-aggregated module edges from the raw graph (reuses aggregateEdges). */
export function computeAggregatedModuleEdges(
  graph: Graph,
  design: RecomposedDesign,
): FlowEdge<AggregatedEdgeData>[] {
  const atomToModule = new Map<string, string>();
  for (const m of design.modules) {
    for (const atomId of m.atomIds) atomToModule.set(atomId, m.id);
  }
  const externalIds = new Set(graph.externalModules.map((x) => x.id));

  const resolveEndpoint = (fileId: string): string | null => {
    if (externalIds.has(fileId)) return THIRD_PARTY_NODE_ID;
    const atom = atomForFile(fileId);
    if (!atom) return null; // noise file
    return atomToModule.get(atom.id) ?? null;
  };

  // Drop edges resolved inside the same module before aggregation.
  const cross = graph.edges.filter((e) => {
    const s = resolveEndpoint(e.source);
    const t = resolveEndpoint(e.target);
    return s !== null && t !== null && s !== t;
  });

  return aggregateEdges(cross, resolveEndpoint, {
    extraData: { displayLabel: '依赖', aggregated: true },
  }).map((e) => ({ ...e, id: `module-edge-${e.source}->${e.target}` }));
}

/**
 * Final rendered edges. Default is **zero auto edges** (D1): only user-drawn
 * `addedEdges` render, and only when they match a real aggregated dependency
 * (invariant #2) — the rendered data then carries that edge's real `rawEdges`
 * evidence with `manual: false` so the Inspector shows the call sites, not the
 * "手动添加" fallback (#18, D3/裁决2). A non-real added edge is never rendered.
 */
export function finalEdges(
  aggregated: FlowEdge<AggregatedEdgeData>[],
  design: RecomposedDesign,
): FlowEdge[] {
  const byKey = indexAggregatedEdges(aggregated);
  const rendered: FlowEdge[] = [];
  for (const r of design.addedEdges) {
    const agg = byKey.get(edgeKey(r));
    if (!agg || !agg.data) continue; // not a real dependency — never render
    rendered.push({
      // The `manual-edge-` prefix keeps delete-routing (`parseEdgeId` kind
      // 'manual') stable; here it means "user-drawn", NOT "no evidence" — the
      // rendered data below carries the real raw-edge evidence (manual:false).
      id: `manual-edge-${r.source}->${r.target}`,
      source: r.source,
      target: r.target,
      type: 'labeledEdge',
      label: '真实依赖',
      data: {
        manual: false,
        kinds: agg.data.kinds,
        rawEdges: agg.data.rawEdges,
        displayLabel: '真实依赖',
      },
      markerEnd: { type: MarkerType.ArrowClosed },
    });
  }
  return rendered;
}

/**
 * Connect event router (#18). Validity is already decided by
 * `isValidConnection` (§5.2a / 裁决1) before this runs, so here we only dedupe
 * and push the drawn pair into `addedEdges`. Auto-edge unhide no longer applies
 * (aggregated edges are not rendered, D1).
 */
export function onConnectEdge(
  design: RecomposedDesign,
  source: string,
  target: string,
): RecomposedDesign {
  const key = edgeKey(source, target);
  if (design.addedEdges.some((r) => edgeKey(r) === key)) return design; // dedupe
  return { ...design, addedEdges: [...design.addedEdges, { source, target }] };
}

/**
 * Edge delete event router (#18). Only user-drawn (`manual-`) edges are ever
 * rendered, so deletion only removes from `addedEdges`; `hiddenEdges` is
 * deprecated and no longer written (裁决4).
 */
export function onDeleteEdge(
  design: RecomposedDesign,
  edgeId: string,
): RecomposedDesign {
  const parsed = parseEdgeId(edgeId);
  if (!parsed || parsed.kind !== 'manual') return design;
  const key = edgeKey(parsed.source, parsed.target);
  return {
    ...design,
    addedEdges: design.addedEdges.filter((r) => edgeKey(r) !== key),
  };
}
