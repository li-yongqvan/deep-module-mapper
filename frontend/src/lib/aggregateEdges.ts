/**
 * Shared edge aggregation: group raw Graph edges by resolved (source, target)
 * and emit one React Flow edge per pair (design doc D12 / audit M2). This is
 * the logic that used to live inline in graphToFlow.ts, extracted so the
 * real-view and feature-view transforms share a single implementation
 * (issue #8 D8 / C4). The real-view behavior is the default; the feature view
 * passes options to simplify the edge label (C1).
 */
import { MarkerType, type Edge as FlowEdge } from '@xyflow/react';
import type { Graph } from '../api/types';
import type { AggregatedEdgeData } from './graphToFlow';

/** Resolve a raw edge endpoint to a rendered node id, or null to drop it. */
export type EndpointResolver = (id: string) => string | null;

export interface AggregateEdgesOptions {
  /** Extra fields merged into each edge's data (e.g. feature-view displayLabel). */
  extraData?: Record<string, unknown>;
}

/**
 * Aggregate edges by resolved (source, target), merging `kinds` into the
 * label while keeping every raw edge + call site in `data` for the Inspector.
 * Endpoints that resolve to null are dropped (dangling-edge backstop, B1).
 */
export function aggregateEdges(
  rawEdges: Graph['edges'],
  resolveEndpoint: EndpointResolver,
  options: AggregateEdgesOptions = {},
): FlowEdge<AggregatedEdgeData>[] {
  const grouped = new Map<string, Graph['edges']>();
  for (const edge of rawEdges) {
    const source = resolveEndpoint(edge.source);
    const target = resolveEndpoint(edge.target);
    if (source === null || target === null) continue;
    const key = `${source}->${target}`;
    const list = grouped.get(key) ?? [];
    list.push(edge);
    grouped.set(key, list);
  }

  const extraData = options.extraData ?? {};

  return [...grouped.entries()].map(([key, edges], index) => {
    const [source, target] = key.split('->');
    const kinds = [...new Set(edges.map((e) => e.kind))];
    return {
      id: `edge-${index}-${source}->${target}`,
      source,
      target,
      type: 'labeledEdge',
      label: kinds.join(', '),
      data: { kinds, rawEdges: edges, ...extraData },
      markerEnd: { type: MarkerType.ArrowClosed },
    };
  });
}
