/**
 * Module node: rounded rectangle whose border color reflects the naive
 * depth score (green/yellow/red traffic light, D2/D10).
 *
 * NOTE (audit B2 / Q1): this ticket does NOT render one Handle per public
 * port. Dependencies are expressed at the module level with a single
 * source (right) / target (left) handle pair, matching the prototype
 * (prototype-ui.html renders one in/out dot pair per node).
 */
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import type { CSSProperties } from 'react';
import type { ModuleNodeData } from '../lib/graphToFlow';
import { scoreColor } from '../lib/depthScore';

const NODE_STYLE: CSSProperties = {
  width: 160,
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
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </div>
  );
}

/** 10px circular accent handle with a 2px node-color border (prototype §2.6). */
const handleStyle: CSSProperties = {
  width: 10,
  height: 10,
  borderRadius: '50%',
  background: 'var(--accent, #38bdf8)',
  border: '2px solid var(--bg, #0f172a)',
};
