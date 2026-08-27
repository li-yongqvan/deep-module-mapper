/**
 * Feature-atom node (issue #8): rounded rectangle titled with the atom's
 * Chinese name + one-line description, so a non-developer reads "what this
 * does" rather than "where the files are". Border color reflects the atom's
 * naive depth score (reused from depthScore.ts).
 *
 * Node width comes from the shared ATOM_NODE_WIDTH constant (C6: same source
 * drives the grid spacing in layout.ts).
 */
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import type { CSSProperties } from 'react';
import type { AtomNodeData } from '../lib/graphToFeatureFlow';
import { scoreColor } from '../lib/depthScore';
import { ATOM_NODE_WIDTH } from '../lib/layout';

const NODE_STYLE: CSSProperties = {
  width: ATOM_NODE_WIDTH,
  borderRadius: 10,
  border: '2px solid var(--border, #475569)',
  background: 'var(--panel, #1e293b)',
  color: 'var(--text, #f8fafc)',
  padding: 12,
  fontSize: 13,
  fontFamily:
    'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
  boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
};

const badgeStyle: CSSProperties = {
  padding: '2px 6px',
  borderRadius: 4,
  background: 'rgba(255,255,255,0.08)',
  fontSize: 10,
};

export default function FeatureAtomNode({ data }: NodeProps<Node<AtomNodeData>>) {
  const borderColor = scoreColor(data.score);
  return (
    <div
      style={{ ...NODE_STYLE, borderColor }}
      className="atom-node"
      title={`${data.name}\n${data.description}\n成员文件：\n${data.files.join('\n')}`}
    >
      <div style={{ fontWeight: 600, marginBottom: 4, wordBreak: 'break-all' }}>
        {data.name}
      </div>
      <div
        style={{
          fontSize: 11,
          color: 'var(--text-2, #94a3b8)',
          marginBottom: 8,
          lineHeight: 1.4,
        }}
      >
        {data.description}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <span style={badgeStyle}>{data.files.length} 个文件</span>
        <span style={{ ...badgeStyle, color: borderColor }}>{data.score}</span>
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
