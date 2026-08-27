/**
 * Atom chip: a compact child node inside a module container (issue #10).
 * It never carries handles — dependency edges attach at the module level — and
 * it is draggable so the user can pull it in/out of modules.
 *
 * Size comes from the shared recompose constants (CHIP_W/CHIP_H) via the node
 * width/height set in deriveNodes; the div fills the node box.
 */
import { type Node, type NodeProps } from '@xyflow/react';
import type { CSSProperties } from 'react';
import type { AtomNodeData } from '../lib/graphToFeatureFlow';

const chipStyle: CSSProperties = {
  width: '100%',
  height: '100%',
  borderRadius: 8,
  border: '1px solid var(--border, #475569)',
  background: 'var(--panel, #1e293b)',
  color: 'var(--text, #f8fafc)',
  padding: '0 8px',
  fontSize: 11,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  boxSizing: 'border-box',
  fontFamily:
    'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
};

export default function AtomChipNode({ data }: NodeProps<Node<AtomNodeData>>) {
  return (
    <div
      style={chipStyle}
      className="atom-chip-node"
      title={`${data.name}\n${data.description}\n成员文件：\n${data.files.join('\n')}`}
    >
      <span
        style={{
          fontWeight: 600,
          flex: 1,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {data.name}
      </span>
      <span style={{ flexShrink: 0, fontSize: 10, opacity: 0.8 }}>
        {data.files.length} 文件
      </span>
    </div>
  );
}
