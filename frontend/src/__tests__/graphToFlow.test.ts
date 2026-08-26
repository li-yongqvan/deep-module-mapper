import { describe, expect, it } from 'vitest';
import { graphToFlow, externalNodeId } from '../lib/graphToFlow';
import type { Graph } from '../api/types';
// Real scan output from parser/tests/fixtures/sample_pkg (audit M7): stored so
// graphToFlow/render tests run on real data, not hand-written mocks.
import samplePkgGraph from './fixtures/sample_pkg.graph.json';

const baseGraph: Graph = {
  modules: [
    { id: 'pkg/a.py', path: 'pkg/a.py', ports: [{ kind: 'function', name: 'fa', line: 10, signature: 'fa()', params: [] }] },
    { id: 'pkg/b.py', path: 'pkg/b.py', ports: [{ kind: 'function', name: 'fb', line: 100, signature: 'fb()', params: [] }] },
  ],
  ports: [
    { kind: 'function', name: 'fa', line: 10, signature: 'fa()', params: [], moduleId: 'pkg/a.py' },
    { kind: 'function', name: 'fb', line: 100, signature: 'fb()', params: [], moduleId: 'pkg/b.py' },
  ],
  edges: [],
  externalModules: [],
  diagnostics: [],
};

describe('graphToFlow', () => {
  it('renders external modules as nodes (B1) and does not drop their edges', () => {
    const graph: Graph = {
      ...baseGraph,
      edges: [{ source: 'pkg/a.py', target: 'requests', kind: 'import', sites: [{ line: 3 }] }],
      externalModules: [{ id: 'requests', name: 'requests', kind: 'third_party' }],
    };
    const flow = graphToFlow(graph);
    const extNode = flow.nodes.find((n) => n.id === externalNodeId('requests'));
    expect(extNode).toBeDefined();
    expect(extNode?.type).toBe('externalNode');
    // Node counts: 2 internal + 1 external (design doc §8.1).
    const internal = flow.nodes.filter((n) => n.data.kind === 'module');
    const external = flow.nodes.filter((n) => n.data.kind === 'external');
    expect(internal).toHaveLength(2);
    expect(external).toHaveLength(1);
    // The edge to the external module is kept (not dangling).
    expect(flow.edges.some((e) => e.target === externalNodeId('requests'))).toBe(true);
  });

  it('handles the real sample_pkg fixture (B1/M2 on real data, audit M7)', () => {
    const graph = samplePkgGraph as unknown as Graph;
    const flow = graphToFlow(graph);

    // 4 internal modules + 2 external (requests, sample_pkg).
    const internal = flow.nodes.filter((n) => n.data.kind === 'module');
    const external = flow.nodes.filter((n) => n.data.kind === 'external');
    expect(internal).toHaveLength(4);
    expect(external).toHaveLength(2);
    expect(flow.nodes).toHaveLength(6);

    // Real data has 5 edges main.py -> core.py; they aggregate into one.
    const mainToCore = flow.edges.filter(
      (e) => e.source === 'main.py' && e.target === 'core.py',
    );
    expect(mainToCore).toHaveLength(1);
    expect(mainToCore[0]?.data?.rawEdges).toHaveLength(5);

    // Real external edges survive, remapped to ext: node ids.
    const toRequests = flow.edges.filter(
      (e) => e.target === externalNodeId('requests'),
    );
    expect(toRequests.length).toBeGreaterThan(0);

    // No dangling edges (every endpoint resolves to a rendered node).
    const known = new Set(flow.nodes.map((n) => n.id));
    for (const e of flow.edges) {
      expect(known.has(e.source)).toBe(true);
      expect(known.has(e.target)).toBe(true);
    }
  });

  it('aggregates multiple kinds between the same module pair into one edge (M2)', () => {
    const graph: Graph = {
      ...baseGraph,
      edges: [
        { source: 'pkg/a.py', target: 'pkg/b.py', kind: 'import', sites: [{ line: 3 }] },
        { source: 'pkg/a.py', target: 'pkg/b.py', kind: 'call', sites: [{ line: 20 }, { line: 22 }] },
      ],
    };
    const flow = graphToFlow(graph);
    const pairEdges = flow.edges.filter(
      (e) => e.source === 'pkg/a.py' && e.target === 'pkg/b.py',
    );
    expect(pairEdges).toHaveLength(1);
    const aggregated = pairEdges[0];
    expect(aggregated).toBeDefined();
    expect(aggregated?.label).toContain('import');
    expect(aggregated?.label).toContain('call');
    expect(aggregated?.data?.rawEdges).toHaveLength(2);
  });

  it('drops edges whose endpoints have no node (dangling-edge backstop)', () => {
    const graph: Graph = {
      ...baseGraph,
      edges: [{ source: 'pkg/a.py', target: 'ghost.py', kind: 'import', sites: [{ line: 5 }] }],
    };
    const flow = graphToFlow(graph);
    expect(flow.edges).toHaveLength(0);
  });

  it('reports isEmpty when modules is empty (M5)', () => {
    const flow = graphToFlow({ ...baseGraph, modules: [], ports: [] });
    expect(flow.isEmpty).toBe(true);
    expect(flow.nodes).toHaveLength(0);
    expect(flow.edges).toHaveLength(0);
  });

  it('stores score, portCount and diagnostics on module node data', () => {
    const graph: Graph = {
      ...baseGraph,
      diagnostics: [
        { kind: 'unresolved_symbol', moduleId: 'pkg/a.py', line: 30, message: 'unknown X' },
      ],
    };
    const flow = graphToFlow(graph);
    const node = flow.nodes.find((n) => n.id === 'pkg/a.py');
    const data = node?.data as { score: string; portCount: number; diagnostics: string[] };
    expect(data.score).toBe('shallow'); // 1 port, line 10 → ratio 10 < 15
    expect(data.portCount).toBe(1);
    expect(data.diagnostics[0]).toContain('unresolved_symbol');
  });
});
