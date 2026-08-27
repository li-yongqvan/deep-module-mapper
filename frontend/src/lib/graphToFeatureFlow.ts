/**
 * Feature-view transform (issue #8): aggregate file-level modules into
 * functional-atom nodes (Chinese name + one-line description), hide noise
 * (tests/fixtures/`__init__.py` not in any named atom), aggregate dependencies
 * at the atom level, and fold third-party imports into one "第三方依赖" node.
 *
 * Sibling of graphToFlow.ts (real view). The grouping source of truth is the
 * hand-maintained manifest (src/manifest/feature-atoms.json); AI aggregation
 * (#11) will later produce the same format as a drop-in replacement.
 */
import type { Node, Edge as FlowEdge } from '@xyflow/react';
import type { Graph } from '../api/types';
import { atomForFile, FEATURE_ATOMS } from '../manifest/featureAtoms';
import { depthScore, type DepthScore } from './depthScore';
import { aggregateEdges } from './aggregateEdges';
import type { AggregatedEdgeData, ExternalNodeData } from './graphToFlow';

/** Pinned node id for the aggregated third-party node (audit I2). */
export const THIRD_PARTY_NODE_ID = 'ext:third-party';

export interface AtomNodeData {
  kind: 'atom';
  atomId: string;
  name: string; // Chinese name, node title
  description: string; // one-line Chinese description
  files: string[]; // member module ids, for drill-down
  portCount: number;
  score: DepthScore;
  // React Flow v12 requires node/edge data to satisfy Record<string, unknown>.
  [key: string]: unknown;
}

export type FeatureFlowNode = Node<AtomNodeData | ExternalNodeData>;

export interface FeatureFlowGraph {
  nodes: FeatureFlowNode[];
  edges: FlowEdge<AggregatedEdgeData>[];
  isEmpty: boolean;
  /** File-modules hidden as unassigned noise (C3: surfaced in the UI hint). */
  unassignedCount: number;
}

export function graphToFeatureFlow(graph: Graph): FeatureFlowGraph {
  const isEmpty = graph.modules.length === 0;

  // Group modules by atom; anything unassigned is noise (hidden by default).
  const modulesByAtom = new Map<
    string,
    { files: string[]; ports: Graph['modules'][number]['ports'] }
  >();
  const moduleToAtom = new Map<string, string>();
  let unassignedCount = 0;
  for (const m of graph.modules) {
    const atom = atomForFile(m.id);
    if (!atom) {
      unassignedCount += 1;
      continue;
    }
    moduleToAtom.set(m.id, atom.id);
    const bucket = modulesByAtom.get(atom.id) ?? { files: [], ports: [] };
    bucket.files.push(m.id);
    bucket.ports.push(...m.ports);
    modulesByAtom.set(atom.id, bucket);
  }

  // One node per atom that matched ≥1 file in THIS graph.
  const atomNodes: FeatureFlowNode[] = [];
  for (const atom of FEATURE_ATOMS) {
    const bucket = modulesByAtom.get(atom.id);
    if (!bucket) continue; // atom with zero matched files → no node
    const score = depthScore(bucket.ports);
    atomNodes.push({
      id: `atom:${atom.id}`,
      type: 'atomNode',
      position: { x: 0, y: 0 }, // layout.ts assigns real positions
      data: {
        kind: 'atom',
        atomId: atom.id,
        name: atom.name,
        description: atom.description,
        files: bucket.files,
        portCount: bucket.ports.length,
        score,
      },
    });
  }

  // Third-party imports used by atom files fold into one grey node (D2).
  const externalIds = new Set(graph.externalModules.map((x) => x.id));
  const referencedExternal = new Set<string>();
  for (const e of graph.edges) {
    if (moduleToAtom.has(e.source) && externalIds.has(e.target)) {
      referencedExternal.add(e.target);
    }
    if (moduleToAtom.has(e.target) && externalIds.has(e.source)) {
      referencedExternal.add(e.source);
    }
  }
  const hasThirdParty = referencedExternal.size > 0;
  const thirdPartyNode: FeatureFlowNode = {
    id: THIRD_PARTY_NODE_ID,
    type: 'externalNode',
    position: { x: 0, y: 0 },
    data: {
      kind: 'external',
      externalId: THIRD_PARTY_NODE_ID, // required field (audit I2)
      label: '第三方依赖',
      externalNames: [...referencedExternal].sort(),
    },
  };
  const nodes: FeatureFlowNode[] = hasThirdParty
    ? [...atomNodes, thirdPartyNode]
    : atomNodes;

  // Atom-level edges: cross-atom file deps → atom edge; same-atom → internal
  // (dropped); atom↔third-party → edge to/from the aggregated node; any
  // endpoint in a noise file → dropped.
  const resolveEndpoint = (id: string): string | null => {
    const atomId = moduleToAtom.get(id);
    if (atomId) return `atom:${atomId}`;
    if (hasThirdParty && externalIds.has(id)) return THIRD_PARTY_NODE_ID;
    return null;
  };
  // Drop same-atom internal edges before aggregation: a cross-atom edge exists
  // iff a file in one atom depends on a file in the other. External-touching
  // edges pass through; noise endpoints are dropped by the resolver.
  const atomLevelEdges = graph.edges.filter((e) => {
    const sAtom = moduleToAtom.get(e.source);
    const tAtom = moduleToAtom.get(e.target);
    return !(sAtom && tAtom && sAtom === tAtom);
  });
  // Non-developer edge label (C1): the canvas renders `data.displayLabel` = 「依赖」
  // (LabeledEdge), while `edge.label` keeps the merged kinds for Inspector drill-down.
  const edges = aggregateEdges(atomLevelEdges, resolveEndpoint, {
    extraData: { displayLabel: '依赖' },
  });

  return { nodes, edges, isEmpty, unassignedCount };
}
