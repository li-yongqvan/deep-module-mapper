/**
 * Graph JSON → React Flow nodes/edges (design doc §5.5).
 *
 * Handles three parser realities that a naive mapping would miss:
 *  - B1: edges may point at `externalModules` ids, not `modules` ids → render
 *    external modules as distinct grey/dashed nodes (D11).
 *  - M2: the same module pair may produce several edges with different `kind`s
 *    → aggregate into one edge, merging labels, keeping all sites (D12).
 *  - M5: an empty `modules` array must not crash React Flow → return empty lists.
 */
import { MarkerType, type Node, type Edge as FlowEdge } from '@xyflow/react';
import type { Graph } from '../api/types';
import { depthScore, type DepthScore } from './depthScore';

export interface ModuleNodeData {
  kind: 'module';
  moduleId: string;
  label: string;
  score: DepthScore;
  portCount: number;
  diagnostics: string[];
  // React Flow v12 requires node/edge data to satisfy Record<string, unknown>.
  [key: string]: unknown;
}

export interface ExternalNodeData {
  kind: 'external';
  externalId: string;
  label: string;
  [key: string]: unknown;
}

export type FlowNode = Node<ModuleNodeData | ExternalNodeData>;

export interface AggregatedEdgeData {
  kinds: string[];
  rawEdges: Graph['edges'];
  // React Flow v12 requires node/edge data to satisfy Record<string, unknown>.
  [key: string]: unknown;
}

export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge<AggregatedEdgeData>[];
  /** True when the scan produced no internal modules (M5). */
  isEmpty: boolean;
}

/**
 * Build a stable node id for an external module, namespaced so it can never
 * collide with a real module id (relative posix path).
 */
export function externalNodeId(id: string): string {
  return `ext:${id}`;
}

/** Convert a parsed Graph into React Flow nodes/edges. */
export function graphToFlow(graph: Graph): FlowGraph {
  const isEmpty = graph.modules.length === 0;

  const diagnosticsByModule = new Map<string, string[]>();
  for (const d of graph.diagnostics) {
    const list = diagnosticsByModule.get(d.moduleId) ?? [];
    list.push(`${d.kind} @${d.line}: ${d.message}`);
    diagnosticsByModule.set(d.moduleId, list);
  }

  // Internal module nodes (rounded rectangles, scored).
  const internalNodes: FlowNode[] = graph.modules.map((module) => {
    const score = depthScore(module.ports);
    return {
      id: module.id,
      type: 'moduleNode',
      position: { x: 0, y: 0 }, // layout.ts assigns real positions
      data: {
        kind: 'module',
        moduleId: module.id,
        label: module.path,
        score,
        portCount: module.ports.length,
        diagnostics: diagnosticsByModule.get(module.id) ?? [],
      },
    };
  });

  // External module nodes (grey dashed, no score).
  const externalNodes: FlowNode[] = graph.externalModules.map((ext) => ({
    id: externalNodeId(ext.id),
    type: 'externalNode',
    position: { x: 0, y: 0 },
    data: { kind: 'external', externalId: ext.id, label: ext.name },
  }));

  const knownNodeIds = new Set<string>([
    ...internalNodes.map((n) => n.id),
    ...externalNodes.map((n) => n.id),
  ]);

  // Map an endpoint to the node id that actually exists in the flow.
  // External modules keep their original `externalModules[].id` in edges, but
  // their nodes are namespaced (`ext:...`), so edges must be remapped (B1).
  const resolveEndpoint = (id: string): string | null => {
    if (knownNodeIds.has(id)) return id;
    const extId = externalNodeId(id);
    return knownNodeIds.has(extId) ? extId : null;
  };

  // Aggregate edges by (source, target); drop dangling edges (B1 backstop).
  const grouped = new Map<string, Graph['edges']>();
  for (const edge of graph.edges) {
    const source = resolveEndpoint(edge.source);
    const target = resolveEndpoint(edge.target);
    if (source === null || target === null) continue;
    const key = `${source}->${target}`;
    const list = grouped.get(key) ?? [];
    list.push(edge);
    grouped.set(key, list);
  }

  const edges: FlowEdge<AggregatedEdgeData>[] = [...grouped.entries()].map(
    ([key, rawEdges], index) => {
      const [source, target] = key.split('->');
      const kinds = [...new Set(rawEdges.map((e) => e.kind))];
      return {
        id: `edge-${index}-${source}->${target}`,
        source,
        target,
        type: 'labeledEdge',
        label: kinds.join(', '),
        data: { kinds, rawEdges },
        markerEnd: { type: MarkerType.ArrowClosed },
      };
    },
  );

  return { nodes: [...internalNodes, ...externalNodes], edges, isEmpty };
}
