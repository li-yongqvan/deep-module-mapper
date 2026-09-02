# Handoff: 模块级循环依赖与孤儿模块检测（Cycle & Orphan Detection）

**Ticket**: GitHub issue #21 — https://github.com/li-yongqvan/deep-module-mapper/issues/21
**Role**: **执行 Agent（Worker）** — 本会话是一个执行分支
**Mission**: 在**重组视图**上，基于**真实代码聚合边**，检测**模块容器级**的循环依赖、孤儿模块、仅连第三方模块，用**节点标记 + Inspector 详情 + 工具栏轻量计数**呈现。纯前端，不自动改图、不提供一键修复。

## 你的身份与边界（重要，先读）

你是**执行 Agent**，不是统筹方。只完成本 ticket，开 PR，汇报。

**你做**：实现、写测试、开 PR，完成时把报告**追加**到 `wayfinder/统筹.md` 收件箱（见文末）。
**你不做**：不更新 `wayfinder/map.md`/`统筹.md`（收件箱追加除外）、不创建/改写/关闭 issue（含本 ticket）、不分配后续 ticket、不规划排期、不擅自合并 PR/关闭 issue/删除分支/push 到 main。
**何时停下请示**：范围不清、需要新决策、需要跨 ticket 改动时，停下来问统筹方/用户。

## 关键事实（统筹方已核实，不要假设）

1. **权威规格 = 设计文档**：`wayfinder/design-doc-issue-21-module-cycle-orphan-detection.md`。§0-§7 是你要实现的完整规格（真值核对 V1-V10、决策 D1-D5、裁决 1-5、不变量表）。先通读它再动代码。§9 的 Q1-Q5 是运行时/边界细节，见下面「PR 里要说明的决策」。
2. **范围收窄（用户 2026-09-01 确认）**：票面「现实视图」收窄为**重组视图·模块容器级（最大粒度）**。现实视图/功能视图**不做**。检测依据 = 真实聚合边（`computeAggregatedModuleEdges`），**不是**用户画的线。
3. **你的核心改动面**（纯前端，后端零改动）：
   - `frontend/src/lib/recompose/detect.ts` — **新建**：`detectModuleFindings(aggregated, design)` 纯函数（Tarjan SCC + 孤儿三分类）。
   - `frontend/src/components/RecomposeCanvas.tsx` — `useMemo` 算 findings，传给 `deriveNodes` / `RecomposeToolbar` / Inspector。
   - `frontend/src/lib/recompose/derive.ts` — `RecomposeModuleData` 增加 `diagnostic` 字段，`deriveNodes` 注入。
   - `frontend/src/components/RecomposeModuleNode.tsx` — `ModuleNodeBody` 按 `diagnostic` 渲染 badge/描边。
   - `frontend/src/components/RecomposeToolbar.tsx` — 新增 `diagnostics` 计数 + 可点列表。
   - `frontend/src/components/Inspector.tsx` — 模块选中带 finding → 三类详情。
4. **检测数据已齐，不用新后端**：`aggregated`（`RecomposeCanvas.tsx:150-153`）就是输入；每条聚合边带 `data.rawEdges`（文件级证据，含 `kind`/`targetPort`/`sites[].line`，`api/types.ts:31-44`）。「仅连第三方」的功能说明复用现有 `description`/`memberAtomNames`/`ports`，**不新写 AI**。
5. **真实 fixture 已知环（已实测，可复现）**：`frontend/src/__tests__/fixtures/deep-module-mapper.graph.json`（自扫描）+ 默认设计（模块=原子）下，Tarjan 检出**唯一非平凡 SCC = {training-logging, aggregation-orchestration, ai-provider-integration}**。无真孤立/仅连第三方原子 → 这两分支用合成图单测。
6. **已确认决策（用户 2026-09-01）**：呈现 = 只标节点 + Inspector（**不画环边**）；**不做画线时提示**（#18 交互原样）；**轻量汇总计数**。实现时别在这三点上自由发挥。

## Context pointers

先读这些再写代码：

- `deep-module-mapper/wayfinder/design-doc-issue-21-module-cycle-orphan-detection.md` — **权威规格**（§0-§7），一切以它为准。
- `deep-module-mapper/UBIQUITOUS_LANGUAGE.md` — 术语（模块容器/功能原子/依赖边）。
- `frontend/src/lib/recompose/edges.ts` + `types.ts` + `derive.ts` — 聚合边来源、`RecomposedDesign`/`RecomposeModuleData` 形状。
- `frontend/src/components/RecomposeCanvas.tsx` — `aggregated`（`:150-153`）、`deriveNodes` 调用、工具栏/Inspector 接线处。
- `frontend/src/components/RecomposeModuleNode.tsx` + `RecomposeToolbar.tsx` — 标记与计数渲染落点。
- `frontend/src/components/Inspector.tsx` — `RecomposedModuleSelection`（`:48-59`）、证据渲染（`:283-294`）。
- `frontend/src/api/types.ts` + `frontend/src/lib/aggregateEdges.ts` — `Graph.edges` 结构与聚合边证据。
- `frontend/src/__tests__/recompose.issue18.fixture.test.ts` — 真实 fixture 测试风格（四折门，对拍参考）。
- `deep-module-mapper/wayfinder/handoff-issue-18-recomposition-edge-check.md` — 上一票 handoff 的结构（本票沿用）。

## Steps

### 1. 通读设计文档，对照现状代码

把 `design-doc-issue-21` §2（真值核对 V1-V10）逐条在代码里核对一遍。重点确认：`aggregated` 在 `RecomposeCanvas.tsx:150-153` 已算好；`RecomposeModuleData` 有 `[key: string]: unknown` 兜底；`ModuleNodeBody` 渲染位置。有任何与文档不符的，停下来回报。

**Done when**: 你能说出「聚合边已算好」「标记注入点」「badge 渲染落点」「计数落点」各对应 `file:line`。

### 2. 新建 `detect.ts`（核心，纯函数）

实现 `detectModuleFindings(aggregated, design) → ModuleFindings`（§5.1 形状）：
- 建模块图：节点 = `design.modules`；边 = 聚合边中两端都在模块集合的（模块边）+ `target === THIRD_PARTY_NODE_ID` 的（第三方出边）。第三方节点不参与环检测。
- 环 = Tarjan SCC（非平凡 ≥2）。
- 孤儿三分类（D2）：正常 / `orphan/isolated`（无模块边无第三方边）/ `orphan/third-party-only`（无模块边、有第三方边）。
- 产出 `ModuleFindings`（`cycles`/`orphans`/`thirdPartyOnly`/`count`/`byModule`）。
- **空输入**（`design.modules=[]` 或 `aggregated=[]`）返回全空结构（S3）。
- **纯函数、无 React 依赖、不写回 design**。

**Done when**: 合成图单测通过（见 Step 5）：单环/多环/无环、孤儿三分类、证据非空、`byModule` 查表正确。

### 3. 接线 `RecomposeCanvas.tsx`

- `const findings = useMemo(() => detectModuleFindings(aggregated, design), [aggregated, design])` —— **活更新，v1 不去抖**（I4）。
- 传给 `deriveNodes`（新参数）注入每模块 `moduleDiagnostic`（I7）；传给 `RecomposeToolbar` 计数 + 可点列表；选中模块时带 finding 给 Inspector。

**Done when**: 设计一变（拖原子/增删模块）findings 即时重算；三个消费方都收到数据。

### 4. 渲染标记 + 计数 + Inspector

- `derive.ts`：`RecomposeModuleData` 增 `moduleDiagnostic: 'cycle' | 'orphan' | 'third-party-only' | null`（I7），`deriveNodes` 注入。
- `RecomposeModuleNode.tsx`（I2）：把 `containerStyle` 改为函数 `containerStyle(moduleDiagnostic)`，在 `RecomposeModuleNode` 中按 `data.moduleDiagnostic` 传入；badge 放 header 第一行「模块」标签左侧；颜色按 `severity` 映射（cycle=error=实线红；orphan/third-party-only=warning=虚线灰/琥珀）。
- `RecomposeToolbar.tsx`（I1）：接收 `diagnostics: ModuleFindings`，展示「N 个环 · M 个孤立 · K 个仅连第三方」pill；点击 pill 展开列表，项显示 `[标签] 模块中文名`；点击项调用 `onSelect(moduleId)` + `rf.fitView({ nodes: [moduleId], duration: 300 })`。
- `Inspector.tsx`（I3/S4）：模块选中带 finding → 环（SCC 成员 + 成员之间每段边证据）/ 孤儿（无入无出说明）/ 仅连第三方（功能说明，description 为空时 fallback）。

**Done when**: 三类 finding 在 UI 上各自可见；计数正确；正常模块无标记。

### 5. 测试

- 新建 `recompose.detect.test.ts`（合成图，§8 用例清单）。
- 新建 `recompose.issue21.fixture.test.ts`（真实 fixture：已知 3 原子环 + 计数断言）。
- 新建/扩 `RecomposeModuleNode.test.tsx`、`RecomposeToolbar.test.tsx`、`Inspector.test.tsx`。
- 不破坏既有测试（#18 的四折门、重组逻辑）。

**Done when**: `cd frontend && npm test` 全绿；`npx tsc --noEmit` 0 错误；`npm run build` 成功。

### 6. 真实 fixture 手动验证（交付门）

扫 deep-module-mapper 自身 → 重组视图（默认设计）：
1. training-logging / aggregation-orchestration / ai-provider-integration 三个模块显示「在环里」badge。
2. 点开任一 → Inspector 显示环成员及每段边代码证据。
3. 工具栏显示「1 个环 · 0 个孤立 · 0 个仅连第三方」。

**Done when**: 上面 3 步全部符合预期，把结果写进 PR 描述。

## PR 里要说明的决策

- **环路径提取**（§9 Q1）：v1 不展示环路径；Inspector 只展示 SCC 成员集合 + 成员之间所有聚合边证据。
- **模块内部环不可见**（§9 Q2）：确认未做、理由（模块=抽象边界；分组后环从视觉上消失是已知缺口）。
- **活更新稳定化**（§9 Q3）：v1 不去抖，依赖 `useMemo` 即时重算。
- **`ModuleFinding` 命名**（§9 Q5）：与 #18 `EdgeCheckReceipt` 的平行关系说明；节点 data 字段用 `moduleDiagnostic` 避免与 parser `Diagnostic` 混淆。

## Red lines

- 不动后端（`backend/`），不新增端点。
- **不改 #18 的画线交互**：不碰 `isValidConnection`/`checkDependency`/`finalEdges` 的校验语义；**不做画线构成环时提示**（D4）。
- **不画环边**：标记只进节点 data，不渲染新边（D3，尊重 #18 零边）。
- 现实视图 / 功能视图不标（D1）。
- 不自动改图、不提供一键修复、不写回代码库（issue #21「不做」）。
- 不改 `RecomposedDesign` 持久化格式、不改 parser 公共 API。
- 不用 AI 生成「说明功能」文案——只能复用现有 `description`/成员原子/端口（D2 + #18 D6 精神）。
- 不擅自合并 PR/关闭 issue/删除分支。

## Worktree discipline

本仓库可能有多并行会话。开始前：
1. 确认你在独立 git worktree（不是主 checkout）。
2. `git status --short` + `git branch --show-current`。
3. 不要动别的 Agent 的 worktree。

见 `C:\Users\liyongquan\.claude\projects\C--Users-liyongquan-agent-panel\memory\parallel-session-worktree-discipline.md`。

## Useful skills

- `/tdd` — 先写 `detect.ts` 的合成图测试（环 + 三分类）。
- `/codebase-design` — 保持 `detect.ts` 单职责、纯函数。
- `/mattpocock-skills:code-review` — 开 PR 前自查。

## 完成后：报告追加到统筹文件收件箱（执行 agent 的唯一出口）

把下面这份报告**追加**到 `wayfinder/统筹.md` 第 1 段「待处理」末尾（这是执行 agent 唯一允许写的协调文件），并在会话里给用户一句总结：

```markdown
### [报告] #21 Cycle & orphan detection —— 完成
- 日期：
- 一句话总结：
- 改动 + PR：
- 验证结果（测试输出 + 真实 fixture 三连验证 3 条结论）：
- 阻塞点/需拍板：
```
