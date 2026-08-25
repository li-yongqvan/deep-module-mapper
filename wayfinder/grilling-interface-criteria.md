---
name: grilling-interface-criteria
wayfinder: grilling
status: closed
---

## Question

在本工具中，一个「接口」具体怎么从代码里识别？不同项目形态（脚本集合、Web 服务、库、CLI 工具）下接口判定标准是否统一？

## Context

已达成原则：
- 模块 = 实现 + 端口。
- 接口 = 端口 = 功能使用说明书。
- 用户只关心接口功能和作用，不关心实现。

## Resolution

- 第一版接口识别范围：**公开函数 / 导出符号**（函数、方法、导出类）。
- 描述生成策略：**规则提取硬事实**（函数名、参数、返回值、docstring 第一句）**+ 本地模型润色一句话描述**。
- 第一版支持语言：**Python**；JS/TS 等后续关卡扩展。
- 不同项目形态第一版不做特殊处理，统一按"公开/导出"判定；HTTP 端点、CLI 子命令等形态放到后续关卡。

## Blocking

- `research-market-survey` 已关闭，本 ticket 已解锁并完成。

## Notes

- HITL ticket，已与用户逐项确认。
- 结论直接影响解析器设计与 AI 提示词。
