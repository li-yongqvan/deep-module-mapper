# Issue #5 Backend API Decisions

**日期**：2026-08-26  
**对应任务**：GitHub issue #5 — Build core backend API: scan + graph endpoints  
**归档依据**：设计文档 §3 决策记录，经 plan-review 评审修订后确认。

## 已确认决策

| 编号 | 问题 | 定案 | 确认方式 |
|---|---|---|---|
| D1 | Web 框架 | Starlette 1.3.1 + Uvicorn，约束 `starlette>=1.3.1,<2` | 用户确认（2026-08-26） |
| D2 | 后台任务 | `threading.Thread(daemon=True)` | 用户确认（2026-08-26） |
| D3 | 错误体 | `{"error": "snake_case_code", "details": "..."}` | 用户确认（2026-08-26） |
| D4 | CORS | 本地 dev 默认 `["*"]`，可用 `BACKEND_CORS_ORIGINS` 覆盖；绑定 127.0.0.1、不启用 `allow_private_network` | 用户确认方向（2026-08-26） |
| D5 | Job eviction | 最多保留 100 条，仅淘汰最旧的 `done`/`error` 终态 job | 用户确认（2026-08-26） |
| D6 | 路径沙箱 | 不限制，允许任意本地目录 | 用户确认（2026-08-26） |
| D7 | 默认绑定 | `127.0.0.1:8123` | 用户确认（2026-08-26） |

## 威胁模型与缓解

D4 选择 `*` CORS 源配合以下约束：
- 后端仅绑定 `127.0.0.1`，不接受外部网络请求。
- 不启用 `allow_private_network`，禁止私网预检绕过。
- 前端端口确定后，应立即将默认源从 `*` 收紧为具体 origin。

## 未决事项

- 前端最终 dev server 端口确定后，需更新 `backend/app.py` 默认 CORS 源。
