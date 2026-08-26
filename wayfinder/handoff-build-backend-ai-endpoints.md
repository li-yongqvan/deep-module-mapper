# Handoff: Build backend AI endpoints

**Ticket**: GitHub issue #8 — https://github.com/li-yongqvan/deep-module-mapper/issues/8  
**Role**: Worker Agent  
**Mission**: Add AI endpoints to the backend so the frontend can draft module descriptions and review design canvases.

## Context pointers

Read these before writing code:

- `deep-module-mapper/UBIQUITOUS_LANGUAGE.md` — domain terms.
- `deep-module-mapper/wayfinder/design-data-schema.md` — AI contract and endpoint design.
- `deep-module-mapper/wayfinder/implement-python-parser.md` — how ports are extracted.
- `deep-module-mapper/wayfinder/handoff-issue-5-complete.md` — backend API contract and locked decisions.
- `backend/README.md` — how to start the backend.
- `backend/app.py` or equivalent — existing Starlette app to extend.

## Steps

### 1. Add an AI provider interface

Create a small internal abstraction for AI calls so local and cloud models can be swapped without touching endpoint code.

**Done when**: you can instantiate a `DescriptionProvider` and a `ReviewProvider` and call them with simple inputs/outputs.

### 2. Implement description endpoints

Add these routes to the existing backend:

- `POST /api/descriptions/draft` — accept `{ "moduleIds": [...] }`, return drafted descriptions for each module.
- `GET /api/descriptions/:moduleId` — return the saved description for a module.
- `PUT /api/descriptions/:moduleId` — save a human-edited description.

Store descriptions in memory for now.

**Done when**: you can curl all three endpoints and get consistent results.

### 3. Implement review endpoint

Add `POST /api/review` — accept a design canvas JSON and return structured feedback:

```json
{
  "badSmells": [...],
  "boundaryIssues": [...],
  "deepModuleJudgments": [...],
  "simplicityAssessment": "..."
}
```

**Done when**: the endpoint returns a valid review shape for any well-formed canvas.

### 4. Stub model calls

If no local/cloud model is configured, return deterministic stubs that still exercise the full wiring:

- Description stub: derive a one-line description from port names/signatures.
- Review stub: return a generic but valid feedback object.

Make stubs easy to replace with real model calls later.

**Done when**: tests pass without requiring a running model.

### 5. Add tests and config docs

- Tests for description draft, get, put, and review endpoints.
- Tests for stub behavior and provider switching.
- Update `backend/README.md` with env vars or config file for model endpoints.

**Done when**: `pytest backend/tests` passes and README explains how to configure AI providers.

## Decisions already locked

- Backend framework: Starlette + Uvicorn.
- Backend base URL: `http://127.0.0.1:8123`.
- AI contract from issue #2:
  - Local model drafts descriptions from port signatures.
  - Cloud model reviews design canvas and returns structured feedback.
- Descriptions live in memory for now; persistence is later.

## Decisions to make in the PR

State your choice and why:

- Provider interface design (protocol, abstract base class, or simple functions).
- Configuration method (env vars, `.env`, or config file).
- Stub fallback strategy.
- Whether to support batch description drafting or one module at a time.

## Red lines

- Do **not** modify the existing `/api/scan`, `/api/scan/:jobId/status`, or `/api/scan/:jobId/graph` endpoints.
- Do **not** add database persistence in this ticket.
- Do **not** implement the design canvas UI; this ticket is backend-only.
- Do **not** merge, close issues, or delete branches without explicit user approval.

## Worktree discipline

This repo may have parallel Agents. Before you start:

1. Confirm you are in a dedicated git worktree.
2. Run `git status --short` and `git branch --show-current`.
3. Do not operate in another Agent's worktree.

See [[parallel-session-worktree-discipline]].

## Useful skills

- `/tdd` — write tests first.
- `/codebase-design` — keep provider abstraction clean.
- `/prototype` — quick endpoint smoke test if needed.

## Report back with

1. One-sentence summary of what changed.
2. Files modified and PR link.
3. Verification results (test output, manual curl output).
4. Next step or blocker.
5. Any decision that still needs the user.
