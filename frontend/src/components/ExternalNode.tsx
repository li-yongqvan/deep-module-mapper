/**
 * External (third-party) module node: grey dashed border, no score, no
 * handles (D11 / audit B1). Keeps third-party imports visible without
 * implying any deep/shallow semantics for them.
 */
import type { Node, NodeProps } from '@xyflow/react';
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
    </div>
  );
}
