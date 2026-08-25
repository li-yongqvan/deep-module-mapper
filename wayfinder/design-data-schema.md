---
name: design-data-schema
wayfinder: grilling
status: closed
---

## Question

What is the canonical data schema and API contract between the Python parser, the backend, the frontend, and the AI review layer?

## Context

- Module boundary: one `.py` file = one module.
- Port: public functions, classes, and `__all__` exports.
- Edge: import / from-import / call / inheritance / annotation / decorator.
- Parser: AST-only first, optional Jedi refinement.
- UI: React Flow canvas; real view uses traffic-light scoring; design canvas uses neutral nodes.
- AI: local model drafts descriptions; cloud model reviews design canvas.

## Resolution

- Core data model: JSON with `modules`, `ports`, `edges`, `externalModules`, `diagnostics`.
- Backend API: REST endpoints for `/api/scan`, `/api/graph`, `/api/descriptions/draft`, `/api/descriptions/:moduleId`, `/api/review`, `/api/designs`.
- Real-time refresh: polling first (5s interval); WebSocket later.
- AI contract:
  - Local model drafts module descriptions from port signatures.
  - Cloud model reviews design canvas and returns structured feedback.
- Design canvas save format: JSON with module list, edges, and layout positions.

## Blocking

None — this was the current frontier ticket, now closed.

## Notes

- HITL ticket. Schema confirmed by user; implementation can now begin.
- GitHub issue: https://github.com/li-yongqvan/deep-module-mapper/issues/2
