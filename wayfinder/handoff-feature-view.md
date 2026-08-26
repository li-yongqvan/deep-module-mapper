# Handoff: Feature view — functional-atom grouping + Chinese descriptions

**Ticket**: GitHub issue #8 — https://github.com/li-yongqvan/deep-module-mapper/issues/8  
**Role**: Worker Agent  
**Mission**: Make the map readable by a non-developer. Aggregate file-level modules into **functional atoms** (a group of files that together implement one capability), render each atom as a node titled with its **Chinese name + one-line description**, few interfaces, simple dependencies. This ticket is the **view layer**; the human optimizes later in the recomposition layer (issue #10).

## North star

The map's reader is a non-developer. A node must say "what this thing does" in Chinese, not "where this file lives." Node count and edge count must drop to a handful. An atom is like a car: steering wheel + lights + brakes + AC grouped, exposed as one interface.

## Context pointers

Read these before writing code:

- `deep-module-mapper/UBIQUITOUS_LANGUAGE.md` — domain terms.
- `deep-module-mapper/wayfinder/design-data-schema.md` — Graph schema.
- `frontend/src/api/types.ts` — `Graph`/`Module`/`Edge`/`ExternalModule` TypeScript types.
- `frontend/src/lib/graphToFlow.ts` — existing modules → React Flow nodes transform.
- `frontend/src/lib/depthScore.ts` — existing traffic-light scoring.
- `deep-module-mapper/wayfinder/handoff-issue-7-complete.md` — what #7 shipped and its locked decisions.
- `deep-module-mapper/wayfinder/design-doc-issue-7-frontend-real-view.md` — #7 design doc.

## The functional-atom manifest

A **hand-maintained manifest** is the single source of truth for grouping in this version. Design its format (JSON or Markdown), then ship a curated manifest for `deep-module-mapper` itself. AI aggregation (issue #11) will later produce the same format as a drop-in replacement, so keep the format clean and stable.

Each atom: a **Chinese name**, a **one-line Chinese description**, and the **list of file paths** it groups. Example intent:

```json
{
  "atoms": [
    {
      "id": "scan-and-parse",
      "name": "扫描并解析代码库",
      "description": "读取目录，提取每个文件的公开接口与依赖关系",
      "files": ["parser/__init__.py", "parser/_scanner.py", "parser/_ports.py", "parser/_edges.py", "parser/_external.py", "parser/_diagnostics.py"]
    }
  ]
}
```

Files not in any atom are hidden by default (noise). Decide the manifest location (e.g. `frontend/src/manifest/feature-atoms.json` or `wayfinder/feature-atoms.md`); state the choice in the PR.

## Steps

### 1. Design the manifest format and ship the curated manifest

Decide the format, then author atoms for `deep-module-mapper` itself. Group its real modules into a handful of atoms (e.g. `parser/`, `backend/` internals) with Chinese names and one-line descriptions. Exclude tests/fixtures/`__init__.py` from atoms (they are noise, not features).

**Done when**: every production file of `deep-module-mapper` is assigned to exactly one atom, and unassigned files are only tests/fixtures/`__init__.py`.

### 2. Aggregate the Graph into atom-level nodes

Given the file-level `Graph`, produce atom-level nodes:

- One node per atom, titled with its **Chinese name**, body showing the **one-line description**.
- Drill-down: clicking/hovering an atom shows the files inside it.
- Dependencies aggregate: an edge between two atoms exists iff any file in one depends on any file in the other. Fewer nodes, fewer edges.
- Recompute traffic-light score at the atom level (atom's interface = union of its files' ports; fewer ports = simpler = deeper).

Extend `graphToFlow.ts` (or add a sibling transform) to consume the manifest.

**Done when**: scanning `deep-module-mapper` renders ~3–6 Chinese-named nodes instead of 29 file nodes, with aggregated edges.

### 3. Filter noise by default

Tests, fixtures, `__init__.py` and any file not in an atom do not appear as nodes. Keep them reachable (drill-down or a toggle) but off the default map.

**Done when**: default view contains only atom nodes.

### 4. Keep existing behavior working

The scan → poll → render flow must still work. The real-view and the feature view may be two modes/views, or the feature view replaces the default; state the choice in the PR. Keep `depthScore`, `graphToFlow`, and the existing tests passing.

**Done when**: `npm test` passes (existing tests updated or new ones added) and `npm run build` succeeds.

### 5. Add tests

Cover: file→atom mapping, edge aggregation, noise filtering, drill-down, atom-level scoring. Update any #7 tests that assumed file-level nodes.

**Done when**: new + existing tests pass.

### 6. Update README/design doc

Document the manifest format, how to edit atoms, and how the feature view relates to the real view.

**Done when**: a new reader can extend the manifest and see the map update.

## Decisions already locked

- North star: non-developer readable; functional atoms; few interfaces; simple dependencies.
- First version: hand-maintained manifest (no AI).
- This ticket: view layer only. Recomposition is #10. AI aggregation is #11.
- Noise files hidden by default.
- Do not modify parser public API.

## Decisions to make in the PR

- Manifest location + format (JSON vs Markdown).
- Where aggregation lives: frontend transform (extend `graphToFlow`) vs backend endpoint.
- Feature view vs real view: replace default, or separate mode/toggle.
- Drill-down UX (click vs hover, files shown where).

## Red lines

- Do **not** modify `parser` public API (`scan_codebase` signature/return shape).
- Do **not** modify existing `/api/scan`, `/api/scan/:jobId/status`, `/api/scan/:jobId/graph` endpoints (if you add a backend endpoint, add it, don't change those).
- Do **not** implement AI aggregation here (that's #11) — manual manifest only.
- Do **not** implement the recomposition canvas here (that's #10).
- Do **not** merge, close issues, or delete branches without explicit user approval.

## Worktree discipline

This repo may have parallel Agents. Before you start:

1. Confirm you are in a dedicated git worktree.
2. Run `git status --short` and `git branch --show-current`.
3. Do not operate in another Agent's worktree.

See [[parallel-session-worktree-discipline]].

## Useful skills

- `/tdd` — write tests first.
- `/frontend-design` — Chinese-description node styling.
- `/codebase-design` — keep the aggregation transform clean.

## Report back with

1. One-sentence summary of what changed.
2. Files modified and PR link.
3. Verification results (test output; screenshot or manual scan of `deep-module-mapper` showing ~3–6 Chinese nodes).
4. Next step or blocker.
5. Any decision that still needs the user.
