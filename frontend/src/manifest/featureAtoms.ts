/**
 * Functional-atom manifest (hand-maintained, single source of truth for
 * grouping, issue #8). AI aggregation (#11) is expected to produce the same
 * format as a drop-in replacement, so keep the shape stable.
 *
 * A *functional atom* is a group of files that together implement one
 * capability. Files not listed in any atom are hidden from the feature view
 * as noise (tests/fixtures/`__init__.py`).
 */
import featureAtomsJson from './feature-atoms.json';

export interface FeatureAtom {
  id: string;
  name: string; // Chinese name, shown as the node title
  description: string; // one-line Chinese description
  files: string[]; // module ids (repo-root-relative posix paths)
}

export interface FeatureAtomManifest {
  atoms: FeatureAtom[];
}

/** Curated manifest for deep-module-mapper itself. */
export const FEATURE_ATOMS: FeatureAtom[] = (
  featureAtomsJson as FeatureAtomManifest
).atoms;

const atomByFile = new Map<string, FeatureAtom>();
for (const atom of FEATURE_ATOMS) {
  for (const file of atom.files) {
    atomByFile.set(file, atom);
  }
}

/** The atom a module file belongs to, or undefined if it is unassigned noise. */
export function atomForFile(file: string): FeatureAtom | undefined {
  return atomByFile.get(file);
}
