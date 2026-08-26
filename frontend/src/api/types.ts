/**
 * TypeScript types aligned with `parser/schema.json` (canonical shape, issue #2).
 *
 * Note the two `ports` variants (audit m9):
 *  - `Module["ports"]` items are plain `$defs.port` objects, NO `moduleId`.
 *  - The top-level `Graph["ports"]` items are `$defs.port` + `moduleId`.
 */

/** One public symbol exposed by a module. Schema `#/$defs/port`. */
export interface Port {
  kind: 'function' | 'class' | 'export';
  name: string;
  line: number;
  signature: string;
  params: string[];
  docstring?: string | null;
}

/** A module-level port entry carrying its owning module id (top-level `ports`). */
export interface PortWithModuleId extends Port {
  moduleId: string;
}

/** One `.py` file = one module. */
export interface Module {
  id: string; // relative posix path
  path: string;
  ports: Port[]; // NOTE: no moduleId inside module.ports
}

/** A dependency edge between two module ids (may reference externalModules ids). */
export interface Edge {
  source: string;
  target: string;
  targetPort?: string | null;
  kind:
    | 'import'
    | 'from_import'
    | 'call'
    | 'inheritance'
    | 'annotation'
    | 'decorator';
  sites: { line: number }[];
}

/** Third-party module referenced by the scanned codebase. */
export interface ExternalModule {
  id: string;
  name: string;
  kind: 'third_party';
}

/** Parser warning/error about a module. */
export interface Diagnostic {
  kind: 'dynamic_import' | 'unresolved_symbol' | 'parse_error';
  moduleId: string;
  line: number;
  message: string;
}

/** Top-level Graph JSON returned by GET /api/scan/:jobId/graph. */
export interface Graph {
  modules: Module[];
  ports: PortWithModuleId[];
  edges: Edge[];
  externalModules: ExternalModule[];
  diagnostics: Diagnostic[];
}
