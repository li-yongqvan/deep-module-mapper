import { describe, expect, it } from 'vitest';
import type { Graph } from '../api/types';
import {
  computeAggregatedModuleEdges,
  edgeKey,
  finalEdges,
  onConnectEdge,
  onDeleteEdge,
  parseEdgeId,
} from '../lib/recompose/edges';
import { THIRD_PARTY_NODE_ID } from '../lib/graphToFeatureFlow';
import type { RecomposedDesign } from '../lib/recompose/types';
// Real self-scan snapshot of deep-module-mapper.
import deepModuleMapperGraph from './fixtures/deep-module-mapper.graph.json';

const atoms = {
  scanParse: 'scan-and-parse',
  scanApi: 'scan-api',
};

/** Design with the two manifest atoms as separate implicit modules. */
const twoModuleDesign: RecomposedDesign = {
  version: 1,
  modules: [
    {
      id: `atom:${atoms.scanApi}`,
      name: '扫描 API 服务',
      description: '',
      atomIds: [atoms.scanApi],
      position: { x: 0, y: 0 },
      implicit: true,
      nameCustomized: false,
      descriptionCustomized: false,
    },
    {
      id: `atom:${atoms.scanParse}`,
      name: '扫描并解析代码库',
      description: '',
      atomIds: [atoms.scanParse],
      position: { x: 0, y: 300 },
      implicit: true,
      nameCustomized: false,
      descriptionCustomized: false,
    },
  ],
  addedEdges: [],
  hiddenEdges: [],
};

const baseGraph: Graph = {
  modules: [
    { id: 'parser/_scanner.py', path: 'parser/_scanner.py', ports: [] },
    { id: 'parser/_ports.py', path: 'parser/_ports.py', ports: [] },
    { id: 'backend/backend/app.py', path: 'backend/backend/app.py', ports: [] },
    { id: 'parser/tests/test_edges.py', path: 'parser/tests/test_edges.py', ports: [] },
  ],
  ports: [],
  edges: [],
  externalModules: [],
  diagnostics: [],
};

describe('edgeKey / parseEdgeId', () => {
  it('round-trips both edge id schemes', () => {
    expect(edgeKey('atom:a', 'atom:b')).toBe('atom:a->atom:b');
    expect(edgeKey({ source: 'atom:a', target: 'atom:b' })).toBe('atom:a->atom:b');
    expect(parseEdgeId('module-edge-atom:a->atom:b')).toEqual({
      kind: 'module',
      source: 'atom:a',
      target: 'atom:b',
    });
    expect(parseEdgeId('manual-edge-ext:third-party->atom:a')).toEqual({
      kind: 'manual',
      source: 'ext:third-party',
      target: 'atom:a',
    });
    expect(parseEdgeId('edge-0-atom:a->atom:b')).toBeNull(); // aggregateEdges-style id
  });
});

describe('computeAggregatedModuleEdges', () => {
  it('drops same-module internal edges and noise-file edges, keeps cross-module', () => {
    const graph: Graph = {
      ...baseGraph,
      edges: [
        { source: 'backend/backend/app.py', target: 'parser/_scanner.py', kind: 'call', sites: [{ line: 16 }] },
        { source: 'parser/_scanner.py', target: 'parser/_ports.py', kind: 'call', sites: [{ line: 45 }] },
        { source: 'parser/tests/test_edges.py', target: 'parser/_scanner.py', kind: 'call', sites: [{ line: 3 }] },
        { source: 'parser/_scanner.py', target: 'parser/tests/test_edges.py', kind: 'call', sites: [{ line: 7 }] },
      ],
    };
    const edges = computeAggregatedModuleEdges(graph, twoModuleDesign);
    expect(edges).toHaveLength(1);
    expect(edges[0].id).toBe(`module-edge-atom:${atoms.scanApi}->atom:${atoms.scanParse}`);
    expect(edges[0].source).toBe(`atom:${atoms.scanApi}`);
    expect(edges[0].target).toBe(`atom:${atoms.scanParse}`);
  });

  it('merges kinds into the label and keeps raw edges for drill-down', () => {
    const graph: Graph = {
      ...baseGraph,
      edges: [
        { source: 'backend/backend/app.py', target: 'parser/_scanner.py', kind: 'call', sites: [{ line: 16 }] },
        { source: 'backend/backend/app.py', target: 'parser/_ports.py', kind: 'import', sites: [{ line: 3 }] },
      ],
    };
    const edges = computeAggregatedModuleEdges(graph, twoModuleDesign);
    expect(edges).toHaveLength(1);
    expect(edges[0].label).toContain('call');
    expect(edges[0].label).toContain('import');
    const data = edges[0].data as { displayLabel?: string; rawEdges: unknown[] };
    expect(data.displayLabel).toBe('依赖');
    expect(data.rawEdges).toHaveLength(2);
  });

  it('keeps module -> third-party edges', () => {
    const graph: Graph = {
      ...baseGraph,
      edges: [
        { source: 'backend/backend/app.py', target: 'starlette.applications', kind: 'from_import', sites: [{ line: 9 }] },
      ],
      externalModules: [{ id: 'starlette.applications', name: 'starlette.applications', kind: 'third_party' }],
    };
    const edges = computeAggregatedModuleEdges(graph, twoModuleDesign);
    expect(edges.some((e) => e.target === THIRD_PARTY_NODE_ID)).toBe(true);
    expect(edges[0].id).toBe(`module-edge-atom:${atoms.scanApi}->${THIRD_PARTY_NODE_ID}`);
  });

  it('aggregates the real deep-module-mapper scan to 2 module edges (1 cross + 1 to third-party)', () => {
    const edges = computeAggregatedModuleEdges(
      deepModuleMapperGraph as unknown as Graph,
      twoModuleDesign,
    );
    expect(
      edges.some((e) => e.source === `atom:${atoms.scanApi}` && e.target === `atom:${atoms.scanParse}`),
    ).toBe(true);
    expect(edges.some((e) => e.source === `atom:${atoms.scanApi}` && e.target === THIRD_PARTY_NODE_ID)).toBe(true);
    expect(edges).toHaveLength(2);
  });
});

describe('finalEdges', () => {
  const aggEdge = {
    id: 'module-edge-atom:a->atom:b',
    source: 'atom:a',
    target: 'atom:b',
    type: 'labeledEdge',
    label: 'call',
    data: { kinds: ['call'], rawEdges: [], displayLabel: '依赖', aggregated: true },
  };

  it('hides auto edges that are in hiddenEdges', () => {
    const d: RecomposedDesign = { ...twoModuleDesign, hiddenEdges: [{ source: 'atom:a', target: 'atom:b' }] };
    const edges = finalEdges([aggEdge as never], d);
    expect(edges).toHaveLength(0);
  });

  it('adds manual edges with the fixed shape (#1)', () => {
    const d: RecomposedDesign = {
      ...twoModuleDesign,
      addedEdges: [{ source: 'atom:x', target: 'atom:y' }],
    };
    const edges = finalEdges([aggEdge as never], d);
    const manual = edges.find((e) => e.id === 'manual-edge-atom:x->atom:y');
    expect(manual).toBeDefined();
    if (!manual) return;
    expect(manual.source).toBe('atom:x');
    expect(manual.type).toBe('labeledEdge');
    const data = manual.data as Record<string, unknown>;
    expect(data.manual).toBe(true);
    expect(data.kinds).toEqual([]);
    expect(data.rawEdges).toEqual([]);
    expect(data.displayLabel).toBe('手动');
  });

  it('lets an auto edge win the same key as a manual one', () => {
    const d: RecomposedDesign = {
      ...twoModuleDesign,
      addedEdges: [{ source: 'atom:a', target: 'atom:b' }],
    };
    const edges = finalEdges([aggEdge as never], d);
    expect(edges).toHaveLength(1);
    expect(edges[0].id).toBe('module-edge-atom:a->atom:b');
  });
});

describe('edge transition table (#3)', () => {
  const aggKeys = new Set(['atom:a->atom:b']);

  it('delete aggregated edge -> hiddenEdges += key', () => {
    const d = onDeleteEdge(twoModuleDesign, 'module-edge-atom:a->atom:b', aggKeys);
    expect(d.hiddenEdges).toEqual([{ source: 'atom:a', target: 'atom:b' }]);
  });

  it('delete manual edge -> addedEdges -= key', () => {
    const base: RecomposedDesign = {
      ...twoModuleDesign,
      addedEdges: [{ source: 'atom:x', target: 'atom:y' }],
    };
    const d = onDeleteEdge(base, 'manual-edge-atom:x->atom:y', aggKeys);
    expect(d.addedEdges).toEqual([]);
  });

  it('dual edge delete -> hiddenEdges += key AND addedEdges -= key', () => {
    const base: RecomposedDesign = {
      ...twoModuleDesign,
      hiddenEdges: [{ source: 'atom:a', target: 'atom:b' }],
      addedEdges: [{ source: 'atom:a', target: 'atom:b' }],
    };
    const d = onDeleteEdge(base, 'module-edge-atom:a->atom:b', aggKeys);
    expect(d.hiddenEdges).toEqual([{ source: 'atom:a', target: 'atom:b' }]);
    expect(d.addedEdges).toEqual([]);
  });

  it('connect A->B when hidden + aggregate exists -> unhide', () => {
    const base: RecomposedDesign = {
      ...twoModuleDesign,
      hiddenEdges: [{ source: 'atom:a', target: 'atom:b' }],
    };
    const d = onConnectEdge(base, 'atom:a', 'atom:b', aggKeys);
    expect(d.hiddenEdges).toEqual([]);
  });

  it('connect A->B with no aggregate -> addedEdges += key, dead hidden cleared', () => {
    const base: RecomposedDesign = {
      ...twoModuleDesign,
      hiddenEdges: [{ source: 'atom:x', target: 'atom:y' }],
    };
    const d = onConnectEdge(base, 'atom:x', 'atom:y', aggKeys);
    expect(d.addedEdges).toEqual([{ source: 'atom:x', target: 'atom:y' }]);
    expect(d.hiddenEdges).toEqual([]);
  });

  it('connect a visible aggregate pair -> no-op', () => {
    const d = onConnectEdge(twoModuleDesign, 'atom:a', 'atom:b', aggKeys);
    expect(d.addedEdges).toEqual([]);
    expect(d.hiddenEdges).toEqual([]);
  });

  it('delete a non-parseable edge id -> no-op', () => {
    const d = onDeleteEdge(twoModuleDesign, 'edge-0-atom:a->atom:b', aggKeys);
    expect(d).toEqual(twoModuleDesign);
  });

  it('unhide also clears a stale manual entry for the same pair', () => {
    const base: RecomposedDesign = {
      ...twoModuleDesign,
      hiddenEdges: [{ source: 'atom:a', target: 'atom:b' }],
      addedEdges: [{ source: 'atom:a', target: 'atom:b' }],
    };
    const d = onConnectEdge(base, 'atom:a', 'atom:b', aggKeys);
    expect(d.hiddenEdges).toEqual([]);
    expect(d.addedEdges).toEqual([]);
  });
});
