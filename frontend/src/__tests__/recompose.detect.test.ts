/**
 * Unit tests for issue #21 structural diagnostics (cycles + orphans).
 */
import { describe, expect, it } from 'vitest';
import type { Edge as FlowEdge } from '@xyflow/react';
import { detectModuleFindings, findingLabel } from '../lib/recompose/detect';
import type { AggregatedEdgeData } from '../lib/graphToFlow';
import { THIRD_PARTY_NODE_ID } from '../lib/graphToFeatureFlow';
import type { RecomposedDesign } from '../lib/recompose/types';

function agg(
  source: string,
  target: string,
  rawEdges: AggregatedEdgeData['rawEdges'] = [],
): FlowEdge<AggregatedEdgeData> {
  return {
    id: `module-edge-${source}->${target}`,
    source,
    target,
    data: { kinds: ['import'], rawEdges },
  } as FlowEdge<AggregatedEdgeData>;
}

function design(modules: { id: string; name: string }[]): RecomposedDesign {
  return {
    version: 1,
    modules: modules.map((m) => ({
      id: m.id,
      name: m.name,
      description: '',
      atomIds: [],
      position: { x: 0, y: 0 },
      implicit: false,
      nameCustomized: false,
      descriptionCustomized: false,
    })),
    addedEdges: [],
    hiddenEdges: [],
  };
}

describe('detectModuleFindings', () => {
  it('returns empty findings for empty modules', () => {
    const result = detectModuleFindings([], design([]));
    expect(result.cycles).toEqual([]);
    expect(result.orphans).toEqual([]);
    expect(result.thirdPartyOnly).toEqual([]);
    expect(result.count).toEqual({ cycles: 0, orphan: 0, thirdPartyOnly: 0 });
    expect(result.byModule.size).toBe(0);
  });

  it('returns empty findings when aggregated is empty', () => {
    const result = detectModuleFindings([], design([{ id: 'mod:a', name: 'A' }]));
    expect(result.count).toEqual({ cycles: 0, orphan: 0, thirdPartyOnly: 0 });
    expect(result.byModule.size).toBe(0);
  });

  it('detects a 2-node cycle', () => {
    const d = design([
      { id: 'mod:a', name: 'A' },
      { id: 'mod:b', name: 'B' },
    ]);
    const edges = [agg('mod:a', 'mod:b'), agg('mod:b', 'mod:a')];
    const result = detectModuleFindings(edges, d);
    expect(result.count.cycles).toBe(1);
    expect(result.cycles[0].subject.moduleIds).toEqual(
      expect.arrayContaining(['mod:a', 'mod:b']),
    );
    expect(result.cycles[0].code).toBe('cycle/scc');
    expect(result.cycles[0].severity).toBe('error');
    expect(result.cycles[0].evidence?.cycleEdges).toHaveLength(2);
    expect(result.byModule.get('mod:a')?.code).toBe('cycle/scc');
    expect(result.byModule.get('mod:b')?.code).toBe('cycle/scc');
  });

  it('detects a 3-node cycle', () => {
    const d = design([
      { id: 'mod:a', name: 'A' },
      { id: 'mod:b', name: 'B' },
      { id: 'mod:c', name: 'C' },
    ]);
    const edges = [agg('mod:a', 'mod:b'), agg('mod:b', 'mod:c'), agg('mod:c', 'mod:a')];
    const result = detectModuleFindings(edges, d);
    expect(result.count.cycles).toBe(1);
    expect(result.cycles[0].subject.moduleIds).toHaveLength(3);
    expect(result.cycles[0].evidence?.cycleEdges).toHaveLength(3);
  });

  it('counts multiple separate SCCs as multiple cycles', () => {
    const d = design([
      { id: 'mod:a', name: 'A' },
      { id: 'mod:b', name: 'B' },
      { id: 'mod:c', name: 'C' },
      { id: 'mod:d', name: 'D' },
    ]);
    const edges = [
      agg('mod:a', 'mod:b'),
      agg('mod:b', 'mod:a'),
      agg('mod:c', 'mod:d'),
      agg('mod:d', 'mod:c'),
    ];
    const result = detectModuleFindings(edges, d);
    expect(result.count.cycles).toBe(2);
  });

  it('does not flag DAGs as cycles', () => {
    const d = design([
      { id: 'mod:a', name: 'A' },
      { id: 'mod:b', name: 'B' },
      { id: 'mod:c', name: 'C' },
    ]);
    const edges = [agg('mod:a', 'mod:b'), agg('mod:b', 'mod:c')];
    const result = detectModuleFindings(edges, d);
    expect(result.count.cycles).toBe(0);
    expect(result.byModule.get('mod:a')).toBeNull();
    expect(result.byModule.get('mod:b')).toBeNull();
    expect(result.byModule.get('mod:c')).toBeNull();
  });

  it('classifies a true isolated module', () => {
    const d = design([
      { id: 'mod:a', name: 'A' },
      { id: 'mod:b', name: 'B' },
    ]);
    const edges = [agg('mod:a', 'mod:b')];
    const result = detectModuleFindings(edges, d);
    expect(result.count.orphan).toBe(0);
    expect(result.byModule.get('mod:a')).toBeNull();
    expect(result.byModule.get('mod:b')).toBeNull();
  });

  it('classifies a third-party-only module', () => {
    const d = design([
      { id: 'mod:a', name: 'A' },
      { id: 'mod:b', name: 'B' },
      { id: 'mod:c', name: 'C' },
    ]);
    const edges = [
      agg('mod:a', 'mod:c'),
      agg('mod:b', THIRD_PARTY_NODE_ID, [
        { source: 'b.py', target: 'requests', kind: 'import', sites: [{ line: 1 }] },
      ]),
    ];
    const result = detectModuleFindings(edges, d);
    expect(result.count.thirdPartyOnly).toBe(1);
    expect(result.thirdPartyOnly[0].code).toBe('orphan/third-party-only');
    expect(result.thirdPartyOnly[0].severity).toBe('warning');
    expect(result.thirdPartyOnly[0].evidence?.thirdPartyEdges).toHaveLength(1);
    expect(result.byModule.get('mod:b')?.code).toBe('orphan/third-party-only');
    expect(result.byModule.get('mod:a')).toBeNull();
    expect(result.byModule.get('mod:c')).toBeNull();
  });

  it('does not flag a module with only incoming edges as orphan', () => {
    const d = design([
      { id: 'mod:a', name: 'A' },
      { id: 'mod:b', name: 'B' },
    ]);
    const edges = [agg('mod:a', 'mod:b')];
    const result = detectModuleFindings(edges, d);
    expect(result.count.orphan).toBe(0);
    expect(result.count.thirdPartyOnly).toBe(0);
    expect(result.byModule.get('mod:b')).toBeNull();
  });

  it('does not flag a module with only outgoing edges as orphan', () => {
    const d = design([
      { id: 'mod:a', name: 'A' },
      { id: 'mod:b', name: 'B' },
    ]);
    const edges = [agg('mod:a', 'mod:b')];
    const result = detectModuleFindings(edges, d);
    expect(result.count.orphan).toBe(0);
    expect(result.byModule.get('mod:a')).toBeNull();
  });

  it('keeps cycle membership mutually exclusive with orphan classification', () => {
    const d = design([
      { id: 'mod:a', name: 'A' },
      { id: 'mod:b', name: 'B' },
      { id: 'mod:c', name: 'C' },
    ]);
    const edges = [
      agg('mod:a', 'mod:b'),
      agg('mod:b', 'mod:a'),
      agg('mod:c', THIRD_PARTY_NODE_ID),
    ];
    const result = detectModuleFindings(edges, d);
    expect(result.count.cycles).toBe(1);
    expect(result.count.thirdPartyOnly).toBe(1);
    expect(result.byModule.get('mod:a')?.code).toBe('cycle/scc');
    expect(result.byModule.get('mod:b')?.code).toBe('cycle/scc');
    expect(result.byModule.get('mod:c')?.code).toBe('orphan/third-party-only');
  });

  it('labels findings for UI badges', () => {
    expect(findingLabel('cycle/scc')).toBe('cycle');
    expect(findingLabel('orphan/isolated')).toBe('orphan');
    expect(findingLabel('orphan/third-party-only')).toBe('third-party-only');
    expect(findingLabel(undefined)).toBeNull();
  });
});
