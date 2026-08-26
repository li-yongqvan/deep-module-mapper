---
name: implement-python-parser
wayfinder: task
status: open
---

## Question

Implement the first version of the Python AST parser that extracts modules, ports, and dependency edges according to the confirmed schema.

## Context

- Module boundary: one `.py` file = one module.
- Port: public functions, classes, and `__all__` exports.
- Edge kinds: import / from-import / call / inheritance / annotation / decorator.
- Strategy: AST-only (stdlib `ast`); Jedi optional later.
- Dynamic imports and unresolved symbols become diagnostics.
- Third-party packages become external module nodes.

## Acceptance criteria

- [ ] Accept a repo root path and scan all `.py` files under it.
- [ ] Emit modules with id, path, ports (kind, name, line, signature).
- [ ] Emit edges with source, target, targetPort (when resolvable), kind, sites.
- [ ] Emit externalModules for third-party packages.
- [ ] Emit diagnostics for dynamic imports and unresolved symbols.
- [ ] Output matches the schema confirmed in issue #2.
- [ ] Includes a small CLI/test script that runs against `agent-lib/` or a fixture repo.

## Blocking

- Issue #2 (Design: data schema and API contract) — closed, this ticket is now unblocked.

## Notes

- AFK implementation task; user wants to build while planning.
- Start with a minimal Python package under `deep-module-mapper/parser/`.

## Amendments from 2026-08-25 review

After reviewing this ticket against deep-module principles, the following amendments should guide the first implementation:

### 1. One thin public interface

The parser package should expose exactly one public entry point:

```python
from pathlib import Path

def scan_codebase(root_path: Path) -> dict:
    """Return a Graph dict matching the schema from issue #2."""
```

Backend and frontend depend only on this function and the returned schema, never on parser internals.

### 2. Do not over-split internal modules prematurely

The original note "Keep parser/resolver/reporter behind protocols" is too abstract for the first version and risks creating shallow modules.

Instead, start with a single cohesive parser package whose internal files are private implementation details:

```
parser/
├── __init__.py      # public: scan_codebase
├── _scanner.py      # module discovery + AST traversal
├── _ports.py        # port extraction
├── _edges.py        # dependency resolution
├── _external.py     # third-party package detection
└── _diagnostics.py  # diagnostic collection
```

These files are prefixed with `_` to signal that they are not public API.

### 3. Split internally only when a real signal appears

Do not introduce abstract protocols or extra submodules until one of these conditions is met:

- A function becomes too long to understand as a unit.
- Two functions with different responsibilities are forced to share mutable state.
- A subsystem needs to be tested or replaced independently (e.g., swapping `ast` for `jedi`).
- The same logic is duplicated in multiple places.

### 4. First version is monolingual

Multi-language extension is out of scope for this ticket. Avoid designing protocols "just in case" for future languages.

### 5. Jedi remains optional

Keep the first implementation AST-only (`stdlib ast`). Do not add Jedi yet, even behind an interface.
