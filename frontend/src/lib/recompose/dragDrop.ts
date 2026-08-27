/**
 * Drag-in/drag-out and module lifecycle operations (issue #10), all pure.
 *
 * The canvas never measures the DOM: module bounds are recomputed from the
 * design (position + deterministic `moduleSize`), so the drop target can be
 * resolved and unit-tested without a React Flow instance.
 */
import type { XYPosition } from '@xyflow/react';
import { CHIP_W, CHIP_H, CHIP_GAP, DROP_TOLERANCE, firstChipOffset, deriveModuleName, deriveModuleDescription, moduleSize, type AtomMeta } from './derive';
import type { RecomposedDesign, RecomposedModule } from './types';

export interface ModuleBounds {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

/** All module bounds, computed purely from the design (no DOM). */
export function moduleBoundsFromDesign(design: RecomposedDesign): ModuleBounds[] {
  return design.modules.map((m) => {
    const size = moduleSize(m.atomIds);
    return { id: m.id, x: m.position.x, y: m.position.y, ...size };
  });
}

function contains(b: ModuleBounds, x: number, y: number): boolean {
  return (
    x >= b.x + DROP_TOLERANCE &&
    x <= b.x + b.width - DROP_TOLERANCE &&
    y >= b.y + DROP_TOLERANCE &&
    y <= b.y + b.height - DROP_TOLERANCE
  );
}

/**
 * Resolve where a chip dropped at `absPos` (chip top-left, canvas absolute)
 * should live. Returns the current parent if still inside it; otherwise the
 * topmost (last) containing module; null = blank space (becomes its own module).
 */
export function resolveDropTarget(
  currentParentId: string | null,
  bounds: ModuleBounds[],
  absPos: XYPosition,
): string | null {
  const cx = absPos.x + CHIP_W / 2;
  const cy = absPos.y + CHIP_H / 2;

  const current = bounds.find((b) => b.id === currentParentId);
  if (current && contains(current, cx, cy)) return current.id;

  let hit: string | null = null;
  for (const b of bounds) {
    if (b.id === currentParentId) continue;
    if (contains(b, cx, cy)) hit = b.id; // last hit wins (topmost render order)
  }
  return hit;
}

/** A stable id generator, injectable so pure tests stay deterministic. */
let counter = 0;
export function defaultGenId(): string {
  try {
    return `mod:${crypto.randomUUID()}`;
  } catch {
    counter += 1;
    return `mod:${Date.now().toString(36)}-${counter}`;
  }
}

function implicitModule(atomId: string, atoms: Map<string, AtomMeta>, position: XYPosition): RecomposedModule {
  const meta = atoms.get(atomId);
  return {
    id: `atom:${atomId}`,
    name: meta?.name ?? atomId,
    description: meta?.description ?? '',
    atomIds: [atomId],
    position,
    implicit: true,
    nameCustomized: false,
    descriptionCustomized: false,
  };
}

/** Drop an atom chip: into a module, within its module (no-op), or onto blank space. */
export function applyAtomDrop(
  design: RecomposedDesign,
  atomId: string,
  absPos: XYPosition,
  bounds: ModuleBounds[],
  atoms: Map<string, AtomMeta>,
  genId: () => string = defaultGenId,
): RecomposedDesign {
  const current = design.modules.find((m) => m.atomIds.includes(atomId));
  const target = resolveDropTarget(current?.id ?? null, bounds, absPos);

  // Dropped back inside its own module: nothing changes.
  if (target !== null && target === current?.id) return design;

  // 1. Remove the atom from its current module.
  let modules = design.modules.map((m) =>
    m.atomIds.includes(atomId)
      ? { ...m, atomIds: m.atomIds.filter((x) => x !== atomId) }
      : m,
  );

  // 2. A source module emptied by the drag-out is deleted — but only if it is
  //    not also the drop target (an empty target must survive to receive the
  //    atom). Other user-created empty modules are left alone.
  if (current && current.atomIds.length === 1 && current.id !== target) {
    modules = modules.filter((m) => m.id !== current.id);
  }

  if (target) {
    const oldTarget = modules.find((m) => m.id === target);
    if (!oldTarget) return pruneEdges({ ...design, modules });

    // An implicit single-atom module becoming multi-atom is re-ided to a fresh
    // explicit id, so the `atom:<id>` = exactly-one-atom invariant holds.
    let newTargetId = target;
    let t: RecomposedModule = oldTarget;
    if (oldTarget.implicit && oldTarget.atomIds.length >= 1) {
      newTargetId = genId();
      t = { ...oldTarget, id: newTargetId };
    }

    const nextAtomIds = [...t.atomIds, atomId];
    const updated: RecomposedModule = {
      ...t,
      atomIds: nextAtomIds,
      implicit: false,
      // Re-derive only fields the user hasn't customized (#7).
      name:
        !t.nameCustomized && nextAtomIds.length >= 2
          ? deriveModuleName(nextAtomIds, atoms)
          : t.name,
      description:
        !t.descriptionCustomized && nextAtomIds.length >= 2
          ? deriveModuleDescription(nextAtomIds, atoms)
          : t.description,
    };
    // Replace the entry under its current (old) id with the updated one; when
    // re-ided, the entry still sits under `target` and `updated` carries the new id.
    modules = modules.map((m) =>
      m.id === (newTargetId !== target ? target : newTargetId) ? updated : m,
    );

    if (newTargetId !== target) {
      return pruneEdges(replaceModuleId({ ...design, modules }, target, newTargetId));
    }
  } else {
    // Dropped on blank space: its own implicit module. Position the container so
    // the chip appears exactly where it was dropped (#8).
    const offset = firstChipOffset();
    modules = [
      ...modules,
      implicitModule(atomId, atoms, { x: absPos.x - offset.x, y: absPos.y - offset.y }),
    ];
  }

  return pruneEdges({ ...design, modules });
}

/** Move a module container to a new canvas position. */
export function applyModuleMove(
  design: RecomposedDesign,
  moduleId: string,
  position: XYPosition,
): RecomposedDesign {
  return {
    ...design,
    modules: design.modules.map((m) =>
      m.id === moduleId ? { ...m, position } : m,
    ),
  };
}

/** Create an empty explicit module below the current lowest one (no overlap). */
export function createModule(
  design: RecomposedDesign,
  genId: () => string = defaultGenId,
): RecomposedDesign {
  const id = genId();
  const maxY = design.modules.reduce(
    (acc, m) => Math.max(acc, m.position.y + moduleSize(m.atomIds).height),
    0,
  );
  const module: RecomposedModule = {
    id,
    name: '新模块',
    description: '',
    atomIds: [],
    position: { x: 0, y: maxY + 40 },
    implicit: false,
    nameCustomized: false,
    descriptionCustomized: false,
  };
  return { ...design, modules: [...design.modules, module] };
}

/** Delete a module; its atoms are released as implicit single-atom modules. */
export function deleteModule(
  design: RecomposedDesign,
  moduleId: string,
  atoms: Map<string, AtomMeta>,
): RecomposedDesign {
  const target = design.modules.find((m) => m.id === moduleId);
  if (!target) return design;

  const base = target.position;
  const released = target.atomIds.map((atomId, i) =>
    implicitModule(atomId, atoms, {
      x: base.x,
      y: base.y + i * (CHIP_H + CHIP_GAP),
    }),
  );
  const modules = [
    ...design.modules.filter((m) => m.id !== moduleId),
    ...released,
  ];
  return pruneEdges({ ...design, modules });
}

/** Rename a module (marks the name as customized so re-derivation skips it). */
export function renameModule(
  design: RecomposedDesign,
  moduleId: string,
  name: string,
): RecomposedDesign {
  return {
    ...design,
    modules: design.modules.map((m) =>
      m.id === moduleId ? { ...m, name, nameCustomized: true } : m,
    ),
  };
}

/** Edit a module's interface description (marks it customized). */
export function setModuleDescription(
  design: RecomposedDesign,
  moduleId: string,
  description: string,
): RecomposedDesign {
  return {
    ...design,
    modules: design.modules.map((m) =>
      m.id === moduleId
        ? { ...m, description, descriptionCustomized: true }
        : m,
    ),
  };
}

/** Re-point edge overrides after a module id change. */
export function replaceModuleId(
  design: RecomposedDesign,
  oldId: string,
  newId: string,
): RecomposedDesign {
  const rep = (refs: { source: string; target: string }[]) =>
    refs.map((r) => ({
      source: r.source === oldId ? newId : r.source,
      target: r.target === oldId ? newId : r.target,
    }));
  return {
    ...design,
    addedEdges: rep(design.addedEdges),
    hiddenEdges: rep(design.hiddenEdges),
  };
}

/** Drop edge overrides whose endpoints no longer exist (invariant #4). */
export function pruneEdges(design: RecomposedDesign): RecomposedDesign {
  const valid = new Set(design.modules.map((m) => m.id));
  const keep = (refs: { source: string; target: string }[]) =>
    refs.filter((r) => valid.has(r.source) && valid.has(r.target));
  return {
    ...design,
    addedEdges: keep(design.addedEdges),
    hiddenEdges: keep(design.hiddenEdges),
  };
}

/** Fallback absolute position for a chip when the store lookup is unavailable. */
export function fallbackAbsolutePosition(
  nodePosition: XYPosition,
  parentPosition: XYPosition | undefined,
): XYPosition {
  return parentPosition
    ? { x: parentPosition.x + nodePosition.x, y: parentPosition.y + nodePosition.y }
    : nodePosition;
}
