/**
 * External (third-party) module node: grey dashed border, no score (D11 /
 * audit B1). Keeps third-party imports visible without implying any
 * deep/shallow semantics for them.
 *
 * NOTE (issue #8): this node DOES render a source/target handle pair. Without
 * handles React Flow cannot attach edges to it (error #008: "Couldn't create
 * edge for target handle id null"), so external edges were silently dropped
 * in both views. Handles fix the edge rendering for the real view and the
 * feature view's aggregated "第三方依赖" node alike.
 */
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import type { CSSProperties } from 'react';
import type { ExternalNodeData } from '../lib/graphToFlow';

export default function ExternalNode({ data }: NodeProps<Node<ExternalNodeData>>) {
  return (
    <div
      style={{
        width: 160,
        borderRadius: 10,
        border: '2px dashed var(--text-2, #94a3b8)',
        background: 'var(--panel, #1e293b)',
        color: 'var(--text-2, #94a3b8)',
        padding: 10,
        fontSize: 12,
        fontFamily:
          'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
        boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
      }}
      title={`third-party: ${data.label}`}
    >
      <div style={{ fontWeight: 600, wordBreak: 'break-all' }}>
        {data.label}
      </div>
      <div style={{ marginTop: 4, fontSize: 10, opacity: 0.8 }}>
        third-party
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
