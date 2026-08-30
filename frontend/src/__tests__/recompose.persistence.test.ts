import { describe, expect, it, beforeEach } from 'vitest';
import type { FeatureFlowGraph } from '../lib/graphToFeatureFlow';
import type { Graph } from '../api/types';
import {
  clearDesign,
  loadDesign,
  parseDesign,
  sanitizeDesign,
  saveDesign,
  storageKey,
} from '../lib/recompose/persistence';
import { initialDesign } from '../lib/recompose/derive';
import type { RecomposedDesign } from '../lib/recompose/types';

// Real manifest atoms (issue #11 grouping) — atomForFile resolves only these
// files, so every fixture edge must use them or the aggregated set is empty.
const WEB = 'web-api-service'; // app.py / models.py / scanner.py / store.py
const SCAN = 'codebase-scanning'; // parser/*.py
const AGG = 'aggregation-orchestration'; // backend/backend/aggregate/{init,main,config,runner,report}.py

const FILE_WEB = 'backend/backend/app.py';
const FILE_SCAN = 'parser/_scanner.py';
const FILE_AGG = 'backend/backend/aggregate/runner.py';

const featureFlow: FeatureFlowGraph = {
  nodes: [
    { id: `atom:${WEB}`, type: 'atomNode', position: { x: 0, y: 0 }, data: { kind: 'atom', atomId: WEB, name: 'Web服务接口', description: '提供扫描、状态和图查询接口', files: [FILE_WEB], portCount: 1, score: 'shallow' } },
    { id: `atom:${SCAN}`, type: 'atomNode', position: { x: 0, y: 0 }, data: { kind: 'atom', atomId: SCAN, name: '代码库扫描解析', description: '扫描代码库并构建模块依赖图', files: [FILE_SCAN], portCount: 1, score: 'shallow' } },
    { id: `atom:${AGG}`, type: 'atomNode', position: { x: 0, y: 0 }, data: { kind: 'atom', atomId: AGG, name: '聚合流程编排', description: '编排AI聚合流程并处理配置与报告', files: [FILE_AGG], portCount: 1, score: 'shallow' } },
  ],
  edges: [],
  isEmpty: false,
  unassignedCount: 0,
};

/** Graph where app.py (Web) really imports _scanner.py (Scan): one real edge. */
const graph: Graph = {
  modules: [
    { id: FILE_WEB, path: FILE_WEB, ports: [] },
    { id: FILE_SCAN, path: FILE_SCAN, ports: [] },
    { id: FILE_AGG, path: FILE_AGG, ports: [] },
  ],
  ports: [],
  edges: [{ source: FILE_WEB, target: FILE_SCAN, kind: 'from_import', sites: [{ line: 7 }] }],
  externalModules: [],
  diagnostics: [],
};

const path = 'C:\\work\\my-repo';

beforeEach(() => {
  window.localStorage.clear();
});

describe('storageKey', () => {
  it('encodes the path so backslashes are safe', () => {
    expect(storageKey(path)).toContain('dmm:recompose:v1:');
    expect(storageKey(path)).not.toContain('\\');
  });
});

describe('save/load round trip', () => {
  it('persists and restores a design under the path key', () => {
    const d = initialDesign(featureFlow);
    saveDesign(path, d);
    expect(loadDesign(path)).toEqual(d);
  });

  it('returns null when nothing is saved for a path', () => {
    expect(loadDesign(path)).toBeNull();
  });

  it('clearDesign removes the entry', () => {
    saveDesign(path, initialDesign(featureFlow));
    clearDesign(path);
    expect(loadDesign(path)).toBeNull();
  });
});

describe('parseDesign validation', () => {
  it('rejects a bad version', () => {
    expect(parseDesign('{"version":2,"modules":[]}')).toBeNull();
  });

  it('rejects non-array modules', () => {
    expect(parseDesign('{"version":1,"modules":{}}')).toBeNull();
  });

  it('rejects a module missing required fields', () => {
    expect(parseDesign('{"version":1,"modules":[{"id":"mod:1"}]}')).toBeNull();
  });

  it('rejects invalid JSON', () => {
    expect(parseDesign('not json')).toBeNull();
  });

  it('normalizes missing customization flags to false', () => {
    const d = parseDesign(
      '{"version":1,"modules":[{"id":"mod:1","name":"m","description":"d","atomIds":["a"],"position":{"x":1,"y":2},"implicit":true}],"addedEdges":[],"hiddenEdges":[]}',
    );
    expect(d?.modules[0].nameCustomized).toBe(false);
    expect(d?.modules[0].descriptionCustomized).toBe(false);
  });
});

describe('sanitizeDesign (#6 + #18 裁决3 re-validation)', () => {
  it('keeps valid modules/edges and re-adds orphaned atoms', () => {
    // Design: a grouped module [Web, Scan], a stale module for an atom no
    // longer in the scan; the drawn Web->Scan edge is a real dependency.
    const d: RecomposedDesign = {
      version: 1,
      modules: [
        { id: 'mod:g', name: '组', description: '组合', atomIds: [WEB, SCAN], position: { x: 0, y: 0 }, implicit: false, nameCustomized: true, descriptionCustomized: false },
        { id: `atom:${AGG}`, name: '聚合流程编排', description: '编排AI聚合流程并处理配置与报告', atomIds: [AGG], position: { x: 400, y: 400 }, implicit: true, nameCustomized: false, descriptionCustomized: false },
      ],
      addedEdges: [{ source: 'mod:g', target: `atom:${SCAN}` }],
      hiddenEdges: [],
    };
    // New scan no longer contains the Scan atom (its files are gone).
    const flowWithoutScan: FeatureFlowGraph = {
      ...featureFlow,
      nodes: featureFlow.nodes.filter((n) => n.data.kind !== 'atom' || n.data.atomId !== SCAN),
    };
    const graphWithoutScan: Graph = {
      ...graph,
      modules: graph.modules.filter((m) => m.id !== FILE_SCAN),
      edges: [],
    };
    const s = sanitizeDesign(d, flowWithoutScan, graphWithoutScan);
    const group = s.modules.find((m) => m.id === 'mod:g')!;
    expect(group.atomIds).toEqual([WEB]); // Scan filtered out, module retained
    expect(group.name).toBe('组'); // unsaved edit preserved
    // Orphaned atom Web re-covered; AGG still present.
    const covered = new Set(s.modules.flatMap((m) => m.atomIds));
    expect(covered.has(WEB)).toBe(true);
    expect(covered.has(AGG)).toBe(true);
    // Web->Scan no longer exists (Scan vanished) and the edge endpoint is gone,
    // so the edge is pruned.
    expect(s.addedEdges).toEqual([]);
  });

  it('drops modules that become empty and prunes their edges', () => {
    const d: RecomposedDesign = {
      version: 1,
      modules: [
        { id: 'mod:gone', name: '消失', description: '', atomIds: [SCAN], position: { x: 0, y: 0 }, implicit: false, nameCustomized: false, descriptionCustomized: false },
        { id: `atom:${WEB}`, name: 'Web服务接口', description: '提供扫描、状态和图查询接口', atomIds: [WEB], position: { x: 300, y: 300 }, implicit: true, nameCustomized: false, descriptionCustomized: false },
      ],
      addedEdges: [{ source: 'mod:gone', target: `atom:${WEB}` }],
      hiddenEdges: [],
    };
    const flowWithoutScan: FeatureFlowGraph = {
      ...featureFlow,
      nodes: featureFlow.nodes.filter((n) => n.data.kind !== 'atom' || n.data.atomId !== SCAN),
    };
    const graphWithoutScan: Graph = {
      ...graph,
      modules: graph.modules.filter((m) => m.id !== FILE_SCAN),
      edges: [],
    };
    const s = sanitizeDesign(d, flowWithoutScan, graphWithoutScan);
    expect(s.modules.find((m) => m.id === 'mod:gone')).toBeUndefined();
    expect(s.addedEdges).toEqual([]); // pruned
  });

  it('re-validates drawn edges against real dependencies: keeps real, drops reversed/none (裁决3)', () => {
    const d: RecomposedDesign = {
      ...initialDesign(featureFlow),
      addedEdges: [
        { source: `atom:${WEB}`, target: `atom:${SCAN}` }, // real: app.py imports _scanner.py
        { source: `atom:${WEB}`, target: `atom:${AGG}` }, // nonexistent: no such edge
        { source: `atom:${SCAN}`, target: `atom:${WEB}` }, // reversed: code depends the other way
      ],
    };
    const s = sanitizeDesign(d, featureFlow, graph);
    expect(s.addedEdges).toEqual([{ source: `atom:${WEB}`, target: `atom:${SCAN}` }]);
  });

  it('clears deprecated hiddenEdges on load (裁决4) and keeps version 1', () => {
    const d: RecomposedDesign = {
      ...initialDesign(featureFlow),
      addedEdges: [{ source: `atom:${WEB}`, target: `atom:${SCAN}` }],
      hiddenEdges: [{ source: `atom:${WEB}`, target: `atom:${SCAN}` }],
    };
    const s = sanitizeDesign(d, featureFlow, graph);
    expect(s.hiddenEdges).toEqual([]);
    expect(s.version).toBe(1);
  });

  it('keeps a real edge with real evidence when the design reloads (no silent loss)', () => {
    const d: RecomposedDesign = {
      ...initialDesign(featureFlow),
      addedEdges: [{ source: `atom:${WEB}`, target: `atom:${SCAN}` }],
    };
    const s = sanitizeDesign(d, featureFlow, graph);
    expect(s.addedEdges).toEqual([{ source: `atom:${WEB}`, target: `atom:${SCAN}` }]);
  });
});
