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
- Keep parser/resolver/reporter behind protocols for future multi-language extension.
