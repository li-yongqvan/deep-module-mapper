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

---

## 完成状态（执行 Agent 回填 · 2026-08-28）

**状态**：✅ 已交付。PR **#14**（OPEN，base=`master`，head=`worktree-issue-10-recomposition`）
https://github.com/li-yongqvan/deep-module-mapper/pull/14 · **21 文件，+2971 / −105**。

### 六个核心任务 → 交付对应

| 任务 | 交付 |
|---|---|
| 1. 第三模式 | `viewMode: 'feature' \| 'real' \| 'recompose'`，顶栏「重组视图」按钮，独立 `<RecomposeCanvas>`（自包 `ReactFlowProvider`），feature/real 共享画布未动 |
| 2. 模块容器 | React Flow **父节点**容器 + 原子 chip 子节点；中文名可双击编辑；拖进/拖出；不在显式模块的原子 = 自己的隐式单原子模块 |
| 3. 模块间依赖边 | 自动聚合（复用 `aggregateEdges`）∪ 手动新增 − 手动隐藏；Inspector 可删手动边 |
| 4. 重组后重渲染 | `deriveNodes` + `finalEdges` 纯函数按 design 重派生，design 状态提升到 App，切视图不丢未保存编辑 |
| 5. 保存/加载/重置 | 工具栏按钮；localStorage（`dmm:recompose:v1:<encodedPath>`）；重置 = manifest 派生建议分组 |
| 6. 测试 + README | 新增 6 个测试文件 + Inspector 扩展；`frontend/README.md` 增三视图与重组用法 |

### PR 需拍板的四个决策 → 定案（详见 `wayfinder/grilling-decisions/issue-10-recomposition-decisions.md`）

1. **模块画布表示** = 父节点容器（模块）+ 子节点（原子 chip），一个原子单独成模块（隐式）。
2. **持久化** = localStorage（按代码库路径分 key）；`/api/designs` 是后续 ticket，未碰后端。
3. **模块能否嵌套** = **V1 不嵌套**。
4. **模块命名** = 自动派生中文名 + 双击编辑；`nameCustomized`/`descriptionCustomized` 标记，重扫不覆盖用户编辑。

补充定案：模块边语义 = 自动聚合 + 手动增删；第三方依赖节点保留在重组画布上。

### 验证结果

- `npm test`：13 文件 / **99 测试全绿**（含空模块拖入回归、re-id、改名保持、#8 坐标一致、转移表每行）。
- `npx tsc --noEmit` / `tsc -b`：**0 错误**；`npm run build` 成功；lint 无 error。
- Playwright 冒烟：`smoke_recompose.py`（建模块/拖入/改名/保存重载/未保存保留/重置）九步全过；`smoke_edges.py`（自动边/手动连线/保存恢复/Inspector 删除）全流程过。
- 过程中发现并修复 **2 个真实逻辑 bug**（拖入空模块时目标被误删、对偶删除提前返回），均有回归测试钉住。

### 红线合规

未改 parser 公共 API、未动 `/api/scan/*` 三端点、未做 AI 聚合（#11）、未做画布评审端点；未更新 `wayfinder/map.md`、未建/改/关 issue、未排期、未合并 PR。

### 已补文档

`UBIQUITOUS_LANGUAGE.md` 补「功能原子」「模块容器」术语 + 模块双义说明（commit `634028e`，评审基线 #16 的可选部分，经统筹方同意后补）。

### 待统筹方

- **评审 PR #14** 并合入；合并后本 worktree `deep-module-mapper-issue-10` 可清理。
- 后续 ticket：AI 聚合（#11）将以本层数据源替换手工 manifest；画布评审端点另行安排。

