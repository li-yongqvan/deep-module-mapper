import { describe, expect, it } from 'vitest';
import type { Graph, Edge } from '../api/types';
import {
  checkDependency,
  computeAggregatedModuleEdges,
  edgeKey,
  finalEdges,
  onConnectEdge,
  onDeleteEdge,
  parseEdgeId,
  rejectionMessage,
  shouldShowFeedback,
  REJECTION_FEEDBACK_COOLDOWN_MS,
} from '../lib/recompose/edges';
import type { AggregatedEdgeData } from '../lib/graphToFlow';
import { MarkerType, type Edge as FlowEdge } from '@xyflow/react';
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

/** A synthetic aggregated edge carrying real raw-edge evidence. */
function aggEdge(
  source: string,
  target: string,
  rawEdges: Edge[],
): FlowEdge<AggregatedEdgeData> {
  return {
    id: `module-edge-${source}->${target}`,
    source,
    target,
    type: 'labeledEdge',
    label: 'call',
    data: { kinds: [...new Set(rawEdges.map((e) => e.kind))], rawEdges, displayLabel: '依赖', aggregated: true },
    markerEnd: { type: MarkerType.ArrowClosed },
  };
}

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

describe('checkDependency (draw-to-verify, #18)', () => {
  const raw: Edge[] = [
    {
      source: APP,
      target: SCANNER,
      targetPort: 'scan_codebase',
      kind: 'from_import',
      sites: [{ line: 42 }],
    },
  ];
  const forward = aggEdge('atom:a', 'atom:b', raw);
  const backward = aggEdge('atom:b', 'atom:a', raw);

  it('real: forward pair exists in the aggregated set, with raw-edge evidence', () => {
    const r = checkDependency([forward], 'atom:a', 'atom:b');
    expect(r.status).toBe('real');
    expect(r.evidence).toBeDefined();
    expect(r.evidence!.data!.rawEdges).toHaveLength(1);
    expect(r.evidence!.data!.rawEdges[0]).toMatchObject({
      targetPort: 'scan_codebase',
      kind: 'from_import',
      sites: [{ line: 42 }],
    });
  });

  it('reversed: only the backward pair exists → status reversed with that evidence', () => {
    const r = checkDependency([backward], 'atom:a', 'atom:b');
    expect(r.status).toBe('reversed');
    expect(r.evidence!.source).toBe('atom:b');
    expect(r.evidence!.target).toBe('atom:a');
  });

  it('none: neither direction exists → no evidence', () => {
    const r = checkDependency([forward], 'atom:a', 'atom:c');
    expect(r.status).toBe('none');
    expect(r.evidence).toBeUndefined();
  });

  it('forward wins when both directions exist (direction-sensitive, D5)', () => {
    const r = checkDependency([forward, backward], 'atom:a', 'atom:b');
    expect(r.status).toBe('real');
    expect(r.evidence!.source).toBe('atom:a');
  });
});

describe('rejectionMessage (#18 D4/D5 wording)', () => {
  const namedDesign: RecomposedDesign = {
    version: 1,
    modules: [
      { id: 'mod:scan', name: '扫描模块', description: '', atomIds: [], position: { x: 0, y: 0 }, implicit: false, nameCustomized: false, descriptionCustomized: false },
      { id: 'mod:web', name: 'Web模块', description: '', atomIds: [], position: { x: 0, y: 0 }, implicit: false, nameCustomized: false, descriptionCustomized: false },
    ],
    addedEdges: [],
    hiddenEdges: [],
  };

  it('none: 无任何依赖关系, naming the drawn source/target', () => {
    expect(
      rejectionMessage('none', namedDesign, 'mod:scan', 'mod:web'),
    ).toBe('这两个模块之间无任何依赖关系（扫描模块 的文件里没有任何 import 指向 Web模块）');
  });

  it('reversed: 实际是 B 依赖 A，方向反了', () => {
    expect(
      rejectionMessage('reversed', namedDesign, 'mod:scan', 'mod:web'),
    ).toBe('实际是 Web模块 依赖 扫描模块，方向反了');
  });
});

describe('shouldShowFeedback (#18 §9 Q1 one-shot gate)', () => {
  const sig = 'mod:scan->mod:web|none';
  const now = 1_000_000;

  it('first call for a signature fires', () => {
    expect(shouldShowFeedback(null, sig, now)).toBe(true);
  });

  it('immediate repeat of the same signature is suppressed', () => {
    const gate = { signature: sig, shownAt: now };
    expect(shouldShowFeedback(gate, sig, now + 50)).toBe(false);
  });

  it('a different signature fires even within the cooldown window', () => {
    const gate = { signature: sig, shownAt: now };
    expect(shouldShowFeedback(gate, 'mod:web->mod:scan|reversed', now + 50)).toBe(true);
  });

  it('the same signature fires again after the cooldown elapses', () => {
    const gate = { signature: sig, shownAt: now };
    expect(
      shouldShowFeedback(gate, sig, now + REJECTION_FEEDBACK_COOLDOWN_MS + 1),
    ).toBe(true);
  });
});

describe('finalEdges (zero edges by default + real evidence, #18)', () => {
  const raw: Edge[] = [
    {
      source: APP,
      target: SCANNER,
      targetPort: 'scan_codebase',
      kind: 'call',
      sites: [{ line: 16 }],
    },
  ];
  const real = aggEdge('atom:a', 'atom:b', raw);

  it('renders nothing when no edges were drawn (D1)', () => {
    expect(finalEdges([real], baseDesign)).toHaveLength(0);
  });

  it('renders a drawn edge only when it is a real dependency, carrying its evidence', () => {
    const d: RecomposedDesign = {
      ...baseDesign,
      addedEdges: [{ source: 'atom:a', target: 'atom:b' }],
    };
    const edges = finalEdges([real], d);
    expect(edges).toHaveLength(1);
    const e = edges[0];
    expect(e.id).toBe('manual-edge-atom:a->atom:b');
    expect(e.label).toBe('真实依赖');
    const data = e.data as AggregatedEdgeData;
    expect(data.manual).toBe(false);
    expect(data.rawEdges).toEqual(raw); // real evidence, not []
    expect(data.displayLabel).toBe('真实依赖');
  });

  it('never renders a drawn edge that is not a real dependency', () => {
    const d: RecomposedDesign = {
      ...baseDesign,
      addedEdges: [{ source: 'atom:a', target: 'atom:zzz' }],
    };
    expect(finalEdges([real], d)).toHaveLength(0);
  });
});

describe('onConnectEdge / onDeleteEdge (#18 simplified)', () => {
  it('onConnectEdge pushes a new drawn pair', () => {
    const d = onConnectEdge(baseDesign, 'atom:a', 'atom:b');
    expect(d.addedEdges).toEqual([{ source: 'atom:a', target: 'atom:b' }]);
    expect(d.hiddenEdges).toEqual([]); // never written
  });

  it('onConnectEdge dedupes the same key (drawing twice adds once)', () => {
    const once = onConnectEdge(baseDesign, 'atom:a', 'atom:b');
    const twice = onConnectEdge(once, 'atom:a', 'atom:b');
    expect(twice.addedEdges).toEqual([{ source: 'atom:a', target: 'atom:b' }]);
  });

  it('onDeleteEdge removes a manual edge from addedEdges', () => {
    const base: RecomposedDesign = {
      ...baseDesign,
      addedEdges: [{ source: 'atom:a', target: 'atom:b' }],
    };
    const d = onDeleteEdge(base, 'manual-edge-atom:a->atom:b');
    expect(d.addedEdges).toEqual([]);
  });

  it('onDeleteEdge ignores aggregate/module edge ids and writes no hiddenEdges', () => {
    const d = onDeleteEdge(baseDesign, 'module-edge-atom:a->atom:b');
    expect(d).toEqual(baseDesign);
    expect(d.hiddenEdges).toEqual([]);
  });

  it('onDeleteEdge ignores a non-parseable id', () => {
    const d = onDeleteEdge(baseDesign, 'edge-0-atom:a->atom:b');
    expect(d).toEqual(baseDesign);
  });
});
