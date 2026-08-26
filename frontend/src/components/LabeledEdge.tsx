/**
 * Edge with a kind label. Because edges are aggregated by (source, target)
 * (D12 / audit M2), `label` holds the merged kinds (e.g. "import, call");
 * the Inspector shows the full raw edges + call sites.
 */
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type Edge,
  type EdgeProps,
} from '@xyflow/react';
import type { AggregatedEdgeData } from '../lib/graphToFlow';

export default function LabeledEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps<Edge<AggregatedEdgeData>>) {
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: 'var(--text-2, #94a3b8)',
          strokeWidth: 2,
          markerEnd: 'url(#arrowhead)',
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            background: 'rgba(15,23,42,0.85)',
            color: 'var(--text-2, #94a3b8)',
            fontSize: 9,
            padding: '1px 5px',
            borderRadius: 4,
            border: '1px solid var(--border, #475569)',
            pointerEvents: 'none',
          }}
        >
          {data?.kinds.join(', ') ?? ''}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
