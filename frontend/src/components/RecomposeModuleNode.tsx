/**
 * Module container node (issue #10): an editable Chinese name, one aggregated
 * interface line, and a delete button. The member atom chips render as React
 * Flow child nodes positioned by childGridPositions inside this box, so the
 * body only owns the header band.
 *
 * `ModuleNodeBody` is exported separately WITHOUT the PortHandles so jsdom
 * component tests can render it without a React Flow provider (#2).
 */
import { Position, type Node, type NodeProps } from '@xyflow/react';
import { useState, type CSSProperties, type KeyboardEvent } from 'react';
import type { RecomposeModuleData } from '../lib/recompose/derive';
import { scoreColor } from '../lib/depthScore';
import PortHandle from './PortHandle';

interface EditableTextProps {
  value: string;
  onCommit: (next: string) => void;
  style?: CSSProperties;
  placeholder?: string;
  title?: string;
}

/**
 * Double-click to edit, Enter/blur to commit, Escape to cancel.
 * `nodrag` class keeps React Flow from starting a drag on the input.
 */
function EditableText({ value, onCommit, style, placeholder, title }: EditableTextProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const commit = () => {
    setEditing(false);
    const next = draft.trim();
    if (next && next !== value) onCommit(next);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') commit();
    if (e.key === 'Escape') setEditing(false);
  };

  if (editing) {
    return (
      <input
        className="nodrag"
        value={draft}
        autoFocus
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={onKeyDown}
        style={{
          ...inputStyle,
          ...style,
        }}
      />
    );
  }
  return (
    <span
      onDoubleClick={() => {
        setDraft(value);
        setEditing(true);
      }}
      style={{ ...style, cursor: 'text' }}
      title={title}
    >
      {value || <em style={{ opacity: 0.6 }}>{placeholder ?? '双击编辑'}</em>}
    </span>
  );
}

const inputStyle: CSSProperties = {
  width: '100%',
  background: 'rgba(0,0,0,0.35)',
  border: '1px solid var(--accent, #38bdf8)',
  borderRadius: 4,
  color: 'var(--text, #f8fafc)',
  fontSize: 12,
  padding: '2px 4px',
  boxSizing: 'border-box',
  outline: 'none',
};

const headerStyle: CSSProperties = {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  height: 58,
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
  padding: '8px 12px 0',
  boxSizing: 'border-box',
};

const containerStyle: CSSProperties = {
  width: '100%',
  height: '100%',
  position: 'relative',
  borderRadius: 12,
  border: '2px solid var(--border, #475569)',
  background: 'rgba(30, 41, 59, 0.55)',
  color: 'var(--text, #f8fafc)',
  fontFamily:
    'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
  boxShadow: '0 4px 20px rgba(0,0,0,0.25)',
  overflow: 'visible',
};

/** Pure presentational module body (no React Flow handles) — jsdom-testable. */
export function ModuleNodeBody({ data }: { data: RecomposeModuleData }) {
  return (
    <div style={headerStyle} className="recompose-module-node">
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 10, opacity: 0.7, flexShrink: 0 }}>模块</span>
        <EditableText
          value={data.name}
          onCommit={data.onRename}
          title="双击修改模块中文名"
          style={{ fontWeight: 700, fontSize: 13, flex: 1, minWidth: 0 }}
        />
        {!data.implicit && (
          <button
            onClick={data.onDelete}
            title="删除模块（成员原子释放为独立模块）"
            aria-label="删除模块"
            style={deleteStyle}
          >
            ✕
          </button>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontSize: 10, opacity: 0.7, flexShrink: 0 }}>接口</span>
        <EditableText
          value={data.description}
          onCommit={data.onSetDescription}
          placeholder="描述模块的聚合接口"
          style={{ fontSize: 11, color: 'var(--text-2, #94a3b8)', flex: 1, minWidth: 0 }}
        />
        <span
          style={{
            flexShrink: 0,
            fontSize: 10,
            color: scoreColor(data.score),
            fontWeight: 600,
          }}
          title="模块聚合深度分（成员端口并集）"
        >
          {data.score}
        </span>
      </div>
    </div>
  );
}

const deleteStyle: CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--text-2, #94a3b8)',
  cursor: 'pointer',
  fontSize: 12,
  padding: '2px 6px',
  borderRadius: 4,
  flexShrink: 0,
};

export default function RecomposeModuleNode({ data }: NodeProps<Node<RecomposeModuleData>>) {
  return (
    <div style={containerStyle} className="recompose-module">
      <ModuleNodeBody data={data} />
      <PortHandle type="target" position={Position.Left} />
      <PortHandle type="source" position={Position.Right} />
    </div>
  );
}
