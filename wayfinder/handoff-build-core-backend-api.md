# Handoff: Build core backend API

> Ticket: GitHub issue #5 — https://github.com/li-yongqvan/deep-module-mapper/issues/5
> 角色：执行 Agent（Worker）
> 目标：实现后端核心 API，让前端可以请求扫描代码库并获取 Graph。

## 背景

Parser 已完成（PR #4）。现在需要一层 HTTP API 把 `parser.scan_codebase()` 暴露给前端。前端会先做一个「现实视图」：用户输入代码目录 → 后端扫描 → 前端展示模块图。

本 ticket 只覆盖最核心的 scan + graph 两个端点，AI 描述、设计画布、评审等后续再做。

## 当前状态

- Parser 包：`deep-module-mapper/parser/`
- 公共 API：`from parser import scan_codebase; graph = scan_codebase(Path("some/repo"))`
- Schema 定义：`deep-module-mapper/wayfinder/design-data-schema.md`
- Parser 设计文档：`deep-module-mapper/wayfinder/implement-python-parser.md`
- 原型 UI（参考，非实现）：`deep-module-mapper/wayfinder/prototype-ui.html`
- 地图：`deep-module-mapper/wayfinder/map.md`（GitHub issue #1）

## 必须读取的文档

开工前按顺序读：

1. `deep-module-mapper/UBIQUITOUS_LANGUAGE.md`
2. `deep-module-mapper/wayfinder/design-data-schema.md`
3. `deep-module-mapper/wayfinder/implement-python-parser.md`
4. `parser/__init__.py` 和 `parser/_scanner.py`（了解公共 API 和返回结构）
5. `parser/schema.json`（Graph schema）

## 具体任务

见 issue #5 acceptance criteria。提炼为：

1. 在 `backend/` 下搭建一个 Python web 服务。
2. 实现 `POST /api/scan`：接收路径，异步扫描，返回 job id。
3. 实现 `GET /api/scan/:jobId/status`：返回扫描状态。
4. 实现 `GET /api/scan/:jobId/graph`：返回 Graph JSON。
5. 写测试：用 `parser/tests` 里的 fixture 或自己建 `backend/tests/fixtures/`。
6. 更新 README，写清楚怎么启动后端。

## 关键决策（已确定，无需再讨论）

- 模块边界：一个 `.py` 文件 = 一个模块。
- Graph schema：包含 `modules`、`ports`、`edges`、`externalModules`、`diagnostics`。
- 实时刷新：第一版用轮询，不是 WebSocket。
- 扫描结果：本 ticket 只存内存，不持久化。

## 需要你做的决策

在 PR 里说明并让用户确认：

- **Web 框架选哪个？** FastAPI / Flask / Starlette / 其他。建议 FastAPI，因为类型提示和自动文档对 schema 校验友好。
- **job 存储实现？** 内存 dict 即可，不用数据库。
- **扫描是同步还是异步？** 建议异步后台任务（thread 或 asyncio），前端轮询 status。
- **错误格式？** 建议统一返回 `{ "error": "...", "details": "..." }`。

## 建议使用的 skills

- `/tdd` — 先写测试再写实现
- `/codebase-design` — 保持后端包结构清晰
- `/prototype` — 如果需要快速验证 API 行为

## 红线 / 不做

- **不要实现 AI 相关端点**（`/api/descriptions/*`、`/api/review`），那是后续 ticket。
- **不要实现设计画布持久化**（`/api/designs`），那是后续 ticket。
- **不要改动 parser 公共 API**（`scan_codebase` 的签名和返回结构）。如果发现有必须改的地方，先请示统筹方/用户。
- **不要引入数据库或持久化**。扫描结果只存内存。
- 合并 PR、关闭 issue、删除分支等敏感操作必须用户明确授权。

## 工作区隔离

- 本仓库已有其他 Agent 可能并行工作。开工前务必确认自己在独立 git worktree，并检查 `git status` 和当前分支。
- 参考：[[parallel-session-worktree-discipline]]

## 完成汇报格式

完成后请按以下结构汇报：

1. 做了什么（一句话）
2. 改了哪些文件 / 开了哪个 PR
3. 验证结果（测试通过？手动 curl 结果？）
4. 下一步是什么 / 阻塞点在哪
5. 是否需要用户决策

---

> 本 handoff 由统筹方生成。执行 Agent 遇到范围不清或红线冲突时，先暂停并请示用户/统筹方。
