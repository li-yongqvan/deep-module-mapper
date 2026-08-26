/**
 * Real-view page: scan form + status banner on top, React Flow canvas below,
 * right-side inspector (M8). Dark theme matches prototype-ui.html palette.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  useNodesState,
  useEdgesState,
  type NodeMouseHandler,
  type EdgeMouseHandler,
  type Edge as FlowEdge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import type { Graph, Module } from './api/types';
import { useScanJob } from './hooks/useScanJob';
import { graphToFlow, type AggregatedEdgeData, type FlowNode } from './lib/graphToFlow';
import { gridPositions } from './lib/layout';
import ModuleNode from './components/ModuleNode';
import ExternalNode from './components/ExternalNode';
import LabeledEdge from './components/LabeledEdge';
import ScanForm from './components/ScanForm';
import ScanStatus from './components/ScanStatus';
import Inspector, {
  type Selection,
  type NodeSelection,
  type EdgeSelection,
} from './components/Inspector';

// Custom node/edge types must be stable across renders (React Flow requirement).
const nodeTypes = { moduleNode: ModuleNode, externalNode: ExternalNode };
const edgeTypes = { labeledEdge: LabeledEdge };

export default function App() {
  const { state, start, cancel } = useScanJob();
  const [selection, setSelection] = useState<Selection | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);

  const flowGraph = useMemo(() => (graph ? graphToFlow(graph) : null), [graph]);

  // Rehydrate React Flow node positions on every new graph.
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<
    FlowEdge<AggregatedEdgeData>
  >([]);

  useEffect(() => {
    if (!flowGraph) return;
    const positions = gridPositions(flowGraph.nodes.map((n) => n.id));
    setNodes(
      flowGraph.nodes.map((n) => ({
        ...n,
        position: positions.get(n.id) ?? n.position,
      })),
    );
    setEdges(flowGraph.edges);
    setSelection(null); // reset inspector on a fresh graph
  }, [flowGraph, setNodes, setEdges]);

  // Lift the finished graph out of the scan state.
  useEffect(() => {
    if (state.kind === 'done' || state.kind === 'empty') {
      setGraph(state.graph);
    } else if (state.kind === 'idle') {
      setGraph(null);
    }
  }, [state]);

  const handleSubmit = useCallback(
    (path: string) => {
      void start(path);
      setGraph(null);
    },
    [start],
  );

  const handleNodeClick: NodeMouseHandler<FlowNode> = useCallback(
    (_, node) => {
      const data = node.data;
      if (data.kind === 'external') {
        setSelection({
          type: 'node',
          kind: 'external',
          id: node.id,
          label: data.label,
        } satisfies NodeSelection);
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
      } satisfies NodeSelection);
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
          现实视图
        </h1>
        <ScanForm onSubmit={handleSubmit} disabled={state.kind === 'scanning'} />
        <ScanStatus
          state={state}
          onCancel={cancel}
          onRescan={() => (state.kind === 'jobLost' || state.kind === 'networkError' || state.kind === 'timeout' ? cancel() : undefined)}
        />
      </header>

      <main style={{ flex: 1, position: 'relative' }}>
        {!flowGraph && !empty && !scanFailed && (
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

        {flowGraph && !empty && (
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

        {flowGraph && selection && (
          <Inspector
            selection={selection}
            graphDiagnostics={graph?.diagnostics ?? []}
            onClose={() => setSelection(null)}
          />
        )}
      </main>
    </div>
  );
}
