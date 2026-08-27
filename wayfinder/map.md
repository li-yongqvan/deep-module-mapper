---
name: deep-module-mapper-map
wayfinder: map
---

## Destination

一个通用「模块地图」工具：本地 Web 应用，指向任意代码库后自动提取其**模块（实现+端口）**与**接口依赖**，以规则几何体可视化每个模块的接口功能与职责；提供「自定义依赖画布」供用户拖拽设计理想架构，并由云端模型输出结构化评审（坏味道、职责边界、深模块判断、简洁性）。AI 起草走本地模型，评审走云端模型。按关卡边建边用，成品本身无关卡。

## Notes

- 当前项目目录：`C:/Users/liyongquan/agent panel/deep-module-mapper/`。
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

## Open frontier

- GitHub issue #10: [Recomposition layer: custom canvas with module-content editing](https://github.com/li-yongqvan/deep-module-mapper/issues/10) — 当前 active frontier ticket：用户在画布上把功能原子拖进/拖出模块 + 连依赖。
- GitHub issue #11: [AI aggregation: local model clusters files into functional atoms](https://github.com/li-yongqvan/deep-module-mapper/issues/11) — 依赖 #8（已关闭）；本地模型读文件内容自动判断功能原子，替代手工清单。

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

## Out of scope

- C4 层级视图：用户明确不要。
- 多格式导出 Mermaid/DOT/JSON：用户明确不要。
- Git 历史波动率评分：用户明确不要。
