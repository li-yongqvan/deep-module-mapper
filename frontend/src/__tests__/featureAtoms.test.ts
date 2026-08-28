import { describe, expect, it } from 'vitest';
import { FEATURE_ATOMS, atomForFile } from '../manifest/featureAtoms';
import type { Graph } from '../api/types';
// Real self-scan snapshot (issue #8 §2.2): anchors the curated manifest to the
// current deep-module-mapper tree. Audit C2 — refreshing this fixture forces a
// manifest sync if the production file set changes (a parallel branch adding a
// production file would otherwise vanish from the feature view silently).
import deepModuleMapperGraph from './fixtures/deep-module-mapper.graph.json';

const graph = deepModuleMapperGraph as unknown as Graph;

/** tests/ or fixtures/ directories mark noise (manifest must not name them). */
const isNoiseLike = (p: string) => p.includes('/tests/') || p.includes('/fixtures/');
/** Package marker files are legitimate noise too (issue #8; parser/__init__.py
 * is the D6 exemption and is in the manifest, so it simply isn't checked here). */
const isInitPy = (p: string) => p.endsWith('__init__.py');

describe('featureAtoms manifest', () => {
  it('has unique atom ids and non-empty name/description/files', () => {
    const ids = FEATURE_ATOMS.map((a) => a.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const atom of FEATURE_ATOMS) {
      expect(atom.name.length).toBeGreaterThan(0);
      expect(atom.description.length).toBeGreaterThan(0);
      expect(atom.files.length).toBeGreaterThan(0);
    }
  });

  it('assigns each file to at most one atom', () => {
    const seen = new Map<string, string>();
    for (const atom of FEATURE_ATOMS) {
      for (const file of atom.files) {
        expect(seen.has(file), `${file} in both ${seen.get(file)} and ${atom.id}`).toBe(false);
        seen.set(file, atom.id);
      }
    }
  });

  it('leaves noise and unknown files unassigned', () => {
    // Grouping is AI-proposed (issue #11) — no specific atom id is pinned here.
    // What must hold for any valid manifest: noise and unknown files are never
    // assigned (INV3 mirrors), and every production module IS (C2, next test).
    expect(atomForFile('parser/tests/test_edges.py')).toBeUndefined();
    expect(atomForFile('backend/tests/fixtures/mini_pkg/lib.py')).toBeUndefined();
    expect(atomForFile('unknown.py')).toBeUndefined();
  });

  it('covers every non-noise module in the self-scan fixture (C2)', () => {
    for (const m of graph.modules) {
      if (isNoiseLike(m.id) || isInitPy(m.id)) continue;
      expect(atomForFile(m.id), `production module ${m.id} must be in an atom`).toBeDefined();
    }
  });

  it('manifest paths all exist as modules and never name test/fixture files', () => {
    const moduleIds = new Set(graph.modules.map((m) => m.id));
    for (const atom of FEATURE_ATOMS) {
      for (const file of atom.files) {
        expect(moduleIds.has(file), `manifest file ${file} missing from fixture`).toBe(true);
        expect(isNoiseLike(file), `manifest must not name test/fixture file ${file}`).toBe(false);
      }
    }
  });
});
