import { describe, expect, it } from 'vitest';
import type { Port } from '../api/types';
import type { FeatureFlowGraph } from '../lib/graphToFeatureFlow';
import {
  aggregateInterface,
  atomMetaById,
  childGridPositions,
  deriveModuleName,
  deriveNodes,
  initialDesign,
  moduleSize,
} from '../lib/recompose/derive';
import type { RecomposeModuleActions } from '../lib/recompose/derive';
import type { RecomposedDesign } from '../lib/recompose/types';

const featureFlow: FeatureFlowGraph = {
  nodes: [
    {
      id: 'atom:a',
      type: 'atomNode',
      position: { x: 0, y: 0 },
      data: {
        kind: 'atom',
        atomId: 'a',
        name: '原子甲',
        description: '甲',
        files: ['pkg/a.py'],
        portCount: 1,
        score: 'shallow',
      },
    },
    {
      id: 'atom:b',
      type: 'atomNode',
      position: { x: 0, y: 0 },
      data: {
        kind: 'atom',
        atomId: 'b',
        name: '原子乙',
        description: '乙',
        files: ['pkg/b.py'],
        portCount: 2,
        score: 'moderate',
      },
    },
  ],
  edges: [],
  isEmpty: false,
  unassignedCount: 0,
};

const actions: RecomposeModuleActions = {
  onRename: () => {},
  onSetDescription: () => {},
  onDelete: () => {},
};

const port = (name: string, line: number): Port => ({
  kind: 'function',
  name,
  line,
  signature: `${name}()`,
  params: [],
});

describe('initialDesign', () => {
  it('creates one implicit single-atom module per atom, empty overrides', () => {
    const d = initialDesign(featureFlow);
    expect(d.version).toBe(1);
    expect(d.modules).toHaveLength(2);
    expect(d.addedEdges).toEqual([]);
    expect(d.hiddenEdges).toEqual([]);

    const a = d.modules.find((m) => m.id === 'atom:a');
    expect(a?.atomIds).toEqual(['a']);
    expect(a?.implicit).toBe(true);
    expect(a?.name).toBe('原子甲');
    expect(a?.nameCustomized).toBe(false);
    expect(Number.isFinite(a?.position.x)).toBe(true);
  });

  it('assigns distinct grid positions', () => {
    const d = initialDesign(featureFlow);
    const a = d.modules.find((m) => m.id === 'atom:a')!.position;
    const b = d.modules.find((m) => m.id === 'atom:b')!.position;
    expect(a).not.toEqual(b);
  });
});

describe('moduleSize / childGridPositions', () => {
  it('handles 0 / 1 / 4 / 5 atoms', () => {
    // Empty module: placeholder size (header band + padding only).
    expect(moduleSize([]).width).toBe(200 + 2 * 14);
    expect(moduleSize([]).height).toBe(58 + 2 * 14);
    // 4 atoms -> 2 cols x 2 rows; 5 atoms -> 3 cols x 2 rows (width grows).
    const five = moduleSize(['1', '2', '3', '4', '5']);
    const four = moduleSize(['1', '2', '3', '4']);
    expect(five.height).toBe(four.height); // same 2 rows
    expect(five.width).toBeGreaterThan(four.width);
  });

  it('lays chips out left-to-right, top-to-bottom inside the module', () => {
    const pos = childGridPositions(['1', '2', '3']);
    expect(pos.get('1')).toEqual({ x: 14, y: 58 + 14 });
    expect(pos.get('2')?.x).toBeGreaterThan(pos.get('1')!.x);
    expect(pos.get('3')?.y).toBeGreaterThan(pos.get('1')!.y);
  });
});

describe('atomMetaById / deriveModuleName', () => {
  it('indexes atom metadata from the feature flow', () => {
    const atoms = atomMetaById(featureFlow);
    expect(atoms.get('a')?.name).toBe('原子甲');
    expect(atoms.get('b')?.files).toEqual(['pkg/b.py']);
  });

  it('derives a module name from member atom names', () => {
    const atoms = atomMetaById(featureFlow);
    expect(deriveModuleName(['a', 'b'], atoms)).toBe('原子甲 + 原子乙');
  });
});

describe('aggregateInterface', () => {
  it('unions member ports and scores the union (#13)', () => {
    const module = {
      id: 'mod:1',
      name: 'm',
      description: '',
      atomIds: ['a', 'b'],
      position: { x: 0, y: 0 },
      implicit: false,
      nameCustomized: false,
      descriptionCustomized: false,
    };
    const portsByAtom = new Map<string, Port[]>([
      ['a', [port('f1', 60)]],
      ['b', [port('f2', 20), port('f3', 10)]],
    ]);
    const { ports, score } = aggregateInterface(module, portsByAtom);
    expect(ports).toHaveLength(3);
    expect(score).toBe('moderate'); // maxLine 60 / 3 = 20, 15 <= 20 < 50
  });
});

describe('deriveNodes', () => {
  it('places module containers before their child chips (#10)', () => {
    const d = initialDesign(featureFlow);
    const nodes = deriveNodes(d, featureFlow, new Map(), actions);
    const idx = (id: string) => nodes.findIndex((n) => n.id === id);
    expect(idx('atom:a')).toBeGreaterThanOrEqual(0);
    expect(idx('chip:a')).toBeGreaterThan(idx('atom:a')); // parent first
    const chip = nodes.find((n) => n.id === 'chip:a');
    expect(chip?.parentId).toBe('atom:a');
    expect(chip?.type).toBe('atomChipNode');
    expect(chip?.position).toEqual(childGridPositions(['a']).get('a'));
  });

  it('gives the module container deterministic width/height', () => {
    const d = initialDesign(featureFlow);
    const nodes = deriveNodes(d, featureFlow, new Map(), actions);
    const moduleNode = nodes.find((n) => n.id === 'atom:a');
    expect(moduleNode?.width).toBe(moduleSize(['a']).width);
    expect(moduleNode?.height).toBe(moduleSize(['a']).height);
  });

  it('appends the third-party node with a default position when absent from design (#14)', () => {
    const d: RecomposedDesign = {
      version: 1,
      modules: initialDesign(featureFlow).modules,
      addedEdges: [],
      hiddenEdges: [],
    };
    const flowWithThirdParty: FeatureFlowGraph = {
      ...featureFlow,
      nodes: [
        ...featureFlow.nodes,
        {
          id: 'ext:third-party',
          type: 'externalNode',
          position: { x: 0, y: 0 },
          data: {
            kind: 'external',
            externalId: 'ext:third-party',
            label: '第三方依赖',
            externalNames: ['requests'],
          },
        },
      ],
    };
    const nodes = deriveNodes(d, flowWithThirdParty, new Map(), actions);
    const ext = nodes.find((n) => n.id === 'ext:third-party');
    expect(ext).toBeDefined();
    expect(Number.isFinite(ext?.position.x)).toBe(true);
    expect(Number.isNaN(ext?.position.y)).toBe(false);
  });
});
