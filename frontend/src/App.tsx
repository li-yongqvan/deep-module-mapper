/**
 * Deep Module Mapper page: scan form + status banner on top, view toggle,
 * React Flow canvas below, right-side inspector (M8). Dark theme matches
 * prototype-ui.html palette.
 *
 * Two views (issue #8 D1): the **feature view** (default) aggregates files
 * into functional atoms (Chinese name + one-line description, noise hidden);
 * the **real view** shows the file-level module graph (#7). Switching views
 * resets the inspector selection (audit S3 / I1).
 */
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type NodeMouseHandler,
  type EdgeMouseHandler,
  type Edge as FlowEdge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import type { Graph, Module } from './api/types';
import type { ExternalNodeData, ModuleNodeData } from './lib/graphToFlow';
import {
  graphToFeatureFlow,
  type AtomNodeData,
  type FeatureFlowGraph,
} from './lib/graphToFeatureFlow';
import { useScanJob } from './hooks/useScanJob';
import { graphToFlow, type AggregatedEdgeData } from './lib/graphToFlow';
import { gridPositions, NODE_WIDTH, ATOM_NODE_WIDTH } from './lib/layout';
import ModuleNode from './components/ModuleNode';
import ExternalNode from './components/ExternalNode';
import FeatureAtomNode from './components/FeatureAtomNode';
import LabeledEdge from './components/LabeledEdge';
import ScanForm from './components/ScanForm';
import ScanStatus from './components/ScanStatus';
import RecomposeCanvas from './components/RecomposeCanvas';
import Inspector, {
  type Selection,
  type ModuleNodeSelection,
  type AtomNodeSelection,
  type ExternalNodeSelection,
  type EdgeSelection,
} from './components/Inspector';
// Recompose model helpers (issue #10): design init/sanitize + edge delete for
// the Inspector's "删除此边" button.
import { initialDesign } from './lib/recompose/derive';
import { loadDesign, sanitizeDesign } from './lib/recompose/persistence';
import { onDeleteEdge as recomposeOnDeleteEdge } from './lib/recompose/edges';
import type { RecomposedDesign } from './lib/recompose/types';

type ViewMode = 'feature' | 'real' | 'recompose';

/** Union of every node type either view can render. */
type AppFlowNode = Node<ModuleNodeData | ExternalNodeData | AtomNodeData>;

// Custom node/edge types must be stable across renders (React Flow requirement).
const nodeTypes = {
  moduleNode: ModuleNode,
  externalNode: ExternalNode,
  atomNode: FeatureAtomNode,
};
const edgeTypes = { labeledEdge: LabeledEdge };

export default function App() {
  const { state, start, cancel } = useScanJob();
  const [selection, setSelection] = useState<Selection | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  // Feature view (atoms) is the default; real view keeps the file-level map;
  // recompose view is the issue #10 canvas (atoms -> modules).
  const [viewMode, setViewMode] = useState<ViewMode>('feature');
  // Last submitted path, so the rescan button can re-run the same scan.
  const [lastPath, setLastPath] = useState('');
  // Recompose design lives in App (not the canvas) so switching views never
  // loses unsaved edits (§6.8); localStorage is the explicit "保存" write.
  const [recomposeDesign, setRecomposeDesign] = useState<RecomposedDesign | null>(null);

  // Feature-flow transform, shared by the feature view and the recompose canvas.
  const featureFlow = useMemo(
    () => (graph ? graphToFeatureFlow(graph) : null),
    [graph],
  );

  const flowGraph = useMemo(
    () =>
      graph
        ? viewMode === 'feature'
          ? featureFlow
          : viewMode === 'real'
            ? graphToFlow(graph)
            : null
        : null,
    [graph, viewMode, featureFlow],
  );

  // Rehydrate React Flow node positions on every new graph or view switch.
  const [nodes, setNodes, onNodesChange] = useNodesState<AppFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<
    FlowEdge<AggregatedEdgeData>
  >([]);

  useEffect(() => {
    if (!flowGraph) return;
    const nodeWidth = viewMode === 'feature' ? ATOM_NODE_WIDTH : NODE_WIDTH;
    const positions = gridPositions(flowGraph.nodes.map((n) => n.id), nodeWidth);
    setNodes(
      flowGraph.nodes.map((n) => ({
        ...n,
        position: positions.get(n.id) ?? n.position,
      })) as AppFlowNode[],
    );
    setEdges(flowGraph.edges);
    setSelection(null); // reset inspector on a fresh graph OR view switch
  }, [flowGraph, viewMode, setNodes, setEdges]);

  // Lift the finished graph out of the scan state.
  useEffect(() => {
    if (state.kind === 'done' || state.kind === 'empty') {
      setGraph(state.graph);
    } else if (state.kind === 'idle') {
      setGraph(null);
    }
  }, [state]);

  // Recompute design when the scan settles (#6): a NEW path reloads from that
  // path's saved design (or the manifest baseline); the SAME path rescanned
  // keeps the in-memory design (layout + unsaved edits) and only sanitizes it
  // against the fresh graph.
  useEffect(() => {
    if (!featureFlow || !graph) return;
    setRecomposeDesign((d) => {
      if (d === null) return loadDesign(lastPath) ?? initialDesign(featureFlow);
      return sanitizeDesign(d, featureFlow, graph);
    });
  }, [featureFlow, lastPath, graph]);

  // Reset the inspector when switching modes (shared canvas also does this on
  // flowGraph change, but recompose has no flowGraph to key off).
  useEffect(() => setSelection(null), [viewMode]);

  // Inspector "删除此边" routes through the recompose edge transition table
  // (only user-drawn edges are ever rendered, so deletion is manual-only, #18).
  const handleRecomposeDeleteEdge = useCallback((edgeId: string) => {
    setRecomposeDesign((d) => (d ? recomposeOnDeleteEdge(d, edgeId) : d));
  }, []);

  const handleSubmit = useCallback(
    (path: string) => {
      setLastPath(path);
      // A different path gets a fresh design (loaded from ITS storage key on
      // scan settle); a same-path rescan keeps the in-memory design (#6).
      if (path !== lastPath) setRecomposeDesign(null);
      void start(path);
      setGraph(null);
    },
    [lastPath, start],
  );

  // Rescan from the last submitted path (fixes inert "重新扫描" button).
  const handleRescan = useCallback(() => {
    if (lastPath) {
      void start(lastPath);
      setGraph(null);
    }
  }, [lastPath, start]);

  const handleNodeClick: NodeMouseHandler<AppFlowNode> = useCallback(
    (_, node) => {
      const data = node.data;
      if (data.kind === 'external') {
        const extData = data as ExternalNodeData & { externalNames?: string[] };
        setSelection({
          type: 'node',
          kind: 'external',
          id: node.id,
          label: extData.label,
          externalNames: extData.externalNames ?? [],
        } satisfies ExternalNodeSelection);
        return;
      }
      if (data.kind === 'atom') {
        // Drill-down: the files that make up this atom, with their ports.
        const members =
          graph?.modules.filter((m) => data.files.includes(m.id)) ?? [];
        setSelection({
          type: 'node',
          kind: 'atom',
          id: node.id,
          label: data.name,
          name: data.name,
          description: data.description,
          files: data.files,
          modules: members,
          score: data.score,
          portCount: data.portCount,
        } satisfies AtomNodeSelection);
        return;
      }
      const module: Module | undefined = graph?.modules.find(
        (m) => m.id === node.id,
      );
      setSelection({
        type: 'node',
        kind: 'module',
        id: node.id,
        label: data.label,
        module,
        score: data.score,
        diagnostics: data.diagnostics,
      } satisfies ModuleNodeSelection);
    },
    [graph],
  );

  const handleEdgeClick: EdgeMouseHandler = useCallback((_, edge) => {
    setSelection({
      type: 'edge',
      source: edge.source,
      target: edge.target,
      label: String(edge.label ?? ''),
      data: edge.data as unknown as AggregatedEdgeData,
    } satisfies EdgeSelection);
  }, []);

  const empty = state.kind === 'empty';
  const scanFailed = state.kind === 'error';
  // Feature view with zero atoms (e.g. a codebase the manifest doesn't cover):
  // show a hint instead of an empty canvas (I3). `isEmpty` alone is not enough
  // — a graph with modules but no manifest match has nodes.length === 0.
  const featureEmpty =
    viewMode === 'feature' && flowGraph !== null && flowGraph.nodes.length === 0;
  const unassignedCount =
    viewMode === 'feature' && flowGraph
      ? (flowGraph as FeatureFlowGraph).unassignedCount
      : 0;

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg, #0f172a)',
        color: 'var(--text, #f8fafc)',
        fontFamily:
          'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
      }}
    >
      <header
        style={{
          padding: '12px 20px',
          borderBottom: '1px solid var(--border, #475569)',
          display: 'flex',
          gap: 16,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <h1 style={{ fontSize: 16, margin: 0, whiteSpace: 'nowrap' }}>
          模块地图
        </h1>
        <div style={{ display: 'flex', gap: 4 }} role="group" aria-label="视图切换">
          {(['feature', 'real', 'recompose'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              style={{
                ...toggleStyle,
                ...(viewMode === mode ? toggleActiveStyle : {}),
              }}
              aria-pressed={viewMode === mode}
            >
              {mode === 'feature' ? '功能视图' : mode === 'real' ? '现实视图' : '重组视图'}
            </button>
          ))}
        </div>
        <ScanForm onSubmit={handleSubmit} disabled={state.kind === 'scanning'} />
        <ScanStatus
          state={state}
          onCancel={cancel}
          onRescan={handleRescan}
        />
      </header>

      <main style={{ flex: 1, position: 'relative' }}>
        {viewMode === 'recompose' ? (
          <RecomposeCanvas
            design={recomposeDesign}
            graph={graph}
            featureFlow={featureFlow}
            onDesignChange={setRecomposeDesign}
            path={lastPath}
            selection={selection}
            onSelect={setSelection}
          />
        ) : (
          <>
            {!flowGraph && !empty && !scanFailed && !featureEmpty && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text-2, #94a3b8)',
                }}
              >
                输入代码目录路径并点击「扫描」，等待完成后渲染模块图
              </div>
            )}

            {empty && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--mid, #fbbf24)',
                }}
              >
                扫描完成，但未解析到任何模块
              </div>
            )}

            {featureEmpty && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  color: 'var(--text-2, #94a3b8)',
                  textAlign: 'center',
                  padding: '0 24px',
                }}
              >
                <div>该代码库暂无功能清单（feature-atoms.json）</div>
                <div style={{ fontSize: 12 }}>
                  {unassignedCount} 个文件未分组。可切换到「现实视图」查看文件级结构。
                </div>
              </div>
            )}

            {flowGraph && !empty && !featureEmpty && (
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                onNodeClick={handleNodeClick}
                onEdgeClick={handleEdgeClick}
                fitView
                proOptions={{ hideAttribution: true }}
                colorMode="dark"
              >
                <Background
                  variant={BackgroundVariant.Dots}
                  gap={24}
                  size={1}
                  color="rgba(148,163,184,0.15)"
                />
                <Controls />
              </ReactFlow>
            )}
          </>
        )}

        {/* Inspector shows on selection, OR when the parser reported
            diagnostics (handoff §5: show diagnostics without a click). */}
        {(flowGraph || viewMode === 'recompose') &&
          (selection !== null || (graph?.diagnostics?.length ?? 0) > 0) && (
            <Inspector
              selection={selection}
              graphDiagnostics={graph?.diagnostics ?? []}
              onClose={() => setSelection(null)}
              onDeleteEdge={
                viewMode === 'recompose' ? handleRecomposeDeleteEdge : undefined
              }
            />
          )}
      </main>
    </div>
  );
}

const toggleStyle: CSSProperties = {
  padding: '6px 12px',
  borderRadius: 6,
  border: '1px solid var(--border, #475569)',
  background: 'transparent',
  color: 'var(--text-2, #94a3b8)',
  fontSize: 12,
  cursor: 'pointer',
};
const toggleActiveStyle: CSSProperties = {
  background: 'var(--accent, #38bdf8)',
  borderColor: 'var(--accent, #38bdf8)',
  color: '#000',
  fontWeight: 600,
};
