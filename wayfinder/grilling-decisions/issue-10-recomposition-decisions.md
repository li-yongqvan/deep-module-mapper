# Issue #10 Recomposition layer（自定义画布 + 模块内容编辑）— 决策归档

> 用途：为设计文档 §3 的「用户确认」决策提供可复核落档（评审基线 #5）。设计文档位于 `.claude/plans/`（不入库）；本文件为入库的决策原文。
> 关联文档：`wayfinder/handoff-recomposition-layer.md`（本票交接）；`.claude/plans/humming-moseying-bentley-设计文档-执行基线.md`（评审合并版执行要求）。

| 编号 | 决策 | 定案 | 确认方式 |
|---|---|---|---|
| D1 | 重组画布保存/加载的持久化方案 | **localStorage**（前端本地，按代码库路径分 key；schema 对齐 design-data-schema「module list + edges + layout positions」） | 用户确认（2026-08-28，AskUserQuestion 选定「localStorage」；弃选「后端 /api/designs 端点」——map.md 已把 /api/designs 列为待 ticketing 的未来 ticket，本票零后端改动） |
| D2 | 模块间依赖边语义 | **自动聚合 + 手动增删**：默认边 = 原子依赖聚合；用户可新增（`addedEdges`）/删除（`hiddenEdges`） | 用户确认（2026-08-28，AskUserQuestion 选定「自动聚合+手动增删」；弃选「纯手动显式」——初始画布即见继承依赖，且同时满足 handoff「边从模块内原子的依赖聚合而来」+「画/删依赖边」两条） |
| D3 | 重组画布是否保留「第三方依赖」聚合节点 | **保留**（复用 `ExternalNode`，可拖动，位置持久化） | 用户确认（2026-08-28，AskUserQuestion 选定「保留」；弃选「砍掉」——重组后用户仍需看到对第三方库的依赖） |

**AskUserQuestion 原文**（2026-08-28，逐项确认）：
1. 问：「重组画布的保存/加载用哪种持久化方案？（map.md 已把 /api/designs 列为「待 ticketing」的未来 ticket）」选项 A=localStorage（推荐：零后端改动、跨会话恢复、不碰未来 ticket）、B=后端 /api/designs 端点（服务端持久化但需改后端+与后续 ticket 重叠）→ 定案 A。
2. 问：「模块之间的依赖边采用哪种语义？」选项 A=自动聚合+手动增删（推荐）、B=纯手动显式（初始无边，丢失聚合洞察）→ 定案 A。
3. 问：「重组画布上是否保留『第三方依赖』聚合节点？」选项 A=保留（推荐）、B=砍掉（范围更小但视图不完整）→ 定案 A。

**实现落地对照**：D1 → `src/lib/recompose/persistence.ts`；D2 → `src/lib/recompose/edges.ts`；D3 → `src/components/RecomposeCanvas.tsx`（复用 `ExternalNode`）。模块画布表示 / 不嵌套 / 中文名命名策略等工程裁决见设计文档 §6（评审基线已通过）。
