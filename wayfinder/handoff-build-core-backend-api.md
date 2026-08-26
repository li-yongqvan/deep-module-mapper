# Handoff: Build core backend API

**Ticket**: GitHub issue #5 — https://github.com/li-yongqvan/deep-module-mapper/issues/5  
**Role**: Worker Agent  
**Mission**: Expose `parser.scan_codebase()` through a small HTTP API so the frontend can request a scan and fetch the resulting Graph.

## Context pointers

Read these before writing code:

- `deep-module-mapper/UBIQUITOUS_LANGUAGE.md` — domain terms.
- `deep-module-mapper/wayfinder/design-data-schema.md` — Graph schema and endpoint contract.
- `deep-module-mapper/wayfinder/implement-python-parser.md` — parser scope and public API.
- `parser/__init__.py` and `parser/schema.json` — the function and schema you wrap.
- `deep-module-mapper/wayfinder/prototype-ui.html` — rough UI direction only; do not implement it here.

## Steps

### 1. Scaffold the backend package

Create `backend/` as a runnable Python package. Choose a lightweight web framework and justify it in the PR.

**Done when**: `cd backend && <start-command>` starts a server on a documented port without errors.

### 2. Implement scan job lifecycle

Implement three endpoints:

- `POST /api/scan` — accept `{ "path": "..." }`, validate the path, start a scan in the background, return `{ "jobId": "..." }`.
- `GET /api/scan/:jobId/status` — return `pending | running | done | error`.
- `GET /api/scan/:jobId/graph` — return the Graph JSON when status is `done`; return a clear error otherwise.

Keep job state in memory only. Use a thread or async task for the background scan.

**Done when**: you can curl all three endpoints end-to-end against a real repo and get the expected responses.

### 3. Handle errors cleanly

For invalid paths, parser crashes, and missing jobs, return sensible HTTP status codes and a consistent error body.

**Done when**: every error path has a test and returns JSON with `error` and `details` fields.

### 4. Add tests

Add `backend/tests/` with fixtures under `backend/tests/fixtures/`. Cover:

- happy-path scan → status → graph
- invalid repo path
- missing job id
- parser error isolation (if a file has a syntax error, the scan still returns diagnostics, not a 500)

**Done when**: `pytest backend/tests` passes green.

### 5. Update README

Document how to start the backend and how to hit the three endpoints.

**Done when**: a new reader can clone, start, and test the API from README alone.

## Decisions already locked

- Module boundary: one `.py` file = one module.
- Graph schema: `modules`, `ports`, `edges`, `externalModules`, `diagnostics`.
- Live refresh: polling first, WebSocket later.
- Persistence: none in this ticket; scan results live in memory.

## Decisions to make in the PR

State your choice and why:

- Web framework: FastAPI, Flask, Starlette, or other.
- Background task mechanism: thread, asyncio, or a tiny in-process queue.
- Error response shape: keep it consistent with the schema contract.

## Red lines

- Do **not** implement `/api/descriptions/*`, `/api/review`, or `/api/designs`.
- Do **not** add a database or any persistence.
- Do **not** change `parser.scan_codebase()` signature or return shape. If you discover it must change, pause and ask the coordinator/user.
- Do **not** merge, close issues, or delete branches without explicit user approval.

## Worktree discipline

This repo may have parallel Agents. Before you start:

1. Confirm you are in a dedicated git worktree.
2. Run `git status --short` and `git branch --show-current`.
3. Do not operate in another Agent's worktree.

See [[parallel-session-worktree-discipline]].

## Useful skills

- `/tdd` — write tests first.
- `/codebase-design` — keep package boundaries clean.
- `/prototype` — only if you need a quick manual API smoke test.

## Report back with

1. One-sentence summary of what changed.
2. Files modified and PR link.
3. Verification results (test output, manual curl output).
4. Next step or blocker.
5. Any decision that still needs the user.
