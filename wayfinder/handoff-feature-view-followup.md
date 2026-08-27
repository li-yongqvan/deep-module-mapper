# Handoff: Feature-view follow-up — code-review findings cleanup

**Ticket**: GitHub issue #13 — https://github.com/li-yongqvan/deep-module-mapper/issues/13  
**Role**: **执行 Agent（Worker）** — 本会话是一个执行分支  
**Mission**: Clean up four code-review findings from PR #12 (issue #8). Small, well-scoped refactor + one missing test. No new features.

## 你的身份与边界（重要，先读）

你是**执行 Agent**，不是统筹方。你只做一件事：完成本 ticket 的清理，开 PR，汇报。

**你做**：实现、写测试、开 PR、汇报。
**你不做**：不更新 `wayfinder/map.md`、不创建/改写/关闭任何 issue（含本 ticket）、不分配后续 ticket、不规划排期、不擅自合并 PR/关闭 issue/删除分支/push 到 main。
**何时停下请示**：范围不清、需要新决策、需要跨 ticket 改动时，停下来问统筹方/用户。

## Context pointers

Read these before writing code:

- `deep-module-mapper/UBIQUITOUS_LANGUAGE.md` — domain terms.
- `frontend/src/components/ModuleNode.tsx` — duplicated `handleStyle` (site 1), hardcoded `width: 160`.
- `frontend/src/components/ExternalNode.tsx` — duplicated `handleStyle` (site 2).
- `frontend/src/components/FeatureAtomNode.tsx` — duplicated `handleStyle` (site 3).
- `frontend/src/components/LabeledEdge.tsx` — double-channel edge label.
- `frontend/src/components/Inspector.tsx` — drill-down UI, no render test.
- `frontend/src/lib/layout.ts` — `NODE_WIDTH` (160) and `ATOM_NODE_WIDTH` (220) constants.
- `frontend/src/lib/aggregateEdges.ts` — edge aggregation (extracted in #8).
- `deep-module-mapper/wayfinder/design-doc-issue-7-frontend-real-view.md` — §5.6 planned a shared `PortHandle`.
- `deep-module-mapper/wayfinder/handoff-issue-8-feature-view-complete.md` — #8 handoff with the code-review findings.

## The four findings

All four are confirmed present in the current code. Fix them exactly; do not expand scope.

### 1. Extract shared `PortHandle`

`handleStyle` is copy-pasted in `ModuleNode.tsx`, `ExternalNode.tsx`, `FeatureAtomNode.tsx` (three identical 10px circular handle styles). #7 design doc §5.6 already planned this.

**Fix**: one shared component/module (e.g. `components/PortHandle.tsx` or a shared style) used by all three node types.

**Done when**: `handleStyle` exists in exactly one place; all three nodes use it; behavior unchanged (same rendered style).

### 2. Unify `ModuleNode` width

`ModuleNode.tsx` hardcodes `width: 160` while `NODE_WIDTH` exists in `layout.ts` and `FeatureAtomNode` already uses `ATOM_NODE_WIDTH`.

**Fix**: `ModuleNode` imports and uses `NODE_WIDTH` from `layout.ts`.

**Done when**: no hardcoded node width remains in `ModuleNode`; `NODE_WIDTH` is the single source.

### 3. Single-channel edge label

The feature-view edge label `'依赖'` is expressed via `formatLabel` + `extraData.displayLabel` (double channel), but `LabeledEdge` only renders the latter.

**Fix**: collapse to one channel. If `displayLabel` is the only thing rendered, drop the dead `formatLabel` path or make `LabeledEdge` render one source of truth.

**Done when**: `LabeledEdge` reads the label from exactly one field; no dead label path remains.

### 4. Add Inspector drill-down render test

Issue #8 acceptance criterion 8 (drill-down) only tested at the transform level (`data.files`). The Inspector component has no component test at all.

**Fix**: add a render test for Inspector's atom branch — atom click shows member files + port signatures.

**Done when**: a component test renders Inspector with an atom selected and asserts member files / ports appear.

## Not in scope (accepted already)

- **ExternalNode Handle addition** — accepted in PR #12 as a real bug fix. Do not revert it.
- **Atomic depth-score semantics** — spec wording was ambiguous; recorded as known limit. Do not touch scoring.
- Edge-label **Chinese text** itself, node colors, layout, manifest format — none of these change.

## Acceptance criteria

- [ ] `handleStyle` lives in one shared place; all three node types use it.
- [ ] `ModuleNode` uses `NODE_WIDTH` (no hardcoded `160`).
- [ ] Edge label uses a single channel.
- [ ] Inspector drill-down has a render test.
- [ ] All existing tests still pass (32+; the new test makes it 33+).
- [ ] `npx tsc --noEmit` 0 errors; `npm run build` succeeds.

## Verification

```bash
cd frontend
npm test          # 32 existing + new Inspector test all pass
npx tsc --noEmit  # 0 errors
npm run build     # succeeds
```

Also do a quick manual check in the running dev server: feature view still renders the 3 Chinese nodes; drill-down still shows member files.

## Red lines

- Do **not** modify parser public API, backend endpoints, or the manifest format.
- Do **not** touch the ExternalNode Handle fix, scoring semantics, or edge Chinese text.
- Do **not** expand scope into new features (this is cleanup only).
- Do **not** merge, close issues, or delete branches without explicit user approval.

## Worktree discipline

This repo may have parallel Agents. Before you start:

1. Confirm you are in a dedicated git worktree (not the main checkout).
2. Run `git status --short` and `git branch --show-current`.
3. Do not operate in another Agent's worktree.

See [[parallel-session-worktree-discipline]].

## Useful skills

- `/tdd` — write the Inspector test first, then make it pass.
- `/codebase-design` — keep the shared component clean.
- `/simplify` — the single-channel label collapse is a simplification.

## Report back with

1. One-sentence summary of what changed.
2. Files modified and PR link.
3. Verification results (test output, tsc/build).
4. Next step or blocker.
5. Any decision that still needs the user.
