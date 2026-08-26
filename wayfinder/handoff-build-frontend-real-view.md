# Handoff: Build frontend real-view

**Ticket**: GitHub issue #7 — https://github.com/li-yongqvan/deep-module-mapper/issues/7  
**Role**: Worker Agent  
**Mission**: Build the "real view" frontend: user inputs a repo path, the frontend polls the backend scan, then renders the Graph as a React Flow canvas.

## Context pointers

Read these before writing code:

- `deep-module-mapper/UBIQUITOUS_LANGUAGE.md` — domain terms.
- `deep-module-mapper/wayfinder/design-data-schema.md` — Graph schema and endpoint contract.
- `deep-module-mapper/wayfinder/prototype-ui-interaction.md` — node/port/color decisions.
- `deep-module-mapper/wayfinder/prototype-ui.html` — rough UI reference only.
- `deep-module-mapper/wayfinder/handoff-issue-5-complete.md` — backend API contract and locked decisions.
- `backend/README.md` — how to start the backend.
- `parser/schema.json` — the Graph JSON shape.

## Steps

### 1. Scaffold the frontend package

Create `frontend/` as a runnable React app. Use Vite or a similarly lightweight setup.

**Done when**: `cd frontend && <start-command>` starts a dev server without errors.

### 2. Wire up the backend scan flow

Build a simple form and polling logic:

- Input field for local repo path.
- Submit calls `POST http://127.0.0.1:8123/api/scan`.
- Poll `GET /api/scan/:jobId/status` every 2 seconds until `done` or `error`.
- On `done`, fetch `GET /api/scan/:jobId/graph`.
- On `error`, display `error` and `details`.

**Done when**: you can input a path, wait for the scan, and receive a Graph object in the browser console.

### 3. Render the Graph with React Flow

Transform the Graph JSON into React Flow nodes and edges:

- One node per module; rounded-rectangle shape.
- One small circular port handle per public port.
- One edge per dependency; label with edge kind if space allows.
- Layout the nodes automatically for now (simple grid or a lightweight layout lib).

**Done when**: a scanned repo renders as a visible, navigable React Flow canvas.

### 4. Apply traffic-light scoring

Compute a naive deep-module score per module and color the node:

- Green: deep module (small interface, thick implementation).
- Yellow: moderate.
- Red: shallow module (large interface, thin implementation).

Use port count and lines of code as a first approximation. Document the formula in code comments.

**Done when**: nodes appear in green/yellow/red based on the naive score.

### 5. Add interaction basics

- Hover or click a node to show module name, path, and ports.
- Hover or click an edge to show source, target, kind, and call sites.
- Show diagnostics in a small panel when the parser reports them.

**Done when**: a user can inspect any module, edge, or diagnostic without reading raw JSON.

### 6. Add tests and README

- At least one component test for the scan form.
- At least one integration-style test for polling logic.
- `frontend/README.md` with install/start/test instructions and the backend dependency.

**Done when**: `npm test` (or equivalent) passes and README is sufficient for a new reader.

## Decisions already locked

- Backend base URL: `http://127.0.0.1:8123`.
- Node shape: rounded rectangle.
- Port shape: small circular handle.
- Color semantics: green/yellow/red for deep/medium/shallow modules.
- Real-time refresh: polling, not WebSocket.
- Scope: real view only; no custom design canvas here.

## Decisions to make in the PR

State your choice and why:

- Frontend framework/build tool: Vite, Create React App, Next.js, or other.
- State management: React context, Zustand, Redux, or none.
- Layout library: react-flow built-in layout, dagre, elkjs, or a simple manual grid.
- Styling: CSS modules, Tailwind, styled-components, or other.

## Red lines

- Do **not** build the custom design canvas in this ticket.
- Do **not** implement AI description or review features.
- Do **not** change the backend API contract. If the frontend needs a different shape, transform it on the client.
- Do **not** merge, close issues, or delete branches without explicit user approval.

## Worktree discipline

This repo may have parallel Agents. Before you start:

1. Confirm you are in a dedicated git worktree.
2. Run `git status --short` and `git branch --show-current`.
3. Do not operate in another Agent's worktree.

See [[parallel-session-worktree-discipline]].

## Useful skills

- `/frontend-design` — UI/UX decisions.
- `/prototype` — quick UI spike if needed.
- `/tdd` — test the polling and rendering logic.

## Report back with

1. One-sentence summary of what changed.
2. Files modified and PR link.
3. Verification results (test output, manual screenshot or curl output).
4. Next step or blocker.
5. Any decision that still needs the user.
