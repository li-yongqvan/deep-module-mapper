# 设计文档：模块级循环依赖与孤儿模块检测（Cycle & Orphan Detection）

> 文档用途：交付专业评审 agent 的评审对象。范围 = 背景 / 真值核对 / 决策记录 / 实现方案 / 不变量 / 验证。
> 溯源约定：**事实**标来源（代码 `file:line` / 实测命令 / 用户确认）；**判断性裁决**单独标注【决策】并给出理由与备选，不冒充事实。
> 数据时点：2026-09-01（真值核对执行日；纯前端改动，无服务器/DB 实查项）。
> 评审状态：待评审（对应 GitHub issue #21 — https://github.com/li-yongqvan/deep-module-mapper/issues/21）。

## §0 项目上下文（给零背景评审 agent）

- **这是什么**：Deep Module Mapper —— 本地 Web 应用，指向任意代码库后提取**模块（实现+端口）**与**依赖边**，可视化并支持在**重组画布**上把人理解的**功能原子**装进**模块容器**、设计依赖关系。四层架构：解析层（Python AST）→ 聚合层（AI 把文件聚成功能原子）→ 重组层（人设计模块分组与依赖）→ 视图层（React Flow 画布）。共同语言见 `deep-module-mapper/UBIQUITOUS_LANGUAGE.md`。
- **技术栈**：前端 Vite 8 + React 19 + TypeScript + `@xyflow/react` 12（`frontend/`）；后端 Starlette + Uvicorn，仅 `scan/status/graph` 三端点（`backend/`）。本票**纯前端**，后端零改动。
- **三视图**：**现实视图**（文件级，`graphToFlow.ts`，一个 `.py` = 一个节点）；**功能视图**（原子级，`graphToFeatureFlow.ts`）；**重组视图**（模块容器级，`RecomposeCanvas.tsx`，#10 建立、#18 加了「画线即校验」）。**本票检测只落在重组视图。**
- **与本次相关的关键组件**（均可自行查阅）：
  - `frontend/src/components/RecomposeCanvas.tsx` — 重组画布主组件；`aggregated`（真实聚合边）已算好（`:150-153`）
  - `frontend/src/lib/recompose/edges.ts` — 聚合边语义（`computeAggregatedModuleEdges` / `finalEdges` / `checkDependency`）
  - `frontend/src/lib/recompose/derive.ts` — 设计 → React Flow 节点（`deriveNodes`，模块节点 data 形状 `RecomposeModuleData`，`:225-245`）
  - `frontend/src/components/RecomposeModuleNode.tsx` — 模块容器节点渲染（`ModuleNodeBody`，`:113-157`；标记/badge 落点）
  - `frontend/src/components/RecomposeToolbar.tsx` — 工具栏（轻量汇总计数落点）
  - `frontend/src/components/Inspector.tsx` — 详情面板（`RecomposedModuleSelection`，`:48-59`；evidence 渲染 `:283-294`）
  - `frontend/src/api/types.ts` — `Graph` / `Edge` 数据结构（边的端口与行号证据）
  - `frontend/src/__tests__/fixtures/deep-module-mapper.graph.json` — 真实自扫描 fixture（#18 四折门在用）
- **关键架构纪律**：
  - **聚合层纯 AI**（#11）：文件→功能原子由 DeepSeek 判定，无人工逐文件纠错；人只价值集中在重组层。
  - **北极星（#8）**：读者是不懂代码的人；节点按功能聚合；接口少 → 依赖简单。重组画布 = 人探索/学习的工具。
  - **#18 画线即校验**：重组画布默认**零边**（D1），人画的每条线当场对照代码事实校验，真依赖才画上并带证据。
- **前序工作**：#10 重组层（PR #14）建模块容器；#11 AI 聚合（PR #15/#16）把功能原子清单改为 DeepSeek 生成；#18（PR #19，已合并）重组画布「画线即校验」。**本票在 #18 之上加一层「结构诊断」**：环与孤儿——检测依据正是 #18 已算好的真实聚合边，不新增管线。
- **角色与权限**：本票由**执行 Agent（Worker）**实现；统筹方负责地图、本设计文档、handoff、红线。执行方不更新地图、不建/关 issue、不分配后续票。
- **术语速查**：**模块容器** = 重组画布上装 1+ 功能原子的框（单原子自动成隐式模块，`derive.ts:176-194`）；**真实聚合边** = `computeAggregatedModuleEdges` 产出的「容器↔容器」代码事实边（带底层 `rawEdges` 证据）；**环** = 模块间真实依赖构成的循环；**孤儿** = 与其它模块容器且第三方都无边的容器（真孤立）；**仅连第三方** = 只连第三方节点、与其它模块容器无边的容器（单独高亮 + 说明功能）。

## §1 背景与目标

- **需求来源**：GitHub issue #21 body + 用户 2026-09-01 grilling 确认（决策记录见 §3）。
- **现状矛盾**：解析层已产出全部文件级依赖边（`Graph.edges`，含证据）；#18 已把「容器↔容器真依赖」的聚合边算好（`RecomposeCanvas.tsx:150-153`）。但**没有任何一层检测/标注结构坏味道**——代码库里有没有循环依赖、有没有孤儿模块，用户看不到。而「依赖越简单越好」（map.md 已确认原则）：循环依赖是最直接的架构坏味道，直接影响深模块判断；孤儿模块常是死代码或遗留模块信号。
- **目标（一句话）**：在**重组视图**上，基于**真实代码聚合边**，检测**模块容器级**的循环依赖、孤儿模块、仅连第三方模块，用**节点标记 + Inspector 详情 + 工具栏轻量计数**呈现。纯前端，不自动改图、不提供一键修复（人拍板）。
- **范围收窄说明**：issue #21 票面写「在解析/现实视图层面检测」「现实视图的模块/原子粒度」。用户 2026-09-01 明确收窄：**不用管现实视图，只做模块那一级（最大粒度 = 重组视图模块容器）**（§3 D1）。这是对票面的用户确认性收窄，评审请以此为准。
- **相关背景（不影响本票范围）**：2026-09-01 用户反馈功能视图/现实视图设计可能偏离其想法、或需重设计（已记入 `wayfinder/map.md` Notes，拟独立会话）。本票不触碰它们，只做重组视图。

## §2 真值核对（数据来源，全部可复现）

> 纯前端改动，无服务器/DB 真值。以下均为本地仓库实查。

### 2.1 代码真值

**V1｜重组画布已算好真实聚合边（检测的直接输入）**
- 命令：Read `frontend/src/components/RecomposeCanvas.tsx`
- 结果摘录：
  - `:150-153` `const aggregated = useMemo(() => computeAggregatedModuleEdges(graph, design), [graph, design])`
- 结论：✅ 属实 —— 检测模块直接以 `aggregated` 为输入，零新增管线。

**V2｜聚合边已丢弃同模块边与噪音端点**
- 命令：Read `frontend/src/lib/recompose/edges.ts:128-144`
- 结果摘录：`resolveEndpoint` 把外部文件解析到 `THIRD_PARTY_NODE_ID`、无原子归属的文件解析为 null 丢弃；`cross = graph.edges.filter((e) => s !== null && t !== null && s !== t)`
- 结论：✅ 属实 —— 模块**内部**环（成员原子之间）天然不可见；自环不存在。这是 §6 裁决4 的事实基础。

**V3｜模块 → 第三方 的真实边保留在聚合集合**
- 命令：Read `edges.ts:129` + #18 D10
- 结果摘录：`if (externalIds.has(fileId)) return THIRD_PARTY_NODE_ID`
- 结论：✅ 属实 —— 「仅连第三方」分类的判定数据（模块→第三方边）存在于聚合集合，无需新提取。

**V4｜默认设计 = 隐式单原子模块；模块容器随拖拽变粗**
- 命令：Read `frontend/src/lib/recompose/derive.ts:176-194`（`initialDesign`）
- 结果摘录：每个功能原子 → `id: atom:<atomId>` 的隐式模块；用户分组后模块含多原子。
- 结论：✅ 属实 —— 检测在「默认设计」时等价于原子级；用户分组后自动收窄/内化（§6 裁决2 活检测）。

**V5｜模块节点 data 形状（标记注入点）**
- 命令：Read `derive.ts:225-245`
- 结果摘录：模块节点 `data: { kind: 'recomposeModule', moduleId, name, description, atomIds, implicit, memberNames, score, portCount, ... }`，类型 `RecomposeModuleData`（`:45-62`），有 `[key: string]: unknown` 兜底。
- 结论：✅ 属实 —— 新增 `diagnostic` 字段有兜底可放，不影响既有字段。

**V6｜模块容器节点渲染（badge/描边落点）**
- 命令：Read `frontend/src/components/RecomposeModuleNode.tsx:113-157`
- 结果摘录：`ModuleNodeBody` 渲染 header（`模块` 标签 + 名称 + `接口` 描述 + 深度分）；容器边框 `containerStyle`（`:98-110`）。
- 结论：✅ 属实 —— 可按 `diagnostic` 分支加 badge 与边框色，纯 presentational、可 jsdom 测。

**V7｜工具栏（汇总计数落点）**
- 命令：Read `frontend/src/components/RecomposeToolbar.tsx`
- 结果摘录：浮动在画布左上，按钮行 + `feedback` 文案。
- 结论：✅ 属实 —— 新增 `diagnostics` 计数 prop 即可，改动小。

**V8｜Inspector 已能渲染 rawEdges 证据 + 已有模块选中类型**
- 命令：Read `frontend/src/components/Inspector.tsx:283-294`（evidence 列表）+ `:48-59`（`RecomposedModuleSelection`）
- 结果摘录：证据渲染 `e.kind → ${targetPort} @ line`；模块选中已含 `description`/`memberAtomNames`/`memberFileCount`/`ports`。
- 结论：✅ 属实 —— 环的证据与「仅连第三方」的功能说明都可复用现有字段渲染，无新 UI 骨架。

**V9｜真实 fixture 存在已知 3 原子环（本设计实测，可复现）**
- 命令：node 脚本读 `frontend/src/__tests__/fixtures/deep-module-mapper.graph.json`（53 模块 / 14 external / 301 原始边）+ `frontend/src/manifest/feature-atoms.json`，按默认设计（模块 = 原子）建模块图，跑 Tarjan SCC。
- 结果摘录：`non-trivial SCCs: 1 [["training-logging","aggregation-orchestration","ai-provider-integration"]]`；`atoms participating in any edge: 7 of 7`；无「仅连第三方」/真孤立原子。
- 结论：✅ 属实 —— 真实 fixture 可直接验证「已知环」（默认设计下模块图 = 原子图）；孤儿 / 仅连第三方两分支用合成图单测（§8）。

**V10｜检测所需全部数据前端已有，无新后端**
- 命令：Read `frontend/src/api/types.ts`（`Graph.edges`/`externalModules`）+ `derive.ts`（`portsByAtom`）
- 结论：✅ 属实 —— 检测输入 = `aggregated`（V1）+ `design` + 现有端口/描述数据；无服务器/DB 项。

### 2.2 未复核项

- 无服务器/DB 项。所有设计所依赖的代码事实均已核（V1-V10）。实现时若发现与本设计不符，以代码为准并回报。

## §3 Grilling 决策记录

> 以下决策均为用户 2026-09-01 确认（grilling 会话当场合），决策原文随附，后续会话可复核。**完整落档见 `wayfinder/grilling-decisions/issue-21-cycle-orphan-detection-decisions.md`**。

| 编号 | 决策问题 | 定案 | 依据 |
|---|---|---|---|
| D1 | 检测粒度与视图？ | **重组视图·模块容器级（最大粒度）**；现实视图/功能视图不做。检测依据 = **真实代码聚合边**（`computeAggregatedModuleEdges`），不是用户画的线。 | 用户确认（2026-09-01）「不用管现实视图。这个循环检测只要去做模块那个层级就好了，也就是最大的那一级」；「对的，就是最大粒度」+ 确认「检测依据用真实代码聚合边」。弃选现实视图（文件级）/功能视图（原子级）——票面「现实视图的模块/原子粒度」措辞收窄 |
| D2 | 孤儿边界：一个模块容器只有指向第三方的边（只 import 第三方）、且无人依赖它——算孤儿吗？ | **不算，拆成三分类**：正常（与其它模块容器有 ≥1 条边）/ 孤儿（与其它模块容器**且**第三方都无边的真孤立）/ **仅连第三方**（无模块边、有第三方边 → 单独高亮 + 说明功能） | 用户确认（2026-09-01）「我认为这种需要单独高亮显示，然后说明功能」+ 「对，三分类」。弃选「算孤儿」（能 import 第三方说明它在做事，不该当死代码） |
| D3 | 检测出的环在重组画布怎么呈现？ | **只标节点 + Inspector**：环成员模块容器加标记，**不画环边**（尊重 #18 D1 零边）；点节点 → Inspector 展示环路径 + 每段边的代码证据。孤儿/仅连第三方同理（节点标记 + Inspector）。 | 用户确认（2026-09-01）「只标节点+Inspector（推荐）」。弃选「选中时临时显边」「直接画环边」——与 D1「默认零边、人画线探索」冲突 |
| D4 | 用户画下构成环的那条边时，是否当场提示「构成了循环依赖」？ | **不做画线时提示**：#21 只做检测 + 标记；#18 画线交互保持原样（只校验边真实）。 | 用户确认（2026-09-01）「不做画线时提示（推荐）」。弃选「画线构成环时提示」——范围收窄、不碰 #18 的 `isValidConnection`/反馈通道 |
| D5 | 除了节点标记 + Inspector，要不要加汇总总览？ | **轻量汇总计数**：工具栏「N 个环 · M 个孤立 · K 个仅连第三方」，可点开列表定位节点。 | 用户确认（2026-09-01）「轻量汇总计数（推荐）」。弃选「无汇总」（要看全部得逐个点）/「完整诊断面板」（UI 重、信息过载） |

**本票不替用户拍板的遗留**：功能视图/现实视图设计是否重设计（2026-09-01 用户反馈，拟独立会话，已记 map.md Notes）；环路径展示的精确形式（§9 Q1）；模块内部环是否提示（§9 Q2）。

## §4 范围收敛与明确不做

| 项 | 决策 | 依据 |
|---|---|---|
| 检测 = 模块容器级（重组视图）环 / 孤儿 / 仅连第三方 | 做 | D1/D2 |
| 呈现 = 节点标记 + Inspector 详情 + 工具栏轻量计数 | 做 | D3/D5 |
| 检测依据 = 真实聚合边（活更新） | 做 | D1 + 裁决2 |
| 环证据 = 复用聚合边 `rawEdges`（代码事实，非 AI 编造） | 做 | V2/V5 + #18 D6 精神 |
| 检测纯函数单测 + 真实 fixture 验证已知环 | 做 | §8 |
| 后端改动 / 新端点 | **不做** | V10 |
| 现实视图 / 功能视图的标记 | **不做** | D1 |
| 画线构成环时当场提示 | **不做** | D4 |
| 自动改图 / 一键修复 / 写回代码库 / 跨仓库检测 | **不做** | issue #21 body「不做」+ 本设计不引入 `supportedFixes` |
| 模块内部（成员原子之间）的环 | **不做**（聚合边已丢弃，天然不可见） | V2 + 裁决4 |
| 完整诊断面板（环路径/证据全列） | **不做**（只做轻量计数） | D5 |
| 改变 `RecomposedDesign` 持久化格式 / 后端 schema | **不做** | 检测只读 `design` + `graph`，不改写 |

## §5 实现方案

### 5.1 新检测模块 `frontend/src/lib/recompose/detect.ts`（纯函数，核心）

**契约**：`detectModuleFindings(aggregated, design) → ModuleFindings`

- 输入 `aggregated` = `computeAggregatedModuleEdges` 产物（`FlowEdge<AggregatedEdgeData>[]`，V1）；`design` = `RecomposedDesign`。
- 建模块图：
  - 节点 = `design.modules`（`mod:*` / `atom:*`）。
  - 边 = `aggregated` 中 `source`、`target` 都 ∈ 模块集合 → 模块边；`target === THIRD_PARTY_NODE_ID` → 第三方出边。第三方节点**不参与环检测**（无出边，不可能成环，V3 + 裁决3）。
- **环**：对模块边跑 Tarjan SCC（有向图，O(V+E)）。每个非平凡 SCC（成员 ≥2）= 一个环 finding。v1 不展示「环路径」：Inspector 只展示 SCC 成员集合 + 成员之间所有聚合边的 `rawEdges` 证据（§5.4）。
- **孤儿三分类**（每模块，D2）：
  - 有 ≥1 条模块边（出或入）→ 正常（无 finding）。
  - 无模块边、有 ≥1 条第三方边 → `orphan/third-party-only`（单独高亮 + 说明功能）。
  - 无模块边、无第三方边 → `orphan/isolated`（真孤立）。
- **空输入**（S3）：`design.modules` 为空或 `aggregated` 为空时，返回 `{ cycles: [], orphans: [], thirdPartyOnly: [], count: { cycles: 0, orphan: 0, thirdPartyOnly: 0 }, byModule: new Map() }`。

**产出形状（receipt 风格，对齐 #18 §5.5 的 `EdgeCheckReceipt`；图级 finding ≠ 边级 receipt，见 §9 Q5）**：

```typescript
interface ModuleFinding {
  code: 'cycle/scc' | 'orphan/isolated' | 'orphan/third-party-only';
  severity: 'error' | 'warning';          // cycle=error；两种孤儿=warning；UI 按 severity 决定描边实/虚（I5）
  subject: { moduleIds: string[] };       // cycle ≥2；orphan =1
  evidence?: {
    cycleEdges?: AggregatedEdgeData[];      // cycle：SCC 成员之间的聚合边（rawEdges = 代码证据）
    thirdPartyEdges?: AggregatedEdgeData[]; // third-party-only：指向第三方的聚合边
  };
  message: string;                         // 人类可读摘要（中文）
}

interface ModuleFindings {
  cycles: ModuleFinding[];                 // code: 'cycle/scc'
  orphans: ModuleFinding[];                // code: 'orphan/isolated'
  thirdPartyOnly: ModuleFinding[];         // code: 'orphan/third-party-only'
  count: { cycles: number; orphan: number; thirdPartyOnly: number };
  byModule: Map<string, ModuleFinding | null>; // 节点 badge 查表；null = 正常；key 只含模块容器 id，不含第三方节点（S1）
}
```

- 设计约束：纯函数、无 React/React Flow 依赖，直接可单测；不写回 `design`（只读，不改持久化格式，§4）。

### 5.2 `RecomposeCanvas.tsx` 接线

- `const findings = useMemo(() => detectModuleFindings(aggregated, design), [aggregated, design])` —— **活更新，v1 不去抖**（I4）：拖原子、增删模块、改名/改描述时，聚合边变化 → 检测即时重算。模块图规模小（当前 fixture 7 原子 / 真实库 50+ 模块），Tarjan O(V+E) 远低于一帧；去抖反而让探索反馈滞后。
- 传给 `deriveNodes`（新参数）把每模块 `findings.byModule.get(module.id)` 注入节点 data（§5.3）。
- 传给 `RecomposeToolbar` 新 prop `diagnostics={findings}`（含 `count` + 三个列表），支持计数展示与可点列表定位（I1）。
- 传给 Inspector：选中模块时按 finding 渲染详情（§5.4）。

### 5.3 `derive.ts` + `RecomposeModuleNode.tsx` 标记渲染

- `RecomposeModuleData` 增加 **`moduleDiagnostic`: `'cycle' | 'orphan' | 'third-party-only' | null`**（I7）。避免与 `api/types.ts` 的 `Diagnostic`（parser 诊断）混淆；字段名在类型、组件、测试中保持一致。
- **`RecomposeModuleNode.tsx` 外框实现**（I2）：把当前常量 `containerStyle`（`:98-110`）改为函数 `containerStyle(moduleDiagnostic)`，在 `RecomposeModuleNode` 组件中读取 `data.moduleDiagnostic` 传入；边框样式按诊断类型切换：
  - `cycle` → 2px solid `var(--warn, #f87171)`（实线红，`severity='error'`）
  - `orphan` → 2px dashed `var(--text-2, #94a3b8)`（虚线灰，`severity='warning'`）
  - `third-party-only` → 2px dashed `var(--mid, #fbbf24)`（虚线琥珀，`severity='warning'`）
  - `null` → 现状（2px solid `var(--border, #475569)`）
- **Badge 位置**（I2）：放在 `ModuleNodeBody` header 第一行「模块」标签左侧（或删除按钮左侧，优先前者以不挤压操作区）。badge 文案：「在环里」「孤立」「仅连第三方」。字体 9px，圆角 4px，背景色与边框色同系、深色底。
- **颜色对齐现有交通灯语义**（`depthScore.ts:41-49`），不新造色系；`severity` 直接映射为描边实/虚（I5）。

#### `RecomposeToolbar.tsx` 可点列表交互（I1）

工具栏接收 `diagnostics: ModuleFindings` prop，展示为：

```
[在环里 N] [孤立 M] [仅连第三方 K]
```

- 每个计数是一块可点击/可 hover 的 pill；点击后下方展开一个 `<ul>`（绝对定位下拉，不挤占画布），每项显示 `[标签] 模块中文名`，例如「[在环里] 训练日志」。
- 点击列表项 → 调用 `onSelect(moduleId)`：选中该模块（与点击节点等效）并 `rf.fitView({ nodes: [moduleId], duration: 300 })` 居中定位。
- 列表收起：再次点击同一 pill、点击画布空白处、或按 Escape。
- 计数为 0 的 pill 不可点击、不展开列表。

### 5.4 `Inspector.tsx` 三类 finding 展示

选中模块时，`RecomposedModuleSelection` 带上 `finding?: ModuleFinding`。在现有模块详情（名称、描述、成员原子、端口）**之后**追加 finding 区域（I3）。

#### 环（`cycle/scc`）渲染草图

```
─────────────────────────────
⚠ 循环依赖
以下模块互相构成循环：
• 训练日志
• 聚合编排
• AI 能力接入

证据（成员之间的依赖边）：
训练日志 → 聚合编排
  import → orchestrate @ 12
  import → dispatch @ 15
聚合编排 → AI 能力接入
  import → complete @ 8
AI 能力接入 → 训练日志
  import → log @ 22
```

- 顶部标题「⚠ 循环依赖」，正文列出 SCC 成员模块中文名（从 `data.name` / `memberNames` 取）。
- 不展示「闭合路径 A→B→C→A」；v1 只展示「成员集合 + 成员之间所有聚合边证据」。
- 证据区按 `cycleEdges` 顺序迭代；每条聚合边显示 `source 模块名 → target 模块名`，下面缩进列出该边 `rawEdges` 的 `kind → targetPort @ line`（复用 `:283-294` 渲染，V8）。
- 若某段 `rawEdges` 为空（理论上不应发生，防御性处理），显示「无底层调用点」。

#### 孤儿（`orphan/isolated`）渲染草图

```
─────────────────────────────
⚠ 孤立模块
该模块与其它模块及外部库都没有任何依赖边（无入无出），可能是：
• 死代码 / 未使用工具
• 尚未接入主流程的新模块
• 需要人工确认是否保留
```

- 说明文字 + 建议方向（纯文案，不自动删）。
- 下方保留常规模块详情（成员原子、端口）供用户判断。

#### 仅连第三方（`orphan/third-party-only`）渲染草图

```
─────────────────────────────
⚠ 仅连接外部库
该模块只依赖外部库、不被任何其它模块使用。

功能说明：
训练日志组件：记录实验与运行的结构化日志。

成员原子：
• 训练日志

公开端口：
• log(event: TrainingEvent)
```

- 说明文字。
- **功能说明 fallback**（S4）：优先显示 `description`；若为空，显示「该模块未填写接口描述」。
- 下方列出成员原子名 + 端口签名（复用现有字段，不新写 AI）。

### 5.5 不新增后端；与 #18 的关系

- 检测全部基于前端已有的 `graph.edges` + `design`（V10），无新端点。
- 与 #18 解耦：本票不碰 `isValidConnection`/`checkDependency`/`finalEdges`（D4）。`detect.ts` 是只读的新纯函数层。
- 不引入 `supportedFixes`（#21 明确不提供一键修复，§4）；finding 的 `message` 只描述事实与人工方向，不触发任何自动行为。

## §6 关键设计裁决

**【裁决1】检测层级 = 模块容器图（真实聚合边），而非文件/原子图**
- 问题：票面写「现实视图的模块/原子粒度」，到底在哪层建图检测？
- 定案【决策】：**重组视图的模块容器级**，节点 = `design.modules`，边 = `computeAggregatedModuleEdges`（D1）。默认设计（模块 = 原子）时即原子级；用户分组后自动收窄。
- 备选：文件级（现实视图）——Python import 环常见、噪音大，且与北极星（读者不懂代码）不符；原子级单独一套——与模块级是同一算法在不同粒度，先做模块级（用户已定 D1），原子级可后续扩展。

**【裁决2】检测时机 = 活更新（useMemo），不做手动按钮**
- 问题：什么时候重算检测？
- 定案【决策】：`useMemo` 依赖 `[aggregated, design]`，设计一变即重算。画布是探索工具，拖原子后标记应即时反映分组变化。
- 备选：手动「检测」按钮——多一个交互、结果滞后，与画布定位不符。

**【裁决3】环算法 = Tarjan SCC，非 DFS 枚举全部简单环**
- 问题：环怎么找？
- 定案【决策】：**Tarjan 强连通分量**（O(V+E)），每个非平凡 SCC（≥2 成员）即一个环 finding。SCC 是标准做法（dependency-cruiser / import-linter 同思路）；成员集合确定、证据可追溯。
- 备选：枚举全部简单环——#P 级爆炸（指数级环数），大库不可行；不选。
- 代价：SCC 只给「环组」，不给全部简单环路径。展示路径的取舍见 §9 Q1。

**【裁决4】模块内部环不可见**
- 问题：用户把互为环的两个原子装进同一模块容器，环会不会消失？
- 定案【决策】：会消失——聚合边丢弃同模块边（V2），模块 = 抽象边界，内部结构由模块封装。本票不检测模块内部环。
- 备选：检测模块内部环 → 违背「模块 = 实现 + 端口」的封装语义，且「最大粒度」检测的目标就是模块间结构；不选。评审确认见 §9 Q2。

**【裁决5】检测与 #18 画线解耦**
- 问题：#21 会不会改画线交互？
- 定案【决策】：不改（D4）。检测只读、只标；画线校验保持 #18 原样。
- 备选：画线构成环时当场提示——教育时刻但扩到 #18 交互面，v1 不做。

## §7 边界与不变量清单

| # | 不变量 | 防护层 | 依据 |
|---|---|---|---|
| 1 | 检测只作用于模块容器（重组视图），现实/功能视图不标 | `detect.ts` 只被 RecomposeCanvas 消费 | D1 |
| 2 | 检测依据 = 真实聚合边（代码事实），与用户画的线无关 | `detectModuleFindings(aggregated, design)` 输入即聚合边 | D1 / V1 |
| 3 | 环 = 非平凡 SCC（≥2 模块）；每模块至多属一个环组 | Tarjan SCC 划分（不相交） | 裁决3 |
| 4 | 孤儿三分类互斥（正常 / 孤儿 / 仅连第三方） | 分类分支顺序判定 | D2 |
| 5 | 不画环边，只标节点 + Inspector（尊重 #18 D1 零边） | 渲染层不新增边；标记只进节点 data | D3 |
| 6 | 画线交互保持 #18 原样（只校验边真实） | 不改 `isValidConnection`/`finalEdges` | D4 / 裁决5 |
| 7 | 纯前端、无新端点；检测函数纯、可单测、不写回 design | 新 `detect.ts` 只读 | V10 / §4 |
| 8 | 第三方节点不参与环检测（无出边，不可能成环） | 建图时排除第三方出边入 SCC | V3 / 裁决3 |
| 9 | 模块内部环不可见（聚合边丢弃同模块边）；分组后环可能从视觉上「消失」，是本票已知缺口 | `computeAggregatedModuleEdges` 既有行为 | V2 / 裁决4 / Q2 |
| 10 | 自环不算孤儿（self-loop 不存在） | 聚合边丢弃同模块边 | V2 / issue #21 body |
| 11 | 「仅连第三方」的功能说明来自现有描述/端口，非 AI 现编；`description` 为空时显示 fallback | Inspector 复用 `description`/`memberAtomNames`/`ports` + 空描述 fallback | D2 / V8 / S4 |
| 12 | `byModule` 的 key 只含模块容器 id，第三方节点不在其中 | `detect.ts` 建图时第三方节点不加入模块集合 | V3 / S1 |
| 13 | 检测输出不写回 `RecomposedDesign`；不触发自动改图 | `detect.ts` 只读；渲染层只接收 findings 不反向写 design | §4 / S1 |

**交互三态推演**（设计-doc-for-review 纪律）：
1. **页面停留期间数据变化**：画布本地设计态，`graph`/`featureFlow` 以 props 传入（`RecomposeCanvas.tsx:96-117`），只随用户重扫更新。检测依赖 `aggregated`+`design`，随设计变化活更新 → 无显示与数据矛盾。
2. **挂载时序竞态**：无异步拉取，`graph` 渲染前已就绪 → 无「未看即读」类竞态。
3. **退出再进刷新**：localStorage 加载设计 → 检测基于当前 design + 当前 graph 重算；换库重扫后旧设计与新 graph 分组不符时，检测随设计/图变化自然更新（与 #18 的加载重校验同理）。

## §8 测试与验证计划

### 前端单测（Vitest，`frontend/src/__tests__/`）

**`recompose.detect.test.ts`**（新增，核心；合成图，确定性）：
- 环：单环 2 节点 / 3 节点、多环、共享节点（链式 SCC）、无环（纯 DAG）→ SCC 分组正确、`code='cycle/scc'`、`severity='error'`。
- 孤儿三分类：真孤立（无模块边无第三方边 → `orphan/isolated`）/ 仅连第三方（只连第三方 → `orphan/third-party-only`）/ 正常（有入 / 有出 / 双有 → 无 finding）。
- 自环不算孤儿（聚合边已丢同模块边；合成图里构造同模块边不产生 finding）。
- 证据：cycle 的 `cycleEdges[].rawEdges` 非空；third-party-only 的 `thirdPartyEdges` 非空。v1 不测 `path`。
- `byModule` 查表：环成员/孤儿/仅连第三方各命中，正常模块为 null。

**`recompose.issue21.fixture.test.ts`**（新增，真实 fixture，对拍 #18 四折门风格）：
- 用 `deep-module-mapper.graph.json` + 默认设计（模块 = 原子），断言检测出**已知环** `{training-logging, aggregation-orchestration, ai-provider-integration}`（V9 实测）。
- 断言环成员模块 `byModule` 命中、`moduleDiagnostic='cycle'`（I7）。
- 断言 `count.cycles ≥ 1`、`count.orphan === 0`、`count.thirdPartyOnly === 0`（fixture 无真孤立/仅连第三方原子，V9）。

**`RecomposeModuleNode.test.tsx`**（新增）：`ModuleNodeBody` 对 `moduleDiagnostic` 三分支渲染 badge/描边；`null` 保持现状（I2/I7）。

**`RecomposeToolbar.test.tsx`**（新增）：
- `diagnostics` 计数渲染「N 个环 · M 个孤立 · K 个仅连第三方」。
- 点击 pill 展开列表、列表项显示 `[标签] 模块中文名`、点击列表项调用 `onSelect(moduleId)`（I1/I8）。
- 计数为 0 的 pill 不可点击。

**`Inspector.test.tsx`**（新增用例）：模块选中带 finding → 三类详情渲染（环成员+每段边证据 / 孤儿说明 / 仅连第三方功能说明 + description fallback，I3/S4）。

**需更新的既有用例**（I6）：
- 所有调用 `deriveNodes` 的测试需传入新的 `findings: ModuleFindings` 参数；或实现时把该参数设为可选并给出默认值，并在 §5.2 说明。

**新增边界与活更新测试**（I8）：
- `recompose.detect.test.ts` 空输入：`design.modules=[]` 与 `aggregated=[]` 均返回空 findings（S3）。
- `RecomposeCanvas.test.tsx`（或等效集成测试）：拖拽原子改变模块分组后，`detectModuleFindings` 随 `design` 变化重新调用，badge 相应更新。
- `RecomposeModuleNode.test.tsx`：`moduleDiagnostic` 从 `null` 变为 `'cycle'` 时 badge 出现、描边变色。

**性能注记**（S2）：v1 不测性能。已知边界：当 `design.modules.length > 200` 时，每次 `useMemo` 跑 Tarjan 仍轻量，但若拖拽卡顿可考虑移入 Web Worker 或 16ms 节流；当前 fixture 与真实库远低于此阈值。

### 可复现命令

```bash
cd frontend && npm test            # 全量前端单测
cd frontend && npx tsc --noEmit    # 类型检查
cd frontend && npm run build       # 构建
# 手动体验（可选）：扫 deep-module-mapper 自身 → 重组视图默认设计下应见 3 个「在环里」模块
cd frontend && npm run dev
```

### 交付门

- 前端全量测试绿 + `tsc` 0 错误 + `build` 成功。
- 真实 fixture 手动验证：扫 deep-module-mapper → 重组视图（默认设计）→ training-logging / aggregation-orchestration / ai-provider-integration 三个模块显示「在环里」badge → 点开任一看到环成员及每段边证据 → 工具栏显示「1 个环 · 0 个孤立 · 0 个仅连第三方」。

## §9 待评审焦点（Q1-QN）

- **Q1（展示，已裁决）**：v1 **不展示环路径**；`ModuleFinding.evidence` 只保留 `cycleEdges`/`thirdPartyEdges`。Inspector 展示 SCC 成员集合 + 成员之间所有聚合边的 `rawEdges` 证据。环路径作为后续迭代候选。
- **Q2（边界，已裁决）**：模块内部环被聚合边隐藏（裁决4）——用户把互为环的原子装进同一模块时环从图上消失。符合「模块 = 抽象边界」的封装语义，是本票**已知缺口**；v1 不提示，在 §7 不变量 #9 中记录。
- **Q3（运行时，已裁决）**：检测活更新（裁决2），v1 **不去抖**。`useMemo` 依赖 `[aggregated, design]`，设计一变即重算；模块图规模小，即时反馈与画布探索定位一致。
- **Q4（一致性）**：默认设计（模块 = 原子）下模块级环 = 原子级环。用户 2026-09-01 已反馈功能视图/现实视图或需重设计（map.md Notes）——本票检测形态与将来功能视图重设计的关系，评审确认无冲突。
- **Q5（契约）**：`ModuleFinding` 与 #18 §5.5 `EdgeCheckReceipt` 是**平行结构**（图级 finding vs 边级 receipt），字段命名（`subject.moduleIds` vs `subject.sourceModuleId`）有意区分。评审确认字段/命名是否合理、是否要与 #18 统一前缀（如 `finding/cycle/scc`）。

## §10 评审意见采纳记录

> 评审完成后回填：评审项 → 结论 → 采纳落地。

| 评审项 | 结论 | 采纳落地 |
|---|---|---|
| B1 `evidence.path` 算法未裁决 | 阻塞 → 用户选 B（v1 不展示路径） | §5.1 移除 `path`；§5.4/§8 同步改为「成员集合 + 边证据」；§9 Q1 标记已裁决 |
| B2 范围收窄决策未落档 | 阻塞 → 采纳 | `wayfinder/grilling-decisions/issue-21-cycle-orphan-detection-decisions.md`（D1-D5 + B1 + 评审采纳记录） |
| I1 Toolbar 可点列表交互未明确 | 重要 → 采纳 | §5.3 新增「`RecomposeToolbar.tsx` 可点列表交互」小节；§8 新增 Toolbar 定位测试 |
| I2 节点边框色/badge 落点未明确 | 重要 → 采纳 | §5.3 明确 `containerStyle(moduleDiagnostic)` 函数化方案、badge 位置、颜色与 severity 映射；§8 测试同步改 `moduleDiagnostic` |
| I3 Inspector 环证据渲染结构未明确 | 重要 → 采纳 | §5.4 给出三类 finding 渲染草图（含环成员 + 每段边证据迭代方式） |
| I4 活更新去抖策略未裁决 | 重要 → 采纳 | §5.2 明确「v1 不去抖」；§9 Q3 标记已裁决 |
| I5 `severity` 字段无人消费 | 重要 → 采纳 | §5.1 注释说明 severity 映射描边实/虚；§5.3 明确 error=实线红、warning=虚线灰/琥珀 |
| I6 `deriveNodes` 签名变更对既有测试影响 | 重要 → 采纳 | §8 新增「需更新的既有用例」小节 |
| I7 `diagnostic` 与 parser `Diagnostic` 同名冲突 | 重要 → 采纳 | 字段/类型统一改为 `moduleDiagnostic`，避免混淆；§5.3/§8 同步 |
| I8 测试覆盖缺口 | 重要 → 采纳 | §8 新增 Toolbar 定位、RecomposeCanvas 活更新、空输入边界、badge 更新测试 |
| S1 补不变量 | 建议 → 采纳 | §7 新增不变量 #12（byModule 不含第三方节点）、#13（检测输出不写回 design） |
| S2 性能注记 | 建议 → 采纳 | §8 新增性能注记（200 模块阈值 / Web Worker 候选） |
| S3 空输入返回值 | 建议 → 采纳 | §5.1 新增空输入返回值说明；§8 新增空输入边界测试 |
| S4 description fallback | 建议 → 采纳 | §5.4 仅连第三方渲染草图新增 fallback 文案；§8 Inspector 测试覆盖 |

评审状态：经本轮修订后，设计文档已满足「有条件通过」的全部通过条件（B1/B2/I1-I8/S1-S4），可作为 issue #21 执行基线。
