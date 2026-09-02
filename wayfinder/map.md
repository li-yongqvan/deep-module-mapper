---
name: deep-module-mapper-map
wayfinder: map
---

## Destination

一个通用「模块地图」工具：本地 Web 应用，指向任意代码库后自动提取其**模块（实现+端口）**与**接口依赖**，以规则几何体可视化每个模块的接口功能与职责；提供「自定义依赖画布」供用户拖拽设计理想架构，并由云端模型输出结构化评审（坏味道、职责边界、深模块判断、简洁性）。AI 起草走本地模型，评审走云端模型。按关卡边建边用，成品本身无关卡。

## Notes

- 当前项目目录：`C:/Users/liyongquan/agent panel/deep-module-mapper/`。
- **2026-09-01（用户反馈，待独立会话）**：功能视图 / 现实视图的设计可能偏离用户最初想法，或需重新设计。已创建 issue #22 跟踪；计划文档 `wayfinder/plan-issue-22-redesign-real-feature-views.md`。拟单独开会话讨论（用户建议用 handoff 引导）；具体偏离点待用户说明。不阻塞 #21。
- **GitHub 仓库**：https://github.com/li-yongqvan/deep-module-mapper
- **Canonical wayfinder map**：GitHub issue #1 — https://github.com/li-yongqvan/deep-module-mapper/issues/1
- 本地 `wayfinder/*.md` 文件是 GitHub issues 的 mirror/缓存。
- 共同语言：`deep-module-mapper/UBIQUITOUS_LANGUAGE.md`。
- 用户偏好：先理解原理再实操（CLAUDE.md）。
- 已确认原则：模块 = 实现 + 端口；接口 = 端口/说明书；依赖越简单越好。
- 技术选型参考（来自市场调研）：
  - 画布层：React Flow（xyflow）
  - 规则/契约层：dependency-cruiser、import-linter、ArchUnit 的模式
  - 深模块评分：vladikk/modularity（Balanced Coupling 思想）、wily（复杂度趋势）
  - 端口提取：Tach 的 public-interface 概念

## Decisions so far

- [research-market-survey](research-market-survey.md) — 市场调研完成；核心 5 项第一版实现，扩展 4 项后续关卡实现，3 项明确不采纳。
- [grilling-interface-criteria](grilling-interface-criteria.md) — 第一版接口 = 公开函数/导出符号；描述 = 硬事实 + AI 润色；语言 = Python；HTTP/CLI 形态后续再做。
- [prototype-ui-interaction](prototype-ui-interaction.md) — 节点 = 圆角矩形；端口 = 小圆点；现实视图 = 交通灯语义；自定义画布 = 中性灰蓝 + 评审后标红。
- [research-dependency-detection](research-dependency-detection.md) — 模块边界 = 一个 `.py` 文件；AST-only 提取；jedi 可选；动态导入标 unresolved；第三方包当不透明节点。
- [design-data-schema](design-data-schema.md) — JSON schema、REST API、轮询刷新、AI 调用合同、画布保存格式已确认。
- [implement-python-parser](implement-python-parser.md) — 第一版 Python AST 解析器已完成（PR #4，2026-08-26）：单一公共 API `scan_codebase`、端口/六类边/externalModules/diagnostics 提取、语法错误隔离、venv 排除、stdlib 忽略；39 测试全绿；设计文档 v3 + 评审意见书（条件通过，F1/F2/F10 已解决）+ grilling 决策落档均已归档。
- [build-core-backend-api](handoff-issue-5-complete.md) — 后端核心 API 已完成（PR #6）：Starlette + Uvicorn，内存 job 状态，三端点 `/api/scan`/`/status`/`/graph`，44 测试全绿；CORS、job 驱逐、错误格式等决策已落档。
- [build-frontend-real-view](design-doc-issue-7-frontend-real-view.md) — 现实视图前端已完成（PR #9，2026-08-26）：Vite 8.2.2 + React 19.2.8 + `@xyflow/react` 12；路径输入 → 2s 轮询 → React Flow 渲染；红绿灯 naive 评分（`maxLine/portCount`，50/15 暂定）；外部模块灰色虚线节点；同对多边聚合；右侧 Inspector。18 测试全绿 + 真实 fixture 端到端验证。设计文档（合并审计：5 阻断+8 重要+10 次要全部采纳）+ 决策落档均已归档。
- [module-map-north-star](module-map-north-star.md) — 视图设计北极星：读者是不懂代码的人；节点按「功能」聚合（AI 给出功能原子，最小可拖动单位）；接口数量尽量少 → 依赖简单。工作流 = 视图层先输出结果，人再据此在重组层优化。第一版用手工维护的功能清单顶替 AI 聚合。
- [feature-view-functional-atoms](handoff-issue-8-feature-view-complete.md) — 功能视图已完成（PR #12，2026-08-27）：扫描 deep-module-mapper 自生图 29 文件节点 → 3 中文节点 / 2 边；functional-atom manifest（`frontend/src/manifest/feature-atoms.json`）；噪音默认隐藏；原子下钻成员文件；功能视图默认 + 顶部切换。设计文档 + 合并审计（有条件通过，W1-W3/I1-I5 已落实）+ code-review（无阻塞）+ 决策落档 D1-D8 均已归档。code-review 发现项已修复并 cherry-pick 进 master（`b2cc611`）：抽共享 PortHandle、NODE_WIDTH 统一、'依赖' 单通道 label、Inspector 下钻渲染测试，35/35 测试全绿。
- [recomposition-layer](handoff-recomposition-layer.md) — 重组视图已完成（PR #14，2026-08-28）：第三视图「重组视图」，模块容器（React Flow 父节点）+ 功能原子 chip（子节点）；原子拖进/拖出模块，单原子自动成隐式模块；模块间依赖 = 自动聚合 ∪ 手动增删；localStorage 持久化（按库路径分 key）+ 重置回 manifest 建议分组；模块 V1 不嵌套；中文名自动派生 + 双击编辑。实测 99 测试全绿、tsc 0、build 成功；发现并修复 2 个真实逻辑 bug（有回归测试）。共同语言补「功能原子」「模块容器」术语。决策 D1-D8 已落档。
- [ai-aggregation](wayfinder/grilling-decisions/issue-11-ai-aggregation-decisions.md) — AI 聚合已完成（PR #15 S1 + #16 S2-S8，2026-08-28）：聚合主力 = **DeepSeek（OpenAI 兼容）CLI 脚本**（`python -m backend.backend.aggregate <repo>`），质量对拍手写 manifest（真实 e2e accuracy=1.0，11/11）；**本地模型只做学习角色**（best-effort 产自己答案 + 对比云端反思，永不充当权威 manifest）；失败明确报错 + 退出码 + 不写任何 manifest（不回退手工）；digest 轻量方案（路径+imports+端口+docstring，本地 12K/API 40K）；降级明确提示。86 后端测试 + 99 前端测试全绿。spec + 评审（magical-herding-swan 有条件通过）+ 决策 D1-D14 + U1-U6 均已落档。
- [research-archify-design-reference](research-archify-design-reference.md) — 研究 Archify 设计思路（生成→校验→预览→交付→迭代、typed JSON IR、校验回执、Delta 对比），产出 deep-module-mapper 运行时架构图原型与 7 条落地建议（#18 回执格式、schema 版本化、自动布局等），ticket #20 已关闭。
- [recomposition-edge-check](design-doc-issue-18-recomposition-edge-check.md) — 重组画布「画线即校验」已完成（PR #19，2026-09-01，mergeCommit 34996a7）：默认零边（D1）、人画线当场校验真依赖（方向+存在性）、真边画上并带 parser 代码证据（D3）、无依赖/方向反拒绝并一次性反馈（D4/D5）；加载旧设计重校验（裁决3）、hiddenEdges 废弃（裁决4）。纯前端，后端零改动。114 前端测试全绿 + tsc 0 错误 + build 成功；review 核验通过。决策确认：`none` 拒绝文案接受实现版、旧设计非真实边静默丢弃（§9 Q2 不做提示）。
- [module-cycle-orphan-detection](design-doc-issue-21-module-cycle-orphan-detection.md) — 模块级循环依赖/孤儿模块检测**设计文档已评审通过（2026-09-02，可执行基线）**：检测落在**重组视图·模块容器级**（最大粒度，用户确认收窄票面「现实视图」）；依据 = 真实代码聚合边（非用户画的线）；孤儿**三分类**（正常 / 孤儿 / **仅连第三方**·单独高亮+说明功能）；呈现 = **只标节点 + Inspector + 工具栏轻量计数**，不画环边（尊重 #18 零边）、不做画线构成环时提示（#18 交互原样）；不自动改图/一键修复。节点 data 字段定名 `moduleDiagnostic`（避免与 parser `Diagnostic` 混淆），v1 不去抖、不展示环路径。真实 fixture 已实测存在已知 3 原子环 {training-logging, aggregation-orchestration, ai-provider-integration}（默认设计下直接可见）。决策 D1-D5 与 B1 见 `wayfinder/grilling-decisions/issue-21-cycle-orphan-detection-decisions.md`；执行 handoff 见 `handoff-issue-21-module-cycle-orphan-detection.md`。

## Open frontier

暂无 active frontier ticket。#18（重组画布「画线即校验」）已完成（PR #19）并关闭。待办按优先级（2026-08-28 用户确认方向）：
1. 循环依赖 / 孤儿模块检测 — **已 ticketing** → issue #21（2026-09-01 创建）；**设计文档完成（2026-09-01）**，待评审/实现 → `design-doc-issue-21-module-cycle-orphan-detection.md` + `handoff-issue-21-module-cycle-orphan-detection.md`
2. **现实视图 / 功能视图重设计** — **已 ticketing** → issue #22（2026-09-01 创建），待 grilling 明确偏离点 → `wayfinder/plan-issue-22-redesign-real-feature-views.md`
3. Trace path（变更影响追踪）
4. 画布评审端点（云端模型评审重组后的设计）
5. GitHub 仓库来源（后置）

其余待办尚未 ticketing，需统筹方创建。

## Not yet specified

- 数据持久化：模块元数据、用户画布、人工修改存哪。
- 启动方式：Docker / 脚本 / dev server（当前 dev server：`cd frontend && npm run dev` @ 5175）。
- 界面二交互细节：选模块、拖拽、连箭头、保存/读取理想设计（prototype 已部分验证）。
- 后续关卡功能（已确认纳入范围，待 ticketing，编号待分配）：
  - 变更影响追踪（trace path）
  - 模块目录（metadata + relations）
  - 循环依赖与孤儿模块检测
  - 遗留模块渐进式 enforcement
  - 设计画布持久化（`/api/designs`）
  - 画布评审端点（云端模型评审重组后的设计，依赖 #10）
- 已定（不再开放）：实时刷新 = 2s 轮询（#7 已实现）；图布局 = 简单网格（dagre 优化留后续）；评分公式 = naive `maxLine/portCount`（50/15 暂定，见设计文档附录 A）。
- 已定（2026-08-28，方向讨论）：**不做实时重扫**——按需重扫即可（现有功能已支持）；**GitHub 仓库来源**方向保留但后置，本阶段仍以本地路径扫描为主；**聚合层「文件→功能原子」必须是纯 AI 判断，且不加人工纠错**（人不逐文件修改；#11 才算是真正的聚合层，手工 manifest 只是 #8 的临时脚手架，非最终形态）。人工价值集中在重组层（功能原子→模块，业务边界人拍板，#10 已做）。

## Out of scope

- C4 层级视图：用户明确不要。
- 多格式导出 Mermaid/DOT/JSON：用户明确不要。
- Git 历史波动率评分：用户明确不要。
