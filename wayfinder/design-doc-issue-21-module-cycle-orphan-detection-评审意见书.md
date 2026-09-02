# 设计文档：模块级循环依赖与孤儿模块检测（Cycle & Orphan Detection）评审意见书

> **评审对象**：《设计文档：模块级循环依赖与孤儿模块检测（Cycle & Orphan Detection）》（`wayfinder/design-doc-issue-21-module-cycle-orphan-detection.md`，§0–§9）
> **参考对照**：《设计文档：重组画布"画线即校验"》（`wayfinder/design-doc-issue-18-recomposition-edge-check.md`）
> **执行边界参考**：`wayfinder/handoff-issue-21-module-cycle-orphan-detection.md`
> **评审方式**：独立复核 —— 以当前仓库 `frontend/src` 为真值源，逐项核对文档引用；对 §5.1/§5.3/§5.4/§7/§8/§9 做对抗性盘问；实测跑通 §8 可复现命令并独立复现 V9 环断言。
> **评审结论**：**有条件通过**

---

## 一、总体结论

设计方向与用户 grilling 决策（D1–D5）、#18 零边纪律、北极星定位一致：**在重组视图基于真实聚合边做只读诊断，不改 #18 画线交互、不自动改图、不新增后端**。核心算法（Tarjan SCC + 孤儿三分类）选型合理，输入数据（`aggregated`）真实存在，`detect.ts` 作为纯函数层的拆分符合 deep-module 纪律。

但有三类问题必须在执行前钉死：

1. **两个阻塞项**：§5.1 接口已提前承诺 `evidence.path`，却把路径提取算法留成 §9 Q1 开放问题（执行方必须自发明）；issue #21 从票面「现实视图」到「重组视图」的范围收窄未在 `grilling-decisions/` 归档，canonical 可复现性不足。
2. **四个重要实现缺口**：节点边框色实际落点、Toolbar 可点击列表交互、Inspector 环证据渲染结构、活更新是否去抖 —— 文档均未给出足够裁决，执行方会各自发明。
3. **若干建议**：字段命名与既有 `Diagnostic` 冲突、`severity` 字段无人消费、测试计划未覆盖 Toolbar 定位/活更新/边界空输入等。

总体评价：骨架可信、证据基础扎实；阻塞项和重要项解决后，可作为执行基线。

---

## 二、事实与证据复核

复核范围：§2 真值核对 V1–V10、§3 决策依据、§5 实现方案中所有可代码验证的断言。

### 2.1 核实为真

| 文档主张 | 复核结果 |
|---|---|
| `RecomposeCanvas.tsx:150-153` 已算好 `aggregated` | ✅ 属实，`computeAggregatedModuleEdges(graph, design)` 在 `:150-153` |
| `edges.ts:128-144` `resolveEndpoint` 丢弃同模块边与噪音端点 | ✅ 属实，`:128-140` 过滤 `s !== t` 且丢弃 null |
| `edges.ts:129` 外部文件解析到 `THIRD_PARTY_NODE_ID` | ✅ 属实 |
| `derive.ts:176-194` 默认设计 = 隐式单原子模块 | ✅ 属实，`initialDesign` 创建 `atom:<atomId>` |
| `derive.ts:225-245` `RecomposeModuleData` 有 `[key: string]: unknown` 兜底 | ✅ 属实，`:61` 兜底存在 |
| `RecomposeModuleNode.tsx:113-157` `ModuleNodeBody` 渲染 header | ✅ 属实；但 `containerStyle` 在 `:98-110` 为常量，边框色需改父组件或传样式 |
| `RecomposeToolbar.tsx` 浮动在画布左上，按钮行 + feedback | ✅ 属实 |
| `Inspector.tsx:283-294` 已能渲染 rawEdges 证据 | ✅ 属实 |
| `api/types.ts:31-44` Edge 带 `kind/targetPort/sites[].line` | ✅ 属实 |
| 真实 fixture 存在已知 3 原子环 | ✅ **独立复现**：对 `deep-module-mapper.graph.json` + `feature-atoms.json` 跑 Tarjan，唯一非平凡 SCC = `{atom:aggregation-orchestration, atom:ai-provider-integration, atom:training-logging}`，与 V9 一致；0 孤立、0 仅连第三方 |
| 前端测试/类型检查/构建命令可跑通 | ✅ `npm test` 114 passed；`npx tsc --noEmit` 0 错误；`npm run build` 成功 |

### 2.2 不可复核 / 部分复核项

| 项 | 问题 |
|---|---|
| 用户 2026-09-01 grilling 原话 | 未在 `wayfinder/grilling-decisions/` 找到 issue-21 归档文件；§3 仅摘要，未附原话。见 B2 |
| issue #21 body「现实视图」原始措辞 | 无远端 GitHub 访问通道，按文档引用采信；但范围收窄的权限边界仍需落档 |

---

## 三、决策清单评审（D1–D5）

| 决策 | 结论 | 评审意见 |
|---|---|---|
| D1 检测粒度 = 重组视图·模块容器级（最大粒度），依据真实聚合边 | **认可（附条件）** | 与用户确认一致，输入数据真实存在，可执行。条件：须把范围收窄的决策落档到 `grilling-decisions/issue-21-cycle-orphan-decisions.md`（见 B2）。 |
| D2 孤儿三分类：正常 / 真孤立 / 仅连第三方 | **认可** | 分类互斥、无歧义。实现时统计每个模块在模块边中的 `source`/`target` 出现次数即可判定。 |
| D3 呈现 = 只标节点 + Inspector，不画环边 | **认可** | 与 #18 D1 零边纪律一致。 |
| D4 不做画线时提示，保持 #18 原样 | **认可** | 范围控制合理，不扩到 #18 交互面。 |
| D5 轻量汇总计数，工具栏显示 | **认可（附条件）** | 方向对。但「可点列表」交互未裁决（见 I1）。 |

---

## 四、开放点裁决（Q1–Q5）

### Q1 环路径提取 —— **必须裁决，阻塞**

§5.1 产出形状已承诺 `evidence.path?: string[]`，但 §9 Q1 才问「怎么提取」。执行方不能在没有算法裁决的情况下实现接口。建议二选一：

- **选项 A（推荐）**：在 §5.1 中明确算法 —— 对 SCC 子图跑一次 DFS 找一条简单环路径，取最先找到的一条；`cycleEdges` 与 `path` 顺序一一对应；Inspector 渲染时标注「环内模块互相可达，仅展示其中一条路径」。
- **选项 B**：v1 不展示 `path`，只展示 SCC 成员集合 + 成员间所有边证据；把 `path` 从 `ModuleFinding` 中移除，留到后续迭代。

**裁决**：任选 A 或 B 均可，但必须在 §5.1/§6 中形成明确决策，不能留到 §9。

### Q2 模块内部环不可见 —— **可接受，须写进不变量/已知缺口**

聚合边丢弃同模块边是既有行为（V2），模块 = 抽象边界，内部环被隐藏符合语义。但用户可能误以为「拖进同一模块 = 修好环」。

**裁决**：v1 接受。要求：在 §7 不变量 #9 基础上，于 §4「明确不做」或 §7 新增「已知缺口」写明「模块内部原子间环不被检测，分组后可能从视觉上消失」。

### Q3 活更新去抖 —— **重要，须裁决**

§5.2/裁决2 选择 `useMemo` 活更新，§9 Q3 问是否去抖。当前文档未裁决。

**裁决**：建议 v1 **不加去抖**，理由：模块图小、Tarjan O(V+E) 极快；badge 即时反馈与画布探索定位一致。但须在 §5.2 或 §9 明确写下「v1 不去抖」，避免执行方各自实现。

### Q4 与功能视图/现实视图重设计的关系 —— **可接受，保持现状**

这是跨票战略问题，不在本票范围。文档 §1 已说明不影响本票。

**裁决**：保留为 §9 已知风险，但不在本票解决。

### Q5 `ModuleFinding` 与 `EdgeCheckReceipt` 命名 —— **建议统一前缀，非阻塞**

两者是平行结构（图级 vs 边级），字段命名有意区分可接受。但 `code` 值 `cycle/scc`、`orphan/isolated`、`orphan/third-party-only` 与 `edge/real` 风格一致，无需改。唯一风险是 `subject.moduleIds` vs `subject.sourceModuleId` 差异较小，未来扩展时可能混淆。

**裁决**：保持当前命名；如后续要合并消费端，再统一。

---

## 五、新发现问题

### 5.1 阻塞项

| # | 级别 | 问题 | 要求 |
|---|---|---|---|
| B1 | **阻塞** | §5.1 `ModuleFinding.evidence.path` 已写入接口契约，但 §9 Q1 才把路径提取当开放问题。执行方必须自发明算法，违反 Pass 0「任何需要 agent 自己发明才能跑起来的地方都是 defect」。 | **二选一**：① 在 §5.1 增加路径提取算法（推荐：SCC 内 DFS 找一条简单环，`cycleEdges` 与 `path` 顺序对应）；② 把 `path` 从 v1 接口中移除，留待后续。无论选哪个，必须在 §5.1/§6 形成裁决，不能留在 §9。 |
| B2 | **阻塞** | issue #21 从票面「现实视图」收窄到「重组视图·模块容器级」的决策，仅在 §3 D1 有摘要，未在 `grilling-decisions/` 落档。`wayfinder/grilling-decisions/` 下无 issue-18/issue-21 文件，后续 agent / 第三方无法从 canonical 源复核。 | 新增 `wayfinder/grilling-decisions/issue-21-cycle-orphan-decisions.md`，记录 D1–D5 的问题、选项、定案、用户确认日期与原话摘要；或在设计文档 §3 每条决策后附用户原话引文+日期。 |

### 5.2 重要项

| # | 级别 | 问题 | 要求 |
|---|---|---|---|
| I1 | **重要** | §5.2 说 Toolbar 新增「可点列表（定位 = `onSelect` 到该模块）」，但 §5.3/§8 只说渲染计数。点击后弹出什么、列表项展示模块名还是 finding 类型、如何调用 `onSelect` / `rf.fitView` 均未裁决。 | 在 §5.3 中明确 Toolbar 交互：点击计数区展开一个 `<ul>`，每项显示「[在环里] 模块中文名」，点击后调用 `onSelect` 选中模块并 `rf.fitView({ nodes: [moduleId], duration: 300 })` 定位。单测覆盖至少一项点击。 |
| I2 | **重要** | §5.3 要求按 `diagnostic` 改节点「边框色」，但 `RecomposeModuleNode.tsx:98-110` 的 `containerStyle` 是常量，且 `ModuleNodeBody` 只拥有 header 区域、不拥有外框。执行方没有落点。 | 在 §5.3 明确实现方案：把 `containerStyle` 改为函数 `containerStyle(diagnostic)`，在 `RecomposeModuleNode` 组件中按 `data.diagnostic` 传入；或把边框样式从 `containerStyle` 下放到 `ModuleNodeBody` 的最外层 `div`。同时指定 badge 在 header 中的具体位置（建议放在删除按钮左侧或深度分左侧）。 |
| I3 | **重要** | §5.4 说 Inspector 展示「环路径 + 每段边证据」，但未给出 UI 结构。聚合边 `rawEdges` 的 source/target 是文件路径，如何映射到模块名？路径 `A→B→C→A` 用模块 ID 还是中文名展示？ | 在 §5.4 给出 Inspector 渲染草图：顶部显示「循环依赖：A → B → C → A」（用模块中文名），下面按 `cycleEdges` 顺序列出每段的 `kind → targetPort @ line` 证据。明确当 `path` 与 `cycleEdges` 顺序一一对应时如何迭代。 |
| I4 | **重要** | §5.2/裁决2 选择活更新，§9 Q3 问去抖但未裁决。直接执行可能导致拖拽时 badge 高频闪烁。 | 在 §5.2 或 §9 明确写下「v1 不去抖，依赖 React `useMemo` 即时重算」；若选择去抖，须给出阈值（如 150ms）和触发条件。 |
| I5 | **重要** | `ModuleFinding.severity` 字段已定义，但 §5.3/§5.4 的渲染/badge/颜色均按 `code` 硬编码，没有消费 `severity`。 | 要么在 §5.3 说明 `severity` 决定 badge/描边强度（如 `error` 用实线红、`warning` 用虚线黄），要么从 v1 接口中移除 `severity`，避免 dead code。 |
| I6 | **重要** | `deriveNodes` 签名将新增 finding 参数（§5.2），但 §8 未提及需要更新 `recompose.derive.test.ts` 中所有 `deriveNodes` 调用。 | 在 §8「需更新的既有用例」中补一条：所有调用 `deriveNodes` 的测试需要传入新的 `findings` 参数（或改为可选参数并给出默认值）。 |
| I7 | **重要** | 新增字段名 `diagnostic` 与 `api/types.ts:54` 的 `Diagnostic` 类型同名，且 `Inspector.tsx:11` 已导入 `Diagnostic`。未来代码中「模块诊断」与「parser 诊断」容易混淆。 | 建议把字段/类型命名为 `moduleDiagnostic` 或 `finding`，并在 §5.3 的 `RecomposeModuleData` 中体现。若坚持 `diagnostic`，须在 §0 术语速查中区分两个概念。 |
| I8 | **重要** | §8 测试计划未覆盖：Toolbar 点击定位、拖拽后 findings 重算、badge 在 `diagnostic` 变化时更新、空 `design.modules` / 空 `aggregated` 边界。 | 在 §8 补全：新增 Toolbar 定位测试、RecomposeCanvas 活更新测试（拖拽原子后 `detectModuleFindings` 重新调用）、空输入边界测试。 |

### 5.3 建议项

| # | 级别 | 问题 | 要求 |
|---|---|---|---|
| S1 | 建议 | §7 不变量可补一条「第三方节点不出现在 `byModule` 中」和「检测输出不写回 `RecomposedDesign`」。 | 在 §7 末尾补不变量 #12、#13。 |
| S2 | 建议 | 文档多次说「图小，代价可忽略」，但未给出模块数/边数上限或性能测试计划。大库可能出现上百模块。 | 在 §8 增加一条性能注记：当 `design.modules.length > 200` 时考虑 Web Worker 或节流；v1 不测性能，但记录已知边界。 |
| S3 | 建议 | `detectModuleFindings` 对空 `design.modules` 或空 `aggregated` 的返回值未说明。 | 在 §5.1 补一句：空输入时返回 `{ cycles: [], orphans: [], thirdPartyOnly: [], count: { cycles: 0, orphan: 0, thirdPartyOnly: 0 }, byModule: new Map() }`。 |
| S4 | 建议 | Inspector 中「仅连第三方」的功能说明依赖 `description`，若用户未填写则为空。 | 在 §5.4 给 fallback：空 `description` 时显示「该模块未填写接口描述」+ 成员原子名 + 端口。 |

---

## 六、通过条件清单（执行前勾选）

- [ ] **B1**：`ModuleFinding.evidence.path` 要么在 §5.1 给出提取算法，要么从 v1 接口中移除。
- [ ] **B2**：issue #21 范围收窄决策落档到 `grilling-decisions/issue-21-cycle-orphan-decisions.md`，或在 §3 附用户原话摘要+日期。
- [ ] **I1**：Toolbar 可点击列表的交互在 §5.3 明确（展开形式、列表项、定位调用）。
- [ ] **I2**：节点边框色实现方案在 §5.3 明确（`containerStyle` 函数化或样式下放），badge 位置明确。
- [ ] **I3**：Inspector 环证据渲染结构在 §5.4 给出草图（路径展示 + 每段证据迭代）。
- [ ] **I4**：活更新去抖策略在 §5.2/§9 明确（v1 不去抖或给出阈值）。
- [ ] **I5**：`severity` 字段在 UI 中被消费，或从 `ModuleFinding` 中移除。
- [ ] **I6**：§8 补全 `deriveNodes` 签名变更对既有测试的影响。
- [ ] **I7**：决定 `diagnostic` 字段命名（保留或改为 `moduleDiagnostic`/`finding`），并在文档中一致。
- [ ] **I8**：§8 补全 Toolbar 定位、活更新、badge 更新、空输入边界测试。
- [ ] **S1/S2/S3/S4**：酌情补全不变量、性能注记、空输入返回值、description fallback。

---

## 七、结语

本设计文档的事实基础扎实，核心算法与范围收敛合理，与 #18 的边界划分清晰。真正需要动手前解决的是两类：**接口契约与算法不一致**（B1 `evidence.path`）和 **决策未归档导致 canonical 不可复现**（B2）。其余问题集中在 UI 实现落点、测试覆盖和字段消费，修后不会动摇骨架。

建议修复阻塞项并按 §六清单自检后，作为 issue #21 的执行基线。

—— 评审方（独立复核：仓库当前 HEAD，前端测试 114 passed / tsc 0 错误 / build 成功；真实 fixture Tarjan 复现 V9 环断言，2026-09-01）

---

## 附录：执行检查表（Pass 1 产出）

> 标注每行状态：`✅ 实测通过` / `❌ 实测失败` / `⚠️ 无法实测（原因）`

| # | 类别 | 可执行陈述 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | 命令 | `cd frontend && npm test` | ✅ 实测通过 | exit 0，Test Files 14 passed，Tests 114 passed |
| 2 | 命令 | `cd frontend && npx tsc --noEmit` | ✅ 实测通过 | exit 0，无输出 |
| 3 | 命令 | `cd frontend && npm run build` | ✅ 实测通过 | exit 0，dist 构建成功 |
| 4 | 数据流/引用完整性 | `aggregated`（`RecomposeCanvas.tsx:150-153`）→ `detectModuleFindings` → `deriveNodes` → `RecomposeModuleNode.data.diagnostic` | ⚠️ 消费端未实测（设计未实现） | 当前代码无 `detect.ts`，无法从消费端跑；待实现后按此链路复测 |
| 5 | 数据流/引用完整性 | `findings.byModule` → `RecomposeToolbar` 计数 + 列表 → `onSelect` 定位 | ⚠️ 消费端未实测（设计未实现） | Toolbar 当前无 `diagnostics` prop |
| 6 | 数据流/引用完整性 | `findings` → `Inspector.tsx` `RecomposedModuleSelection.finding` → 环/孤儿/仅连第三方详情 | ⚠️ 消费端未实测（设计未实现） | Inspector 当前无 finding 字段 |
| 7 | 复用/零改动 | `computeAggregatedModuleEdges`、`deriveNodes`、`RecomposeModuleNode`、`RecomposeToolbar`、`Inspector` 现有行为 | ✅ 实测/代码核实 | 现有函数签名与文档 §2 引用一致；实现时 `deriveNodes` 将新增参数 |
| 8 | 远端/GitHub | issue #21 body 原始措辞、用户 2026-09-01 grilling 原话 | ⚠️ 无法实测 | 无 GitHub 访问通道；`grilling-decisions/` 下无 issue-21 文件 |
| 9 | 算法断言 | 真实 fixture 默认设计下存在 3 原子环 `{training-logging, aggregation-orchestration, ai-provider-integration}` | ✅ 实测通过 | Node Tarjan 脚本独立复现，唯一非平凡 SCC 与该集合一致 |
| 10 | 算法断言 | 真实 fixture 无孤立 / 仅连第三方原子 | ✅ 实测通过 | 同上脚本，计数均为 0 |
