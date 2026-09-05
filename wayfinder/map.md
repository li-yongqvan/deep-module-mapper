---
name: deep-module-mapper-map
wayfinder: map
---

## Destination

一个通用的「深模块评审」Claude Code skill `/deep-module-review`：用户每完成一个开发阶段，在 Claude Code 中输入 `/deep-module-review [path]`，工具指向任意代码库，自动提取其模块与接口依赖，用轻量 HTML Artifact 呈现架构 + 由「生成图的 Claude」直接给出的结构化评审结论（深模块对齐性、依赖简洁性、模块深度分布、关键发现、建议）。

> **2026-09-03 方向转型（已立项，issue #24）**：原「独立 Web 应用」Destination 已废弃。本项目从本地 Web 应用降级/迁移为一个 Claude Code skill —— 用户反思后认为原独立应用已偏离「轻量工具」初衷（膨胀、维护成本高、与开发上下文割裂）。skill 形态下：保留纯 Python `parser/`；删除 `frontend/`、`backend/` 与 AI 聚合 CLI；深度评分/边聚合/环检测算法迁为 Python 复用；AI 由 Claude 直接评审，不再走 DeepSeek/本地模型。

## Notes

- 当前项目目录：`C:/Users/liyongquan/agent panel/deep-module-mapper/`。
- **2026-09-03（方向转型，issue #24，已立项）**：废弃独立 Web 应用路线，改为 Claude Code skill `/deep-module-review`。设计文档已评审（有条件通过，F1–F8 已解决，2026-09-02），执行 handoff 就绪，**待实现**。旧票 #22（现实/功能视图重设计）已关闭——被 #24 取代（skill 形态下这些视图不复存在）。旧票 **#17**（本地助手训练 collect-reflect，源自 #11 S6）也已关停——其依赖的聚合 CLI 被 #24 D6 删除。
- **2026-09-05（#24 完成）**：**v1 迁移已合并——PR #25，mergeCommit `4d7e7f6`**（parser `exclude_dirs`；skill `/deep-module-review` 落成；frontend/backend 删除；README/.gitignore 收尾）。**v2 已合并——PR #26，mergeCommit `f73caf4`**（parser 第 6 键 `intra` + to_archify/assemble v2 管线 → map.html 可下钻模块地图；10 commits、22 文件 +7201/−95；121 测试全绿、golden 5 键逐字节一致、自扫 8 面板核验一致、降级 e2e ×3）。**issue #24 已随 PR #26 `Closes #24` 自动关闭——#24 全票完成。** showcase/standard 遗留拍板项已于当日消解（写进设计文档 §15 + README）。
- **2026-09-06（v2 真实仓库狗粮 + skill 外装 agent panel）**：按用户指令用三个外部仓库验证 v2——QuickCut（7628 行单文件巨石，正确判 deep、星号导入噪音 586 条）、ai-forum（Go+Vue 零 .py，暴露零模块守卫缺失）、you-get（137 个 .py：124 生产模块/191 边，真实检出 common↔ffmpeg 环；但布局兜底搜索 124 模块下 17+ 分钟不收敛，暴露性能天花板）。四发现立两票：**#27（布局性能）、#28（鲁棒性三项）**。另：skill 已外装 `agent panel/.claude/skills/`（analyze.py 加三级定位 parser：env → 上溯 → 兄弟目录，master `04158a3`），agent panel 副本与仓库副本双份维护需手动同步。
- **GitHub 仓库**：https://github.com/li-yongqvan/deep-module-mapper
- **Canonical wayfinder map**：GitHub issue #1 — https://github.com/li-yongqvan/deep-module-mapper/issues/1
- 本地 `wayfinder/*.md` 文件是 GitHub issues 的 mirror/缓存。
- 共同语言：`deep-module-mapper/UBIQUITOUS_LANGUAGE.md`。
- 用户偏好：先理解原理再实操（CLAUDE.md）。
- 已确认原则：模块 = 实现 + 端口；接口 = 端口/说明书；依赖越简单越好。
- 转型基线技术事实（2026-09-02 真值核对，见设计文档 §2）：parser 无第三方运行时依赖、39 测试全绿；`python -m parser <repo>` CLI 可用；backend/frontend 为 HTTP/React-only，随转型删除。

## Decisions so far

- **2026-09-03 之前的所有决策均属已废弃的「独立 Web 应用」路线**，作为历史记录保留；自 #24 起以 skill 方向为准。详见下方各条目与 `wayfinder/grilling-decisions/`。
- [deep-module-review-skill](wayfinder/grilling-decisions/deep-module-review-skill-decisions.md) — **方向转型（issue #24，2026-09-03）**：把 deep-module-mapper 从独立 Web 应用改为 Claude Code skill `/deep-module-review`。D1/D2 形态+名称；D3 输出 HTML Artifact（架构图+AI 结论）；D4 删除重组画布（拖拽/连线），只留 AI 结论+静态图；D5 AI 主动先给结论；D6 删除聚合 CLI（DeepSeek/本地模型），由 Claude 直接评审；D7 v1 图不渲染外部依赖节点（仅 metrics 表汇总）。设计文档 `design-doc-deep-module-review-skill.md` + 评审意见书（有条件通过，F1–F8 已解决）+ handoff 均已归档。**取代 #22。**
- [deep-module-review-skill 迁移 v1 已合并](wayfinder/grilling-decisions/deep-module-review-skill-decisions.md) — **迁移 v1 完成（PR #25，mergeCommit `4d7e7f6`，2026-09-05）**：parser `exclude_dirs`（向后兼容，默认排除 `.dagr`）；skill `SKILL.md` + `analyze/metrics/digest/diagram.py` + `template.html` + 13 单测落成；`frontend/`、`backend/` 删除（回滚锚点 tag `archive/app-before-skill-migration`）；README/.gitignore 收尾。验证：parser 39 + skill 13 单测全绿、e2e 4 产物齐、自扫本仓库 metrics 与人工核对一致。
- [deep-module-review-skill 迁移 v2 已合并](wayfinder/grilling-decisions/deep-module-review-skill-decisions.md) — **v2 完成（PR #26，mergeCommit `f73caf4`，2026-09-05）**：parser 第 6 键 `intra`（每模块函数级调用图 `{funcs, calls}`，纯附加不动既有 5 键，golden 逐字节一致）；`to_archify`/`assemble` v2 管线（确定性布局 + 布局缓存 + 质量档位写回 IR；9 图缝合单文件 `map.html`，点模块卡片下钻「内部函数路线」泳道图；id 前缀防碰撞、样式去重拼接兜底）；`archify_env.py` 探测（archify/node）+ 降级 e2e ×3；SKILL.md/README v2。验证：121 测试全绿、自扫本仓库 8 面板函数/边与 `intra` 逐条一致、合并样式与原始 deliver 逐字节一致。主图质量 = standard（showcase 对多模块依赖簇不可达，按评审 §15 接受降级，遗留拍板项见 Open frontier）。**#24 全票完成关闭。**
- [research-market-survey](research-market-survey.md) — 市场调研完成；核心 5 项第一版实现，扩展 4 项后续关卡实现，3 项明确不采纳。（历史）
- [grilling-interface-criteria](grilling-interface-criteria.md) — 第一版接口 = 公开函数/导出符号；描述 = 硬事实 + AI 润色；语言 = Python；HTTP/CLI 形态后续再做。（历史）
- [prototype-ui-interaction](prototype-ui-interaction.md) — 节点 = 圆角矩形；端口 = 小圆点；现实视图 = 交通灯语义；自定义画布 = 中性灰蓝 + 评审后标红。（历史）
- [research-dependency-detection](research-dependency-detection.md) — 模块边界 = 一个 `.py` 文件；AST-only 提取；jedi 可选；动态导入标 unresolved；第三方包当不透明节点。（历史；外部节点渲染已被 D7 取代）
- [design-data-schema](design-data-schema.md) — JSON schema、REST API、轮询刷新、AI 调用合同、画布保存格式已确认。（历史）
- [implement-python-parser](implement-python-parser.md) — 第一版 Python AST 解析器已完成（PR #4，2026-08-26）：单一公共 API `scan_codebase`、端口/六类边/externalModules/diagnostics 提取、语法错误隔离、venv 排除、stdlib 忽略；39 测试全绿；设计文档 v3 + 评审意见书（条件通过，F1/F2/F10 已解决）+ grilling 决策落档均已归档。**parser 在本票中保留、沿用。**
- [build-core-backend-api](handoff-issue-5-complete.md) — 后端核心 API 已完成（PR #6）：Starlette + Uvicorn，内存 job 状态，三端点 `/api/scan`/`/status`/`/graph`，44 测试全绿；CORS、job 驱逐、错误格式等决策已落档。（历史）
- [build-frontend-real-view](design-doc-issue-7-frontend-real-view.md) — 现实视图前端已完成（PR #9，2026-08-26）：Vite 8.2.2 + React 19.2.8 + `@xyflow/react` 12；路径输入 → 2s 轮询 → React Flow 渲染；红绿灯 naive 评分（`maxLine/portCount`，50/15 暂定）；外部模块灰色虚线节点；同对多边聚合；右侧 Inspector。18 测试全绿 + 真实 fixture 端到端验证。设计文档（合并审计：5 阻断+8 重要+10 次要全部采纳）+ 决策落档均已归档。（历史）
- [module-map-north-star](module-map-north-star.md) — 视图设计北极星：读者是不懂代码的人；节点按「功能」聚合（AI 给出功能原子，最小可拖动单位）；接口数量尽量少 → 依赖简单。工作流 = 视图层先输出结果，人再据此在重组层优化。第一版用手工维护的功能清单顶替 AI 聚合。（历史）
- [feature-view-functional-atoms](handoff-issue-8-feature-view-complete.md) — 功能视图已完成（PR #12，2026-08-27）：扫描 deep-module-mapper 自生图 29 文件节点 → 3 中文节点 / 2 边；functional-atom manifest（`frontend/src/manifest/feature-atoms.json`）；噪音默认隐藏；原子下钻成员文件；功能视图默认 + 顶部切换。设计文档 + 合并审计（有条件通过，W1-W3/I1-I5 已落实）+ code-review（无阻塞）+ 决策落档 D1-D8 均已归档。code-review 发现项已修复并 cherry-pick 进 master（`b2cc611`）。35/35 测试全绿。（历史）
- [recomposition-layer](handoff-recomposition-layer.md) — 重组视图已完成（PR #14，2026-08-28）：第三视图「重组视图」，模块容器（React Flow 父节点）+ 功能原子 chip（子节点）；原子拖进/拖出模块，单原子自动成隐式模块；模块间依赖 = 自动聚合 ∪ 手动增删；localStorage 持久化（按库路径分 key）+ 重置回 manifest 建议分组；模块 V1 不嵌套；中文名自动派生 + 双击编辑。实测 99 测试全绿、tsc 0、build 成功。决策 D1-D8 已落档。（历史）
- [ai-aggregation](wayfinder/grilling-decisions/issue-11-ai-aggregation-decisions.md) — AI 聚合已完成（PR #15 S1 + #16 S2-S8，2026-08-28）：聚合主力 = **DeepSeek（OpenAI 兼容）CLI 脚本**（`python -m backend.backend.aggregate <repo>`），质量对拍手写 manifest（真实 e2e accuracy=1.0，11/11）；本地模型只做学习角色；失败明确报错 + 退出码 + 不写任何 manifest；digest 轻量方案；降级明确提示。86 后端测试 + 99 前端测试全绿。spec + 评审 + 决策 D1-D14 + U1-U6 均已落档。（历史；聚合 CLI 已被 D6 删除）
- [research-archify-design-reference](research-archify-design-reference.md) — 研究 Archify 设计思路，产出运行时架构图原型与 7 条落地建议，ticket #20 已关闭。（历史）
- [recomposition-edge-check](design-doc-issue-18-recomposition-edge-check.md) — 重组画布「画线即校验」已完成（PR #19，2026-09-01，mergeCommit 34996a7）：默认零边（D1）、人画线当场校验真依赖（方向+存在性）、真边画上并带 parser 代码证据、无依赖/方向反拒绝并一次性反馈；加载旧设计重校验；hiddenEdges 废弃。纯前端，后端零改动。114 前端测试全绿。决策确认：`none` 拒绝文案接受实现版、旧设计非真实边静默丢弃。（历史）
- [module-cycle-orphan-detection](design-doc-issue-21-module-cycle-orphan-detection.md) — 模块级循环依赖/孤儿模块检测**已完成（PR #23，mergeCommit f491927，2026-09-02）**：检测落在重组视图·模块容器级；依据 = 真实代码聚合边；孤儿三分类（正常 / 孤儿 / 仅连第三方·单独高亮）；呈现 = 只标节点 + Inspector + 工具栏轻量计数，不画环边；不自动改图/一键修复。节点 data 字段 `moduleDiagnostic`，v1 不去抖、不展示环路径。真实 fixture 已实测已知 3 原子环 {training-logging, aggregation-orchestration, ai-provider-integration}。决策 D1-D5 与 B1 见 grilling-decisions。（历史；**Tarjan SCC 与孤儿三分类算法由 #24 迁为 Python 复用**）

## Open frontier

- **#27 v2 布局兜底搜索在 100+ 模块仓库不收敛**（2026-09-06 立项，狗粮暴露）— **active**：`to_archify.py` 爬山兜底搜索无候选上限/时间预算/进度输出；you-get 124 生产模块实测单核满载 17+ 分钟无结果（8 模块仓库秒级）。期望方向：时间预算或候选上限 + 到点降级 standard 明示 + 进度心跳。详见 issue #27。
- **#28 评审鲁棒性三项**（2026-09-06 立项，狗粮暴露）— **active**：① 零模块守卫（非 Python 仓库静默产出空 map）；② 星号导入 unresolved_symbol 按使用点洪泛（应按星号导入聚合，QuickCut 586 / you-get 1626 条实测）；③ 被扫代码 SyntaxWarning 泄漏 stderr。三小改动可一包或三 commit。详见 issue #28。
- **#24 已完成关闭**（2026-09-05）：v1（PR #25 `4d7e7f6`）+ v2（PR #26 `f73caf4`）均已合并，issue #24 经 `Closes #24` 自动关闭。当前**无 active frontier**。
- **遗留项已消解（2026-09-05 用户拍板）**：「主图 showcase 对多模块仓库依赖簇不可达」——用户拍板把「standard 为多模块仓库默认预期」写进设计文档 §15（新增「主图质量档位的实测预期」条目）与 README（管线说明新增质量档位条目），commit 见 git log。另：Artifact/生成页人工渲染确认事项已随 v2 改产出单文件 map.html（非 Artifact）而消解，无需再跟踪。
- 其余：原「独立 Web 应用」路线待办（#22 现实/功能视图重设计 [已关闭/被 #24 取代]、Trace path、画布评审端点、GitHub 仓库来源）随方向转型废弃；如未来 skill 方向需要再重新评估立项。

## Not yet specified

- skill v1（PR #25）与 v2（PR #26）均已落地合并；v2 管线（`intra`、to_archify/assemble、map.html 下钻）核验并入。
- 原「独立 Web 应用」路线的未定项（数据持久化、启动方式、界面交互、后续关卡功能、GitHub 仓库来源等）**随方向转型废弃**，不再开放。

## Out of scope

- C4 层级视图：用户明确不要。
- 多格式导出 Mermaid/DOT/JSON：用户明确不要。
- Git 历史波动率评分：用户明确不要。
