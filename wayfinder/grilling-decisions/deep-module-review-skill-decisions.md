---
name: deep-module-review-skill-decisions
description: 将 deep-module-mapper 从独立 Web 应用迁移为 Claude Code skill `/deep-module-review` 的关键决策落档。
---

# deep-module-review skill 迁移 —— 决策记录

**日期**：2026-09-02
**场景**：用户反思后认为当前项目已偏离初衷，需要重大转型。
**落档方式**：用户在本会话中逐条确认，由统筹方整理归档。

---

## D1 项目形态：独立应用 vs. Claude Code skill

- **问题**：deep-module-mapper 应继续作为独立 Web 应用，还是改为更轻量的 Claude Code skill？
- **选项**：
  - A. 保留独立 Web 应用，继续扩展功能。
  - B. 降级为 Claude Code skill，嵌入对话流中使用。
- **定案**：**B — 改为 Claude Code skill**。
- **弃选 A 理由**：用户认为当前应用太重，维护成本高，与日常开发上下文割裂，不符合“轻量化”初衷。
- **依据**：用户确认（2026-09-02）。

---

## D2 skill 名称

- **问题**：skill 的触发词叫什么？
- **选项**：
  - A. `/deep-module-review`
  - B. `/arch-review`
  - C. `/module-review`
- **定案**：**A — `/deep-module-review`**。
- **依据**：用户确认（2026-09-02）。

---

## D3 输出形式

- **问题**：skill 的输出形式是什么？
- **选项**：
  - A. HTML Artifact（可视化架构图 + AI 结论）
  - B. 纯文本 Markdown 报告
  - C. 生成本地文件后由用户自行打开
- **定案**：**A — HTML Artifact**。
- **依据**：用户确认（2026-09-02）。

---

## D4 重组画布是否保留

- **问题**：原应用中的重组画布（拖拽原子、手动连线、画线校验）是否保留？
- **选项**：
  - A. 保留重组画布作为 skill 的一部分。
  - B. 删除重组画布，只保留 AI 结论与静态架构图。
- **定案**：**B — 删除重组画布**。
- **弃选 A 理由**：用户明确表示重组画布只是“锦上添花”，主要关注 AI 给出的结论。
- **依据**：用户确认（2026-09-02）。

---

## D5 AI 是否主动给出结论

- **问题**：AI 应在 Artifact 中先给出结论，还是只在用户追问时回答？
- **选项**：
  - A. AI 主动在 Artifact 顶部给出结论，图作为辅助。
  - B. 只输出图，结论由用户主动询问。
- **定案**：**A — AI 主动给出结论**。
- **依据**：用户确认（2026-09-02）。

---

## D6 AI 评审模型：保留聚合 CLI vs. Claude 直接评审

- **问题**：AI 评审是否继续使用 `backend/backend/aggregate/`（DeepSeek / 本地模型聚合 CLI），还是由生成架构图的 Claude 直接完成？
- **选项**：
  - A. 保留聚合 CLI，作为评审的主要来源。
  - B. 删除聚合 CLI，由 Claude 直接读取 metrics/digest 并输出结论。
- **定案**：**B — 删除聚合 CLI，由 Claude 直接评审**。
- **弃选 A 理由**：用户明确说“直接让生成这个图的 AI 来帮助我评分”。保留聚合 CLI 会引入 API 密钥、模型选择等额外复杂度，与轻量化目标冲突。
- **依据**：用户确认（2026-09-02）。

---

## D7 v1 Artifact 是否显示外部依赖节点

- **问题**：v1 的架构图中是否渲染外部依赖（第三方库）节点？
- **选项**：
  - A. 在图中显示外部依赖节点。
  - B. 不在图中显示外部依赖节点，仅在 metrics 表中汇总外部依赖数量。
- **定案**：**B — v1 不在图中显示外部依赖节点**。
- **理由**：保持 v1 简洁，避免图表 clutter；用户核心关注模块间关系与模块深度。外部依赖数量在 metrics 表中已足够支撑“依赖简洁性”评审。
- **依据**：计划建议，评审意见书要求用户书面确认（2026-09-02，本文件即确认）。

---

## 附带决策：工作区未提交 frontend 改动的处理

- **问题**：当前工作区有 3 个未提交的 frontend 改动（Inspector.test.tsx、Inspector.tsx、recompose/detect.ts），迁移前如何处理？
- **选项**：
  - A. 提交到 master，作为 #21 的最终收尾状态。
  - B. 直接丢弃，因为 frontend 将被整体删除。
- **定案**：**B — 直接丢弃**。
- **理由**：frontend 目录将在迁移中整体删除，这些 UI 微调失去附着点；保留干净工作区更利于迁移。
- **依据**：用户确认（2026-09-02）。

---

## 关联文档

- 设计文档：`wayfinder/design-doc-deep-module-review-skill.md`
- 评审意见书：`wayfinder/design-doc-deep-module-review-skill-评审意见书.md`（待生成）
- 执行 handoff：`wayfinder/handoff-deep-module-review-skill.md`（待生成）
- 项目地图：`wayfinder/map.md`
