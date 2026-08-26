---
name: handoff-issue-7-complete
wayfinder: handoff
ticket: "#7"
status: complete
---

# Handoff: Issue #7 — Frontend Real-View Complete

**Ticket**: https://github.com/li-yongqvan/deep-module-mapper/issues/7  
**PR**: https://github.com/li-yongqvan/deep-module-mapper/pull/9  
**Merged**: `master` @ `5db0f36`（PR #9 squash merge，2026-08-26）  
**Worktree**: `../deep-module-mapper-frontend-real-view`（分支 `feat/frontend-real-view`，已合并，未删除）

## What shipped

一个可运行的 `frontend/` React 应用（现实视图），实现「路径输入 → 轮询扫描 → React Flow 渲染模块图」：

- **ScanForm**：本地目录路径输入 + 提交（空路径禁用）。
- **useScanJob 轮询状态机**：`POST /api/scan` 拿 jobId → 每 2s `setTimeout` 链式轮询 `/status` → `done` 后取 `/graph`。状态含 `idle/scanning/done/empty/error/jobLost/networkError/timeout`；暂态失败容忍 3 次；60s 超时；可取消。
- **graphToFlow 转换**：modules → 圆角矩形节点；**externalModules → 灰色虚线节点**（不评分）；同模块对多 kind 边**聚合为一条**（label 合并，sites 全保留）；悬空边过滤；空图分支。
- **depthScore 评分**：naive `maxLine/portCount`，阈值 50/15，零端口判浅；绿/黄/红 = `#34d399/#fbbf24/#f87171`。
- **ModuleNode**：每模块左右各一个 Handle（模块级 source/target，非 per-port，见偏差声明）。
- **Inspector**：右侧固定面板，展示模块路径/端口签名/深度分、依赖 kinds 与调用点、诊断列表。
- **测试**：`frontend/src/__tests__/`（ScanForm / depthScore / graphToFlow / useScanJob，MSW mock，含 404、getGraph 失败、空图、暂态重试用例），共 **18 项**。
- **fixture**：`frontend/src/__tests__/fixtures/sample_pkg.graph.json`（真实扫描产物，供测试与评分校准）。

## Locked decisions

详见 `wayfinder/design-doc-issue-7-frontend-real-view.md`（§3）与 `wayfinder/grilling-decisions/issue-7-frontend-decisions.md`。要点：

| Decision | Choice |
|---|---|
| Dev server 端口 | **5175**（`vite.config.ts`，非 Vite 默认 5173） |
| 框架/构建 | Vite 8.2.2 + React 19.2.8 + TypeScript + `@xyflow/react` 12.11.5 |
| 评分 | naive `maxLine/portCount`，50/15 暂定（附录 A 有真实分布观测） |
| 布局 | 简单网格（间距常量导出，dagre 留后续） |
| 样式 | CSS Modules + CSS 变量（原型暗色调色板） |
| 轮询 | `setTimeout` 链式 + 暂态失败计数 + 超时/取消 |
| 外部模块 | 灰色虚线节点，不评分（方案 A，用户确认） |
| 把手语义 | **每模块左右各一个 Handle**（模块级，非「per public port」，用户书面确认的偏差） |
| 同对多边 | 按 `(source,target)` 聚合为一条 |

## Verification

```bash
cd frontend
npm test          # 18 passed（vitest）
npm run build     # tsc -b && vite build 成功
npx tsc --noEmit  # 0 errors
```

端到端（真实后端 `backend.backend.app:app` + `sample_pkg` fixture，Playwright）：
- 输入路径 → 轮询 → 渲染 **6 节点**（4 内部 + 2 外部 `third-party`），评分/端口/诊断正确，无控制台错误。
- 后端实测：4 modules / 17 ports / 15 edges / 2 external / 3 diagnostics。

后端启动注意：从仓库根目录须用 `python -m uvicorn backend.backend.app:app`（`backend.app:app` 会报 `Could not import module`）。

## Known risks and limits

1. **评分 naive**：`maxLine` 代理实现厚度有已知偏差（端口集中在头部的大文件判浅、小文件尾端口判深）；50/15 阈值仅基于 sample_pkg 观测（全浅区间），未覆盖中等/深区间。`depthScore.ts` 已注释；阈值用命名常量，方便后续校准。
2. **布局**：简单网格在大模块数时可能拥挤；dagre 分层布局留后续 ticket。
3. **CORS `["*"]`**：仅因后端绑定 `127.0.0.1` 可接受；收紧方式见 `frontend/README.md`（`BACKEND_CORS_ORIGINS`）。
4. **把手模块级**：非端口级连线；`edges[].targetPort` 字段已具备端口级连线的数据基础，未来可实现。
5. **真实 fixture 覆盖有限**：`sample_pkg` 是小 fixture，建议后续用真实规模代码库重扫校准附录 A。
6. **测试 fixture 基于 MSW**：`graphToFlow`/渲染测试用 mock，除真实 fixture 外未覆盖浏览器渲染快照。
7. **多 Python 解释器**：始终用 `python -m uvicorn`/`python -m pytest`，勿用裸命令。

## Next steps for the coordinator

1. **地图已同步**：issue #1（canonical map）已更新 #7 完成、#8 待分配（2026-08-26）。若统筹方有更细的里程碑拆分，可再调整。
2. **决定 #8 与后续关卡顺序**：候选 — 后端 AI endpoints（#8）、设计画布（自定义画布）、布局优化（dagre）、评分校准。
3. **是否删除已合并分支**：`feat/frontend-real-view` 已合并，如需清理请统筹方授权删除。
4. **可选**：对 `frontend/` 跑一轮 `/code-review`（相对 PR #9 的变更）再进入下一票。

## Completion criterion

本交接在统筹方确认地图已更新、并决定 #8/后续关卡分配后视为完成。
