---
name: research-market-survey
wayfinder: research
status: closed
---

## Question

市面上有哪些高星、仍在维护的 GitHub 项目与代码库可视化、模块依赖分析、架构理解、深模块评估相关？它们各自提供什么能力？哪些功能/设计值得我们借鉴到「模块地图」工具中？

## Scope

- 只关注 GitHub 上高星（≥1k stars 优先）且近期仍在维护（近 6-12 个月有提交/release/issue 活动）的项目。
- 领域覆盖：代码依赖图生成、架构/模块可视化、设计质量/深模块分析、交互画布工具。
- 输出格式：候选功能清单，每项附「项目名/链接」「当前 stars/维护状态」「建议理由」「是否要引入/如何修改」。

## Resolution

- 调研报告：`research-market-survey-report.md`
- 用户确认采纳：
  - 核心 5 项全部第一版实现：Port/接口提取、规则契约、深模块健康分、React Flow 画布、AI 起草+云端评审。
  - 扩展 4 项后续关卡实现：#6 变更影响追踪、#7 模块目录、#9 循环/孤儿检测、#10 遗留模块渐进 enforcement。
  - 明确不采纳：#8 C4 层级视图、#11 多格式导出、#12 Git 波动率评分。

## Blocking

无 —— 这是 frontier ticket，已启动并完成。

## Notes

- 使用 `/research` subagent 执行。
- 结果已汇总给用户确认，地图已据此更新。
