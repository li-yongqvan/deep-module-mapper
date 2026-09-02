/**
 * Issue #21 real-fixture verification: the known 3-atom cycle in the
 * deep-module-mapper self-scan is detected at the module-container level
 * when using the default (one module per atom) design.
 */
import { describe, expect, it } from 'vitest';
import type { Graph } from '../api/types';
import { computeAggregatedModuleEdges } from '../lib/recompose/edges';
import { detectModuleFindings, findingLabel } from '../lib/recompose/detect';
import type { RecomposedDesign } from '../lib/recompose/types';
import { FEATURE_ATOMS } from '../manifest/featureAtoms';
import deepModuleMapperGraph from './fixtures/deep-module-mapper.graph.json';

const graph = deepModuleMapperGraph as unknown as Graph;

const design: RecomposedDesign = {
  version: 1,
  modules: FEATURE_ATOMS.map((a, i) => ({
    id: `atom:${a.id}`,
    name: a.name,
    description: a.description,
    atomIds: [a.id],
    position: { x: 0, y: i * 300 },
    implicit: true,
    nameCustomized: false,
    descriptionCustomized: false,
  })),
  addedEdges: [],
  hiddenEdges: [],
};

const aggregated = computeAggregatedModuleEdges(graph, design);

describe('issue #21 real-fixture cycle/orphan detection', () => {
  it('detects the known 3-atom SCC', () => {
    const result = detectModuleFindings(aggregated, design);
    expect(result.count.cycles).toBeGreaterThanOrEqual(1);

    const cycle = result.cycles.find((c) =>
      c.subject.moduleIds.some((id) =>
        ['atom:training-logging', 'atom:aggregation-orchestration', 'atom:ai-provider-integration'].includes(id),
      ),
    );
    expect(cycle).toBeDefined();

    const ids = new Set(cycle!.subject.moduleIds);
    expect(ids.has('atom:training-logging')).toBe(true);
    expect(ids.has('atom:aggregation-orchestration')).toBe(true);
    expect(ids.has('atom:ai-provider-integration')).toBe(true);
    expect(cycle!.evidence?.cycleEdges?.length).toBeGreaterThan(0);
  });

  it('marks the three known modules as cycle members', () => {
    const result = detectModuleFindings(aggregated, design);
    expect(findingLabel(result.byModule.get('atom:training-logging')?.code)).toBe('cycle');
    expect(findingLabel(result.byModule.get('atom:aggregation-orchestration')?.code)).toBe('cycle');
    expect(findingLabel(result.byModule.get('atom:ai-provider-integration')?.code)).toBe('cycle');
  });

  it('reports zero orphans and zero third-party-only modules in this fixture', () => {
    const result = detectModuleFindings(aggregated, design);
    expect(result.count.orphan).toBe(0);
    expect(result.count.thirdPartyOnly).toBe(0);
  });
});
