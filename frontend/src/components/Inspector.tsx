/**
 * Right-side fixed inspector panel (audit M8): shows details for the
 * currently selected node, edge, or diagnostic. Fixed position + width keeps
 * the layout predictable.
 */
import type { CSSProperties } from 'react';
import type { Module, Port, Diagnostic } from '../api/types';
import type { AggregatedEdgeData } from '../lib/graphToFlow';
import type { DepthScore } from '../lib/depthScore';
import { scoreColor } from '../lib/depthScore';

export interface NodeSelection {
  type: 'node';
  kind: 'module' | 'external';
  id: string;
  label: string;
  module?: Module;
  score?: DepthScore;
  diagnostics?: string[];
}

export interface EdgeSelection {
  type: 'edge';
  source: string;
  target: string;
  label: string;
  data: AggregatedEdgeData;
}

export type Selection = NodeSelection | EdgeSelection;

interface InspectorProps {
  selection: Selection | null;
  graphDiagnostics: Diagnostic[];
  onClose: () => void;
}

export default function Inspector({ selection, graphDiagnostics, onClose }: InspectorProps) {
  return (
    <aside
      style={{
        position: 'absolute',
        right: 12,
        top: 12,
        bottom: 12,
        width: 280,
        background: 'var(--panel, #1e293b)',
        border: '1px solid var(--border, #475569)',
        borderRadius: 10,
        padding: 14,
        overflowY: 'auto',
        boxShadow: '0 10px 30px rgba(0,0,0,0.4)',
        zIndex: 10,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, fontSize: 13 }}>详情</h4>
        <button onClick={onClose} style={closeStyle} aria-label="关闭详情">
          ✕
        </button>
      </div>

      {selection?.type === 'node' && <NodeDetail selection={selection} />}
      {selection?.type === 'edge' && <EdgeDetail selection={selection} />}

      {graphDiagnostics.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ margin: '0 0 6px', fontSize: 12, color: 'var(--text-2, #94a3b8)' }}>
            诊断（{graphDiagnostics.length}）
          </h4>
          <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11, color: 'var(--mid, #fbbf24)' }}>
            {graphDiagnostics.slice(0, 20).map((d, i) => (
              <li key={i}>
                {d.moduleId}:{d.line} [{d.kind}] {d.message}
              </li>
            ))}
            {graphDiagnostics.length > 20 && <li>…共 {graphDiagnostics.length} 条</li>}
          </ul>
        </div>
      )}
    </aside>
  );
}

function NodeDetail({ selection }: { selection: NodeSelection }) {
  if (selection.kind === 'external') {
    return (
      <div style={{ fontSize: 12, marginTop: 8 }}>
        <p style={{ margin: '4px 0' }}>类型：第三方模块</p>
        <p style={{ margin: '4px 0', wordBreak: 'break-all' }}>{selection.label}</p>
      </div>
    );
  }
  const ports = selection.module?.ports ?? [];
  return (
    <div style={{ fontSize: 12, marginTop: 8 }}>
      <p style={{ margin: '4px 0', wordBreak: 'break-all' }}>路径：{selection.label}</p>
      <p style={{ margin: '4px 0' }}>
        深度分：<span style={{ color: scoreColor(selection.score ?? 'moderate') }}>{selection.score}</span>
      </p>
      <p style={{ margin: '4px 0' }}>端口（{ports.length}）：</p>
      <ul style={{ margin: '4px 0', paddingLeft: 16 }}>
        {ports.map((p: Port, i) => (
          <li key={i} style={{ marginBottom: 2 }}>
            <code style={{ fontSize: 11 }}>{p.signature}</code>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EdgeDetail({ selection }: { selection: EdgeSelection }) {
  return (
    <div style={{ fontSize: 12, marginTop: 8 }}>
      <p style={{ margin: '4px 0', wordBreak: 'break-all' }}>
        {selection.source} → {selection.target}
      </p>
      <p style={{ margin: '4px 0' }}>类型：{selection.label}</p>
      <p style={{ margin: '4px 0' }}>调用点（{selection.data.rawEdges.length} 条边）：</p>
      <ul style={{ margin: '4px 0', paddingLeft: 16 }}>
        {selection.data.rawEdges.map((e, i) => (
          <li key={i}>
            {e.kind}
            {e.targetPort ? ` → ${e.targetPort}` : ''} @
            {e.sites.map((s) => s.line).join(', ')}
          </li>
        ))}
      </ul>
    </div>
  );
}

const closeStyle: CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--text-2, #94a3b8)',
  cursor: 'pointer',
  fontSize: 14,
};
