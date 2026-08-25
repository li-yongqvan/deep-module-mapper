---
name: research-dependency-detection
wayfinder: research
status: closed
---

## Question

代码中的依赖关系应该怎么提取？不同语言和项目形态下，什么算一条合法的依赖边？现有主流方案怎么做？

## Scope

- 调研静态分析提取依赖的方法：import/require、函数调用、类型引用、继承、装饰器等。
- 调研现有工具（dependency-cruiser、import-linter、pydeps、Tach、jedi 等）的依赖判定策略。
- 输出：推荐的第一版依赖提取策略 + 可扩展点。

## Resolution

- 依赖边定义：模块 A 静态引用模块 B 中定义的符号 = 一条依赖边。
- 计入的边类型：`import`、`from-import`、跨模块调用、类继承、类型注解、装饰器。
- 不计入的：同文件内调用、内置函数、运行时动态模式。
- 模块边界：第一版 **一个 `.py` 文件 = 一个模块**。
- 端口识别：公开函数、类、`__all__` 导出；`_private` 内部符号排除。
- 解析策略：第一版 **AST-only**（Python 标准库 `ast`）；`jedi` 作为可选符号精确定位层。
- 第三方包：当作不透明外部节点，v1 不展开内部。
- 动态导入：检测并生成 `diagnostics` 警告，不强行解析。
- 推荐输出格式：JSON schema（modules / ports / edges / diagnostics）。
- 后端架构分层：Config → Discovery → AST Parser → Optional Jedi Resolver → Graph Builder → JSON Output。

## Blocking

- `research-market-survey` 已关闭。
- `grilling-interface-criteria` 已关闭，本 ticket 已解锁并完成。

## Notes

- AFK research ticket，使用 `/research` subagent。
- 调研报告：`research-dependency-detection-report.md`。
