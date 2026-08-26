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

## Open frontier

- GitHub issue #7: [Build frontend real-view with React Flow](https://github.com/li-yongqvan/deep-module-mapper/issues/7) — 当前 frontier ticket，实现现实视图：输入目录 → 轮询扫描状态 → React Flow 渲染模块图。

## Not yet specified

- 实时刷新机制：第一版确认轮询，细节待实现时定。
- 图布局算法：大图如何自动排版。
- 数据持久化：模块元数据、用户画布、人工修改存哪。
- 启动方式：Docker / 脚本 / dev server。
- 界面二交互细节：选模块、拖拽、连箭头、保存/读取理想设计（prototype 已部分验证）。
- 后续关卡功能（已确认纳入范围，待 ticketing，编号待分配）：
  - 变更影响追踪（trace path）
  - 模块目录（metadata + relations）
  - 循环依赖与孤儿模块检测
  - 遗留模块渐进式 enforcement
  - AI 描述与评审端点（`/api/descriptions/*`、`/api/review`）
  - 设计画布持久化（`/api/designs`）

## Out of scope

- C4 层级视图（#8）：用户明确不要。
- 多格式导出 Mermaid/DOT/JSON（#11）：用户明确不要。
- Git 历史波动率评分（#12）：用户明确不要。
