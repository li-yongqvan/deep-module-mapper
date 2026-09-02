/**
 * Module-level structural diagnostics for the recompose canvas (issue #21).
 *
 * Detects cycles (via Tarjan SCC on real aggregated module edges) and classifies
 * orphan modules into isolated vs third-party-only. Pure function, no React
 * dependency, read-only — it never mutates the design or graph.
 */
import type { Edge as FlowEdge } from '@xyflow/react';
import type { AggregatedEdgeData } from '../graphToFlow';
import { THIRD_PARTY_NODE_ID } from '../graphToFeatureFlow';
import type { RecomposedDesign } from './types';

export type ModuleDiagnosticCode =
  | 'cycle/scc'
  | 'orphan/isolated'
  | 'orphan/third-party-only';

export type ModuleDiagnosticSeverity = 'error' | 'warning';

export type ModuleDiagnosticLabel = 'cycle' | 'orphan' | 'third-party-only';

export interface ModuleFinding {
  code: ModuleDiagnosticCode;
  severity: ModuleDiagnosticSeverity;
  /** Subject module ids. Cycles contain ≥2 modules; orphan findings contain exactly 1. */
  subject: { moduleIds: string[] };
  evidence?: {
    /** For cycles: aggregated edges between SCC members (rawEdges = code evidence). */
    cycleEdges?: Array<AggregatedEdgeData & { source: string; target: string }>;
    /** For third-party-only: aggregated edges from the module to third-party libs. */
    thirdPartyEdges?: Array<AggregatedEdgeData & { source: string; target: string }>;
  };
  message: string;
}

export interface ModuleFindings {
  cycles: ModuleFinding[];
  orphans: ModuleFinding[];
  thirdPartyOnly: ModuleFinding[];
  count: {
    cycles: number;
    orphan: number;
    thirdPartyOnly: number;
  };
  /** Quick lookup for node badges. null = normal module. */
  byModule: Map<string, ModuleFinding | null>;
}

interface TarjanState {
  index: number;
  stack: string[];
  onStack: Set<string>;
  indices: Map<string, number>;
  lowlinks: Map<string, number>;
  sccs: string[][];
}

function tarjanScc(adj: Map<string, string[]>): string[][] {
  const state: TarjanState = {
    index: 0,
    stack: [],
    onStack: new Set(),
    indices: new Map(),
    lowlinks: new Map(),
    sccs: [],
  };

  function strongconnect(v: string): void {
    state.indices.set(v, state.index);
    state.lowlinks.set(v, state.index);
    state.index += 1;
    state.stack.push(v);
    state.onStack.add(v);

    const neighbors = adj.get(v) ?? [];
    for (const w of neighbors) {
      if (!state.indices.has(w)) {
        strongconnect(w);
        state.lowlinks.set(v, Math.min(state.lowlinks.get(v)!, state.lowlinks.get(w)!));
      } else if (state.onStack.has(w)) {
        state.lowlinks.set(v, Math.min(state.lowlinks.get(v)!, state.indices.get(w)!));
      }
    }

    if (state.lowlinks.get(v) === state.indices.get(v)) {
      const scc: string[] = [];
      let w: string;
      do {
        w = state.stack.pop()!;
        state.onStack.delete(w);
        scc.push(w);
      } while (w !== v);
      state.sccs.push(scc);
    }
  }

  for (const v of adj.keys()) {
    if (!state.indices.has(v)) strongconnect(v);
  }

  return state.sccs;
}

function edgeData(edge: FlowEdge<AggregatedEdgeData>): AggregatedEdgeData & {
  source: string;
  target: string;
} {
  return {
    ...(edge.data ?? { kinds: [], rawEdges: [] }),
    source: edge.source,
    target: edge.target,
  };
}

/**
 * Detect cycles and orphan modules from real aggregated module edges.
 *
 * - Cycles = non-trivial strongly connected components (size ≥ 2) in the
 *   module-only directed graph.
 * - Orphan classification uses total degree (module edges + third-party edges,
 *   direction ignored):
 *     • has any module edge (in or out)  → normal
 *     • no module edge, has third-party edge → third-party-only
 *     • no module edge, no third-party edge  → isolated
 */
export function detectModuleFindings(
  aggregated: FlowEdge<AggregatedEdgeData>[],
  design: RecomposedDesign,
): ModuleFindings {
  const moduleIds = new Set(design.modules.map((m) => m.id));
  if (moduleIds.size === 0 || aggregated.length === 0) {
    return {
      cycles: [],
      orphans: [],
      thirdPartyOnly: [],
      count: { cycles: 0, orphan: 0, thirdPartyOnly: 0 },
      byModule: new Map(),
    };
  }

  const moduleEdges: FlowEdge<AggregatedEdgeData>[] = [];
  const thirdPartyEdges = new Map<string, FlowEdge<AggregatedEdgeData>[]>();

  for (const e of aggregated) {
    if (moduleIds.has(e.source) && moduleIds.has(e.target)) {
      moduleEdges.push(e);
      continue;
    }
    if (moduleIds.has(e.source) && e.target === THIRD_PARTY_NODE_ID) {
      const list = thirdPartyEdges.get(e.source) ?? [];
      list.push(e);
      thirdPartyEdges.set(e.source, list);
    }
  }

  // Build adjacency list for Tarjan (only module edges).
  const adj = new Map<string, string[]>();
  const hasModuleEdge = new Set<string>();
  for (const e of moduleEdges) {
    hasModuleEdge.add(e.source);
    hasModuleEdge.add(e.target);
    const list = adj.get(e.source) ?? [];
    list.push(e.target);
    adj.set(e.source, list);
  }
  // Ensure every module appears in the adjacency map (isolated modules too).
  for (const id of moduleIds) {
    if (!adj.has(id)) adj.set(id, []);
  }

  const sccs = tarjanScc(adj);
  const cycles: ModuleFinding[] = [];
  const moduleToFinding = new Map<string, ModuleFinding | null>();

  // Index module edges by key for quick evidence lookup.
  const moduleEdgeByKey = new Map<string, FlowEdge<AggregatedEdgeData>>();
  for (const e of moduleEdges) {
    moduleEdgeByKey.set(`${e.source}->${e.target}`, e);
  }

  for (const scc of sccs) {
    if (scc.length < 2) continue;

    const cycleEdges: Array<AggregatedEdgeData & { source: string; target: string }> = [];
    for (const s of scc) {
      for (const t of scc) {
        if (s === t) continue;
        const key = `${s}->${t}`;
        const edge = moduleEdgeByKey.get(key);
        if (edge) cycleEdges.push(edgeData(edge));
      }
    }

    const nameList = scc
      .map((id) => design.modules.find((m) => m.id === id)?.name ?? id)
      .join('、');

    const finding: ModuleFinding = {
      code: 'cycle/scc',
      severity: 'error',
      subject: { moduleIds: scc },
      evidence: { cycleEdges },
      message: `模块互相构成循环依赖：${nameList}`,
    };
    cycles.push(finding);
    for (const id of scc) moduleToFinding.set(id, finding);
  }

  const orphans: ModuleFinding[] = [];
  const thirdPartyOnly: ModuleFinding[] = [];

  for (const module of design.modules) {
    if (moduleToFinding.has(module.id)) continue; // already in a cycle

    if (hasModuleEdge.has(module.id)) {
      moduleToFinding.set(module.id, null);
      continue;
    }

    const tpEdges = thirdPartyEdges.get(module.id) ?? [];
    if (tpEdges.length > 0) {
      const finding: ModuleFinding = {
        code: 'orphan/third-party-only',
        severity: 'warning',
        subject: { moduleIds: [module.id] },
        evidence: { thirdPartyEdges: tpEdges.map(edgeData) },
        message: `模块「${module.name}」只依赖外部库，不被任何其它模块使用`,
      };
      thirdPartyOnly.push(finding);
      moduleToFinding.set(module.id, finding);
    } else {
      const finding: ModuleFinding = {
        code: 'orphan/isolated',
        severity: 'warning',
        subject: { moduleIds: [module.id] },
        message: `模块「${module.name}」与其它模块及外部库都没有依赖边，可能是死代码或未使用工具`,
      };
      orphans.push(finding);
      moduleToFinding.set(module.id, finding);
    }
  }

  return {
    cycles,
    orphans,
    thirdPartyOnly,
    count: {
      cycles: cycles.length,
      orphan: orphans.length,
      thirdPartyOnly: thirdPartyOnly.length,
    },
    byModule: moduleToFinding,
  };
}

/** Convert a finding code to the short UI label used by badges and toolbar. */
export function findingLabel(code: ModuleDiagnosticCode | undefined): ModuleDiagnosticLabel | null {
  if (code === 'cycle/scc') return 'cycle';
  if (code === 'orphan/isolated') return 'orphan';
  if (code === 'orphan/third-party-only') return 'third-party-only';
  return null;
}
