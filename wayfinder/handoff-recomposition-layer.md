# Handoff: Recomposition layer — custom canvas with module-content editing

**Ticket**: GitHub issue #10 — https://github.com/li-yongqvan/deep-module-mapper/issues/10  
**Role**: **执行 Agent（Worker）** — 本会话是一个执行分支  
**Mission**: Build the recomposition canvas. The user groups functional atoms into **modules** — a module is a container that holds one or more atoms (a single atom may be its own module). The canvas lets the user drag atoms into/out of modules and connect dependency edges between modules.

## 你的身份与边界（重要，先读）

你是**执行 Agent**，不是统筹方。只完成本 ticket，开 PR，汇报。

**你做**：实现、写测试、开 PR、汇报。
**你不做**：不更新 `wayfinder/map.md`、不创建/改写/关闭 issue（含本 ticket）、不分配后续 ticket、不规划排期、不擅自合并 PR/关闭 issue/删除分支/push 到 main。
**何时停下请示**：范围不清、需要新决策、需要跨 ticket 改动时，停下来问统筹方/用户。

## 核心概念（已锁定，不要偏离）

- **功能原子（functional atom）** = 最小的、给人看的单位（一个节点）。例如「扫描并解析代码库」。
- **模块（module）** = 容器，可包含 **1 个或多个** 功能原子；一个原子也可以单独成为一个模块。类比汽车：方向盘+车灯+制动+空调合成一个「汽车」模块，对外一个接口。
- **工作流**：视图层先输出（功能视图，#8 已完成）→ 本层让用户据此优化分组 → 重组后视图重新渲染。
- 第一版数据源 = 手工 manifest（`frontend/src/manifest/feature-atoms.json`）；AI 聚合（#11）后续替代，格式保持稳定。

## Context pointers

Read these before writing code:

- `deep-module-mapper/UBIQUITOUS_LANGUAGE.md` — domain terms.
- `frontend/src/App.tsx` — current app: `viewMode` toggles `'feature' | 'reality'`; hooks up `graphToFeatureFlow` / `graphToFlow`; this is where the recomposition mode joins.
- `frontend/src/lib/graphToFeatureFlow.ts` — produces `FeatureFlowGraph` (atom nodes + external nodes).
- `frontend/src/manifest/featureAtoms.ts` + `feature-atoms.json` — `FeatureAtom { id, name, description, files }`; the atom-level source of truth.
- `frontend/src/components/FeatureAtomNode.tsx` — the atom node component; its handles connect edges.
- `frontend/src/lib/aggregateEdges.ts`, `lib/layout.ts`, `lib/depthScore.ts` — shared utilities.
- `deep-module-mapper/wayfinder/design-data-schema.md` — schema & API contract.
- `deep-module-mapper/wayfinder/handoff-issue-8-feature-view-complete.md` — what #8 shipped (feature view).

## Steps

### 1. Add a recomposition mode to the app

Add a third mode alongside `'feature' | 'reality'` — e.g. `'recompose'`. It starts from the feature view's atom nodes (the suggested grouping) as its canvas state.

**Done when**: a user can switch into recomposition mode and sees the same atom nodes as the feature view.

### 2. Module containers on the canvas

Add **module** as a first-class canvas object — a container that holds one or more atoms. A module shows a Chinese name and exposes a single interface (aggregated). An atom can be dragged into/out of a module. An atom not in any explicit module is its own module (single-atom module).

Decide and state in the PR: how modules are represented (a group node / a named container / a region), and how a module's name/description is edited.

**Done when**: you can create a module, drag an atom into it, drag it out, and rename it.

### 3. Draw/remove dependency edges between modules

Between modules, the user can draw and remove dependency edges (the design-canvas behavior from the prototype). Edges aggregate from the atoms inside each module.

**Done when**: you can connect two modules with an edge and remove it; the edge reflects the underlying atom dependencies.

### 4. Render the recomposed grouping

After any recomposition, the view re-renders: each module = Chinese name + one interface + aggregated dependencies. Keep the existing feature/reality views intact; recomposition is additive.

**Done when**: recomposing changes what the view shows — modules appear with their aggregated edges and one interface each.

### 5. Save / load / reset

- Save the user's grouping (module contents + edges). Persistence decision is yours: in-memory for the session, localStorage, or a backend `/api/designs` endpoint — state the choice and why.
- Load a saved grouping.
- **Reset to suggested grouping** — reverts to the manifest-derived grouping.

**Done when**: save → reload → grouping restored; reset returns to the manifest grouping.

### 6. Tests + README

Cover: module creation, atom drag in/out, edge draw/remove, save/load, reset, aggregated interface rendering. Update `frontend/README.md` with how to use recomposition.

**Done when**: `npm test` passes (new tests included), `npx tsc --noEmit` 0 errors, `npm run build` succeeds.

## Decisions to make in the PR

- Module representation on canvas (group node vs container region vs left panel).
- Persistence: in-memory / localStorage / backend `/api/designs` endpoint.
- Whether modules can nest (keep it simple if uncertain).
- How a module's Chinese name/description is set (auto from contents vs user-typed).

## Red lines

- Do **not** modify `parser` public API (`scan_codebase`).
- Do **not** modify existing `/api/scan`, `/api/scan/:jobId/status`, `/api/scan/:jobId/graph` endpoints. If you add `/api/designs`, add it — don't change the scan endpoints.
- Do **not** implement AI aggregation (that's #11) or the canvas review endpoint (later ticket).
- Do **not** merge, close issues, or delete branches without explicit user approval.

## Worktree discipline

This repo may have parallel Agents. Before you start:

1. Confirm you are in a dedicated git worktree (not the main checkout).
2. Run `git status --short` and `git branch --show-current`.
3. Do not operate in another Agent's worktree.

See [[parallel-session-worktree-discipline]].

## Useful skills

- `/prototype` — quick interaction model spike before committing to a canvas design.
- `/tdd` — test the grouping/edge ops first.
- `/frontend-design` — module container visual design.

## Report back with

1. One-sentence summary of what changed.
2. Files modified and PR link.
3. Verification results (test output, manual interaction notes, screenshot if possible).
4. Next step or blocker.
5. Any decision that still needs the user.
