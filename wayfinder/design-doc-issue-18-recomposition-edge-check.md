# 设计文档：重组画布"画线即校验"（Recomposition Edge Check）

> 文档用途：交付专业评审 agent 的评审对象。范围 = 背景 / 真值核对 / 决策记录 / 实现方案 / 不变量 / 验证。
> 溯源约定：**事实**标来源（代码 `file:line` / 用户确认）；**判断性裁决**单独标注【决策】并给出理由与备选，不冒充事实。
> 数据时点：2026-08-29（真值核对执行日；纯前端改动，无服务器/DB 实查项）。
> 评审状态：待评审（对应 GitHub issue #18 — https://github.com/li-yongqvan/deep-module-mapper/issues/18）。

## §0 项目上下文（给零背景评审 agent）

- **这是什么**：Deep Module Mapper —— 本地 Web 应用，指向任意代码库后提取**模块（实现+端口）**与**依赖边**，可视化并支持在**重组画布**上把人理解的**功能原子**装进**模块容器**、设计依赖关系。四层架构：解析层（Python AST）→ 聚合层（AI 把文件聚成功能原子）→ 重组层（人设计模块分组与依赖）→ 视图层（React Flow 画布）。共同语言见 `deep-module-mapper/UBIQUITOUS_LANGUAGE.md`。
- **技术栈**：前端 Vite 8 + React 19 + TypeScript + `@xyflow/react` 12（`frontend/`）；后端 Starlette + Uvicorn，仅 `scan/status/graph` 三端点（`backend/`）。本票**纯前端**，后端零改动。
- **与本次相关的关键组件**（均可自行查阅）：
  - `frontend/src/components/RecomposeCanvas.tsx` — 重组画布主组件（节点/边渲染、连接事件、反馈 toast）
  - `frontend/src/lib/recompose/edges.ts` — 模块级依赖边语义（聚合边 / 手动边 / 连接与删除事件路由）
  - `frontend/src/lib/recompose/types.ts` — `RecomposedDesign` 数据形状（含持久化格式）
  - `frontend/src/lib/recompose/persistence.ts` — localStorage 保存/加载/sanitize
  - `frontend/src/lib/aggregateEdges.ts` — 共享边聚合 helper（保留每条原始边证据）
  - `frontend/src/api/types.ts` — `Graph` / `Edge` 数据结构（边的端口与行号证据）
  - `frontend/src/components/Inspector.tsx` — 点击节点/边后的详情面板（已能渲染边的证据）
  - `frontend/src/manifest/feature-atoms.json` + `featureAtoms.ts` — 功能原子清单 + 文件→原子映射
- **关键架构纪律**：
  - **聚合层纯 AI**（#11）：文件→功能原子由 DeepSeek 判定，无人工逐文件纠错；人只价值集中在重组层。
  - **北极星（#8）**：读者是不懂代码的人；节点按功能聚合；接口少 → 依赖简单。重组画布 = 人探索/学习的工具，不是出答案的工具。
  - **先理解原理再实操**：本票改动有明确交互语义（"画线即校验"），评审应聚焦语义一致性与运行时行为。
- **前序工作**：#10 重组层（PR #14，已合并）建立了模块容器 + 原子拖拽 + 边增删 + localStorage 持久化；#11 AI 聚合（PR #15/#16，已合并）把功能原子清单改为 DeepSeek 生成。
- **角色与权限**：本票由**执行 Agent（Worker）**实现；统筹方负责地图、本设计文档、handoff、红线。执行方不更新地图、不建/关 issue、不分配后续票。
- **术语速查**：**功能原子** = 功能视图里最小节点（一组文件实现一个能力）；**模块容器** = 重组画布上装 1+ 原子的框（单原子自动成隐式模块）；**依赖边** = 一个有方向的依赖（`source→target`）；**L1/L2/L3** = 画布校验的错误分层（L1 硬规则 / L2 违背代码事实 / L3 设计质量软提示）。

## §1 背景与目标

- **需求来源**：用户 2026-08-29 提出重组画布的功能设想（原话要点）：
  > "他那里所显示的模块是和功能层是一样的但是他们之间没有线去连接……人类就可以自己去画线……如果这两个模块确有依赖关系那你就给出解释如果没有你就直接返回一个无任何依赖关系……其实更倾向于是一个前端……让人探索一下和学习一下到底这样子行不行为什么这样子不行"
- **现状矛盾**：`#10` 的重组画布**默认把聚合出来的依赖边全部渲染出来**（`RecomposeCanvas.tsx:146-157`），人只能在现成线上微调。这与用户"默认零边、人画线、画完当场校验+解释"的设想方向相反。
- **目标（一句话）**：把重组画布改成"**默认零边 → 人画线 → 当场校验真依赖（方向+存在性）→ 有则画上并给代码证据解释，无则拒绝并说明**"的探索/学习工具。纯前端，不新增后端。
- **交接依据**：本设计文档即为评审对象；实现前用户已确认方向（见 §3 决策记录）。

## §2 真值核对（数据来源，全部可复现）

> 纯前端改动，无服务器/DB 真值。以下均为本地仓库实查，命令 = Read/Grep `frontend/src`。

### 2.1 代码真值

**V1｜画布现状：默认渲染全部聚合边**
- 命令：Read `frontend/src/components/RecomposeCanvas.tsx`
- 结果摘录：
  - `:146-149` `const aggregated = useMemo(() => computeAggregatedModuleEdges(graph, design), ...)`
  - `:154-157` `const derivedEdges = useMemo(() => finalEdges(aggregated, design), ...)` → `setEdges(derivedEdges)`
- 结论：✅ 属实 —— 画布把聚合边 + 手动边一并渲染，默认**有**线。

**V2｜画布现状：不存在的依赖也可以画上**
- 命令：Read `frontend/src/lib/recompose/edges.ts`
- 结果摘录：
  - `:114-142` `onConnectEdge` —— pair 不在聚合边集合时 `addedEdges.push({source,target})`（`manual-edge` 边，`finalEdges` 会渲染）
  - `RecomposeCanvas.tsx:222-224` `isValidConnection` 只挡 `c.source === c.target` 和 `c.source === THIRD_PARTY_NODE_ID`
- 结论：✅ 属实 —— 今天人可画一条代码里不存在的依赖，无任何校验。

**V3｜手动边无证据，Inspector 跳过其 rawEdges**
- 命令：Read `edges.ts:84-108` + `frontend/src/components/Inspector.tsx:277-290`
- 结果摘录：
  - `edges.ts:95-105` manual 边 `data: { manual: true, kinds: [], rawEdges: [], displayLabel: '手动' }`
  - `Inspector.tsx:277-283` `manual ? "手动添加的依赖（无底层调用点）" : "调用点（N 条边）"`
- 结论：✅ 属实 —— 手动边在 Inspector 里不显示任何代码证据。

**V4｜Inspector 已能渲染真实证据（kind → targetPort @ line）**
- 命令：Read `Inspector.tsx:285-290`
- 结果摘录：`e.kind {e.targetPort ? \` → ${e.targetPort}\` : ''} @ <line>`
- 结论：✅ 属实 —— 只要边带真实 `rawEdges`，Inspector 自动展示"from_import → scan_codebase @ 42"式证据，无需新 UI。

**V5｜原始边带端口与行号（解释素材齐备）**
- 命令：Read `frontend/src/api/types.ts:31-44`
- 结果摘录：`Edge { source; target; targetPort?: string|null; kind: 'import'|'from_import'|'call'|'inheritance'|'annotation'|'decorator'; sites: { line: number }[] }`
- 结论：✅ 属实 —— 每条文件级边有端口名与行号，可支撑"代码证据"解释。

**V6｜聚合边保留全部底层原始边**
- 命令：Read `frontend/src/lib/aggregateEdges.ts:26-57`
- 结果摘录：`data: { kinds, rawEdges: edges, ...extraData }`
- 结论：✅ 属实 —— `computeAggregatedModuleEdges` 产出的模块级边，`data.rawEdges` 里是全部底层文件级边（含 V5 的端口/行号）。

**V7｜聚合边的解析粒度 = 文件→原子→模块**
- 命令：Read `edges.ts:49-76`
- 结果摘录：`resolveEndpoint` 先查 `externalIds` → 再 `atomForFile(fileId)` → 再 `atomToModule`；同模块内边丢弃（`s !== t`）。
- 结论：✅ 属实 —— 模块级聚合边即为"容器↔容器是否有真依赖"的判据，且方向敏感（`module-edge-<s>-><t>`）。

**V8｜持久化按库路径分 key，且有 sanitizeDesign 落点**
- 命令：Read `frontend/src/lib/recompose/persistence.ts`
- 结果摘录：`:98` `window.localStorage.setItem(storageKey(path), ...)`；`:120` `export function sanitizeDesign(...)`；`:104` `loadDesign(path)`
- 结论：✅ 属实 —— 不同库路径不串扰；加载时重校验可落在 `sanitizeDesign`。

**V9｜RecomposedDesign 形状**
- 命令：Read `frontend/src/lib/recompose/types.ts:38-47`
- 结果摘录：`RecomposedDesign { version: 1; modules; addedEdges: ModuleEdgeRef[]; hiddenEdges: ModuleEdgeRef[]; thirdPartyPosition? }`；`RecomposedModule` 含 `atomIds`（`:12-29`）
- 结论：✅ 属实 —— `addedEdges`（人画的边）/ `hiddenEdges`（隐藏的聚合边）是两个独立字段。

**V10｜功能原子映射**
- 命令：Read `frontend/src/manifest/featureAtoms.ts:36-38` + `feature-atoms.json`
- 结果摘录：`atomForFile(file): FeatureAtom | undefined`；manifest 现含 7 个原子（每个带 `files` 数组）
- 结论：✅ 属实 —— 文件→原子映射存在，聚合校验可复用。

**V11｜反馈 toast 机制**
- 命令：Read `RecomposeCanvas.tsx:171-177`
- 结果摘录：`showFeedback(msg)` → `setFeedback(msg)`，`setTimeout(() => setFeedback(''), 1800)`
- 结论：✅ 属实 —— 已有短暂反馈通道（1.8s），可复用于拒绝提示。

### 2.2 未复核项

- 无服务器/DB 项。所有设计所依赖的代码事实均已核（V1-V11）。实现时若发现与本设计不符，以代码为准并回报。

## §3 Grilling 决策记录

> 以下决策均为用户 2026-08-29 确认（本轮讨论当场合），决策原文（问题+选项+定案）随附，后续会话可复核。

| 编号 | 决策问题 | 定案 | 依据 |
|---|---|---|---|
| D1 | 重组画布初始是否渲染自动聚合的依赖边？ | **默认零边**：画布初始只有节点（功能原子，与功能视图一致），一条线都没有 | 用户确认(2026-08-29)原话"他们之间没有线去连接……人类就可以自己去画线"；弃选"渲染"（与探索/学习定位相反） |
| D2 | 人画的线连接粒度？功能原子还是模块容器？ | **模块容器**（单原子模块=隐式容器）；校验聚合"容器 A 任一原子 ↔ 容器 B 任一原子" | 用户确认(2026-08-29)"还是按你理解来"采纳统筹方推荐 B；#10 容器是已建核心功能不撤；B 已涵盖单原子场景 |
| D3 | 真依赖（方向正确）时怎么处理？ | **画上线并给解释**（代码证据：哪些文件 import 什么、调用什么端口、行号） | 用户确认(2026-08-29)原话"如果这两个模块确有依赖关系那你就给出解释" |
| D4 | 人画了不存在的依赖怎么处理？ | **拒绝画上**，返回"这两个模块之间无任何依赖关系"+ 为什么（B 的文件里没有任何 import 指向 A） | 用户确认(2026-08-29)原话"如果没有你就直接返回一个无任何依赖关系"，并早前 L2 决策选"报错"；弃选"允许画但标红"（与报错语义冲突） |
| D5 | 真实依赖方向相反（画 A→B 但代码是 B→A）？ | **拒绝并单独提示**"实际是 B 依赖 A，方向反了" | 用户确认(2026-08-29)：统筹方提出"方向也要查"用户未反对并整体采纳；方向是"为什么这样不行"最有教育意义的一课 |
| D6 | 解释文案来源？ | **parser 已提取的代码事实**（import/端口/行号），不用 AI 现编 | 用户确认(2026-08-29)"解释来源是代码事实，不需要 AI 现编"；证据链见 §2.1 V5/V6 |
| D7 | 既有 L1/L3 校验保留？ | **保留**：自环、third-party 作源继续拒绝；设计质量软提示保留 | 用户确认(2026-08-29)；现状 `isValidConnection`（§2.1 V2）不推翻 |
| D8 | 后端要不要动？ | **纯前端**，无新端点 | 用户确认(2026-08-29)"其实更倾向于是一个前端"；校验数据前端已齐（§2.1 V6/V7/V10） |
| D9 | "显示真实依赖"开关是否做进 v1？ | **不做进 v1**（保留为后续候选） | 用户确认(2026-08-30)"先不做" |
| D10 | third-party 作为 **target** 的边（模块依赖第三方包）是否放行？ | **放行**：聚合边里真实存在即算真实依赖；source 为 third-party 仍拒绝（L1） | 用户确认(2026-08-30)"Q4我认可"；依据 §2.1 V7（third-party target 解析到 `THIRD_PARTY_NODE_ID`） |

**开放待定（不阻塞本票主干）**：已收窄——开关（Q3）、third-party target（Q4）均已定（D9/D10）。剩余评审焦点见 §9 Q1（一次性反馈）/ Q2（丢弃提示）/ Q5（两视图差异）。

## §4 范围收敛与明确不做

| 项 | 决策 | 依据 |
|---|---|---|
| 重组画布默认零边 | 做 | D1 |
| 画线即校验（方向+存在性）+ 拒绝反馈 | 做 | D3/D4/D5 |
| 画上的边带真实 rawEdges 证据（Inspector 展示） | 做 | D3 + V4/V6 |
| 加载时对 saved design 重校验 | 做 | 裁决3（§6） |
| 单测更新/新增（edges/persistence/Inspector） | 做 | §8 |
| 后端改动 / 新端点 | **不做** | D8 |
| AI 生成解释文案 | **不做** | D6 |
| 功能视图的边（功能视图仍显示聚合边） | **不做** | 本票只改重组画布 |
| 循环依赖/孤儿检测、画布评审端点、Trace path | **不做**（独立票） | map.md Open frontier |
| "显示真实依赖"开关 | **不做**（后续候选） | D9 |
| 改变 `RecomposedDesign` 持久化格式版本 | **不做**（version 保持 1） | 裁决4（§6） |

## §5 实现方案

### 5.1 `frontend/src/lib/recompose/edges.ts`（核心逻辑）

**改动 a｜新增校验函数 `checkDependency`**
- 契约：`checkDependency(aggregated, source, target) → { status: 'real' | 'reversed' | 'none', evidence?: FlowEdge<AggregatedEdgeData> }`
- 逻辑：`aggregated` 按 key `source->target` 建 Map（复用现有 `edgeKey`，`edges.ts:19-28`）。
  - `(source,target)` 命中 → `real`，`evidence` = 该聚合边（其 `data.rawEdges` 即解释证据，§2.1 V6）
  - `(target,source)` 命中且正向未命中 → `reversed`
  - 均未命中 → `none`
- 依据：§2.1 V6/V7；D5（方向敏感）。

**改动 b｜`finalEdges` 默认只渲染人画的边，且每条带真实证据**
- 现状（§2.1 V3）：渲染"可见聚合边 + 手动边"，手动边 `rawEdges: []`。
- 改后：
  - 默认不渲染聚合边（D1）；若"显示真实依赖"开关在 v1 内实现，走开关。
  - 对每条 `addedEdges`（已通过校验才落盘），用 `checkDependency` 取对应聚合边证据，渲染 data 改为 `{ manual: false, kinds, rawEdges: <真实证据>, displayLabel: '真实依赖' }`。
  - `manual: false` 让 Inspector 走证据分支（§2.1 V4）。
- 依据：D1/D3；§2.1 V3/V4。

**改动 c｜`onConnectEdge` 简化**
- 现状（§2.1 V2）：pair 在聚合边 → unhide/no-op；否则 push `addedEdges`。
- 改后：校验已在 `isValidConnection` 拦截（§5.2），`onConnectEdge` 只负责去重 push `addedEdges`（不再需要 `aggregateKeys` 参数与 unhide 分支）。
- 依据：D4 + §6 裁决1。

**改动 d｜`onDeleteEdge` 只保留 manual 分支**
- 现状（`edges.ts:149-177`）：manual 删除 / auto 隐藏（写 `hiddenEdges`）。
- 改后：聚合边不再渲染，删除只作用于 `addedEdges`；`hiddenEdges` 不再写入（见 §5.4）。
- 依据：D1 + 裁决4。

### 5.2 `frontend/src/components/RecomposeCanvas.tsx`

**改动 a｜`isValidConnection` 升级为校验门**
- 保留 L1：`source === target`、`source === THIRD_PARTY_NODE_ID`（现状 `:222-224`）。
- third-party 作为 **target**：聚合边真实存在 → 放行（D10）；作为 source 保持拒绝（L1）。
- 新增：调用 `checkDependency`（§5.1a）。
  - `real` → 返回 `true`（放行，`onConnect` 落盘）。
  - `reversed` / `none` → 触发**一次性**反馈后返回 `false`：
    - `none` → "这两个模块之间无任何依赖关系（B 的文件里没有任何 import 指向 A）"
    - `reversed` → "实际是 B 依赖 A，方向反了"
- 反馈复用 `showFeedback`（§2.1 V11）；注意 `isValidConnection` 可能被 React Flow 多次调用，须防重复弹（见 §9 Q1）。
- 依据：D4/D5 + §6 裁决1。

**改动 b｜去掉默认聚合边渲染**
- 现状（§2.1 V1）：`derivedEdges = finalEdges(aggregated, design)` 全量渲染。
- 改后：默认只渲染"已校验的 addedEdges"（§5.1b）；`aggregated` 保留供校验与开关使用。
- 依据：D1。

**改动 c｜解释展示**
- 画上的边带真实 `rawEdges` → 点击边走现有 `handleEdgeClick`（`:299-311`）→ Inspector 自动渲染证据，无新 UI。
- 依据：D3 + §2.1 V4。

### 5.3 `frontend/src/components/Inspector.tsx`

- 已校验边 `manual: false` + 真实 `rawEdges` → 现有证据分支（`:283-290`）自动生效，**无需改渲染逻辑**。
- 保留 `manual === true` 防御分支（旧 saved design 若仍带 `manual` 标记的边），不删。
- 依据：§2.1 V4/V3。

### 5.4 `frontend/src/lib/recompose/persistence.ts`

- **加载时重校验**：`sanitizeDesign`（`:120`）里对 `addedEdges` 逐条 `checkDependency`，非真实边丢弃（加载即校验，与画线语义一致，裁决3）。
- `hiddenEdges` 废弃：不再写入；读入旧设计的 `hiddenEdges` 直接忽略。
- `version` 保持 1（向后兼容读旧设计）。
- 依据：D4 + 裁决3/裁决4；§2.1 V8/V9。

## §6 关键设计裁决

**【裁决1】校验拦截点 = `isValidConnection`**
- 问题：React Flow 里"阻止画一条无效线"在哪层做？`isValidConnection`（返回 `false` 则不创建边、`onConnect` 不触发）还是 `onConnect`（只对有效连接触发）？
- 定案【决策】：**`isValidConnection`**。无效连接根本不该被创建；`onConnect` 语义是"已接受"，在它里面回滚会产生先画后删的闪烁。
- 备选：`onConnect` 里校验 → 无效边短暂出现再回滚，UI 抖动，且 `onConnect` 对无效连接根本不触发（`RecomposeCanvas.tsx:210-220`），逻辑落点错位；不选。

**【裁决2】画上边复用 Inspector 证据渲染，不新建解释面板**
- 问题：解释（代码证据）展示在哪？
- 定案【决策】：画上边带真实 `rawEdges`，Inspector 现有 evidence 渲染自动生效（§2.1 V4），标签"手动"→"真实依赖"。
- 备选：新做独立解释面板 → 与 Inspector 重复实现、双份维护；不选。

**【裁决3】旧 saved design 加载时重校验，非真实边直接丢弃**
- 问题：旧版设计（旧规则允许画不存在的依赖）加载后，`addedEdges` 里可能含非真实边。
- 定案【决策】：`sanitizeDesign` 时 `checkDependency` 过滤，非真实边丢弃——与"无依赖必须拒绝"的 D4 语义一致。
- 备选：保留并标红 → 与 D4 矛盾（不存在的依赖不该存在）；不选。
- 代价：用户旧设计里"故意画来探索的非真实边"会消失。见 §9 Q2。

**【裁决4】`hiddenEdges` 废弃、持久化 version 不升**
- 问题：默认零边后，`hiddenEdges`（隐藏聚合边）还有意义吗？
- 定案【决策】：废弃，不再写入；version 保持 1，向后兼容读旧设计（§2.1 V9）。
- 备选：升 version 2 + 迁移脚本 → 收益低、复杂度高；不选。

## §7 边界与不变量清单

| # | 不变量 | 防护层 | 依据 |
|---|---|---|---|
| 1 | 画布初始零边（不渲染聚合边） | `finalEdges` 默认只渲染 `addedEdges` | D1 / §5.1b |
| 2 | 画布上的每条边都是真实依赖且方向正确 | `isValidConnection` 校验门 + `checkDependency` 方向敏感 | D4/D5 / §5.2a |
| 3 | 不存在的依赖永不落盘 | 画线校验（写前）+ `sanitizeDesign` 加载重校验（读后） | D4 / 裁决3 / §5.4 |
| 4 | 自环 / third-party 作源 不可连 | `isValidConnection` L1 分支保留 | D7 / §2.1 V2 |
| 5 | 解释证据与代码事实一致 | 证据 = 聚合边的 `rawEdges`（parser 输出，非 AI 编造） | D6 / §2.1 V5/V6 |
| 6 | 旧 saved design 向后兼容可读 | `version:1` + `sanitizeDesign` 忽略 `hiddenEdges` | 裁决4 / §5.4 |
| 7 | 删除边只作用于人画的边 | `onDeleteEdge` 仅 manual 分支 | D1 / §5.1d |
| 8 | 不同库路径不串扰 | `storageKey(path)` 分 key | §2.1 V8 |
| 9 | 模块 → 第三方包 的真实依赖边可画 | `isValidConnection` 对 target=third-party 且真实 → 放行 | D10 / §5.2a |

**交互三态推演**（设计-doc-for-review 纪律）：
1. **页面停留期间数据变化**：画布是本地设计态，`graph`/`featureFlow` 以 props 传入（`RecomposeCanvas.tsx:120-122`），只随用户重扫更新；画布无轮询 → 无显示与数据矛盾。**已知缺口**：用户重扫换库后，旧 `addedEdges` 与新 graph 重校验（裁决3 已覆盖）。
2. **挂载时序竞态**：无异步拉取，`graph` 在渲染前已就绪 → 无"未看即读"类竞态。
3. **退出再进刷新**：localStorage 加载 → `sanitizeDesign` 重校验（裁决3），非真实边不复活。

## §8 测试与验证计划

### 前端单测（Vitest，`frontend/src/__tests__/`）

**`recompose.edges.test.ts`**（新增用例，核心）：
- `checkDependency`：`real`（正向命中）/ `reversed`（反向命中）/ `none`（均未命中）三分支；`real` 时 `evidence.data.rawEdges` 非空且含端口/行号。
- `finalEdges`：默认不渲染聚合边；`addedEdges` 边渲染为 `manual:false` 且 `rawEdges` 为真实证据；标签"真实依赖"。
- `onConnectEdge`：去重；同 key 重复画不产生重复边。
- `onDeleteEdge`：删除 `addedEdges` 边；不写 `hiddenEdges`。

**`recompose.persistence.test.ts`**（新增用例）：
- `sanitizeDesign`：丢弃非真实 `addedEdges`；保留真实边；旧设计含 `hiddenEdges` 可读且被忽略。

**`Inspector.test.tsx`**（新增用例）：
- 已校验边（`manual:false` + rawEdges）渲染"调用点（N 条边）"列表（`kind → targetPort @ line`）。

**需更新的既有用例**：`recompose.edges.test.ts` 中"默认渲染聚合边""手动边 `rawEdges:[]`"等断言需随行为变更改写。

### 可复现命令

```bash
cd frontend && npm test            # 全量前端单测
cd frontend && npx tsc --noEmit    # 类型检查
cd frontend && npm run build       # 构建
# 手动体验（可选）：前端 5175 + 后端 8123，扫 deep-module-mapper 自身
cd frontend && npm run dev
```

### 交付门

- 前端全量测试绿 + `tsc` 0 错误 + `build` 成功。
- 至少一个真实 fixture 的手动验证：扫一个库 → 重组画布零边 → 画一条真实边（有证据解释）→ 画一条不存在边（被拒+"无任何依赖关系"）→ 画反方向（被拒+"方向反了"）。

## §9 待评审焦点（Q1-QN）

- **Q1（运行时）**：`isValidConnection` 在拖拽/悬停期间可能被 React Flow 多次调用——拒绝反馈如何保证**只弹一次**而不是连弹？需定触发时机（如 connectionEnd 单次、或去抖）。这是本票最实际的运行时风险。
- **Q2（用户价值）**：旧 saved design 中"旧规则下画上的非真实边"加载即丢弃（裁决3）——用户若把某些非真实边当"探索草稿"会消失。直接丢弃是否符合预期？是否要提示一次"已移除 N 条无效边"？
- ~~Q3（范围）~~ **已定（2026-08-30 用户确认"先不做"）**："显示真实依赖"开关不做进 v1（D9）。
- ~~Q4（边界）~~ **已定（2026-08-30 用户确认"Q4我认可"）**：third-party 作为 target 的真实依赖边放行（D10），source 仍拒绝。
- **Q5（一致性）**：功能视图仍显示聚合边，重组画布默认零边——两个视图对同一代码库展示不同（一个有边一个无边）。这是 D1 的预期结果，但评审请确认不会让用户困惑。

## §10 评审意见采纳记录

> 评审完成后回填：评审项 → 结论 → 采纳落地。
