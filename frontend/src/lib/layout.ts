/**
 * Simple grid layout (D3, audit Q4).
 *
 * Node positions are assigned from exported constants so a future layout
 * library (e.g. dagre) can replace the internals without touching callers.
 */
import type { XYPosition } from '@xyflow/react';

/** Prototype node width (prototype-ui.html §2.6). */
export const NODE_WIDTH = 160;
/** Horizontal gap between columns. */
export const GAP_X = 40;
/** Vertical gap between rows. */
export const GAP_Y = 40;
/** Fixed number of columns; keeps the layout predictable for any module count. */
export const COLUMNS = 6;

/** Assign grid positions to node ids, in the given order. */
export function gridPositions(nodeIds: string[]): Map<string, XYPosition> {
  const positions = new Map<string, XYPosition>();
  nodeIds.forEach((id, index) => {
    const col = index % COLUMNS;
    const row = Math.floor(index / COLUMNS);
    positions.set(id, {
      x: col * (NODE_WIDTH + GAP_X),
      y: row * (NODE_WIDTH * 0.75 + GAP_Y),
    });
  });
  return positions;
}
