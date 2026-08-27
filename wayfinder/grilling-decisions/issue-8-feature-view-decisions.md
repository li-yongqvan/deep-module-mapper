# Issue #8 Feature view（功能原子聚合 + 中文描述）— 决策归档

> 用途：为设计文档 §3 的「用户确认」决策提供可复核落档（合并审计 I5）。
> 关联文档：评审前设计文档位于 `.claude/plans/`（不入库）；本文件为入库的决策原文。

| 编号 | 决策 | 定案 | 确认方式 |
|---|---|---|---|
| D1 | 功能视图与现实视图如何共存 | **功能视图为默认** + 顶部「功能视图/现实视图」切换按钮；现实视图仍可达（为 #10 重组层保留文件级入口） | 用户确认（2026-08-27，AskUserQuestion 选定「功能视图为默认+顶部切换」；弃选「直接取代不设切换」） |
| D2 | 功能视图里第三方依赖怎么处理 | **聚合为一个「第三方依赖」灰色虚线节点**，保留原子→第三方 依赖边；`externalNames` 供下钻 | 用户确认（2026-08-27，AskUserQuestion 选定「聚合为一个第三方依赖灰色节点」；弃选「完全隐藏」） |
| D6 | `parser/__init__.py` 是否纳入原子 | **纳入 scan-and-parse 原子**——它是导出 `scan_codebase` 的公共门面（`parser/__init__.py:6-8`），不纳入则 `backend → parser` 唯一跨原子边丢失 | 本票决策 + 合并审计 Q2 认可（承重）；issue #8 验收标准含豁免条款（"excluded **unless they belong to a named atom**"）背书 |
| D3 | Manifest 位置 + 格式 | `frontend/src/manifest/feature-atoms.json`（JSON；#11 AI 聚合可 drop-in） | 本票决策 |
| D4 | 聚合逻辑位置 | 前端 sibling transform `lib/graphToFeatureFlow.ts`（不改 `graphToFlow.ts` 语义、不改 backend） | 本票决策 + 红线 |
| D5 | 下钻 UX | 点击原子节点 → 右侧 Inspector 展示成员文件 + 各文件端口签名 | 本票决策 |
| D7 | 原子级深度分 | `depthScore(原子成员 ports 并集)`（ticket 明示算法） | 本票决策 + ticket |
| D8 | 边聚合复用 | 提取 `lib/aggregateEdges.ts` 共享，`graphToFlow.ts` 改为调用（行为逐字节一致；19 测试为回归闸门，失败回退自带实现） | 本票决策 + 合并审计 Q1 认可（附条件）/C4 |

**实现落地对照**：D1 → `src/App.tsx`；D2 → `src/lib/graphToFeatureFlow.ts` + `src/components/ExternalNode.tsx`（Handle 修复 error #008，外部边得以渲染）；D3 → `src/manifest/feature-atoms.json`；D4 → `src/lib/graphToFeatureFlow.ts`；D5 → `src/components/Inspector.tsx`；D6 → `src/manifest/feature-atoms.json`；D7 → `src/lib/graphToFeatureFlow.ts`；D8 → `src/lib/aggregateEdges.ts` + `src/lib/graphToFlow.ts`。
