# Deep Module Mapper — Market Survey Report

**Date:** 2026-08-25  
**Method:** GitHub API queries for stars / last push / latest release, plus project documentation review. Star counts are from the API at query time.  
**Scope:** Tools for dependency graph generation, architecture/module visualization, design-quality / deep-module analysis, and interactive canvas UI.

## Evaluation Criteria

- **Stars:** Prefer >= 1 k. Exceptions are noted when a project is strongly relevant to deep-module assessment.
- **Maintenance:** Active commits or releases within the last 6–12 months.
- **Relevance:** Direct fit to auto-extracting modules (implementation + port/interface), scoring deep-module health, and letting users design ideal dependencies on a canvas.

---

## 1. Code Dependency Graph Generators

### 1.1 dependency-cruiser

- **GitHub:** https://github.com/sverweij/dependency-cruiser
- **Stars / Language:** 7,096 / JavaScript & TypeScript
- **Maintenance:** Last push 2026-08-21; latest release v18.2.0 on 2026-08-10. Very active.
- **Key capabilities:**
  - Parses JS/TS/CoffeeScript/JSX/TSX/Vue/Svelte imports.
  - Rule engine: enforce forbidden dependencies, layers, circularity, orphans, devDeps in production.
  - Outputs DOT, Mermaid, JSON, CSV, HTML.
  - CLI + programmatic API + CI integration.
- **Candidate features to borrow:**
  - Rule-as-code architecture contracts.
  - Multiple export formats (especially Mermaid / DOT for sharing).
  - Circular-dependency and orphan-module detection.
- **Recommendation:** ADAPT. It is JS/TS-only, but its rule-engine pattern and output pipeline are the exact model for Deep Module Mapper’s dependency validation layer.

### 1.2 madge

- **GitHub:** https://github.com/pahen/madge
- **Stars / Language:** 10,161 / JavaScript
- **Maintenance:** Last push 2026-01-21; no GitHub releases, but npm publishes continue. Moderate activity.
- **Key capabilities:**
  - Generate dependency graphs for CommonJS, AMD, ES6 modules and CSS preprocessors.
  - Detect circular dependencies.
  - API methods: `.obj()`, `.circular()`, `.depends()`, `.orphans()`, `.image()`, `.svg()`.
- **Candidate features to borrow:**
  - Simple programmatic API for extracting a module graph object.
  - Circular-dependency finder.
- **Recommendation:** ADAPT. Simpler than dependency-cruiser; useful API shape for a generic backend parser, but not a direct dependency because it is JS-only.

### 1.3 pydeps

- **GitHub:** https://github.com/thebjorn/pydeps
- **Stars / Language:** 2,106 / Python
- **Maintenance:** Last push 2026-08-24; latest release v3.0.7 on 2026-08-03. Very active.
- **Key capabilities:**
  - Python module dependency graphs from bytecode imports.
  - Clustering, max depth (`--max-module-depth`), Erdős-like hop filtering (`--max-bacon`).
  - Import-cycle highlighting, SVG/PNG output, config via `.pydeps` / `pyproject.toml`.
- **Candidate features to borrow:**
  - Module-depth filtering to keep visualizations readable.
  - Cycle-highlighting UX.
  - Config-driven backend parser.
- **Recommendation:** ADAPT. Best reference for Python-specific backend parsing; the depth and clustering concepts transfer directly to multi-language parser design.

### 1.4 import-linter

- **GitHub:** https://github.com/seddonym/import-linter
- **Stars / Language:** 1,146 / Python
- **Maintenance:** Last push 2026-08-24; active PyPI releases. Very active.
- **Key capabilities:**
  - Architectural contracts: layers, forbidden imports, independence, acyclic siblings, protected modules.
  - Browser-based UI for exploring package architecture.
  - Command to draw import graphs.
- **Candidate features to borrow:**
  - Contract types as a vocabulary for "ideal dependencies."
  - Browser-based architecture explorer.
  - Protected-module / public-interface concept.
- **Recommendation:** ADAPT. The contract model maps cleanly to Deep Module Mapper’s "design ideal dependencies on a canvas" workflow.

### 1.5 Tach

- **GitHub:** https://github.com/tach-org/tach
- **Stars / Language:** 2,799 / Rust
- **Maintenance:** Last push 2026-06-11; latest release v0.35.0 on 2026-05-12. Active.
- **Key capabilities:**
  - Python dependency visualization and enforcement.
  - Define module boundaries and public interfaces in `tach.toml`.
  - `tach show` (DOT) and `tach show --web` (interactive).
  - No runtime impact, incremental adoption, CI/pre-commit integration.
- **Candidate features to borrow:**
  - Explicit public-interface / port definition per module.
  - Incremental adoption flags for legacy modules.
  - `tach show --web` interactive graph pattern.
- **Recommendation:** ADOPT. The port/interface abstraction is almost identical to Deep Module Mapper’s mental model; the interactive web show is a good reference for the browser UI.

### 1.6 Nx

- **GitHub:** https://github.com/nrwl/nx
- **Stars / Language:** 29,266 / TypeScript
- **Maintenance:** Last push 2026-08-25; latest release 23.1.1 on 2026-07-30. Very active.
- **Key capabilities:**
  - `nx graph` interactive project graph for monorepos.
  - Affected graph, focus mode, trace paths between projects, file-level edge inspection.
  - Collapsible folder-based composite nodes.
- **Candidate features to borrow:**
  - Trace-path UX: select start/end modules and highlight dependency chains.
  - Affected-graph filtering after changes.
  - Composite / collapsible folder nodes.
- **Recommendation:** ADAPT. Best-in-class interactive dependency graph UX, but it is monorepo-specific. Borrow the interaction patterns, not the implementation.

### 1.7 code2flow

- **GitHub:** https://github.com/scottrogowski/code2flow
- **Stars / Language:** 4,603 / Python
- **Maintenance:** Last push 2025-07-27; no GitHub releases. Below our activity threshold.
- **Key capabilities:**
  - Call-graph / flowchart generation for dynamic languages (Python, JS, Ruby).
  - DOT output.
- **Candidate features to borrow:**
  - None strongly unique versus dependency-cruiser / pydeps.
- **Recommendation:** REJECT. Last meaningful activity is outside the 6–12 month window; call graphs are also lower-level than the module/port abstraction we need.

---

## 2. Code Architecture / Module Visualization Tools

### 2.1 Backstage

- **GitHub:** https://github.com/backstage/backstage
- **Stars / Language:** 34,239 / TypeScript
- **Maintenance:** Last push 2026-08-25; latest release v1.54.4 on 2026-08-24. Very active.
- **Key capabilities:**
  - Software catalog with entities (services, APIs, systems, resources, groups).
  - `DependencyGraph` component and Catalog Graph plugin.
  - Graph exploration with adjustable depth, layout direction, relation filtering.
- **Candidate features to borrow:**
  - Entity graph model: modules as first-class catalog items with metadata and relations.
  - Adjustable-depth graph exploration.
  - Relation-type filtering (depends-on, provides, consumes).
- **Recommendation:** ADAPT. Enterprise portal is overkill, but the catalog-graph UX and entity-relation model fit Deep Module Mapper well.

### 2.2 GitDiagram

- **GitHub:** https://github.com/ahmedkhaleel2004/gitdiagram
- **Stars / Language:** 15,910 / TypeScript
- **Maintenance:** Last push 2026-08-17; continuous deployment via Docker. Active.
- **Key capabilities:**
  - Converts any GitHub repo into an interactive architecture diagram by swapping `github.com` for `gitdiagram.com`.
  - Uses LLMs to generate layered diagrams.
  - FastAPI + Next.js stack, supports self-hosting.
- **Candidate features to borrow:**
  - LLM-generated architecture diagrams from a repo.
  - Replace-in-URL deployment / sharing pattern.
  - Layered diagram layout.
- **Recommendation:** ADAPT. The AI-to-diagram workflow is adjacent to our local-model-drafts / cloud-model-reviews split, but GitDiagram is AI-only and does not score deep-module health.

### 2.3 Structurizr

- **GitHub:** https://github.com/structurizr/structurizr
- **Stars / Language:** 360 / Java
- **Maintenance:** Last push 2026-06-29; latest release v2026.06.28 on 2026-06-29. Active, but low stars.
- **Key capabilities:**
  - Models-as-code for the C4 model.
  - Structurizr DSL generates multiple diagrams from a single model.
  - Docker-deployable web UI and playground.
- **Candidate features to borrow:**
  - C4-style hierarchical abstraction (system / container / component / code).
  - Single model, multiple views.
  - Text-first DSL for architecture design.
- **Recommendation:** ADAPT. Low star count, but the C4 hierarchy and "single model, multiple views" concept are directly useful for zooming between high-level systems and module interfaces.

### 2.4 Sourcetrail

- **GitHub:** https://github.com/CoatiSoftware/Sourcetrail
- **Stars / Language:** 16,489 / C++
- **Maintenance:** Archived 2021-12-14; last push 2021-12-13. Inactive.
- **Key capabilities:**
  - Interactive source explorer with symbol-level graphs.
  - Cross-language index for C/C++, Java, Python.
- **Candidate features to borrow:**
  - Interactive graph navigation patterns.
- **Recommendation:** REJECT. Archived with no ongoing maintenance; symbol-level exploration is also too granular for module/port focus.

---

## 3. Software Design Quality / Deep Module Analyzers

### 3.1 vladikk/modularity

- **GitHub:** https://github.com/vladikk/modularity
- **Stars / Language:** 522 / HTML / Markdown (Claude Code skill)
- **Maintenance:** Last push 2026-04-04. Active, though no releases.
- **Key capabilities:**
  - Claude Code skill for designing and reviewing modular systems.
  - Based on the **Balanced Coupling** model: integration strength, distance, volatility.
  - `/modularity:review` detects coupling imbalances and gives actionable recommendations.
  - `/modularity:design` designs modules with integration contracts and test specs.
- **Candidate features to borrow:**
  - Balanced Coupling scoring dimensions.
  - Actionable, human-readable refactoring recommendations.
  - Integration-contract documentation format.
- **Recommendation:** ADOPT. Despite low stars, it is the closest conceptual match to Deep Module Mapper. Note the CC BY-NC-SA 4.0 license, so borrow ideas, not code.

### 3.2 ArchUnit

- **GitHub:** https://github.com/TNG/ArchUnit
- **Stars / Language:** 3,807 / Java
- **Maintenance:** Last push 2026-08-24; latest release v1.5.0 on 2026-08-04. Very active.
- **Key capabilities:**
  - Testable architecture rules for Java bytecode.
  - Layer, slice, dependency, cyclic-dependency, and naming rules.
  - Fluent API for rule definition.
- **Candidate features to borrow:**
  - Fluent rule DSL for architecture assertions.
  - Layer / slice dependency checks.
- **Recommendation:** ADAPT. The rule DSL and layer checks are excellent reference, but Java-only bytecode analysis is not reusable for a multi-language local web app.

### 3.3 wily

- **GitHub:** https://github.com/tonybaloney/wily
- **Stars / Language:** 1,323 / Python
- **Maintenance:** Last push 2026-08-09, but latest release 1.25.0 is from 2023-10-11. Commits are active; releases are stale.
- **Key capabilities:**
  - Tracks cyclomatic complexity, cognitive complexity, Halstead metrics, maintainability index over git history.
  - `wily diff` and `wily graph` for CI / trend visualization.
- **Candidate features to borrow:**
  - Git-history-based metric trends.
  - Complexity-to-maintainability composite score.
- **Recommendation:** ADAPT. Useful for scoring implementation complexity, but we must translate its file-level metrics into module/port-level health scores.

---

## 4. Interactive Canvas Tools for Designing Software Architecture

### 4.1 xyflow / React Flow

- **GitHub:** https://github.com/xyflow/xyflow
- **Stars / Language:** 38,132 / TypeScript
- **Maintenance:** Last push 2026-08-24; latest release @xyflow/svelte@1.6.3 on 2026-08-12. Very active.
- **Key capabilities:**
  - Node-based UIs: drag-and-drop, pan, zoom, selection, edge routing.
  - React-first with Svelte variant.
  - Custom nodes/edges, minimap, controls, background.
- **Candidate features to borrow:**
  - Node-and-edge canvas primitives.
  - Custom node types (module node, port handle).
  - Selection, grouping, and layout helpers.
- **Recommendation:** ADOPT. The strongest candidate for the "design ideal dependencies on a canvas" UI layer in a React/TypeScript web app.

### 4.2 Excalidraw

- **GitHub:** https://github.com/excalidraw/excalidraw
- **Stars / Language:** 130,449 / TypeScript
- **Maintenance:** Last push 2026-08-22; latest release v0.18.1 on 2026-04-21. Very active.
- **Key capabilities:**
  - Hand-drawn style infinite canvas.
  - Embeddable React component.
  - Library of shapes, arrows, collaborative features.
- **Candidate features to borrow:**
  - Infinite canvas feel and sketch-like presentation.
  - Embeddable component model.
  - Shape libraries for architecture symbols.
- **Recommendation:** ADAPT. Great for free-form design, but it is a generic whiteboard; we need structured nodes/edges and dependency semantics, which React Flow provides more directly.

### 4.3 tldraw

- **GitHub:** https://github.com/tldraw/tldraw
- **Stars / Language:** 49,946 / TypeScript
- **Maintenance:** Last push 2026-08-25; latest release v5.3.2 on 2026-08-18. Very active.
- **Key capabilities:**
  - Infinite canvas SDK with structured shapes.
  - Custom tools, UI overrides, persistence API.
  - Production license required for commercial use.
- **Candidate features to borrow:**
  - Canvas SDK pattern with custom shapes.
  - Persistence and state management design.
- **Recommendation:** ADAPT. Powerful, but production licensing and generic-shape model make it less suitable than React Flow for a dependency-specific canvas.

### 4.4 react-diagrams

- **GitHub:** https://github.com/projectstorm/react-diagrams
- **Stars / Language:** 9,422 / TypeScript
- **Maintenance:** Last push 2025-04-03; latest release 2024-02-15. Inactive by our threshold.
- **Key capabilities:**
  - Flow/process diagramming library inspired by Blender/Labview.
  - HTML nodes as first-class citizens.
- **Candidate features to borrow:**
  - None unique versus xyflow.
- **Recommendation:** REJECT. Maintenance has stalled; xyflow is the clear successor in the React node-graph space.

---

## Candidate Feature List

| # | Feature | Inspired by | Why it fits Deep Module Mapper | Modification needed |
|---|---------|-------------|--------------------------------|---------------------|
| 1 | **Port / interface extraction and rendering** | Tach (public interfaces), import-linter (protected modules), dependency-cruiser (imports) | User only cares about interface, not implementation. | Auto-detect ports from imports/exports; render them as explicit handles on module nodes. |
| 2 | **Rule-based architecture contracts** | dependency-cruiser, import-linter, ArchUnit | Need to validate "ideal dependencies" against actual code. | Express contracts as interface-level rules (allowed/forbidden port usage, layer order). |
| 3 | **Deep-module health score** | vladikk/modularity (Balanced Coupling), wily (complexity trends), Tach | Core goal is to score module depth / health. | Aggregate interface size, fan-in/fan-out, coupling distance, and volatility into a module score. |
| 4 | **Interactive dependency-design canvas** | xyflow / React Flow, Excalidraw, tldraw | User needs to draw ideal dependencies. | Build custom module/port node types on top of React Flow; add snap-to-grid and auto-layout. |
| 5 | **AI-generated draft architecture** | GitDiagram | Local model drafts descriptions, cloud model reviews. | Use local model to draft module names/ports from parsed code; use cloud model to review the designed canvas. |
| 6 | **Trace path / change-impact analysis** | Nx graph | Show ripple effects of changing an interface. | Trace through port-to-port edges, not file-level imports; highlight affected modules. |
| 7 | **Module catalog with metadata and relations** | Backstage catalog graph | Modules should be first-class entities. | Lightweight local catalog (no enterprise portal); tags, owner, description per module. |
| 8 | **Hierarchical C4-style views** | Structurizr | Users need to zoom out from modules to systems. | Auto-generate container/component views from the module graph; keep code-level modules as the leaf layer. |
| 9 | **Circular dependency and orphan detection** | dependency-cruiser, madge, pydeps | Basic hygiene before deep scoring. | Run on port-level graph; surface cycles that cross module boundaries. |
| 10 | **Incremental enforcement for legacy code** | Tach | Not every module can be perfect on day one. | Allow "unchecked" modules that are visible but not scored; migrate them into enforcement over time. |
| 11 | **Multi-format export (Mermaid / DOT / JSON)** | dependency-cruiser | Share diagrams and rules outside the app. | Export both the graph and the architecture contract in portable formats. |
| 12 | **Git-history volatility scoring** | vladikk/modularity, wily | Volatile modules need different coupling thresholds. | Compute change frequency per module from git history; weight coupling scores by volatility. |

---

## Summary of Recommendations

- **ADOPT directly as reference / dependency:** dependency-cruiser, Tach, xyflow / React Flow, vladikk/modularity (ideas only, CC BY-NC-SA).
- **ADAPT patterns from:** import-linter, pydeps, Nx, Backstage, GitDiagram, Structurizr, ArchUnit, wily, Excalidraw, tldraw.
- **REJECT due to inactivity or mismatch:** code2flow, Sourcetrail, react-diagrams.
