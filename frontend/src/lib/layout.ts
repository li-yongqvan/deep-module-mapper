/**
 * Simple grid layout (D3, audit Q4).
 *
 * Node positions are assigned from exported constants so a future layout
 * library (e.g. dagre) can replace the internals without touching callers.
 */
import type { XYPosition } from '@xyflow/react';

/** Prototype node width (prototype-ui.html §2.6). */
export const NODE_WIDTH = 160;
/** Feature-atom node width (issue #8): Chinese name + one-line description need room. */
export const ATOM_NODE_WIDTH = 220;
/** Horizontal gap between columns. */
export const GAP_X = 40;
/** Vertical gap between rows. */
export const GAP_Y = 40;
/** Fixed number of columns; keeps the layout predictable for any module count. */
export const COLUMNS = 6;

/**
 * Assign grid positions to node ids, in the given order. `nodeWidth` defaults
 * to NODE_WIDTH; the feature view passes ATOM_NODE_WIDTH so the wider atom
 * nodes keep the same gap (C6: same constant drives node width and spacing).
 */
export function gridPositions(
  nodeIds: string[],
  nodeWidth: number = NODE_WIDTH,
): Map<string, XYPosition> {
  const positions = new Map<string, XYPosition>();
  nodeIds.forEach((id, index) => {
    const col = index % COLUMNS;
    const row = Math.floor(index / COLUMNS);
    positions.set(id, {
      x: col * (nodeWidth + GAP_X),
      y: row * (nodeWidth * 0.75 + GAP_Y),
    });
  });
  return positions;
}
