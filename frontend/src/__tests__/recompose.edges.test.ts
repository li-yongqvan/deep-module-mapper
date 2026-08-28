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
// Grouping is AI-proposed (issue #11), so atom ids and cross-atom pairs below
// are derived from the manifest at runtime — never pinned to a concrete id.
import { atomForFile } from '../manifest/featureAtoms';

const APP = 'backend/backend/app.py';
const SCANNER = 'parser/_scanner.py';
const PORTS = 'parser/_ports.py';
const NOISE = 'parser/tests/test_edges.py';

/** Atom id a file maps to (undefined = noise/unknown). */
const atomOf = (file: string): string | undefined => atomForFile(file)?.id;

const appAtom = atomOf(APP);
const scannerAtom = atomOf(SCANNER);
const portsAtom = atomOf(PORTS);

/** Distinct atoms among baseGraph's production files, in manifest order. */
const baseAtomIds = [
  ...new Set([appAtom, scannerAtom, portsAtom].filter((x): x is string => Boolean(x))),
];

/** Implicit single-atom-module design built from the derived atoms. */
const baseDesign: RecomposedDesign = {
  version: 1,
  modules: baseAtomIds.map((id, i) => ({
    id: `atom:${id}`,
    name: '',
    description: '',
    atomIds: [id],
    position: { x: 0, y: i * 300 },
    implicit: true,
    nameCustomized: false,
    descriptionCustomized: false,
  })),
  addedEdges: [],
  hiddenEdges: [],
};

const baseGraph: Graph = {
  modules: [
    { id: SCANNER, path: SCANNER, ports: [] },
    { id: PORTS, path: PORTS, ports: [] },
    { id: APP, path: APP, ports: [] },
    { id: NOISE, path: NOISE, ports: [] },
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
        { source: APP, target: SCANNER, kind: 'call', sites: [{ line: 16 }] },
        { source: SCANNER, target: PORTS, kind: 'call', sites: [{ line: 45 }] },
        { source: NOISE, target: SCANNER, kind: 'call', sites: [{ line: 3 }] },
        { source: SCANNER, target: NOISE, kind: 'call', sites: [{ line: 7 }] },
      ],
    };
    const edges = computeAggregatedModuleEdges(graph, baseDesign);
    // Noise-file edges never survive any grouping.
    expect(edges.some((e) => `${e.source}${e.target}`.includes('parser/tests/'))).toBe(false);
    // Surviving count = the cross-atom pairs among {app→scanner, scanner→ports},
    // derived from the manifest (same-atom internal edges always drop).
    const crossCount =
      (appAtom && scannerAtom && appAtom !== scannerAtom ? 1 : 0) +
      (scannerAtom && portsAtom && scannerAtom !== portsAtom ? 1 : 0);
    expect(edges).toHaveLength(crossCount);
    // When app and scanner are cross-atom, that edge is exactly one, aggregated.
    if (appAtom && scannerAtom && appAtom !== scannerAtom) {
      expect(edges.filter((e) => e.source === `atom:${appAtom}` && e.target === `atom:${scannerAtom}`)).toHaveLength(1);
    }
  });

  it('merges kinds into the label and keeps raw edges for drill-down', () => {
    const graph: Graph = {
      ...baseGraph,
      edges: [
        { source: APP, target: SCANNER, kind: 'call', sites: [{ line: 16 }] },
        { source: APP, target: PORTS, kind: 'import', sites: [{ line: 3 }] },
      ],
    };
    const edges = computeAggregatedModuleEdges(graph, baseDesign);
    // Both edges leave app.py. They merge into a single (source,target) pair only
    // when scanner and ports share a target atom; otherwise they stay separate.
    for (const e of edges) {
      const data = e.data as { rawEdges: unknown[] };
      expect(data.rawEdges.length).toBeGreaterThan(0); // raw edges preserved
      expect(e.data as { displayLabel?: string }).toMatchObject({ displayLabel: '依赖' });
    }
    if (
      appAtom &&
      scannerAtom &&
      portsAtom &&
      appAtom !== scannerAtom &&
      scannerAtom === portsAtom
    ) {
      // Both edges converge on one target atom → one aggregated edge.
      expect(edges).toHaveLength(1);
      expect(edges[0].label).toContain('call');
      expect(edges[0].label).toContain('import');
      expect((edges[0].data as { rawEdges: unknown[] }).rawEdges).toHaveLength(2);
    }
  });

  it('keeps module -> third-party edges', () => {
    const graph: Graph = {
      ...baseGraph,
      edges: [{ source: APP, target: 'starlette.applications', kind: 'from_import', sites: [{ line: 9 }] }],
      externalModules: [{ id: 'starlette.applications', name: 'starlette.applications', kind: 'third_party' }],
    };
    const edges = computeAggregatedModuleEdges(graph, baseDesign);
    // app.py is a production module → always assigned to a baseDesign module,
    // so its third-party import always aggregates to the third-party node.
    expect(appAtom).toBeDefined();
    const toExt = edges.find((e) => e.target === THIRD_PARTY_NODE_ID);
    expect(toExt).toBeDefined();
    if (toExt) expect(toExt.id).toBe(`module-edge-atom:${appAtom}->${THIRD_PARTY_NODE_ID}`);
  });

  it('aggregates the real deep-module-mapper scan into valid cross-module edges', () => {
    const edges = computeAggregatedModuleEdges(
      deepModuleMapperGraph as unknown as Graph,
      baseDesign,
    );
    // Every endpoint is a rendered node: an atom-module in the design, or the
    // third-party node (never a dangling/noise endpoint).
    for (const e of edges) {
      expect(baseDesign.modules.some((m) => m.id === e.source)).toBe(true);
      expect(
        baseDesign.modules.some((m) => m.id === e.target) || e.target === THIRD_PARTY_NODE_ID,
      ).toBe(true);
    }
    // The base atoms are linked if the scan really edges them together, and the
    // backend (web-api-service) imports third-party libraries (starlette/uvicorn).
    if (appAtom && scannerAtom && appAtom !== scannerAtom) {
      expect(
        edges.some((e) => e.source === `atom:${appAtom}` && e.target === `atom:${scannerAtom}`),
      ).toBe(true);
    }
    if (appAtom) {
      expect(
        edges.some((e) => e.source === `atom:${appAtom}` && e.target === THIRD_PARTY_NODE_ID),
      ).toBe(true);
    }
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
    const d: RecomposedDesign = { ...baseDesign, hiddenEdges: [{ source: 'atom:a', target: 'atom:b' }] };
    const edges = finalEdges([aggEdge as never], d);
    expect(edges).toHaveLength(0);
  });

  it('adds manual edges with the fixed shape (#1)', () => {
    const d: RecomposedDesign = {
      ...baseDesign,
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
      ...baseDesign,
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
    const d = onDeleteEdge(baseDesign, 'module-edge-atom:a->atom:b', aggKeys);
    expect(d.hiddenEdges).toEqual([{ source: 'atom:a', target: 'atom:b' }]);
  });

  it('delete manual edge -> addedEdges -= key', () => {
    const base: RecomposedDesign = {
      ...baseDesign,
      addedEdges: [{ source: 'atom:x', target: 'atom:y' }],
    };
    const d = onDeleteEdge(base, 'manual-edge-atom:x->atom:y', aggKeys);
    expect(d.addedEdges).toEqual([]);
  });

  it('dual edge delete -> hiddenEdges += key AND addedEdges -= key', () => {
    const base: RecomposedDesign = {
      ...baseDesign,
      hiddenEdges: [{ source: 'atom:a', target: 'atom:b' }],
      addedEdges: [{ source: 'atom:a', target: 'atom:b' }],
    };
    const d = onDeleteEdge(base, 'module-edge-atom:a->atom:b', aggKeys);
    expect(d.hiddenEdges).toEqual([{ source: 'atom:a', target: 'atom:b' }]);
    expect(d.addedEdges).toEqual([]);
  });

  it('connect A->B when hidden + aggregate exists -> unhide', () => {
    const base: RecomposedDesign = {
      ...baseDesign,
      hiddenEdges: [{ source: 'atom:a', target: 'atom:b' }],
    };
    const d = onConnectEdge(base, 'atom:a', 'atom:b', aggKeys);
    expect(d.hiddenEdges).toEqual([]);
  });

  it('connect A->B with no aggregate -> addedEdges += key, dead hidden cleared', () => {
    const base: RecomposedDesign = {
      ...baseDesign,
      hiddenEdges: [{ source: 'atom:x', target: 'atom:y' }],
    };
    const d = onConnectEdge(base, 'atom:x', 'atom:y', aggKeys);
    expect(d.addedEdges).toEqual([{ source: 'atom:x', target: 'atom:y' }]);
    expect(d.hiddenEdges).toEqual([]);
  });

  it('connect a visible aggregate pair -> no-op', () => {
    const d = onConnectEdge(baseDesign, 'atom:a', 'atom:b', aggKeys);
    expect(d.addedEdges).toEqual([]);
    expect(d.hiddenEdges).toEqual([]);
  });

  it('delete a non-parseable edge id -> no-op', () => {
    const d = onDeleteEdge(baseDesign, 'edge-0-atom:a->atom:b', aggKeys);
    expect(d).toEqual(baseDesign);
  });

  it('unhide also clears a stale manual entry for the same pair', () => {
    const base: RecomposedDesign = {
      ...baseDesign,
      hiddenEdges: [{ source: 'atom:a', target: 'atom:b' }],
      addedEdges: [{ source: 'atom:a', target: 'atom:b' }],
    };
    const d = onConnectEdge(base, 'atom:a', 'atom:b', aggKeys);
    expect(d.hiddenEdges).toEqual([]);
    expect(d.addedEdges).toEqual([]);
  });
});
