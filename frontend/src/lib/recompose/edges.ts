/**
 * Module-level dependency edges (issue #10).
 *
 * Edge semantics (decision D2): module edges = auto-aggregated edges from the
 * underlying atom dependencies, PLUS user-drawn edges (`addedEdges`) MINUS
 * user-deleted auto edges (`hiddenEdges`). Aggregation reuses the shared
 * `aggregateEdges` helper with a file -> module resolver, so same-module
 * internal edges are dropped just like same-atom edges in the feature view.
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
 * Final rendered edges = visible auto edges + manual edges.
 * Manual edges have a fixed data shape (`kinds: []`, `rawEdges: []`) so the
 * shared LabeledEdge (`data?.kinds.join(', ')`) and Inspector
 * (`data.rawEdges.length`) never throw on them (#1).
 */
export function finalEdges(
  aggregated: FlowEdge<AggregatedEdgeData>[],
  design: RecomposedDesign,
): FlowEdge[] {
  const aggKeys = new Set(aggregated.map((e) => edgeKey(e.source, e.target)));
  const hiddenKeys = new Set(design.hiddenEdges.map(edgeKey));

  const visibleAgg = aggregated.filter(
    (e) => !hiddenKeys.has(edgeKey(e.source, e.target)),
  );

  const manual = design.addedEdges
    .filter((r) => !aggKeys.has(edgeKey(r))) // an auto edge wins the same key
    .map((r) => ({
      id: `manual-edge-${r.source}->${r.target}`,
      source: r.source,
      target: r.target,
      type: 'labeledEdge' as const,
      label: '手动',
      data: { manual: true, kinds: [], rawEdges: [], displayLabel: '手动' },
      markerEnd: { type: MarkerType.ArrowClosed },
    }));

  return [...visibleAgg, ...manual];
}

/**
 * Connect event router (#3). Only affects manual/hidden overrides; the
 * aggregate edge set is recomputed from the design separately.
 */
export function onConnectEdge(
  design: RecomposedDesign,
  source: string,
  target: string,
  aggregateKeys: Set<string>,
): RecomposedDesign {
  const key = edgeKey(source, target);

  // Pair already exists as an auto edge.
  if (aggregateKeys.has(key)) {
    if (design.hiddenEdges.some((r) => edgeKey(r) === key)) {
      // Un-hide (and clear any stale manual entry for the same pair).
      return {
        ...design,
        hiddenEdges: design.hiddenEdges.filter((r) => edgeKey(r) !== key),
        addedEdges: design.addedEdges.filter((r) => edgeKey(r) !== key),
      };
    }
    return design; // already visible; no-op
  }

  // No auto edge for this pair: add a manual one, clearing a dead hidden entry.
  if (design.addedEdges.some((r) => edgeKey(r) === key)) return design;
  return {
    ...design,
    addedEdges: [...design.addedEdges, { source, target }],
    hiddenEdges: design.hiddenEdges.filter((r) => edgeKey(r) !== key),
  };
}

/**
 * Edge delete event router (#3). The edge id prefix tells us whether the
 * deleted edge was auto or manual; deleting an auto edge also clears any
 * stale manual entry with the same key (the "dual" row of the transition table).
 */
export function onDeleteEdge(
  design: RecomposedDesign,
  edgeId: string,
  aggregateKeys: Set<string>,
): RecomposedDesign {
  const parsed = parseEdgeId(edgeId);
  if (!parsed) return design;
  const key = edgeKey(parsed.source, parsed.target);

  if (parsed.kind === 'manual') {
    return {
      ...design,
      addedEdges: design.addedEdges.filter((r) => edgeKey(r) !== key),
    };
  }

  // Auto edge: hide it (idempotent when already hidden), and clear any stale
  // manual entry with the same key so it cannot "revive" later.
  const alreadyHidden = design.hiddenEdges.some((r) => edgeKey(r) === key);
  const isAggregate = aggregateKeys.has(key);
  return {
    ...design,
    hiddenEdges:
      alreadyHidden || !isAggregate
        ? design.hiddenEdges
        : [...design.hiddenEdges, { source: parsed.source, target: parsed.target }],
    addedEdges: design.addedEdges.filter((r) => edgeKey(r) !== key),
  };
}
