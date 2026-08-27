import { describe, expect, it, beforeEach } from 'vitest';
import type { FeatureFlowGraph } from '../lib/graphToFeatureFlow';
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

const featureFlow: FeatureFlowGraph = {
  nodes: [
    { id: 'atom:a', type: 'atomNode', position: { x: 0, y: 0 }, data: { kind: 'atom', atomId: 'a', name: '原子甲', description: '甲', files: ['p/a.py'], portCount: 1, score: 'shallow' } },
    { id: 'atom:b', type: 'atomNode', position: { x: 0, y: 0 }, data: { kind: 'atom', atomId: 'b', name: '原子乙', description: '乙', files: ['p/b.py'], portCount: 1, score: 'shallow' } },
    { id: 'atom:c', type: 'atomNode', position: { x: 0, y: 0 }, data: { kind: 'atom', atomId: 'c', name: '原子丙', description: '丙', files: ['p/c.py'], portCount: 1, score: 'shallow' } },
  ],
  edges: [],
  isEmpty: false,
  unassignedCount: 0,
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

describe('sanitizeDesign (#6)', () => {
  it('keeps valid modules/edges and re-adds orphaned atoms', () => {
    // Design: a grouped module [a,b], a stale module for an atom no longer in the scan.
    const d: RecomposedDesign = {
      version: 1,
      modules: [
        { id: 'mod:g', name: '组', description: '组合', atomIds: ['a', 'b'], position: { x: 0, y: 0 }, implicit: false, nameCustomized: true, descriptionCustomized: false },
        { id: 'atom:c', name: '原子丙', description: '丙', atomIds: ['c'], position: { x: 400, y: 400 }, implicit: true, nameCustomized: false, descriptionCustomized: false },
      ],
      addedEdges: [{ source: 'mod:g', target: 'atom:c' }],
      hiddenEdges: [],
    };
    // New scan only has atoms a and c (b vanished).
    const flowWithoutB: FeatureFlowGraph = {
      ...featureFlow,
      nodes: featureFlow.nodes.filter((n) => n.data.kind !== 'atom' || n.data.atomId !== 'b'),
    };
    const s = sanitizeDesign(d, flowWithoutB);
    const group = s.modules.find((m) => m.id === 'mod:g')!;
    expect(group.atomIds).toEqual(['a']); // b filtered out, module retained
    expect(group.name).toBe('组'); // unsaved edit preserved
    // Orphaned atom a re-covered; atom c still present; c's stale-atom? c existed.
    const covered = new Set(s.modules.flatMap((m) => m.atomIds));
    expect(covered.has('a')).toBe(true);
    expect(covered.has('c')).toBe(true);
    // Edge mod:g -> atom:c still valid.
    expect(s.addedEdges).toEqual([{ source: 'mod:g', target: 'atom:c' }]);
  });

  it('drops modules that become empty and prunes their edges', () => {
    const d: RecomposedDesign = {
      version: 1,
      modules: [
        { id: 'mod:gone', name: '消失', description: '', atomIds: ['b'], position: { x: 0, y: 0 }, implicit: false, nameCustomized: false, descriptionCustomized: false },
        { id: 'atom:a', name: '原子甲', description: '甲', atomIds: ['a'], position: { x: 300, y: 300 }, implicit: true, nameCustomized: false, descriptionCustomized: false },
      ],
      addedEdges: [{ source: 'mod:gone', target: 'atom:a' }],
      hiddenEdges: [],
    };
    const flowWithoutB: FeatureFlowGraph = {
      ...featureFlow,
      nodes: featureFlow.nodes.filter((n) => n.data.kind !== 'atom' || n.data.atomId !== 'b'),
    };
    const s = sanitizeDesign(d, flowWithoutB);
    expect(s.modules.find((m) => m.id === 'mod:gone')).toBeUndefined();
    expect(s.addedEdges).toEqual([]); // pruned
  });
});
