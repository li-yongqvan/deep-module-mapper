import { describe, expect, it } from 'vitest';
import {
  graphToFeatureFlow,
  THIRD_PARTY_NODE_ID,
} from '../lib/graphToFeatureFlow';
import type { AtomNodeData } from '../lib/graphToFeatureFlow';
import { depthScore } from '../lib/depthScore';
import type { Graph } from '../api/types';
// Real self-scan snapshot of deep-module-mapper (issue #8 §2.2).
import deepModuleMapperGraph from './fixtures/deep-module-mapper.graph.json';
// Grouping is AI-proposed (issue #11), so every expectation is derived from the
// manifest at runtime — never pinned to a specific atom id/name/grouping.
import { atomForFile, FEATURE_ATOMS } from '../manifest/featureAtoms';

const baseGraph: Graph = {
  modules: [
    { id: 'parser/_scanner.py', path: 'parser/_scanner.py', ports: [{ kind: 'function', name: 'scan', line: 10, signature: 'scan()', params: [] }] },
    { id: 'parser/_ports.py', path: 'parser/_ports.py', ports: [{ kind: 'function', name: 'extract', line: 20, signature: 'extract()', params: [] }] },
    { id: 'backend/backend/app.py', path: 'backend/backend/app.py', ports: [{ kind: 'function', name: 'route', line: 12, signature: 'route()', params: [] }] },
    { id: 'parser/tests/test_edges.py', path: 'parser/tests/test_edges.py', ports: [{ kind: 'function', name: 'test', line: 5, signature: 'test()', params: [] }] },
  ],
  ports: [],
  edges: [],
  externalModules: [],
  diagnostics: [],
};

/** Atoms that match ≥1 module of a graph, in manifest order. */
const atomIdsFor = (graph: Graph): string[] =>
  FEATURE_ATOMS.filter((a) => graph.modules.some((m) => atomForFile(m.id)?.id === a.id)).map(
    (a) => a.id,
  );

// graphToFeatureFlow pushes files in graph-module order (same loop below), so
// this helper must mirror that order — sorting would mismatch the component.
const filesForAtom = (graph: Graph, atomId: string): string[] =>
  graph.modules.filter((m) => atomForFile(m.id)?.id === atomId).map((m) => m.id);

describe('graphToFeatureFlow', () => {
  it('maps files to atoms and titles nodes with the Chinese name + description', () => {
    const flow = graphToFeatureFlow(baseGraph);
    const atomNodes = flow.nodes.filter((n) => n.data.kind === 'atom');
    const expectedAtomIds = atomIdsFor(baseGraph);
    expect(atomNodes).toHaveLength(expectedAtomIds.length);

    for (const node of atomNodes) {
      const data = node.data as AtomNodeData;
      const atom = FEATURE_ATOMS.find((a) => a.id === data.atomId);
      expect(atom, `node atomId ${data.atomId} must exist in the manifest`).toBeDefined();
      if (!atom) continue;
      expect(data.name).toBe(atom.name); // title from the manifest
      expect(data.description).toBe(atom.description);
      expect(data.files).toEqual(filesForAtom(baseGraph, atom.id)); // this-graph members
      expect(node.id).toBe(`atom:${atom.id}`); // node id prefix contract (audit I2)
    }
  });

  it('hides noise files (tests/fixtures not in any atom)', () => {
    const flow = graphToFeatureFlow(baseGraph);
    const unassigned = baseGraph.modules.filter((m) => !atomForFile(m.id));
    expect(flow.unassignedCount).toBe(unassigned.length);
    expect(flow.nodes.some((n) => n.data.kind === 'atom' && n.id.startsWith('atom:'))).toBe(true);
    const ids = flow.nodes.map((n) => n.id);
    expect(ids).not.toContain('parser/tests/test_edges.py'); // never a rendered node
  });

  it('aggregates edges: cross-atom → one edge, same-atom → dropped, noise → dropped', () => {
    const graph: Graph = {
      ...baseGraph,
      edges: [
        { source: 'backend/backend/app.py', target: 'parser/_scanner.py', kind: 'call', sites: [{ line: 16 }] },
        { source: 'parser/_scanner.py', target: 'parser/_ports.py', kind: 'call', sites: [{ line: 45 }] },
        { source: 'parser/tests/test_edges.py', target: 'parser/_scanner.py', kind: 'call', sites: [{ line: 3 }] },
        { source: 'parser/_scanner.py', target: 'parser/tests/test_edges.py', kind: 'call', sites: [{ line: 7 }] },
      ],
    };
    const flow = graphToFeatureFlow(graph);
    const sAtom = atomForFile('backend/backend/app.py')?.id;
    const tAtom = atomForFile('parser/_scanner.py')?.id;
    const isCrossAtom = Boolean(sAtom && tAtom && sAtom !== tAtom);

    // Same-atom + noise edges are dropped regardless of grouping.
    expect(flow.edges.some((e) => e.source === e.target && e.source.startsWith('atom:'))).toBe(false);
    expect(
      flow.edges.some(
        (e) => e.source === 'parser/tests/test_edges.py' || e.target === 'parser/tests/test_edges.py',
      ),
    ).toBe(false);

    if (isCrossAtom) {
      // The cross-atom app.py→scanner.py edge survives as exactly one atom edge.
      expect(
        flow.edges.filter((e) => e.source === `atom:${sAtom}` && e.target === `atom:${tAtom}`),
      ).toHaveLength(1);
      expect(flow.edges).toHaveLength(1);
    } else {
      // When the manifest groups both files into one atom, nothing survives.
      expect(flow.edges).toHaveLength(0);
    }
  });

  it('folds third-party imports into one node and keeps a non-developer edge label (C1/I2)', () => {
    const graph: Graph = {
      ...baseGraph,
      edges: [
        { source: 'backend/backend/app.py', target: 'starlette.applications', kind: 'from_import', sites: [{ line: 9 }] },
        { source: 'backend/backend/app.py', target: 'parser/_scanner.py', kind: 'call', sites: [{ line: 16 }] },
      ],
      externalModules: [{ id: 'starlette.applications', name: 'starlette.applications', kind: 'third_party' }],
    };
    const flow = graphToFeatureFlow(graph);
    const extNode = flow.nodes.find((n) => n.id === THIRD_PARTY_NODE_ID);
    // app.py is a production module → always assigned (C2) and imports starlette.
    expect(extNode).toBeDefined();
    if (!extNode) return;
    expect(extNode.data.kind).toBe('external');
    const extData = extNode.data as unknown as {
      externalId: string;
      label: string;
      externalNames: string[];
    };
    expect(extData.externalId).toBe(THIRD_PARTY_NODE_ID); // required field (I2)
    expect(extData.label).toBe('第三方依赖');
    expect(extData.externalNames).toEqual(['starlette.applications']);

    // Edge to the aggregated node: canvas label comes from data.displayLabel (C1),
    // while edge.label keeps the merged kinds for the Inspector drill-down.
    const toExt = flow.edges.find((e) => e.target === THIRD_PARTY_NODE_ID);
    expect(toExt).toBeDefined();
    if (!toExt) return;
    expect(toExt.label).toBe('from_import');
    const toExtData = toExt.data as unknown as { displayLabel?: string; rawEdges: unknown[] };
    expect(toExtData.displayLabel).toBe('依赖');
    expect(toExtData.rawEdges).toHaveLength(1);
  });

  it('scores an atom from the union of its files ports', () => {
    const flow = graphToFeatureFlow(baseGraph);
    for (const node of flow.nodes) {
      if (node.data.kind !== 'atom') continue;
      const data = node.data as AtomNodeData;
      const members = baseGraph.modules.filter((m) => atomForFile(m.id)?.id === data.atomId);
      const ports = members.flatMap((m) => m.ports);
      expect(data.portCount).toBe(ports.length); // union, not one-file-only
      expect(data.score).toBe(depthScore(ports));
    }
  });

  it('exposes member files for drill-down', () => {
    const flow = graphToFeatureFlow(baseGraph);
    for (const node of flow.nodes) {
      if (node.data.kind !== 'atom') continue;
      const data = node.data as AtomNodeData;
      expect(data.files).toEqual(filesForAtom(baseGraph, data.atomId));
    }
  });

  it('reports isEmpty for an empty modules array (M5)', () => {
    const flow = graphToFeatureFlow({ ...baseGraph, modules: [], ports: [] });
    expect(flow.isEmpty).toBe(true);
    expect(flow.nodes).toHaveLength(0);
    expect(flow.edges).toHaveLength(0);
  });

  it('renders the real deep-module-mapper scan with every module accounted for', () => {
    const graph = deepModuleMapperGraph as unknown as Graph;
    const flow = graphToFeatureFlow(graph);
    const assignedAtomIds = atomIdsFor(graph);
    const atomNodes = flow.nodes.filter((n) => n.data.kind === 'atom');
    const externalNodes = flow.nodes.filter((n) => n.data.kind === 'external');

    expect(atomNodes).toHaveLength(assignedAtomIds.length);
    expect(externalNodes.length).toBeLessThanOrEqual(1); // 0 or 1 aggregated node
    expect(flow.nodes).toHaveLength(atomNodes.length + externalNodes.length);

    // unassignedCount is the file-modules hidden as noise — derived, not pinned
    // to a fixed number (F5): any manifest change must not hard-code it here.
    const unassigned = graph.modules.filter((m) => !atomForFile(m.id));
    expect(flow.unassignedCount).toBe(unassigned.length);

    const names = atomNodes.map((n) => (n.data as AtomNodeData).name);
    for (const atom of FEATURE_ATOMS) {
      if (assignedAtomIds.includes(atom.id)) {
        expect(names).toContain(atom.name);
      }
    }

    // No dangling edges (I2 backstop): every endpoint has a rendered node.
    const known = new Set(flow.nodes.map((n) => n.id));
    for (const e of flow.edges) {
      expect(known.has(e.source)).toBe(true);
      expect(known.has(e.target)).toBe(true);
    }
    // Unique node ids.
    expect(known.size).toBe(flow.nodes.length);
  });
});
