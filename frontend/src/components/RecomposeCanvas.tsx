/**
 * Recomposition canvas (issue #10): the third view mode. Users drag functional
 * atoms in/out of module containers and draw/delete dependency edges between
 * modules. The design model lives in App (so switching views never loses
 * unsaved edits, §6.8); this component is the controlled canvas.
 *
 * Structure: `<RecomposeCanvas>` owns the `<ReactFlowProvider>`; `CanvasInner`
 * calls `useReactFlow()` (which requires the provider) — never the other way
 * around (#2).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge as FlowEdge,
  type EdgeChange,
  type EdgeMouseHandler,
  type IsValidConnection,
  type NodeMouseHandler,
  type OnConnect,
  type OnNodeDrag,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import type { Graph } from '../api/types';
import type { FeatureFlowGraph } from '../lib/graphToFeatureFlow';
import { THIRD_PARTY_NODE_ID } from '../lib/graphToFeatureFlow';
import type { AggregatedEdgeData, ExternalNodeData } from '../lib/graphToFlow';
import type { AtomNodeData } from '../lib/graphToFeatureFlow';
import type { RecomposedDesign } from '../lib/recompose/types';
import {
  aggregateInterface,
  atomMetaById,
  buildPortsByAtom,
  deriveNodes,
  initialDesign,
  type RecomposeFlowNode,
} from '../lib/recompose/derive';
import {
  computeAggregatedModuleEdges,
  edgeKey,
  finalEdges,
  onConnectEdge,
  onDeleteEdge,
} from '../lib/recompose/edges';
import {
  applyAtomDrop,
  applyModuleMove,
  createModule,
  deleteModule,
  fallbackAbsolutePosition,
  moduleBoundsFromDesign,
  renameModule,
  setModuleDescription,
} from '../lib/recompose/dragDrop';
import { loadDesign, sanitizeDesign, saveDesign } from '../lib/recompose/persistence';
import RecomposeModuleNode from './RecomposeModuleNode';
import AtomChipNode from './AtomChipNode';
import ExternalNode from './ExternalNode';
import LabeledEdge from './LabeledEdge';
import RecomposeToolbar from './RecomposeToolbar';
import type { Selection } from './Inspector';

// Custom node/edge types must be stable across renders (React Flow requirement).
const recomposeNodeTypes = {
  recomposeModuleNode: RecomposeModuleNode,
  atomChipNode: AtomChipNode,
  externalNode: ExternalNode,
};
const edgeTypes = { labeledEdge: LabeledEdge };

export interface RecomposeCanvasProps {
  design: RecomposedDesign | null;
  graph: Graph | null;
  featureFlow: FeatureFlowGraph | null;
  /** App's design setter (accepts value or updater). */
  onDesignChange: React.Dispatch<React.SetStateAction<RecomposedDesign | null>>;
  /** Scanned codebase path (localStorage key). */
  path: string;
  selection: Selection | null;
  onSelect: (s: Selection | null) => void;
}

export default function RecomposeCanvas(props: RecomposeCanvasProps) {
  if (!props.design || !props.graph || !props.featureFlow) {
    return (
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
        扫描完成后，可在此把功能原子拖进/拖出模块容器，重组出理想架构
      </div>
    );
  }
  return (
    <ReactFlowProvider>
      <CanvasInner {...props} design={props.design} graph={props.graph} featureFlow={props.featureFlow} />
    </ReactFlowProvider>
  );
}

function CanvasInner({
  design,
  graph,
  featureFlow,
  onDesignChange,
  path,
  onSelect,
}: RecomposeCanvasProps & { design: RecomposedDesign; graph: Graph; featureFlow: FeatureFlowGraph }) {
  const rf = useReactFlow();

  const portsByAtom = useMemo(() => buildPortsByAtom(graph), [graph]);
  const atoms = useMemo(() => atomMetaById(featureFlow), [featureFlow]);

  const actions = useMemo(
    () => ({
      onRename: (moduleId: string, name: string) =>
        onDesignChange((d) => (d ? renameModule(d, moduleId, name) : d)),
      onSetDescription: (moduleId: string, description: string) =>
        onDesignChange((d) => (d ? setModuleDescription(d, moduleId, description) : d)),
      onDelete: (moduleId: string) => {
        onSelect(null);
        onDesignChange((d) => (d ? deleteModule(d, moduleId, atoms) : d));
      },
    }),
    [onDesignChange, onSelect, atoms],
  );

  const derivedNodes = useMemo(
    () => deriveNodes(design, featureFlow, portsByAtom, actions),
    [design, featureFlow, portsByAtom, actions],
  );
  const aggregated = useMemo(
    () => computeAggregatedModuleEdges(graph, design),
    [graph, design],
  );
  const aggregateKeys = useMemo(
    () => new Set(aggregated.map((e) => edgeKey(e.source, e.target))),
    [aggregated],
  );
  const derivedEdges = useMemo(
    () => finalEdges(aggregated, design),
    [aggregated, design],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState<RecomposeFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge<AggregatedEdgeData>>([]);

  // Push the derived model into the React Flow store whenever it changes.
  useEffect(() => {
    setNodes(derivedNodes);
  }, [derivedNodes, setNodes]);
  useEffect(() => {
    setEdges(derivedEdges as FlowEdge<AggregatedEdgeData>[]);
  }, [derivedEdges, setEdges]);

  // Toolbar feedback ("已保存" etc.).
  const [feedback, setFeedback] = useState('');
  const feedbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showFeedback = useCallback((msg: string) => {
    setFeedback(msg);
    if (feedbackTimer.current) clearTimeout(feedbackTimer.current);
    feedbackTimer.current = setTimeout(() => setFeedback(''), 1800);
  }, []);

  // Drag stop: dispatch by node identity (#14). The chip's absolute position
  // comes from the store (`internals.positionAbsolute`), never the callback's
  // relative `node.position` (#12).
  const handleNodeDragStop: OnNodeDrag<RecomposeFlowNode> = useCallback(
    (_, node) => {
      const n = node as RecomposeFlowNode;
      if (n.id === THIRD_PARTY_NODE_ID) {
        onDesignChange((d) => (d ? { ...d, thirdPartyPosition: n.position } : d));
        return;
      }
      if (n.data.kind === 'recomposeModule') {
        onDesignChange((d) => (d ? applyModuleMove(d, n.id, n.position) : d));
        return;
      }
      if (n.data.kind === 'atom') {
        const d = n.data as AtomNodeData;
        const internal = rf.getInternalNode(n.id);
        const parent = n.parentId ? rf.getInternalNode(n.parentId) : undefined;
        const abs =
          internal?.internals.positionAbsolute ??
          fallbackAbsolutePosition(n.position, parent?.internals.positionAbsolute);
        onDesignChange((prev) =>
          prev
            ? applyAtomDrop(prev, d.atomId, abs, moduleBoundsFromDesign(prev), atoms)
            : prev,
        );
      }
    },
    [rf, onDesignChange, atoms],
  );

  const handleConnect: OnConnect = useCallback(
    (conn: Connection) => {
      if (!conn.source || !conn.target) return;
      const source = conn.source;
      const target = conn.target;
      onDesignChange((d) =>
        d ? onConnectEdge(d, source, target, aggregateKeys) : d,
      );
    },
    [onDesignChange, aggregateKeys],
  );

  const isValidConnection: IsValidConnection = useCallback((c) => {
    return c.source !== c.target && c.source !== THIRD_PARTY_NODE_ID;
  }, []);

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      for (const ch of changes) {
        if (ch.type === 'remove') {
          onDesignChange((d) =>
            d ? onDeleteEdge(d, ch.id, aggregateKeys) : d,
          );
        }
      }
      onEdgesChange(changes as never);
    },
    [onDesignChange, onEdgesChange, aggregateKeys],
  );

  const handleNodeClick: NodeMouseHandler<RecomposeFlowNode> = useCallback(
    (_, node) => {
      const n = node as RecomposeFlowNode;
      if (n.data.kind === 'recomposeModule') {
        const module = design.modules.find((m) => m.id === n.data.moduleId);
        if (!module) return;
        const { ports, score } = aggregateInterface(module, portsByAtom);
        const memberAtomNames = module.atomIds.map(
          (id) => atoms.get(id)?.name ?? id,
        );
        const memberFileCount = module.atomIds.reduce(
          (acc, id) => acc + (atoms.get(id)?.files.length ?? 0),
          0,
        );
        onSelect({
          type: 'node',
          kind: 'recomposeModule',
          id: module.id,
          label: module.name,
          name: module.name,
          description: module.description,
          memberAtomNames,
          memberFileCount,
          ports,
          score,
        });
        return;
      }
      if (n.data.kind === 'atom') {
        const d = n.data as AtomNodeData;
        const members = graph.modules.filter((m) => d.files.includes(m.id));
        onSelect({
          type: 'node',
          kind: 'atom',
          id: n.id,
          label: d.name,
          name: d.name,
          description: d.description,
          files: d.files,
          modules: members,
          score: d.score,
          portCount: d.portCount,
        });
        return;
      }
      if (n.data.kind === 'external') {
        const d = n.data as ExternalNodeData & { externalNames?: string[] };
        onSelect({
          type: 'node',
          kind: 'external',
          id: n.id,
          label: d.label,
          externalNames: d.externalNames ?? [],
        });
      }
    },
    [design, graph, portsByAtom, atoms, onSelect],
  );

  const handleEdgeClick: EdgeMouseHandler = useCallback(
    (_, edge) => {
      onSelect({
        type: 'edge',
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: String(edge.label ?? ''),
        data: edge.data as unknown as AggregatedEdgeData,
      });
    },
    [onSelect],
  );

  // Toolbar actions.
  const handleCreateModule = useCallback(() => {
    onDesignChange((d) => (d ? createModule(d) : d));
  }, [onDesignChange]);

  const handleSave = useCallback(() => {
    saveDesign(path, design);
    showFeedback('已保存');
  }, [path, design, showFeedback]);

  const handleLoad = useCallback(() => {
    const loaded = loadDesign(path);
    if (!loaded) {
      showFeedback('无已保存设计');
      return;
    }
    onDesignChange(sanitizeDesign(loaded, featureFlow));
    showFeedback('已加载');
  }, [path, featureFlow, onDesignChange, showFeedback]);

  const handleReset = useCallback(() => {
    onDesignChange(initialDesign(featureFlow));
    showFeedback('已重置为建议分组');
  }, [featureFlow, onDesignChange, showFeedback]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={handleEdgesChange}
      nodeTypes={recomposeNodeTypes}
      edgeTypes={edgeTypes}
      onNodeClick={handleNodeClick}
      onEdgeClick={handleEdgeClick}
      onConnect={handleConnect}
      isValidConnection={isValidConnection}
      onNodeDragStop={handleNodeDragStop}
      selectNodesOnDrag={false}
      multiSelectionKeyCode={null}
      deleteKeyCode={null}
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
      <RecomposeToolbar
        onCreateModule={handleCreateModule}
        onSave={handleSave}
        onLoad={handleLoad}
        onReset={handleReset}
        feedback={feedback}
      />
    </ReactFlow>
  );
}
