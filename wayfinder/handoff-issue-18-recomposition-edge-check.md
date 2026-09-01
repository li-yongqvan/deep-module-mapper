# Handoff: Recomposition edge check — draw-to-verify dependencies

**Ticket**: GitHub issue #18 — https://github.com/li-yongqvan/deep-module-mapper/issues/18
**Role**: **执行 Agent（Worker）** — 本会话是一个执行分支
**Mission**: 把重组画布改成"**画线即校验**"：默认零边，人画的每一条线当场对代码事实做校验——真依赖（方向对）→ 画上并带代码证据解释；无依赖 → 拒绝并返回"这两个模块之间无任何依赖关系"；方向反 → 拒绝并提示"实际是 B 依赖 A"。让画布成为人探索/学习的工具，不是出答案的工具。

## 你的身份与边界（重要，先读）

你是**执行 Agent**，不是统筹方。只完成本 ticket，开 PR，汇报。

**你做**：实现、写测试、开 PR，完成时把报告**追加**到 `wayfinder/统筹.md` 收件箱（见文末）。
**你不做**：不更新 `wayfinder/map.md`/`统筹.md`（收件箱追加除外）、不创建/改写/关闭 issue（含本 ticket）、不分配后续 ticket、不规划排期、不擅自合并 PR/关闭 issue/删除分支/push 到 main。
**何时停下请示**：范围不清、需要新决策、需要跨 ticket 改动时，停下来问统筹方/用户。

## 关键事实（统筹方已核实，不要假设）

1. **权威规格 = 设计文档**：`wayfinder/design-doc-issue-18-recomposition-edge-check.md`。§0-§7 是你要实现的完整规格（真值核对 V1-V11、决策 D1-D8、裁决 1-4、不变量表）。先通读它再动代码。§9 的 Q1/Q2/Q4 是运行时/边界细节，见下面"PR 里要说明的决策"。
2. **现状（今天的行为，你要推翻的）**：重组画布**默认把聚合边全部渲染**（`RecomposeCanvas.tsx:146-157`），且 `isValidConnection` 只挡自环/第三方源，**不存在的依赖今天也能画上**（`edges.ts:114-142` `onConnectEdge` 直接 push `addedEdges`）。
3. **你的核心改动面**（纯前端，后端零改动）：
   - `frontend/src/lib/recompose/edges.ts` — 新增 `checkDependency` 校验函数；`finalEdges` 默认只渲染人画的边且带真实 `rawEdges`；`onConnectEdge` 简化；`onDeleteEdge` 只留 manual 分支。
   - `frontend/src/components/RecomposeCanvas.tsx` — `isValidConnection` 升级为校验门 + 一次性拒绝反馈。
   - `frontend/src/lib/recompose/persistence.ts` — `sanitizeDesign` 加载时对 `addedEdges` 重校验。
   - `frontend/src/components/Inspector.tsx` — **大概率无需改渲染逻辑**（已校验边 `manual:false` + 真实 rawEdges 会自动走证据分支，`Inspector.tsx:283-290`）；保留 manual 防御分支即可。
4. **校验数据已齐，不用新后端**：模块级聚合边（`computeAggregatedModuleEdges`）就是"容器↔容器真依赖"的方向敏感判据，且每条带 `data.rawEdges`（文件级边，含 `kind`/`targetPort`/`sites[].line`，`api/types.ts:31-44`）。解释 = 直接引用这些事实，不用 AI。
5. **已确认决策（用户 2026-08-30）**："显示真实依赖"开关**不做进 v1**；模块 → 第三方包 的真实依赖边**放行**（source 为 third-party 仍拒绝）。实现时别在这两点上自由发挥。

## Context pointers

先读这些再写代码：

- `deep-module-mapper/wayfinder/design-doc-issue-18-recomposition-edge-check.md` — **权威规格**（§0-§7），一切以它为准。
- `deep-module-mapper/UBIQUITOUS_LANGUAGE.md` — 术语（功能原子/模块容器/依赖边）。
- `frontend/src/lib/recompose/edges.ts` + `types.ts` + `persistence.ts` — 你要改的核心逻辑与数据形状。
- `frontend/src/components/RecomposeCanvas.tsx` — `isValidConnection`（`:222-224`）、`handleConnect`（`:210-220`）、`showFeedback`（`:171-177`）所在。
- `frontend/src/lib/aggregateEdges.ts` + `frontend/src/api/types.ts` — 聚合 helper 与 `Edge` 结构（证据来源）。
- `frontend/src/components/Inspector.tsx` — 边的证据渲染现状（`manual` 分支）。
- `frontend/src/__tests__/recompose.edges.test.ts` — 现有边逻辑测试（本次要新增/改写）。
- `deep-module-mapper/wayfinder/handoff-issue-8-feature-view-complete.md` — 功能视图如何消费 manifest 边（对照用）。

## Steps

### 1. 通读设计文档，对照现状代码

把 `design-doc-issue-18` §2（真值核对 V1-V11）逐条在代码里核对一遍，确认"现状"与你看到的一致。有任何与文档不符的，停下来回报，不要带着错误假设继续。

**Done when**: 你能说出 4 处现状行为（默认有边、无依赖可画、手动边无证据、Inspector 能渲染证据）各自对应的 `file:line`。

### 2. 新增 `checkDependency` 校验函数（核心）

在 `edges.ts`（或你认为更合适的 recompose lib 文件，保持单一职责）实现：
- 契约：`checkDependency(aggregated, source, target) → { status: 'real' | 'reversed' | 'none', evidence?: FlowEdge<AggregatedEdgeData> }`
- `real` = `(source,target)` 在聚合边集合；`reversed` = `(target,source)` 在且正向不在；`none` = 都不在。
- 复用现有 `edgeKey`（`edges.ts:19-28`）。

**Done when**: 对三种输入（真依赖/反方向/无依赖）都返回正确 status，且 `real` 时 `evidence.data.rawEdges` 非空（含端口/行号）。

### 3. 改 `finalEdges`：默认零边 + 人画的边带证据

- 默认**不渲染聚合边**（D1）。`aggregated` 保留，供校验与证据查用。
- 每条 `addedEdges` 渲染时，从聚合边里取出对应真实证据，data 改为 `{ manual: false, kinds, rawEdges: <真实证据>, displayLabel: '真实依赖' }`。
- `manual: false` 必须成立，Inspector 才会走证据分支（§2.1 V4）。

**Done when**: 画布初始零边；一条画上且校验通过的边，其 Inspector 里显示的是"调用点（N 条边）"证据列表，而不是"手动添加的依赖（无底层调用点）"。

### 4. 改 `isValidConnection` 为校验门 + 一次性反馈

- 保留 L1：自环、`source === THIRD_PARTY_NODE_ID` 拒绝（现状不变）。
- 调 `checkDependency`：
  - `real` → 返回 `true`。
  - `reversed` / `none` → 触发**一次性**反馈后返回 `false`。
- 反馈文案（设计文档 D4/D5 定了，别改语义）：
  - `none` → "这两个模块之间无任何依赖关系（B 的文件里没有任何 import 指向 A）"
  - `reversed` → "实际是 B 依赖 A，方向反了"
- **运行时风险（§9 Q1）**：`isValidConnection` 在拖拽/悬停期间可能被 React Flow 多次调用，反馈必须只弹一次。选一个稳健方案（如去抖、或只在连接完成瞬间判定），PR 里说明你的选择。

**Done when**: 拖一条不存在边 → 无新边 + 反馈只出现一次；拖一条反向边 → 无新边 + "方向反了"；拖一条真边 → 新边出现。连续快速拖多次不连弹。

### 5. 改 `onConnectEdge` / `onDeleteEdge` 简化

- `onConnectEdge`：校验已在 `isValidConnection` 拦截，这里只负责去重 push `addedEdges`。移除不再需要的 unhide/aggregateKeys 分支。
- `onDeleteEdge`：只保留 manual 分支（从 `addedEdges` 移除）；聚合边不再渲染，不再写 `hiddenEdges`。

**Done when**: 连接/删除事件路由的测试通过，且不产生非真实边、不写 `hiddenEdges`。

### 6. 改 `sanitizeDesign`：加载时重校验

- 加载 saved design 时，对每条 `addedEdges` 用 `checkDependency` 过滤，非真实边**丢弃**（裁决3）。真实边保留并补上证据（渲染层会自动查，见 Step 3）。
- `hiddenEdges` 读入后忽略；`version` 保持 1。
- 可选项（PR 里说明是否做）：丢弃非真实边时给用户一条提示，如"已移除 N 条无效边"。

**Done when**: 手工造一份含"非真实 addedEdges"的旧 localStorage 数据 → 加载后该边消失；含真实边的旧数据 → 加载后该边还在且带证据。

### 7. 更新/新增测试

- 改 `recompose.edges.test.ts`：`checkDependency` 三分支、`finalEdges` 默认零边 + 证据边、`onConnectEdge` 去重、`onDeleteEdge` 不写 hiddenEdges。
- 改 `recompose.persistence.test.ts`：`sanitizeDesign` 丢弃非真实边、保留真实边、旧设计可读。
- 改 `Inspector.test.tsx`：已校验边渲染证据列表。
- 更新所有被新行为推翻的旧断言（如"默认渲染聚合边""手动边 rawEdges:[]"）。

**Done when**: `cd frontend && npm test` 全绿；`npx tsc --noEmit` 0 错误；`npm run build` 成功。

### 8. 真实 fixture 手动验证（交付门）

扫一个真实库（可用 deep-module-mapper 自身），手动验证四连：
1. 重组画布初始零边。
2. 画一条真实边 → 画上，Inspector 显示代码证据。
3. 画一条不存在边 → 拒绝 + "无任何依赖关系"。
4. 画反方向 → 拒绝 + "方向反了"。

**Done when**: 上面 4 步全部符合预期，把结果写进 PR 描述。

## PR 里要说明的决策

- **一次性反馈方案**（§9 Q1）：你选了什么、为什么。
- **旧设计非真实边丢弃提示**（§9 Q2）：做/不做，做了的话文案是什么。
- third-party 作为 target 的放行（D10）、"显示真实依赖"开关不做（D9）——**用户已确认（2026-08-30）**，实现时不用再问。

## Red lines

- 不动后端（`backend/`），不新增端点。
- 不改 `RecomposedDesign` 的 `version`（保持 1）。
- 不改功能视图的边渲染（本票只改重组画布）。
- 不用 AI 生成解释文案——解释只能来自 parser 提取的代码事实。
- 不改 `parser` 公共 API。
- 不擅自合并 PR/关闭 issue/删除分支。
- 不实现"显示真实依赖"开关（用户确认 2026-08-30，out of scope）。

## Worktree discipline

本仓库可能有多并行会话。开始前：
1. 确认你在独立 git worktree（不是主 checkout）。
2. `git status --short` + `git branch --show-current`。
3. 不要动别的 Agent 的 worktree。

见 `C:\Users\liyongquan\.claude\projects\C--Users-liyongquan-agent-panel\memory\parallel-session-worktree-discipline.md`。

## Useful skills

- `/tdd` — 先写 `checkDependency` 三分支的测试。
- `/codebase-design` — 保持 `edges.ts` 单职责。
- `/mattpocock-skills:code-review` — 开 PR 前自查。

## 完成后：报告追加到统筹文件收件箱（执行 agent 的唯一出口）

把下面这份报告**追加**到 `wayfinder/统筹.md` 第 1 段「待处理」末尾（这是执行 agent 唯一允许写的协调文件），并在会话里给用户一句总结：

```markdown
### [报告] #18 Recomposition edge check —— 完成
- 日期：2026-08-31
- 一句话总结：
- 改动 + PR：
- 验证结果（测试输出 + 真实 fixture 四连验证 4 条结论）：
- 阻塞点/需拍板：
```
