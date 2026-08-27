/**
 * localStorage persistence for recomposed designs (decision D1).
 *
 * Zero backend changes: `/api/designs` is a future ticket. Designs are keyed
 * by the scanned codebase path so different repos never mix, and the JSON
 * shape follows design-data-schema.md ("module list + edges + layout positions")
 * so a future server endpoint can adopt it unchanged.
 */
import type { XYPosition } from '@xyflow/react';
import type { FeatureFlowGraph } from '../graphToFeatureFlow';
import { atomMetaById, MODULE_GRID_WIDTH } from './derive';
import { pruneEdges } from './dragDrop';
import { gridPositions } from '../layout';
import type { RecomposedDesign, RecomposedModule } from './types';

export function storageKey(path: string): string {
  return `dmm:recompose:v1:${encodeURIComponent(path)}`;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null;
}

function isXYPosition(v: unknown): v is XYPosition {
  return (
    isRecord(v) &&
    typeof v.x === 'number' &&
    typeof v.y === 'number' &&
    Number.isFinite(v.x) &&
    Number.isFinite(v.y)
  );
}

function isModuleEdgeRef(v: unknown): v is { source: string; target: string } {
  return (
    isRecord(v) &&
    typeof v.source === 'string' &&
    typeof v.target === 'string'
  );
}

/** Validate + normalize raw parsed JSON into a RecomposedDesign (null on bad shape). */
export function parseDesign(raw: string): RecomposedDesign | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(parsed) || parsed.version !== 1 || !Array.isArray(parsed.modules)) {
    return null;
  }

  const modules: RecomposedModule[] = [];
  for (const item of parsed.modules) {
    if (!isRecord(item)) return null;
    const { id, name, description, atomIds, position, implicit } = item;
    if (
      typeof id !== 'string' ||
      typeof name !== 'string' ||
      typeof description !== 'string' ||
      !Array.isArray(atomIds) ||
      !atomIds.every((a) => typeof a === 'string') ||
      !isXYPosition(position) ||
      typeof implicit !== 'boolean'
    ) {
      return null;
    }
    modules.push({
      id,
      name,
      description,
      atomIds: atomIds as string[],
      position,
      implicit,
      nameCustomized: item.nameCustomized === true,
      descriptionCustomized: item.descriptionCustomized === true,
    });
  }

  const edgeList = (v: unknown) =>
    Array.isArray(v) && v.every(isModuleEdgeRef) ? v : [];

  return {
    version: 1,
    modules,
    addedEdges: edgeList(parsed.addedEdges),
    hiddenEdges: edgeList(parsed.hiddenEdges),
    thirdPartyPosition: isXYPosition(parsed.thirdPartyPosition)
      ? parsed.thirdPartyPosition
      : undefined,
  };
}

export function saveDesign(path: string, design: RecomposedDesign): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey(path), JSON.stringify(design));
  } catch {
    // Quota/private-mode errors are non-fatal: the design stays in memory.
  }
}

export function loadDesign(path: string): RecomposedDesign | null {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem(storageKey(path));
  return raw ? parseDesign(raw) : null;
}

export function clearDesign(path: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(storageKey(path));
}

/**
 * Make a stored design consistent with the current scan: drop atoms that no
 * longer exist, re-add any orphaned atoms as implicit modules, drop empty
 * modules and dead edge overrides. Keeps valid layout and unsaved edits (#6).
 */
export function sanitizeDesign(
  design: RecomposedDesign,
  featureFlow: FeatureFlowGraph,
): RecomposedDesign {
  const atoms = atomMetaById(featureFlow);
  const validAtomIds = new Set(atoms.keys());

  let modules = design.modules
    .map((m) => ({
      ...m,
      atomIds: m.atomIds.filter((a) => validAtomIds.has(a)),
    }))
    .filter((m) => m.atomIds.length > 0);

  const covered = new Set(modules.flatMap((m) => m.atomIds));
  for (const atomId of validAtomIds) {
    if (covered.has(atomId)) continue;
    const meta = atoms.get(atomId)!;
    const id = `atom:${atomId}`;
    const position =
      gridPositions([...modules.map((m) => m.id), id], MODULE_GRID_WIDTH).get(id) ??
      { x: 0, y: 0 };
    modules.push({
      id,
      name: meta.name,
      description: meta.description,
      atomIds: [atomId],
      position,
      implicit: true,
      nameCustomized: false,
      descriptionCustomized: false,
    });
  }

  return pruneEdges({ ...design, modules });
}
