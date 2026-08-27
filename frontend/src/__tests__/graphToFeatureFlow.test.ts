import { describe, expect, it } from 'vitest';
import {
  graphToFeatureFlow,
  THIRD_PARTY_NODE_ID,
} from '../lib/graphToFeatureFlow';
import type { AtomNodeData } from '../lib/graphToFeatureFlow';
import type { Graph } from '../api/types';
// Real self-scan snapshot of deep-module-mapper (issue #8 §2.2).
import deepModuleMapperGraph from './fixtures/deep-module-mapper.graph.json';

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

describe('graphToFeatureFlow', () => {
  it('maps files to atoms and titles nodes with the Chinese name + description', () => {
    const flow = graphToFeatureFlow(baseGraph);
    const atomNodes = flow.nodes.filter((n) => n.data.kind === 'atom');
    expect(atomNodes).toHaveLength(2); // scan-and-parse + scan-api

    const scanParse = atomNodes.find((n) => n.data.kind === 'atom' && n.data.atomId === 'scan-and-parse');
    const data = scanParse?.data as AtomNodeData;
    expect(data.name).toBe('扫描并解析代码库');
    expect(data.description).toContain('读取代码库');
    expect(data.files).toEqual(['parser/_scanner.py', 'parser/_ports.py']);
    expect(scanParse?.id).toBe('atom:scan-and-parse');
  });

  it('hides noise files (tests/fixtures/__init__.py not in an atom)', () => {
    const flow = graphToFeatureFlow(baseGraph);
    // parser/tests/test_edges.py is unassigned → no node for it, but it is counted.
    expect(flow.nodes.some((n) => n.data.kind === 'atom' && n.id === 'atom:scan-and-parse')).toBe(true);
    expect(flow.unassignedCount).toBe(1);
    const ids = flow.nodes.map((n) => n.id);
    expect(ids).not.toContain('parser/tests/test_edges.py');
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
    // Only the cross-atom edge survives.
    const atomEdges = flow.edges.filter(
      (e) => e.source === 'atom:scan-api' && e.target === 'atom:scan-and-parse',
    );
    expect(atomEdges).toHaveLength(1);
    // Same-atom + noise edges dropped.
    expect(flow.edges.some((e) => e.source === 'atom:scan-and-parse' && e.target === 'atom:scan-and-parse')).toBe(false);
    expect(flow.edges).toHaveLength(1);
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

    // Edge to the aggregated node carries a plain Chinese label.
    const toExt = flow.edges.find((e) => e.target === THIRD_PARTY_NODE_ID);
    expect(toExt).toBeDefined();
    if (!toExt) return;
    expect(toExt.label).toBe('依赖');
    const toExtData = toExt.data as unknown as { displayLabel?: string; rawEdges: unknown[] };
    expect(toExtData.displayLabel).toBe('依赖');
    expect(toExtData.rawEdges).toHaveLength(1);
  });

  it('scores an atom from the union of its files ports', () => {
    const flow = graphToFeatureFlow(baseGraph);
    const scanApi = flow.nodes.find((n) => n.data.kind === 'atom' && n.data.atomId === 'scan-api');
    const data = scanApi?.data as AtomNodeData;
    expect(data.portCount).toBe(1); // backend/backend/app.py only
    expect(data.score).toBe('shallow'); // 1 port, line 12 → ratio 12 < 15
  });

  it('exposes member files for drill-down', () => {
    const flow = graphToFeatureFlow(baseGraph);
    const scanApi = flow.nodes.find((n) => n.data.kind === 'atom' && n.data.atomId === 'scan-api');
    const data = scanApi?.data as AtomNodeData;
    expect(data.files).toEqual(['backend/backend/app.py']);
  });

  it('reports isEmpty for an empty modules array (M5)', () => {
    const flow = graphToFeatureFlow({ ...baseGraph, modules: [], ports: [] });
    expect(flow.isEmpty).toBe(true);
    expect(flow.nodes).toHaveLength(0);
    expect(flow.edges).toHaveLength(0);
  });

  it('renders the real deep-module-mapper scan as 2 atoms + 1 third-party node', () => {
    const flow = graphToFeatureFlow(deepModuleMapperGraph as unknown as Graph);
    const atomNodes = flow.nodes.filter((n) => n.data.kind === 'atom');
    const externalNodes = flow.nodes.filter((n) => n.data.kind === 'external');
    expect(flow.nodes).toHaveLength(3); // 2 atoms + 1 third-party (issue #8 goal)
    expect(atomNodes).toHaveLength(2);
    expect(externalNodes).toHaveLength(1);
    expect(flow.unassignedCount).toBe(17);

    const names = atomNodes.map((n) => (n.data as AtomNodeData).name);
    expect(names).toContain('扫描并解析代码库');
    expect(names).toContain('扫描 API 服务');

    // Aggregated edges: scan-api → scan-and-parse, scan-api → 第三方依赖.
    expect(
      flow.edges.some((e) => e.source === 'atom:scan-api' && e.target === 'atom:scan-and-parse'),
    ).toBe(true);
    expect(flow.edges.some((e) => e.source === 'atom:scan-api' && e.target === THIRD_PARTY_NODE_ID)).toBe(true);
    expect(flow.edges).toHaveLength(2);

    // No dangling edges (I2 backstop): every endpoint has a rendered node.
    const known = new Set(flow.nodes.map((n) => n.id));
    for (const e of flow.edges) {
      expect(known.has(e.source)).toBe(true);
      expect(known.has(e.target)).toBe(true);
    }
  });
});
