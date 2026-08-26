# Issue #3 — Parser 设计决策落档

> 本文档记录 issue #3「Implement Python AST parser」实现前经用户确认的设计决策。
> 评审意见书：《implement-python-parser-评审意见书.md》（2026-08-26，有条件通过）。
> 落档日期：2026-08-26。

## 访谈确认（2026-08-25，AskUserQuestion）

| 编号 | 决策问题 | 选项 | 定案 | 弃选理由 |
|---|---|---|---|---|
| D9 | 模块 id 格式 | 相对路径 / 点分模块名 / 文件名 | **相对路径**（如 `src/utils/helpers.py`） | 点分名需推断包根且相对导入复杂；文件名跨目录冲突 |
| D10 | 标准库/第三方/本地识别 | 白名单+路径匹配 / import+site-packages / 只认内部 | **白名单 + 内部路径匹配** | import 检测会执行代码；只认内部会把 stdlib 当外部 |
| D11 | 测试 fixture | fixture 微型项目 / agent-lib / 两者 | **fixture 微型项目**（`parser/tests/fixtures/`） | agent-lib 不在本地仓库 |
| D12 | 端口 signature 内容 | 参数名+返回值标记+varargs / 完整签名字符串 / 仅参数名数组 | **参数名 + 返回值标记 + varargs 字符串**，另补 `params: list[str]` | 完整字符串含注解脆弱；仅参数名缺返回值 |
| D13 | edges sites 粒度 | 行号 / 行+列 / 行+源码 | **仅行号** | 更精确则体积大，第一版不需要 |

## 评审裁决（2026-08-26，plan-review 意见书 §四）

| 编号 | 焦点 | 裁决 |
|---|---|---|
| Q1 | 相对路径 id + `/` 序列化 | 认可附 2 条件：`resolve()`+`relative_to`、一律 `.as_posix()` |
| Q2 | signature 字符串 vs 结构化参数 | 字符串保留，`Port` 补 `params: list[str]` |
| Q3 | 标准库进不进 externalModules | 不进节点、不产生边，文档化忽略 |
| Q4 | `__all__` 与下划线冲突 | 显式 `__all__` 优先；re-export 仍纳入且不重复建端口 |
| Q5 | 动态导入 severity | 第一版不引入，message 带目标 |
| Q6 | 根目录非包时相对导入 | 可行，基准 = 当前文件所在目录 |
| Q7 | `_schema.py` 私有 / TypedDict | 保持私有；契约载体 = 独立 JSON Schema（`parser/schema.json`） |
| Q8 | dict vs 包装对象 | 否决包装类，dict 足够 |
| Q9 | `_scanner` 何时拆 `_visitor` | 触发器量化：超 ~400 行 / 无法同屏各读 / 测试需绕过编排 |

## 其它确认

- 阻塞项 F10（推送 Amendments + 更新 issue #3）与 F9（本落档）的执行见 PR 记录。
