/**
 * Right-side fixed inspector panel (audit M8): shows details for the
 * currently selected node, edge, or diagnostic. Fixed position + width keeps
 * the layout predictable.
 *
 * Issue #8 adds two drill-down branches: an *atom* node shows its Chinese
 * name, one-line description, depth score and member files with their ports;
 * the aggregated *external* ("第三方依赖") node lists the concrete libraries.
 */
import type { CSSProperties } from 'react';
import type { Module, Port, Diagnostic } from '../api/types';
import type { AggregatedEdgeData } from '../lib/graphToFlow';
import type { DepthScore } from '../lib/depthScore';
import { scoreColor } from '../lib/depthScore';

export interface ModuleNodeSelection {
  type: 'node';
  kind: 'module';
  id: string;
  label: string;
  module?: Module;
  score?: DepthScore;
  diagnostics?: string[];
}

export interface AtomNodeSelection {
  type: 'node';
  kind: 'atom';
  id: string;
  label: string;
  name: string;
  description: string;
  files: string[];
  modules: Module[];
  score: DepthScore;
  portCount: number;
}

export interface ExternalNodeSelection {
  type: 'node';
  kind: 'external';
  id: string;
  label: string;
  externalNames?: string[];
}

/** A recomposed module container (issue #10): aggregated interface drill-down. */
export interface RecomposedModuleSelection {
  type: 'node';
  kind: 'recomposeModule';
  id: string;
  label: string;
  name: string;
  description: string;
  memberAtomNames: string[];
  memberFileCount: number;
  ports: Port[];
  score: DepthScore;
}

export type NodeSelection =
  | ModuleNodeSelection
  | AtomNodeSelection
  | ExternalNodeSelection
  | RecomposedModuleSelection;

export interface EdgeSelection {
  type: 'edge';
  /** Edge id (set by the recompose canvas so "删除此边" can route it, #3). */
  id?: string;
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
  /** When provided, edge details get a "删除此边" button (recompose mode, #3). */
  onDeleteEdge?: (edgeId: string) => void;
}

export default function Inspector({
  selection,
  graphDiagnostics,
  onClose,
  onDeleteEdge,
}: InspectorProps) {
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
      {selection?.type === 'edge' && (
        <EdgeDetail selection={selection} onDeleteEdge={onDeleteEdge} />
      )}

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
  switch (selection.kind) {
    case 'atom':
      return <AtomDetail selection={selection} />;
    case 'external':
      return <ExternalDetail selection={selection} />;
    case 'module':
      return <ModuleDetail selection={selection} />;
    case 'recomposeModule':
      return <RecomposedModuleDetail selection={selection} />;
  }
}

function RecomposedModuleDetail({ selection }: { selection: RecomposedModuleSelection }) {
  return (
    <div style={{ fontSize: 12, marginTop: 8 }}>
      <p style={{ margin: '4px 0', fontWeight: 600, fontSize: 13 }}>{selection.name}</p>
      <p style={{ margin: '4px 0', color: 'var(--text-2, #94a3b8)' }}>
        {selection.description || '（未填写接口描述）'}
      </p>
      <p style={{ margin: '4px 0' }}>
        深度分：
        <span style={{ color: scoreColor(selection.score) }}>{selection.score}</span>
        {' '}（{selection.ports.length} 个端口，{selection.memberFileCount} 个文件）
      </p>
      <p style={{ margin: '4px 0' }}>聚合接口（成员功能原子）：</p>
      <ul style={{ margin: '4px 0', paddingLeft: 16 }}>
        {selection.memberAtomNames.map((n) => (
          <li key={n} style={{ marginBottom: 2 }}>
            {n}
          </li>
        ))}
      </ul>
      {selection.ports.length > 0 && (
        <>
          <p style={{ margin: '4px 0' }}>端口（{selection.ports.length}）：</p>
          <ul style={{ margin: '4px 0', paddingLeft: 16 }}>
            {selection.ports.map((p, i) => (
              <li key={i} style={{ marginBottom: 2 }}>
                <code style={{ fontSize: 11 }}>{p.signature}</code>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function ModuleDetail({ selection }: { selection: ModuleNodeSelection }) {
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

function AtomDetail({ selection }: { selection: AtomNodeSelection }) {
  return (
    <div style={{ fontSize: 12, marginTop: 8 }}>
      <p style={{ margin: '4px 0', fontWeight: 600, fontSize: 13 }}>{selection.name}</p>
      <p style={{ margin: '4px 0', color: 'var(--text-2, #94a3b8)' }}>{selection.description}</p>
      <p style={{ margin: '4px 0' }}>
        深度分：
        <span style={{ color: scoreColor(selection.score) }}>{selection.score}</span>
        {' '}（{selection.portCount} 个端口）
      </p>
      <p style={{ margin: '4px 0' }}>成员文件（{selection.files.length}）：</p>
      <ul style={{ margin: '4px 0', paddingLeft: 16 }}>
        {selection.modules.map((m) => (
          <li key={m.id} style={{ marginBottom: 6 }}>
            <div style={{ wordBreak: 'break-all' }}>{m.id}</div>
            <ul style={{ margin: '2px 0 0', paddingLeft: 16 }}>
              {m.ports.length === 0 && (
                <li style={{ fontSize: 10, color: 'var(--text-2, #94a3b8)' }}>无公开端口</li>
              )}
              {m.ports.map((p, i) => (
                <li key={i}>
                  <code style={{ fontSize: 10 }}>{p.signature}</code>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ExternalDetail({ selection }: { selection: ExternalNodeSelection }) {
  return (
    <div style={{ fontSize: 12, marginTop: 8 }}>
      <p style={{ margin: '4px 0' }}>类型：第三方模块</p>
      <p style={{ margin: '4px 0', wordBreak: 'break-all' }}>{selection.label}</p>
      {selection.externalNames && selection.externalNames.length > 0 && (
        <>
          <p style={{ margin: '4px 0' }}>具体依赖（{selection.externalNames.length}）：</p>
          <ul style={{ margin: '4px 0', paddingLeft: 16 }}>
            {selection.externalNames.map((n) => (
              <li key={n}>
                <code style={{ fontSize: 11 }}>{n}</code>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function EdgeDetail({
  selection,
  onDeleteEdge,
}: {
  selection: EdgeSelection;
  onDeleteEdge?: (edgeId: string) => void;
}) {
  const manual = selection.data.manual === true;
  return (
    <div style={{ fontSize: 12, marginTop: 8 }}>
      <p style={{ margin: '4px 0', wordBreak: 'break-all' }}>
        {selection.source} → {selection.target}
      </p>
      <p style={{ margin: '4px 0' }}>类型：{selection.label}</p>
      {manual ? (
        // Manual edges have no underlying call sites; skip rawEdges entirely (#1).
        <p style={{ margin: '4px 0', color: 'var(--accent, #38bdf8)' }}>
          手动添加的依赖（无底层调用点）
        </p>
      ) : (
        <p style={{ margin: '4px 0' }}>调用点（{selection.data.rawEdges.length} 条边）：</p>
      )}
      {!manual && (
        <ul style={{ margin: '4px 0', paddingLeft: 16 }}>
          {selection.data.rawEdges.map((e, i) => (
            <li key={i}>
              {e.kind}
              {e.targetPort ? ` → ${e.targetPort}` : ''} @
              {e.sites.map((s) => s.line).join(', ')}
            </li>
          ))}
        </ul>
      )}
      {onDeleteEdge && selection.id && (
        <button
          onClick={() => onDeleteEdge(selection.id!)}
          style={{
            marginTop: 8,
            padding: '4px 10px',
            borderRadius: 6,
            border: '1px solid var(--warn, #f87171)',
            background: 'transparent',
            color: 'var(--warn, #f87171)',
            fontSize: 11,
            cursor: 'pointer',
          }}
        >
          删除此边
        </button>
      )}
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
