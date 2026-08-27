import { describe, expect, it } from 'vitest';
import type { FeatureFlowGraph } from '../lib/graphToFeatureFlow';
import {
  atomMetaById,
  deriveNodes,
  firstChipOffset,
} from '../lib/recompose/derive';
import {
  applyAtomDrop,
  applyModuleMove,
  createModule,
  defaultGenId,
  deleteModule,
  moduleBoundsFromDesign,
  renameModule,
  resolveDropTarget,
  setModuleDescription,
} from '../lib/recompose/dragDrop';
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

const atoms = atomMetaById(featureFlow);

/** Design: explicit `mod:target` [b,c] at (500,500); implicit `atom:a` at (100,100). */
const design: RecomposedDesign = {
  version: 1,
  modules: [
    {
      id: 'mod:target',
      name: '目标模块',
      description: '目标',
      atomIds: ['b', 'c'],
      position: { x: 500, y: 500 },
      implicit: false,
      nameCustomized: true, // user-typed name survives member changes (#7)
      descriptionCustomized: false,
    },
    {
      id: 'atom:a',
      name: '原子甲',
      description: '甲',
      atomIds: ['a'],
      position: { x: 100, y: 100 },
      implicit: true,
      nameCustomized: false,
      descriptionCustomized: false,
    },
  ],
  addedEdges: [{ source: 'atom:a', target: 'mod:target' }],
  hiddenEdges: [],
};

const bounds = moduleBoundsFromDesign(design);

describe('resolveDropTarget', () => {
  it('returns the current parent when the drop stays inside it', () => {
    expect(resolveDropTarget('atom:a', bounds, { x: 110, y: 110 })).toBe('atom:a');
  });

  it('returns another module that contains the chip center', () => {
    expect(resolveDropTarget('atom:a', bounds, { x: 600, y: 520 })).toBe('mod:target');
  });

  it('returns null for blank space', () => {
    expect(resolveDropTarget('atom:a', bounds, { x: 2000, y: 2000 })).toBeNull();
  });

  it('ignores the current parent when looking for a new home', () => {
    // Chip center inside mod:target bounds, current parent atom:a.
    expect(resolveDropTarget('atom:a', bounds, { x: 510, y: 510 })).toBe('mod:target');
  });
});

describe('applyAtomDrop', () => {
  it('no-op when dropped back inside its own module', () => {
    const d = applyAtomDrop(design, 'a', { x: 110, y: 110 }, bounds, atoms);
    expect(d).toEqual(design);
  });

  it('moves the atom into another module and deletes the emptied source module', () => {
    const d = applyAtomDrop(design, 'a', { x: 600, y: 520 }, bounds, atoms);
    expect(d.modules.find((m) => m.id === 'atom:a')).toBeUndefined(); // emptied -> deleted
    const target = d.modules.find((m) => m.id === 'mod:target')!;
    expect(target.atomIds).toEqual(['b', 'c', 'a']);
    expect(target.name).toBe('目标模块'); // explicit module name not re-derived
  });

  it('drops an atom into an EMPTY module: the target survives and holds the atom (regression)', () => {
    const d0: RecomposedDesign = {
      version: 1,
      modules: [
        { id: 'mod:empty', name: '新模块', description: '', atomIds: [], position: { x: 500, y: 500 }, implicit: false, nameCustomized: false, descriptionCustomized: false },
        { id: 'atom:a', name: '原子甲', description: '甲', atomIds: ['a'], position: { x: 100, y: 100 }, implicit: true, nameCustomized: false, descriptionCustomized: false },
      ],
      addedEdges: [],
      hiddenEdges: [],
    };
    const b = moduleBoundsFromDesign(d0);
    // Drop atom a inside the empty module (its box is below the header).
    const d = applyAtomDrop(d0, 'a', { x: 520, y: 520 }, b, atoms);
    expect(d.modules.find((m) => m.id === 'mod:empty')?.atomIds).toEqual(['a']);
    expect(d.modules.find((m) => m.id === 'atom:a')).toBeUndefined(); // source deleted
    expect(d.modules).toHaveLength(1);
  });

  it('prunes edges that referenced the deleted source module', () => {
    const d = applyAtomDrop(design, 'a', { x: 600, y: 520 }, bounds, atoms);
    expect(d.addedEdges).toEqual([]); // atom:a module is gone
  });

  it('drops to blank space: atom becomes its own module exactly at the drop point (#8)', () => {
    const absPos = { x: 300, y: 100 };
    const d = applyAtomDrop(design, 'a', absPos, bounds, atoms);
    const m = d.modules.find((m) => m.id === 'atom:a')!;
    const offset = firstChipOffset();
    expect(m.position).toEqual({ x: absPos.x - offset.x, y: absPos.y - offset.y });
    expect(m.atomIds).toEqual(['a']);
    expect(m.implicit).toBe(true);

    // Re-deriving nodes keeps the chip's absolute position identical.
    const nodes = deriveNodes(d, featureFlow, new Map(), {
      onRename: () => {},
      onSetDescription: () => {},
      onDelete: () => {},
    });
    const chip = nodes.find((n) => n.id === 'chip:a')!;
    const abs = {
      x: m.position.x + (chip.position as { x: number }).x,
      y: m.position.y + (chip.position as { y: number }).y,
    };
    expect(abs).toEqual(absPos);
  });

  it('re-ids an implicit single-atom module that becomes multi-atom, and re-derives its name (#7)', () => {
    const genId = () => 'mod:joined';
    // Drag atom a into implicit single-atom module atom:b.
    const d0: RecomposedDesign = {
      version: 1,
      modules: [
        { id: 'atom:a', name: '原子甲', description: '甲', atomIds: ['a'], position: { x: 100, y: 100 }, implicit: true, nameCustomized: false, descriptionCustomized: false },
        { id: 'atom:b', name: '原子乙', description: '乙', atomIds: ['b'], position: { x: 500, y: 500 }, implicit: true, nameCustomized: false, descriptionCustomized: false },
        { id: 'atom:d', name: '原子丁', description: '丁', atomIds: ['d'], position: { x: 900, y: 900 }, implicit: true, nameCustomized: false, descriptionCustomized: false },
      ],
      addedEdges: [{ source: 'atom:b', target: 'atom:d' }],
      hiddenEdges: [],
    };
    const bBounds = moduleBoundsFromDesign(d0);
    const d = applyAtomDrop(d0, 'a', { x: 510, y: 510 }, bBounds, atoms, genId);
    const joined = d.modules.find((m) => m.id === 'mod:joined');
    expect(joined?.atomIds).toEqual(['b', 'a']);
    expect(joined?.implicit).toBe(false);
    expect(joined?.name).toBe('原子乙 + 原子甲'); // re-derived
    // Edge override referencing the old id was remapped to the new one.
    expect(d.addedEdges).toEqual([{ source: 'mod:joined', target: 'atom:d' }]);
  });

  it('keeps a customized module name when a second atom joins (#7)', () => {
    const genId = () => 'mod:joined';
    const d0: RecomposedDesign = {
      version: 1,
      modules: [
        { id: 'atom:a', name: '原子甲', description: '甲', atomIds: ['a'], position: { x: 100, y: 100 }, implicit: true, nameCustomized: false, descriptionCustomized: false },
        { id: 'atom:b', name: '我改的名字', description: '乙', atomIds: ['b'], position: { x: 500, y: 500 }, implicit: true, nameCustomized: true, descriptionCustomized: false },
      ],
      addedEdges: [],
      hiddenEdges: [],
    };
    const bBounds = moduleBoundsFromDesign(d0);
    const d = applyAtomDrop(d0, 'a', { x: 510, y: 510 }, bBounds, atoms, genId);
    const joined = d.modules.find((m) => m.id === 'mod:joined')!;
    expect(joined.name).toBe('我改的名字'); // user value preserved
  });
});

describe('applyModuleMove / createModule / deleteModule / rename', () => {
  it('moves a module to a new position', () => {
    const d = applyModuleMove(design, 'mod:target', { x: 10, y: 20 });
    expect(d.modules.find((m) => m.id === 'mod:target')!.position).toEqual({ x: 10, y: 20 });
  });

  it('creates an empty explicit module below the lowest one', () => {
    const genId = () => 'mod:new';
    const d = createModule(design, genId);
    const m = d.modules.find((m) => m.id === 'mod:new')!;
    expect(m.atomIds).toEqual([]);
    expect(m.implicit).toBe(false);
    expect(m.position.y).toBeGreaterThan(design.modules[1].position.y);
  });

  it('deleteModule releases atoms as implicit modules and prunes edges (#11)', () => {
    const d = deleteModule(design, 'mod:target', atoms);
    expect(d.modules.find((m) => m.id === 'mod:target')).toBeUndefined();
    const b = d.modules.find((m) => m.id === 'atom:b')!;
    const c = d.modules.find((m) => m.id === 'atom:c')!;
    expect(b.atomIds).toEqual(['b']);
    expect(c.atomIds).toEqual(['c']);
    expect(b.implicit).toBe(true);
    // Positions cascade deterministically from the deleted module.
    expect(b.position.y).toBe(design.modules[0].position.y);
    expect(c.position.y).toBeGreaterThan(b.position.y);
    // Edge override referencing the deleted module is pruned (invariant #4).
    expect(d.addedEdges).toEqual([]);
  });

  it('renameModule and setModuleDescription mark the field customized', () => {
    const d = renameModule(design, 'mod:target', '新名字');
    expect(d.modules.find((m) => m.id === 'mod:target')!.name).toBe('新名字');
    expect(d.modules.find((m) => m.id === 'mod:target')!.nameCustomized).toBe(true);

    const d2 = setModuleDescription(design, 'mod:target', '新接口');
    expect(d2.modules.find((m) => m.id === 'mod:target')!.description).toBe('新接口');
    expect(d2.modules.find((m) => m.id === 'mod:target')!.descriptionCustomized).toBe(true);
  });
});

describe('defaultGenId', () => {
  it('produces mod-prefixed ids', () => {
    expect(defaultGenId().startsWith('mod:')).toBe(true);
    expect(defaultGenId()).not.toBe(defaultGenId());
  });
});
