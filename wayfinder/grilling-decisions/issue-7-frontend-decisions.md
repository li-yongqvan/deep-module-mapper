# Issue #7 Frontend Real-View — 决策归档

> 用途：为设计文档 §3 的「用户确认」决策提供可复核落档（审计 m5）。
> 关联文档：`wayfinder/design-doc-issue-7-frontend-real-view.md`。

| 编号 | 决策 | 定案 | 确认方式 |
|---|---|---|---|
| D1 | 前端 dev server 端口 | 5175 | 用户确认（2026-08-26） |
| D2 | 深模块评分 naive ratio（`maxLine/portCount`，阈值 50/15，零端口判浅） | 采纳 | 用户确认（2026-08-26） |
| D3 | 节点布局：简单网格（常量导出，后续可换 dagre） | 采纳 | 用户确认（2026-08-26） |
| D4 | 样式：CSS Modules + CSS 变量（沿用原型暗色调色板） | 采纳 | 用户确认（2026-08-26） |
| D10 | 端口把手 = 每模块左右各一个 Handle（与 issue「per public port」字面偏差，原型实证支撑） | 采纳 | 用户确认（2026-08-26）；PR 声明偏差 |
| D11 | 外部模块渲染为灰色虚线节点，不评分、不显示端口 | 采纳 | 用户确认（2026-08-26），方案 A |
| D5 | 框架：Vite 最新模板 + React 19 + TypeScript（B5 修订，原「Vite 6 + React 18」废弃） | 本票决策 | 2026-08-26 实测 create-vite 输出 Vite 8.2.2 / React 19.2.8 |
| D6–D9 | 状态管理/测试/包管理器/CORS | 本票决策 | 见设计文档 §3 |
| D12 | 同模块对多边按 `(source,target)` 聚合 | 本票决策 | 审计 M2 修订 |
| D13 | 轮询 `setTimeout` 链式 + 暂态失败计数 + 超时/取消 | 本票决策 | 审计 M1 修订 |

**实现落地对照**：D1 → `vite.config.ts`；D2 → `src/lib/depthScore.ts`；D10 → `src/components/ModuleNode.tsx`；D11 → `src/components/ExternalNode.tsx`；D12 → `src/lib/graphToFlow.ts`；D13 → `src/hooks/useScanJob.ts`。
