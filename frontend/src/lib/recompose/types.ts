/**
 * Recompose-layer domain types (issue #10).
 *
 * A *module* is a container holding one or more functional atoms. An atom
 * that is not in any explicit module is its own implicit single-atom module
 * (domain invariant: every atom belongs to exactly one module). A module
 * exposes one aggregated interface (UBIQUITOUS_LANGUAGE: 接口 = 端口的使用说明书).
 */
import type { XYPosition } from '@xyflow/react';

/** A recomposed module container. */
export interface RecomposedModule {
  /** `mod:<uuid>` for explicit modules; `atom:<atomId>` for implicit single-atom ones. */
  id: string;
  /** Chinese name, user-editable (auto-derived at creation). */
  name: string;
  /** Aggregated-interface description, user-editable. */
  description: string;
  /** 1+ FEATURE_ATOM ids; implicit modules always hold exactly one. */
  atomIds: string[];
  /** Module container top-left, canvas absolute coordinates. */
  position: XYPosition;
  /** true = manifest-derived single-atom module; false = user-created/edited. */
  implicit: boolean;
  /** True once the user edited the name (re-derivation must not overwrite it). */
  nameCustomized: boolean;
  /** True once the user edited the description. */
  descriptionCustomized: boolean;
}

/** A module-level dependency edge reference (source/target = module ids). */
export interface ModuleEdgeRef {
  source: string;
  target: string;
}

/** The persisted recomposed design: modules + edge overrides + layout. */
export interface RecomposedDesign {
  version: 1;
  modules: RecomposedModule[];
  /** User-drawn edges with no underlying atom dependency. */
  addedEdges: ModuleEdgeRef[];
  /** Auto-aggregated edges the user deleted. */
  hiddenEdges: ModuleEdgeRef[];
  /** Third-party aggregated node position (optional, derived default when absent). */
  thirdPartyPosition?: XYPosition;
}
