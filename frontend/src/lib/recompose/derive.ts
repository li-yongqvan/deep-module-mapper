/**
 * Pure derivation helpers for the recompose canvas (issue #10).
 *
 * Everything here is a function of the design + feature-flow inputs, so the
 * module content editing logic can be unit-tested without a React Flow canvas
 * (jsdom does not render `<ReactFlow>`). Layout constants are exported so the
 * module container and its child chips never disagree on size/position.
 */
import type { Node, XYPosition } from '@xyflow/react';
import type { Graph, Port } from '../../api/types';
import type { AtomNodeData, FeatureFlowGraph } from '../graphToFeatureFlow';
import { atomForFile } from '../../manifest/featureAtoms';
import { depthScore, type DepthScore } from '../depthScore';
import { gridPositions } from '../layout';
import type { RecomposedDesign, RecomposedModule } from './types';
import type { ExternalNodeData } from '../graphToFlow';

/** Padding inside a module container (around the chip grid). */
export const PAD = 14;
/** Module header band: name + description + delete. */
export const HEADER_H = 58;
/** Atom chip size. */
export const CHIP_W = 200;
export const CHIP_H = 44;
/** Gap between chips inside a module. */
export const CHIP_GAP = 12;
/** Hit-test tolerance when dropping a chip (bounds shrunk by 2px). */
export const DROP_TOLERANCE = 2;
/** Grid column width for initial module layout (single-column module width). */
export const MODULE_GRID_WIDTH = CHIP_W + 2 * PAD;

/** Atom metadata available to derivation (from the feature-flow atom nodes). */
export interface AtomMeta {
  id: string;
  name: string;
  description: string;
  files: string[];
  portCount: number;
  score: DepthScore;
}

/** Chip node data (slim, reused AtomNodeData shape for Inspector drill-down). */
export type AtomChipData = AtomNodeData;

export interface RecomposeModuleData {
  kind: 'recomposeModule';
  moduleId: string;
  name: string;
  description: string;
  atomIds: string[];
  implicit: boolean;
  memberNames: string[];
  score: DepthScore;
  portCount: number;
  /** Bound rename handler (moduleId captured). */
  onRename: (name: string) => void;
  /** Bound description-edit handler (moduleId captured). */
  onSetDescription: (description: string) => void;
  /** Bound delete handler (moduleId captured). */
  onDelete: () => void;
  [key: string]: unknown;
}

/** Actions bound by the canvas, passed to deriveNodes so module nodes can call them. */
export interface RecomposeModuleActions {
  onRename: (moduleId: string, name: string) => void;
  onSetDescription: (moduleId: string, description: string) => void;
  onDelete: (moduleId: string) => void;
}

export type RecomposeFlowNode =
  | Node<RecomposeModuleData>
  | Node<AtomChipData>
  | Node<ExternalNodeData>;

/** Chip node id for an atom (distinct from module ids `mod:*`/`atom:*`). */
export function chipNodeId(atomId: string): string {
  return `chip:${atomId}`;
}

/** Build atom metadata from the feature-flow atom nodes. */
export function atomMetaById(featureFlow: FeatureFlowGraph): Map<string, AtomMeta> {
  const map = new Map<string, AtomMeta>();
  for (const n of featureFlow.nodes) {
    if (n.data.kind !== 'atom') continue;
    const d = n.data as AtomNodeData;
    map.set(d.atomId, {
      id: d.atomId,
      name: d.name,
      description: d.description,
      files: d.files,
      portCount: d.portCount,
      score: d.score,
    });
  }
  return map;
}

/** Ports per atom, aggregated from the graph modules (by manifest atom membership). */
export function buildPortsByAtom(graph: Graph): Map<string, Port[]> {
  const map = new Map<string, Port[]>();
  for (const m of graph.modules) {
    const atom = atomForFile(m.id);
    if (!atom) continue;
    const list = map.get(atom.id) ?? [];
    list.push(...m.ports);
    map.set(atom.id, list);
  }
  return map;
}

/**
 * Number of chip grid columns for a module: 1 for <=1 chip, 2 for <=4, else 3.
 * The module width/height is derived deterministically so children never
 * overflow and no DOM measurement is needed (invariant #6).
 */
export function moduleSize(atomIds: string[]): { width: number; height: number } {
  const n = atomIds.length;
  const cols = n <= 1 ? 1 : n <= 4 ? 2 : 3;
  const rows = Math.ceil(n / cols);
  return {
    width: cols * CHIP_W + (cols - 1) * CHIP_GAP + 2 * PAD,
    height: HEADER_H + rows * CHIP_H + Math.max(rows - 1, 0) * CHIP_GAP + 2 * PAD,
  };
}

/** Relative chip positions inside a module (origin = module top-left). */
export function childGridPositions(atomIds: string[]): Map<string, XYPosition> {
  const positions = new Map<string, XYPosition>();
  const n = atomIds.length;
  const cols = n <= 1 ? 1 : n <= 4 ? 2 : 3;
  atomIds.forEach((id, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    positions.set(id, {
      x: PAD + col * (CHIP_W + CHIP_GAP),
      y: HEADER_H + PAD + row * (CHIP_H + CHIP_GAP),
    });
  });
  return positions;
}

/** The relative position of the first chip cell (used by applyAtomDrop #8). */
export function firstChipOffset(): XYPosition {
  return { x: PAD, y: HEADER_H + PAD };
}

/** Default Chinese name for a module from its member atom names. */
export function deriveModuleName(atomIds: string[], atoms: Map<string, AtomMeta>): string {
  const names = atomIds.map((id) => atoms.get(id)?.name ?? id);
  return names.join(' + ');
}

/** Default interface description for a module from its member atoms. */
export function deriveModuleDescription(atomIds: string[], atoms: Map<string, AtomMeta>): string {
  const names = atomIds.map((id) => atoms.get(id)?.name ?? id);
  return `整合 ${atomIds.length} 个功能：${names.join('、')}`;
}

/**
 * A module's single aggregated interface = the union of its member atoms'
 * ports; score reuses the naive depth heuristic over that union (#13).
 */
export function aggregateInterface(
  module: RecomposedModule,
  portsByAtom: Map<string, Port[]>,
): { ports: Port[]; score: DepthScore } {
  const ports = module.atomIds.flatMap((id) => portsByAtom.get(id) ?? []);
  return { ports, score: depthScore(ports) };
}

/**
 * The manifest-derived "suggested grouping": every feature-flow atom becomes
 * its own implicit single-atom module on a grid. This is also the reset target.
 */
export function initialDesign(featureFlow: FeatureFlowGraph): RecomposedDesign {
  const atoms = atomMetaById(featureFlow);
  const ids = [...atoms.keys()];
  const positions = gridPositions(ids, MODULE_GRID_WIDTH);
  const modules: RecomposedModule[] = ids.map((atomId) => {
    const meta = atoms.get(atomId)!;
    return {
      id: `atom:${atomId}`,
      name: meta.name,
      description: meta.description,
      atomIds: [atomId],
      position: positions.get(atomId) ?? { x: 0, y: 0 },
      implicit: true,
      nameCustomized: false,
      descriptionCustomized: false,
    };
  });
  return { version: 1, modules, addedEdges: [], hiddenEdges: [] };
}

/** Default position for the third-party node: below the lowest module (#14). */
export function thirdPartyDefaultPosition(design: RecomposedDesign): XYPosition {
  const maxY = design.modules.reduce(
    (acc, m) => Math.max(acc, m.position.y + moduleSize(m.atomIds).height),
    0,
  );
  return maxY > 0 ? { x: 0, y: maxY + 40 } : { x: 0, y: 0 };
}

/**
 * Design -> React Flow nodes. Module containers come before their child chips
 * in the array (parent-before-child, required by React Flow's updateChildNode),
 * and the third-party node is appended last (#10, #14).
 */
export function deriveNodes(
  design: RecomposedDesign,
  featureFlow: FeatureFlowGraph,
  portsByAtom: Map<string, Port[]>,
  actions: RecomposeModuleActions,
): RecomposeFlowNode[] {
  const atoms = atomMetaById(featureFlow);
  const nodes: RecomposeFlowNode[] = [];

  for (const m of design.modules) {
    const size = moduleSize(m.atomIds);
    const { ports, score } = aggregateInterface(m, portsByAtom);
    const memberNames = m.atomIds.map((id) => atoms.get(id)?.name ?? id);
    const childPositions = childGridPositions(m.atomIds);

    nodes.push({
      id: m.id,
      type: 'recomposeModuleNode',
      position: m.position,
      width: size.width,
      height: size.height,
      data: {
        kind: 'recomposeModule',
        moduleId: m.id,
        name: m.name,
        description: m.description,
        atomIds: m.atomIds,
        implicit: m.implicit,
        memberNames,
        score,
        portCount: ports.length,
        onRename: (name: string) => actions.onRename(m.id, name),
        onSetDescription: (description: string) => actions.onSetDescription(m.id, description),
        onDelete: () => actions.onDelete(m.id),
      },
    });

    for (const atomId of m.atomIds) {
      const meta = atoms.get(atomId);
      if (!meta) continue;
      nodes.push({
        id: chipNodeId(atomId),
        type: 'atomChipNode',
        parentId: m.id,
        position: childPositions.get(atomId) ?? { x: 0, y: 0 },
        deletable: false, // membership is edited by dragging, not by deleting
        data: {
          kind: 'atom',
          atomId,
          name: meta.name,
          description: meta.description,
          files: meta.files,
          portCount: meta.portCount,
          score: meta.score,
        },
      });
    }
  }

  const externalNode = featureFlow.nodes.find((n) => n.data.kind === 'external');
  if (externalNode) {
    const d = externalNode.data as ExternalNodeData & { externalNames?: string[] };
    nodes.push({
      id: externalNode.id,
      type: 'externalNode',
      position: design.thirdPartyPosition ?? thirdPartyDefaultPosition(design),
      data: {
        kind: 'external',
        externalId: d.externalId,
        label: d.label,
        externalNames: d.externalNames,
      },
    });
  }

  return nodes;
}
