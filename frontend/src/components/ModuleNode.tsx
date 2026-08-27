/**
 * Module node: rounded rectangle whose border color reflects the naive
 * depth score (green/yellow/red traffic light, D2/D10).
 *
 * NOTE (audit B2 / Q1): this ticket does NOT render one Handle per public
 * port. Dependencies are expressed at the module level with a single
 * source (right) / target (left) handle pair, matching the prototype
 * (prototype-ui.html renders one in/out dot pair per node).
 */
import { Position, type Node, type NodeProps } from '@xyflow/react';
import type { CSSProperties } from 'react';
import type { ModuleNodeData } from '../lib/graphToFlow';
import { scoreColor } from '../lib/depthScore';
import { NODE_WIDTH } from '../lib/layout';
import PortHandle from './PortHandle';

const NODE_STYLE: CSSProperties = {
  width: NODE_WIDTH,
  borderRadius: 10,
  border: '2px solid var(--border, #475569)',
  background: 'var(--panel, #1e293b)',
  color: 'var(--text, #f8fafc)',
  padding: 10,
  fontSize: 13,
  fontFamily:
    'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
  boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
};

export default function ModuleNode({ data }: NodeProps<Node<ModuleNodeData>>) {
  const borderColor = scoreColor(data.score);
  return (
    <div
      style={{ ...NODE_STYLE, borderColor }}
      className="module-node"
      title={`${data.label}\nscore: ${data.score}`}
    >
      <div
        style={{ fontWeight: 600, marginBottom: 4, wordBreak: 'break-all' }}
      >
        {data.label}
      </div>
      <div
        style={{
          marginTop: 8,
          display: 'flex',
          gap: 6,
          fontSize: 10,
        }}
      >
        <span
          style={{
            padding: '2px 6px',
            borderRadius: 4,
            background: 'rgba(255,255,255,0.08)',
          }}
        >
          {data.portCount} ports
        </span>
        <span
          style={{
            padding: '2px 6px',
            borderRadius: 4,
            background: 'rgba(255,255,255,0.08)',
            color: borderColor,
          }}
        >
          {data.score}
        </span>
      </div>
      <PortHandle type="target" position={Position.Left} />
      <PortHandle type="source" position={Position.Right} />
    </div>
  );
}
