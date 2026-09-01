/**
 * Issue #18 delivery-gate test: the "draw-to-verify" four-fold contract driven
 * by REAL scanned data (the deep-module-mapper self-scan fixture). Pairs are
 * derived at runtime from the aggregated set — never pinned to a concrete atom
 * id — so the test stays green as the AI grouping / manifest evolves.
 *
 * The four folds (handoff Step 8 / design doc §8 delivery gate):
 *   1. initial canvas has ZERO edges (D1);
 *   2. a real dependency draws on, carrying code evidence (D3);
 *   3. a nonexistent dependency is rejected ("无任何依赖关系", D4);
 *   4. a reversed dependency is rejected ("方向反了", D5).
 */
import { describe, expect, it } from 'vitest';
import type { Graph } from '../api/types';
import {
  checkDependency,
  computeAggregatedModuleEdges,
  finalEdges,
  rejectionMessage,
} from '../lib/recompose/edges';
import type { RecomposedDesign } from '../lib/recompose/types';
import { FEATURE_ATOMS } from '../manifest/featureAtoms';
// Real self-scan snapshot of deep-module-mapper.
import deepModuleMapperGraph from './fixtures/deep-module-mapper.graph.json';

const graph = deepModuleMapperGraph as unknown as Graph;

/** Implicit single-atom-module design covering every manifest atom. */
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

describe('issue #18 real-fixture four-fold verification', () => {
  it('fold 1: the canvas renders zero edges by default (D1)', () => {
    expect(aggregated.length).toBeGreaterThan(0); // the scan really has edges
    expect(finalEdges(aggregated, design)).toHaveLength(0); // but none render
  });

  it('fold 2: a real dependency draws on, with code evidence (D3)', () => {
    // Take the first real aggregated edge as the "user-drawn" pair.
    const real = aggregated[0];
    expect(real).toBeDefined();
    const result = checkDependency(aggregated, real.source, real.target);
    expect(result.status).toBe('real');
    // The drawn edge renders carrying the real underlying raw edges.
    const drawn: RecomposedDesign = {
      ...design,
      addedEdges: [{ source: real.source, target: real.target }],
    };
    const rendered = finalEdges(aggregated, drawn);
    expect(rendered).toHaveLength(1);
    const data = rendered[0].data as { manual: boolean; rawEdges: unknown[] };
    expect(data.manual).toBe(false);
    expect(data.rawEdges.length).toBeGreaterThan(0);
    // Each raw edge carries a parser-extracted kind and a call-site line.
    for (const e of data.rawEdges as { kind: string; sites: { line: number }[] }[]) {
      expect(e.kind.length).toBeGreaterThan(0);
      expect(e.sites.length).toBeGreaterThan(0);
      expect(e.sites[0].line).toBeGreaterThan(0);
    }
  });

  it('fold 3: a nonexistent dependency is rejected (D4)', () => {
    // Find a real module pair with NO dependency in either direction, so the
    // drawn edge is guaranteed nonexistent.
    const moduleIds = design.modules.map((m) => m.id);
    const keys = new Set(aggregated.map((e) => `${e.source}->${e.target}`));
    let pair: { s: string; t: string } | undefined;
    outer: for (const s of moduleIds) {
      for (const t of moduleIds) {
        if (s === t) continue;
        if (keys.has(`${s}->${t}`) || keys.has(`${t}->${s}`)) continue;
        pair = { s, t };
        break outer;
      }
    }
    expect(pair).toBeDefined(); // the scan does not link every module pair
    const result = checkDependency(aggregated, pair!.s, pair!.t);
    expect(result.status).toBe('none');
    expect(result.evidence).toBeUndefined();
    const msg = rejectionMessage('none', design, pair!.s, pair!.t);
    expect(msg).toContain('无任何依赖关系');
    // The rejected pair must not render either.
    const drawn: RecomposedDesign = {
      ...design,
      addedEdges: [{ source: pair!.s, target: pair!.t }],
    };
    expect(finalEdges(aggregated, drawn)).toHaveLength(0);
  });

  it('fold 4: a reversed dependency is rejected with the "方向反了" hint (D5)', () => {
    const real = aggregated[0];
    expect(real).toBeDefined();
    const reversed = checkDependency(aggregated, real.target, real.source);
    expect(reversed.status).toBe('reversed');
    expect(reversed.evidence).toBeDefined(); // the backward edge exists as proof
    const msg = rejectionMessage('reversed', design, real.target, real.source);
    expect(msg).toContain('方向反了');
    // The reversed pair must not render either.
    const drawn: RecomposedDesign = {
      ...design,
      addedEdges: [{ source: real.target, target: real.source }],
    };
    expect(finalEdges(aggregated, drawn)).toHaveLength(0);
  });
});
