> 文档用途：交付专业评审 agent 的评审对象。范围 = 背景 / 真值核对 / 决策记录 / 实现方案 / 不变量 / 验证。
> 溯源约定：**事实**标来源（代码 `file:line` / DB 实查输出 / GitHub issue / grilling 用户确认）；**判断性裁决**单独标注【决策】并给出理由与备选，不冒充事实。
> 数据时点：2026-08-26（真值核对执行日）。
> 评审状态：**有条件通过**（2026-08-26 合并审计：`wayfinder/issue-7-前端现实视图设计文档-合并审计报告.md`；B1-B5/M1-M8/m1-m10 修订全部采纳，见 §10）。本版为实现基线。

# #7 Build frontend real-view with React Flow — 设计文档（供评审）

## §0 项目上下文（给零背景评审 agent，先读本节）

**这是什么**：Deep Module Mapper 是一个「模块地图」工具，用于分析本地代码库并可视化模块、端口（公开函数/类/导出）与依赖关系。当前阶段聚焦 **现实视图**——把后端解析出的真实代码结构用 React Flow 画出来。

**技术栈与目录**：
- 后端：Python 3.10+，Starlette + Uvicorn，包装 `parser.scan_codebase()` 提供 HTTP API（`backend/backend/app.py`，注意包路径是 `backend/backend/`）。
- 解析器：Python，输出符合 `parser/schema.json` 的 Graph JSON（`parser/`）。
- 前端：**本票新建**，当前不存在（见 §2.1）。
- 设计/交接文档：`wayfinder/handoff-build-frontend-real-view.md`、`wayfinder/prototype-ui.html`、`wayfinder/design-data-schema.md`、`wayfinder/prototype-ui-interaction.md`。

**关键架构纪律**：
- 后端 API 契约已锁定，本票**零改动**（handoff §Decisions already locked、§Red lines）。注意：**红线禁止编辑 `backend/` 内文件**，因此后端启动命令由本设计文档自己给出正确形式（见 §2.5）。
- 前端负责把后端 Graph JSON 翻译成 React Flow 节点/边；所有数据转换在客户端完成。
- 工作必须在**独立 git worktree** 中进行（handoff §Worktree discipline、记忆 [[parallel-session-worktree-discipline]]）。

**术语速查**（来源：`UBIQUITOUS_LANGUAGE.md:7-35`）：
- **模块** = 实现 + 端口；一个 `.py` 文件对应一个模块。
- **端口** = 模块对外暴露的公开函数、类、`__all__` 导出。
- **依赖边** = 一个模块的端口使用另一个模块的端口。
- **深模块** = 接口小、实现厚；**浅模块** = 接口大、实现薄。
- **深度分** = 量化深/浅的分数；本次用 naive 启发式。

## §1 背景与目标

- **需求来源**：GitHub issue #7 —— https://github.com/li-yongqvan/deep-module-mapper/issues/7。
- **交接依据**：`wayfinder/handoff-build-frontend-real-view.md` §Steps、§Decisions already locked、§Red lines。
- **数据契约来源**：`wayfinder/design-data-schema.md`（Graph schema 与 API 契约，issue #2 定稿）与 `wayfinder/prototype-ui-interaction.md`（节点/端口/颜色决策）。
- **前序工作**：issue #5 / PR #6 已完成核心后端 API（handoff §Context pointers）。
- **目标**：在 `deep-module-mapper/frontend/` 下新建一个可运行的 React 应用，支持用户输入本地目录路径、轮询扫描状态、并用 React Flow 渲染模块图，节点按 naive 深模块分数显示绿/黄/红。

## §2 真值核对（数据来源，全部可复现）

### 2.1 代码库现状

| 项 | 验证命令/位置 | 结果 | 结论 |
|---|---|---|---|
| `frontend/` 不存在 | `ls -la frontend` | `ls: cannot access 'frontend': No such file or directory` | 属实：需从零创建 |
| 当前分支/工作树 | `git branch --show-current && git worktree list` | `feat/frontend-real-view`（独立 worktree `../deep-module-mapper-frontend-real-view`） | 属实：已在独立 worktree |
| git status | `git status --short` | 仅设计文档等未跟踪文件 | 属实 |

### 2.2 后端 API 契约（含错误响应，代码真值）

| 路由 | 位置 | 成功响应 | 错误响应 |
|---|---|---|---|
| `POST /api/scan` | `backend/backend/app.py:40-71,106-109` | `202 {jobId}` | 400 `invalid_json` / `invalid_request` / `path_not_found` |
| `GET /api/scan/{job_id}/status` | `backend/backend/app.py:74-81,108` | `{status, error?, details?}`，`status ∈ {pending,running,done,error}` | 404 `job_not_found` |
| `GET /api/scan/{job_id}/graph` | `backend/backend/app.py:84-103,109` | `done` 时返回 Graph JSON | 409 `job_not_ready`（竞态）；`error` 返回 500；未知 job 404 `job_not_found` |

错误响应统一形状：`{"error": string, "details": string}`（`app.py:36-37` 的 `_error_response`）。CORS：`app.py:24-33` 默认 `["*"]`，可被 `BACKEND_CORS_ORIGINS` 环境变量覆盖。

### 2.3 Job 生命周期（代码真值）

- `JobStatus` 定义：`backend/backend/store.py:12`。
- `Job` 字段：`backend/backend/store.py:15-23`（`id, status, path, result, error, details, created_at`）。
- 状态转换：`pending` → `running`（`_scan_worker`）→ `done` 或 `error`。
- `JobStore` 容量：`store.py:66-78` `_evict_if_needed` 仅驱逐 terminal（done/error）job；**当没有 terminal job 可驱逐时，上限 100 会被临时突破，`create()` 不会失败**。前端无需处理「扫描被拒绝」。
- **后端为内存 store**：进程重启（含 `--reload` 触发）会清空所有 job。`backend/README.md:30` 明示 reload 中断在途扫描。前端必须处理「轮询时 job 突然 404」。

### 2.4 Graph JSON Schema（代码真值）

来源：`parser/schema.json:1-105`

| 字段 | 类型/约束 |
|---|---|
| `modules` | 数组，每项 `{id, path, ports}`，`id` 为相对 posix 路径 |
| `ports`（顶层） | 扁平数组，每项在 `$defs.port` 基础上加 `moduleId` |
| `modules[].ports`（模块内） | 每项为 `$defs.port` 本身，**不含 `moduleId`**（m9：与顶层 `ports` 字段差异，实现须区分） |
| `$defs.port` | `{kind: function/class/export, name, line, signature, params, docstring?}` |
| `edges` | 数组，每项 `{source, target, targetPort?, kind, sites:[{line}]}`，`kind` 枚举见 `schema.json:49` |
| `externalModules` | 数组，每项 `{id, name, kind: "third_party"}` |
| `diagnostics` | 数组，每项 `{kind, moduleId, line, message}`，`kind` 枚举见 `schema.json:82` |

**关键事实（合并审计实证，B1/M3 依据）**：
- `parser/_edges.py:243-246` `_resolve_import_stmt` 的 `third_party` 分支产出 `Edge(source_id, <第三方模块名>, ...)` 且同时记入 `external=imp.name`；`_resolve_from_import`（`_edges.py:273-277`）与 `_edge_from_entry`（`_edges.py:330-334`）同理。
- 因此 **edges 的 target/source 可能指向 `externalModules` 的 id，而不是 `modules` 的 id**。`externalModules` 与 `modules` 是两个独立数组（`schema.json:7-8`）。
- `schema.json` **无 LOC（代码行数）字段**（M3 关键依据）。
- `edges[].targetPort` 字段存在（`schema.json:48`），为未来端口级连线提供数据基础（B2 备用论据）。
- 同一对模块可产出**多条不同 `kind` 的边**（`import` + `call` + `inheritance`…）（M2 依据，见 §2.4 上表 edges 定义 + `_edges.py` pass-2 多入口）。

### 2.5 后端启动命令（B4 修订，实测）

**正确命令（从仓库根目录执行，本设计文档与手动验证统一使用）**：

```bash
python -m pip install -e parser/ -e backend/
python -m uvicorn backend.backend.app:app --reload --port 8123
```

**B4 实证**：`backend/README.md:23` 写的是 `python -m uvicorn backend.app:app --reload --port 8123`，但从仓库根目录执行报 `Could not import module "backend.app"`（`app.py` 实际位于 `backend/backend/`）。**本设计文档必须给正确命令**（红线禁止编辑 `backend/README.md`）。`--reload` 会重启进程并中断在途扫描（`README.md:30`），长扫描/手动验证建议去掉 `--reload`。

### 2.6 视觉设计基线（代码真值）

来源：`wayfinder/prototype-ui.html`

- 暗色 CSS 变量：`prototype-ui.html:8-19`：`--bg #0f172a`、`--panel #1e293b`、`--panel-2 #334155`、`--text #f8fafc`、`--text-2 #94a3b8`、`--accent #38bdf8`、`--warn #f87171`（`.bad` 类引用 `var(--warn)`，见 `prototype-ui.html:120`）、`--good #34d399`、`--mid #fbbf24`、`--border #475569`。
- 节点样式：`prototype-ui.html:109-123`（宽度 160px、圆角 10px、padding 10px、边框按 `.good/.mid/.bad` 变色）。
- 端口样式：`prototype-ui.html:144-153`（10px 圆形、accent 背景、2px 边框、左右定位）。
- 边样式：`prototype-ui.html:154-159`（2px 描边、箭头标记）。
- **原型实际渲染为每节点一对 in/out 圆点**（B2 缓解事实，§6.1 依据）；`prototype-ui-interaction.md:21`「端口把手：小圆点，位于节点左右两侧」亦支持该简化。

### 2.7 环境可用性

| 工具 | 版本 | 验证命令 | 输出 |
|---|---|---|---|
| Node.js | v24.11.1 | `node --version` | `v24.11.1` |
| npm | 11.6.2 | `npm --version` | `11.6.2` |
| pnpm | 11.8.0 | `pnpm --version` | `11.8.0` |
| Python | 3.10+ | `python --version` | 已装（后端依赖） |

### 2.8 依赖版本实测（B5 修订）

| 包 | 实测版本 | 验证命令 |
|---|---|---|
| create-vite 最新模板 | **Vite `^8.2.2` + React `^19.2.8` + React-DOM `^19.2.8`** | `npm create vite@latest frontend -- --template react-ts`（2026-08-26 实测） |
| `@xyflow/react` | 最新 v12（peerDependencies 支持 React ≥17，React 19 可用） | `npm view @xyflow/react peerDependencies` |

**结论**：D5 修订为「使用 create-vite 最新模板输出（Vite 8 + React 19）」，不再锁定 Vite 6 + React 18（见 §3 D5 修订 + §5.2 版本回填）。

### 2.9 GitHub Issue 状态

来源：GitHub issue #7（MCP 读取，2026-08-26）。

- 状态：open，无标签，无 assignee。
- 阻塞项：issue #5（已关闭）。
- 验收标准：dev server 一键启动、路径输入、轮询、React Flow 渲染、红绿灯节点、hover/click 信息、诊断展示、README。

## §3 Grilling 决策记录

| 编号 | 决策问题 | 定案 | 依据 |
|---|---|---|---|
| D1 | 前端 dev server 端口 | **5175** | 用户确认（2026-08-26）；避免 5173/5176 潜在冲突 |
| D2 | 深模块评分公式 | **naive ratio**：`ratio = maxLine / portCount`；`ratio ≥ 50` 深绿，`≥ 15` 黄，`< 15` 红；`portCount === 0` 视为浅 | 用户确认（2026-08-26）；handoff 允许 naive；阈值暂定，§8.4 校准 |
| D3 | 节点自动布局 | **简单网格布局**（间距常量见 §5.5） | 用户确认（2026-08-26）；可预测、易测、无额外依赖 |
| D4 | 样式方案 | **CSS Modules + CSS 变量** | 用户确认（2026-08-26）；与原型色板一致、零运行时开销 |
| D5 | 前端框架/构建工具 | **Vite 最新模板 + React 19 + TypeScript**（2026-08-26 实测 create-vite 输出 Vite 8/React 19；B5 修订，原「Vite 6 + React 18」与实测冲突已废弃） | 本票决策；handoff 推荐 Vite 或类似轻量方案 |
| D6 | 状态管理 | **React useState/useCallback 组合** | 本票决策；本票状态规模小，无需 Redux/Zustand |
| D7 | 测试方案 | **Vitest + React Testing Library + jsdom + MSW**（`vitest.config.ts` 显式 `environment: 'jsdom'` + setup 文件） | 本票决策；Vite 官方生态 |
| D8 | 包管理器 | **npm** | 本票决策；Node 自带 |
| D9 | 后端 CORS | **保持默认 `["*"]` 不变**；README 注明收紧环境用 `BACKEND_CORS_ORIGINS` 覆盖 | 依据 `backend/app.py:24-33`；5175 在 `["*"]` 下无需改动 |
| D10 | 端口把手语义 | **每模块左右各一个 Handle**（左侧 target、右侧 source）；接受与 issue 字面「per public port」的偏差 | 用户确认（2026-08-26）；原型实证单对把手；PR 显式声明偏差 |
| D11 | 外部模块渲染 | **渲染为灰色虚线节点**，不参与评分、不显示端口 | 用户确认（2026-08-26）；第三方模块无深浅语义 |
| D12 | 同模块对多边 | **按 `(source,target)` 聚合为一条边**（label 合并 kinds，sites 全保留） | 本票决策；单把手布局下多边几何重合，聚合信息无损 |
| D13 | 轮询实现 | **`setTimeout` 链式调用**（非 `setInterval`），带 in-flight 守卫、暂态失败计数、超时与取消 | 本票决策；避免慢请求叠加 |

**决策归档（m5）**：本表决策将在实现会话后归档到 `wayfinder/grilling-decisions/issue-7-frontend-decisions.md`，供后续 agent 独立复核。

## §4 范围收敛与明确不做

| 项 | 决策 | 依据 |
|---|---|---|
| 自定义设计画布 | **不做** | handoff §Red lines、issue #7 Notes |
| AI 描述/评审 | **不做** | handoff §Red lines |
| 后端 API 修改 | **不做**（含不编辑 `backend/` 内任何文件） | handoff §Red lines；所有转换在客户端 |
| 模块保存/加载设计 | **不做** | 现实视图只读渲染 |
| 合并 issue / 删除分支 | **不做**，需用户授权 | handoff §Red lines |
| 复杂自动布局（dagre/elk） | **不做**，用简单网格 | D3；dagre 留后续 issue 跟踪 |
| Tailwind / styled-components | **不做**，用 CSS Modules | D4 |
| Redux / Zustand | **不做**，用内置状态 | D6 |
| 端口级连线（`targetPort` 精细化） | **不做**，本票用模块级单对把手 | D10；`targetPort` 字段已具备数据基础，未来可扩展 |

## §5 实现方案

### 5.1 准备独立 git worktree

1. 从主仓库创建 worktree：`git worktree add -b feat/frontend-real-view ../deep-module-mapper-frontend-real-view master`
2. 切换进 worktree，执行 `git status --short`（应为空）和 `git branch --show-current`（应为 `feat/frontend-real-view`）。
3. 依据：handoff §Worktree discipline、记忆 [[parallel-session-worktree-discipline]]。

### 5.2 前端脚手架

1. 在 worktree 根目录运行 `npm create vite@latest frontend -- --template react-ts`。
2. **版本回填**：脚手架完成后执行 `npm ls react vite` 与 `npm view create-vite version`，将**实际安装版本**回填 §3 D5 与 §2.8（审计 B5/M2：2026-08-26 实测输出 Vite 8 + React 19，与 D5 措辞对齐）。
3. 进入 `frontend/`，安装运行时依赖：`npm install @xyflow/react`。
4. 安装开发依赖：`npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom msw`（**不含 `@types/node`**——Vite `react-ts` 模板已内置，审计 m8）。
5. **配置 `vite.config.ts`**：
   - `server.port: 5175` 与 `preview.port: 5175`（B3）。
   - **不额外配置 `VITE_BACKEND_URL`**（审计 m7）：Vite 自动暴露所有 `VITE_` 前缀环境变量，默认值在 `client.ts` 用 `??` 兜底即可。
6. **配置 `vitest.config.ts`**：`test.environment = 'jsdom'`、`test.setupFiles = ['./src/test/setup.ts']`（D7、M6）。
7. **创建 `src/test/setup.ts`**（M6）：
   - 引入 `@testing-library/jest-dom`。
   - 配置 `msw/node` server：`beforeAll` 启动 / `afterEach` `server.resetHandlers()` / `afterAll` close；`onUnhandledRequest: 'error'`。
8. 依据：D5、D7、D8、D9、D13；环境可用性 §2.7；版本实测 §2.8。

### 5.3 类型与 API 层

1. `src/api/types.ts`：按 `parser/schema.json:1-105` 定义 `Graph`、`Module`、`Port`、`Edge`、`Diagnostic`、`ExternalModule`。**注意**：Edge 的 source/target 同时可能引用 `modules` 或 `externalModules` 的 id；`modules[].ports` 项不含 `moduleId`（§2.4 m9）。
2. `src/api/client.ts`：
   - `BASE_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8123'`
   - 统一 `fetch` 封装，处理 `Content-Type`、HTTP 错误、解析 `{error, details}`（§2.2 错误契约）。
3. `src/api/scan.ts`：
   - `startScan(path)` → `POST /api/scan`
   - `getStatus(jobId)` → `GET /api/scan/:jobId/status`
   - `getGraph(jobId)` → `GET /api/scan/:jobId/graph`
4. 依据：后端契约 §2.2。

### 5.4 扫描与轮询状态机（M1 补全）

1. `src/hooks/useScanJob.ts` 状态机：
   - `{ kind: 'idle' }`
   - `{ kind: 'scanning', jobId, status, retries }`
   - `{ kind: 'done', jobId, graph }`
   - `{ kind: 'error', jobId, error, details }`（扫描本身失败）
   - `{ kind: 'jobLost', jobId }`（404 `job_not_found`，提示重新扫描）
   - `{ kind: 'networkError', jobId, message }`（确认的网络失败）
   - `{ kind: 'timeout', jobId }`（超过最大轮询时长）
   - `{ kind: 'empty', jobId, graph }`（`modules.length === 0` 空 Graph，M5）
2. 轮询流程（D13）：
   - `start(path)`：调用 `startScan` 获取 `jobId`，进入 `scanning`。
   - 使用 **`setTimeout` 链式调用**，每次请求完成后调度下一次（间隔 2000ms），避免慢请求叠加。
   - in-flight 守卫：同一时间仅一个状态请求在途。
   - **暂态失败计数**：网络失败或 5xx 时 `retries + 1`；`retries < 3` 继续轮询，`retries ≥ 3` 进入 `networkError`。
   - **404 `job_not_found`**：直接进入 `jobLost`（后端重启场景，重试无意义）。
   - **`status === 'done'`**：调用 `getGraph`；若 `getGraph` 失败（409 竞态/500/404）→ 按暂态失败计数重试，超限进入 `error`。
   - **`status === 'error'`**：进入 `error`，携带 `error`/`details`。
   - **超时**：最大轮询时长 60s（30 次）；超时进入 `timeout`。提供 `cancel()` 供「放弃等待」按钮调用。
   - 组件卸载或重新提交时清理 pending timeout 与 in-flight 请求。
3. 依据：M1 修订、D13；后端状态机 §2.3。

### 5.5 图数据转换、外部模块、多边聚合与空图

1. `src/lib/depthScore.ts`（D2）：
   - 输入 module + 其 ports，输出 `'deep' | 'moderate' | 'shallow'` 及颜色。
   - `portCount === 0` → `'shallow'`。
   - 代码注释标「naive、暂定、已知偏差」（M3，handoff Steps §4 要求）。阈值用命名常量 `DEPTH_THRESHOLD_DEEP` / `DEPTH_THRESHOLD_MODERATE`，注释 `// Naive thresholds; refine in follow-up issue`。
2. `src/lib/graphToFlow.ts`：
   - 输入 `Graph`，输出 `{ nodes, edges }`。
   - **内部模块节点**：每个 `module` 生成 `Node`（type `'moduleNode'`），data 含 module、ports、评分、诊断。
   - **外部模块节点**（D11/B1）：每个 `externalModules` 项生成 `Node`（type `'externalNode'`，灰色虚线、不评分）。
   - **多边聚合**（D12/M2）：按 `(source, target)` 分组 edges；每组聚合为一条 React Flow 边，`label` 合并所有 kinds（如 `import, call`），`data` 保留全部原始 edges 与 sites。
   - **悬空边防护**：过滤 source 或 target 既不在内部节点也不在外部节点中的边（不变量 7）。
   - **空 Graph 分支**（M5）：若 `modules.length === 0` 返回空 nodes/edges，UI 显示「未解析到模块」提示（`empty` 态，§5.4）。
3. `src/lib/layout.ts`（D3，Q4 修订）：
   - 网格间距常量：`NODE_WIDTH = 160`、`GAP_X = 40`、`GAP_Y = 40`；每行 `floor(viewportWidth / (NODE_WIDTH + GAP_X))` 个节点（或按节点总数固定 6 列），通过常量导出便于后续替换 dagre。
   - 内部节点与外部节点统一参与网格排列。
4. 依据：B1、M2、M3、M5 修订；D2/D3/D11/D12；schema §2.4。

### 5.6 自定义 React Flow 节点与边

1. `src/components/ModuleNode.tsx`：
   - 圆角矩形节点（160px、10px radius、padding 10px）。
   - 边框颜色按评分（`--good/--mid/--warn`）。
   - 左侧一个 `Handle type="target"`，右侧一个 `Handle type="source"`（10px 圆、accent 色、2px 边框）（D10）。
   - 显示模块名、端口数、评分颜色。**注释声明**「本票不按每个 public port 渲染 Handle；以模块级 source/target 表达依赖」（B2/Q1 附带）。
2. `src/components/ExternalNode.tsx`：灰色虚线边框节点，显示模块名，无 Handle、无评分（D11）。
3. `src/components/PortHandle.tsx`：封装小圆点把手样式。
4. `src/components/EdgeWithLabel.tsx`：在边中部显示聚合后的 `kinds` label；Inspector 展示全部原始 sites。
5. 依据：原型样式 §2.6；D10/D11/D12。

### 5.7 主页面与交互

1. `src/App.tsx`：
   - 顶部：`ScanForm`（路径输入 + 提交）+ `ScanStatus`（状态/错误展示）。
   - 主区域：`ReactFlow` 画布，注册 `nodeTypes.moduleNode` 与 `nodeTypes.externalNode`，背景用暗色网格。
   - **`Inspector` 布局（M8 定案）**：固定**右侧面板**（宽度 280px），点击节点/边时显示详情（模块路径、端口列表、依赖 kinds、诊断；外部模块显示名称）。
   - 空 Graph（`empty` 态）显示「未解析到模块」提示（M5）。
   - 扫描状态为 `jobLost` / `networkError` / `timeout` 时显示相应提示与「重新扫描」入口。
2. `src/components/ScanForm.tsx`：受控输入，空路径禁用提交按钮。
3. `src/components/ScanStatus.tsx`：根据 `useScanJob` 状态展示 pending/running/done/error/jobLost/networkError/timeout/empty。
4. `src/components/Inspector.tsx`：右侧固定面板，展示节点/边/diagnostic 详情。
5. 依据：issue #7 验收标准；handoff §Steps 5；M1/M5/M8 修订。

### 5.8 全局样式

1. `src/index.css`：
   - 定义 `:root` 暗色变量（与原型 §2.6 一致）。
   - 导入 `@xyflow/react/dist/style.css`。
   - 覆盖 React Flow 默认节点/边样式以匹配暗色主题。

### 5.9 文档

1. `frontend/README.md`：安装命令、启动命令（端口 5175）、测试命令、后端依赖说明（含 `BACKEND_CORS_ORIGINS` 收紧提示，D9；后端启动正确命令 §2.5）、验证用 fixture 路径（**当前 worktree 相对路径**，m6）。
2. 依据：handoff §Steps 6；issue #7 验收标准「README updated」。

## §6 关键设计裁决（【决策】，含理由与备选）

### 6.1 端口把手数量与位置（B2，用户已确认）
- **问题**：issue 字面要求「per public port」，但原型实证为每节点一对把手。
- **定案【决策】**：每模块**左右各一个 Handle**（左侧 target、右侧 source）。
- **理由**：与原型 `prototype-ui.html` 实际渲染一致（B2 缓解事实）；单把手在 React Flow 中是合法锚点；实现简单、可测试、不遮挡节点内容。用户已明确确认（D10，2026-08-26）。
- **偏差声明**：与 issue #7「ports are small circular handles」及 handoff「one small circular port handle per public port」字面存在偏差，**PR 描述中必须显式声明此偏差及理由**。
- **备选（不选）**：为每个端口动态创建 Handle（更符合字面，但增加布局复杂度和测试成本，本票收益低）。
- **扩展性**：`schema.json` 的 `edges[].targetPort` 字段已存在，未来端口级连线无需改后端。

### 6.2 代码行数代理（M3）
- **问题**：模块没有直接返回行数字段，如何估算实现厚度？
- **定案【决策】**：用 `ports` 中最大 `line` 作为实现厚度代理（`maxLine = max(ports.line)`）。
- **理由**：`schema.json` 无 LOC 字段（§2.4 已实证），红线不允许改后端加字段；`maxLine` 可近似反映文件长度；零端口时直接判浅。本票允许 naive。
- **已知偏差（代码注释须声明）**：① 端口集中在文件头部的大文件会被系统判浅；② 小文件尾部恰有一个端口会被判深。50/15 阈值暂为拍脑袋值，**§8.4 用真实分布校准并回填附录 A**。
- **备选（不选）**：前端读取本地文件统计真实行数（需要 file API 或后端新接口，扩大范围）。

### 6.3 轮询而非 WebSocket
- **问题**：实时状态更新用轮询还是 WebSocket？
- **定案【决策】**：每 2 秒轮询 `GET /api/scan/:jobId/status`，`setTimeout` 链式实现（D13）。
- **理由**：后端无 WebSocket 支持；handoff 与 issue #7 明确锁定 polling。
- **备选（不选）**：为后端加 WebSocket/SSE（改后端契约，违反红线）。

### 6.4 后端 CORS 维持默认（D9）
- **问题**：前端 port 选 5175 后是否需要更新 backend CORS origins？
- **定案【决策】**：**不更新**，保持 `backend/app.py:33` 默认 `["*"]`。
- **理由**：`["*"]` 已覆盖 5175；若后续收紧，README 注明用 `BACKEND_CORS_ORIGINS` 覆盖（D9）。
- **备选（不选）**：把 5175 写进 `backend/app.py` 默认 origins 和 README（编辑 backend 文件，违反红线）。

### 6.5 外部模块渲染策略（B1，用户已确认）
- **问题**：edges 可能指向 `externalModules` 而非 `modules`，如何避免悬空边？
- **定案【决策】**：将 `externalModules` 渲染为**灰色虚线节点**，不参与评分、不显示端口（D11）。
- **理由**：信息完整（保留第三方依赖的可见性），与内部模块视觉区分，避免 React Flow 悬空边报错。用户已明确确认方案 A（2026-08-26）。
- **备选（不选）**：过滤外部边并显示「已折叠 N 条外部依赖」（信息缺失，且不满足用户「渲染出来」的偏好）。

### 6.6 同模块对多边聚合（M2）
- **问题**：同一对模块可有多条不同 kind 的边（`import` + `call` 等），单把手布局下几何完全重合。
- **定案【决策】**：按 `(source, target)` 聚合为一条边，label 合并 kinds，data 保留全部原始 edges 与 sites（D12）。
- **理由**：信息无损（Inspector 展示全部 sites 与 kinds）；避免重叠边视觉歧义。
- **备选（不选）**：平行边偏移（多边视觉平行，但实现复杂、无明确收益）。

## §7 边界与不变量清单

| # | 不变量 | 防护层 | 依据 |
|---|---|---|---|
| 1 | 不修改后端 API 契约（含不编辑 `backend/` 文件） | 前端只做 client-side 转换 | §4、handoff §Red lines |
| 2 | 只在独立 worktree 中修改代码 | 开工第 0 步创建 worktree；提交前核对 `git branch` | handoff §Worktree discipline |
| 3 | 轮询在终态/卸载时停止 | `useScanJob` 终态清理 timeout；`useEffect` cleanup 再清一次 | §5.4 |
| 4 | 空路径不提交 | `ScanForm` 路径为空时禁用提交按钮 | §5.7 |
| 5 | 后端不可达时展示错误 | `api/client.ts` 捕获 fetch 异常；轮询暂态失败 3 次后进 `networkError` | §5.3/§5.4 |
| 6 | 节点不全部重叠在 (0,0) | `layout.ts` 网格布局为每个节点分配唯一 position | §5.5 |
| 7 | 不存在悬空边（source/target 无对应节点） | `graphToFlow` 过滤悬空边；外部模块渲染为节点 | §5.5、B1 |
| 8 | 同模块对多边不重叠 | 按 `(source,target)` 聚合为一条边 | §5.5、M2 |
| 9 | 零端口模块判为浅 | `depthScore.ts` 对 `portCount === 0` 返回 `'shallow'` | D2 |
| 10 | 外部模块不参与评分 | `ExternalNode` 无评分、无 Handle | D11 |
| 11 | 轮询不叠加慢请求 | `setTimeout` 链式 + in-flight 守卫 | D13、§5.4 |
| 12 | 扫描不无限轮询 | 60s 超时进 `timeout`；提供取消按钮 | M1、§5.4 |
| 13 | 空 Graph 不崩溃 | `graphToFlow` 空分支 + UI `empty` 态提示 | M5、§5.4 |
| 14 | 不实现自定义画布 | 仅渲染现实视图 | §4 |
| 15 | 不实现 AI 描述/评审 | 不调用 `/api/descriptions/*` 或 `/api/review` | §4、handoff §Red lines |
| 16 | 敏感操作需用户授权 | 本票不执行 merge/close/delete | §4 |

## §8 测试与验证计划

### 8.1 单元/组件测试

| 文件 | 场景 |
|---|---|
| `src/__tests__/ScanForm.test.tsx` | 输入路径并提交 → `onSubmit` 被调用；空路径 → 提交按钮禁用 |
| `src/__tests__/depthScore.test.ts` | 端口少+line 大 → deep；端口多+line 小 → shallow；零端口 → shallow |
| `src/__tests__/graphToFlow.test.ts` | mock Graph（**含 externalModules**，B1/M2）→ 内部/外部节点数量正确；同模块对多 kind 边聚合成一条；悬空边被过滤；空 modules → 空 nodes + `empty`；评分颜色写入 data |

### 8.2 集成测试

| 文件 | 场景 |
|---|---|
| `src/__tests__/useScanJob.test.tsx` | happy path：MSW mock `POST /api/scan` → jobId；status 序列 `pending→running→done`；`GET /api/scan/:jobId/graph` → mock graph。验证最终状态 `done` |
| `src/__tests__/useScanJob.test.tsx` | error path：status 返回 `error` → 状态 `error` 且含 `error/details` |
| `src/__tests__/useScanJob.test.tsx` | **404 path**（M1）：status 返回 404 `job_not_found` → 状态 `jobLost` |
| `src/__tests__/useScanJob.test.tsx` | **getGraph 失败 path**（M1）：status `done` 后 graph 返回 500 → 暂态失败重试，超限进 `error` |
| `src/__tests__/useScanJob.test.tsx` | 暂态失败计数：status 网络失败 2 次后成功 → 仍 `done` |
| `src/__tests__/useScanJob.test.tsx` | 空 Graph：graph 返回 `modules: []` → 状态 `empty`（M5） |

### 8.3 手动验证（m4 修订：去掉 `--reload` + 正确启动命令 B4）

1. 启动后端（从仓库根目录）：`python -m uvicorn backend.backend.app:app --port 8123`（**去掉 `--reload`**，避免长扫描被中断）
2. 启动前端：`cd frontend && npm run dev`（应起在 5175）
3. 浏览器访问 `http://localhost:5175`
4. 输入路径（**当前 worktree 相对路径**，m6）：`parser/tests/fixtures/sample_pkg`
5. 提交后观察状态从 pending → running → done，出现 React Flow 画布。
6. 检查：内部节点为圆角矩形且有颜色；**外部模块（第三方 import）显示为灰色虚线节点**；边有箭头、label 显示聚合 kinds；右侧 Inspector 显示详情；诊断可见。
7. 对 `backend/tests/fixtures/broken_pkg` 重复，确认错误/诊断被展示。
8. 停止后端再轮询 → 确认出现 `jobLost`/`networkError` 提示而非无限等待。
9. 空目录/无 Python 文件目录 → 确认 `empty` 态「未解析到模块」提示（M5）。

### 8.4 真实分布校准（M3/M7 修订）

1. 后端实跑一次（从仓库根目录，用 `backend.backend.app` 或直接调 parser）：扫描 `parser/tests/fixtures/sample_pkg` 与 `parser/` 自身。
2. 统计各模块的 `maxLine`/`portCount` 分布。
3. **把真实分布数据贴进附录 A**，按分布校准 D2 的 50/15 阈值并回填 §3。
4. 真实 Graph JSON 同时**存为前端测试 fixture**（如 `frontend/src/__tests__/fixtures/sample_pkg.graph.json`），供 `graphToFlow`/渲染测试基于真实数据（M7，避免手写 mock 污染）。

### 8.5 提交前自检

```bash
cd frontend
npm test
npm run build
```

## §9 待评审焦点（Q1-QN，已审计裁决）

> 已由合并审计 agent 逐条裁决（2026-08-26），裁决全部采纳，落地见 §10。

| 问 | 裁决 | 落地 |
|---|---|---|
| Q1 把手语义 | **有条件接受简化** → 已获用户书面确认 | D10（§3）；PR 声明偏差 |
| Q2 行数代理 | **接受，须校准并注释** | §6.2 已知偏差注释 + §8.4 校准 |
| Q3 阈值 50/15 | **暂不可用，须校准后回填** | §8.4 + 附录 A 回填 |
| Q4 布局 | **同意先网格**，须定义间距常量 | §5.5 网格间距常量 |
| Q5 CORS | **同意不改后端**，README 注明收紧方式 | D9 + §5.9 |
| Q6 .gitignore | **非问题** | 开工后 `git status --ignored` 核一下（m10） |
| Q7 测试环境 | **方向错了** → 补 setup 文件 | §5.2 setup.ts（M6） |

## §10 评审意见采纳记录（2026-08-26）

| 评审项 | 结论 | 采纳落地 |
|---|---|---|
| **B1** externalModules 边悬空 | 阻断，属实 | §5.5/§5.6 外部节点渲染（D11）；§8.1 含 external 用例；§7 #7/#10；布局计入外部节点 |
| **B2** 把手语义越权 | 阻断，有条件接受 | 用户确认 D10；§6.1 偏差声明；PR 声明 |
| **B3** 5175 端口未落地 | 阻断，属实 | §5.2 `server.port: 5175` + `preview.port` |
| **B4** 后端启动命令根目录不可执行 | 阻断，属实 | §2.5 改为 `backend.backend.app:app`；§8.3 统一 |
| **B5** Vite/React 版本与 D5 冲突 | 阻断，属实 | §2.8 实测 Vite 8/React 19；D5 修订；§5.2 版本回填 |
| **M1** 状态机缺失败分支 | 重要，属实 | §5.4 补全（jobLost/networkError/timeout/empty）；§8.2 补 4 用例；§7 #3/#11/#12 |
| **M2** 同对多边重叠 | 重要，属实 | §5.5 聚合（D12）；§6.6；§7 #8；§8.1 用例 |
| **M3** 评分代理偏差+阈值无据 | 重要，属实 | §6.2 已知偏差；§8.4 校准；附录 A |
| **M4** 错误契约遗漏 + store 表述 | 重要，属实 | §2.2 补错误表；§2.3 修正上限表述 |
| **M5** 空 Graph 边界 | 重要，属实 | §5.4 `empty` 态；§5.5 空分支；§7 #13；§8.2 用例 |
| **M6** 缺 setup 文件 | 重要，属实 | §5.2 `src/test/setup.ts` + vitest 配置 |
| **M7** mock 手写不可靠 | 重要，属实 | §8.4 真实 Graph JSON fixture |
| **M8** Inspector 位置未定 | 重要，属实 | §5.7 定案右侧固定面板（280px） |
| **m1** 变量名 `--warn` | 次要，采纳 | §2.6 修正 |
| **m2** 漏引 handoff 指定文档 | 次要，采纳 | §1/§0 补引用 |
| **m3** §2.6 行号偏差 | 次要，采纳 | §2.6 行号复核 |
| **m4** 手动验证带 `--reload` | 次要，采纳 | §8.3 去 `--reload` |
| **m5** 决策未归档 | 次要，采纳 | §3 决策归档到 `grilling-decisions/issue-7-frontend-decisions.md` |
| **m6** fixture 路径跨 worktree | 次要，采纳 | §8.3 改为当前 worktree 相对路径 |
| **m7** `VITE_BACKEND_URL` 表述误导 | 次要，采纳 | §5.2 删除额外配置步骤 |
| **m8** `@types/node` 冗余 | 次要，采纳 | §5.2 移除 |
| **m9** `modules[].ports` 字段差异 | 次要，采纳 | §2.4 分两行写明 |
| **m10** .gitignore | 非问题 | Q6 采纳结论 |

---

*本文档为实现基线。合并审计修订完成（2026-08-26），可进入实现（分支→脚手架→编码→测试→PR→用户授权→合并）。*

## 附录 A：评分阈值真实分布（M3 校准回填）

**实测数据**（2026-08-26，`parser/tests/fixtures/sample_pkg`，真实 Graph JSON 已存为 `frontend/src/__tests__/fixtures/sample_pkg.graph.json`）：

| module | ports | maxLine | ratio | score |
|---|---|---|---|---|
| `__init__.py` | 3 | 7 | 2.3 | shallow |
| `core.py` | 3 | 28 | 9.3 | shallow |
| `main.py` | 7 | 46 | 6.6 | shallow |
| `utils.py` | 4 | 28 | 7.0 | shallow |

**观测结论**：
1. sample_pkg 是小型 fixture（4 模块、端口密集），ratio 全落在 2.3–9.3，全部判「浅」——对小文件这是预期行为，未出现「小文件单端口判深」的误判案例。
2. 该样本**未覆盖** ratio ≥ 15 的区间，因此 50/15 阈值在真实项目（更大文件、更少公开端口）上的表现仍待校准。实现中阈值已用命名常量（`DEPTH_THRESHOLD_DEEP`/`DEPTH_THRESHOLD_MODERATE`）并在代码注释标注「naive、暂定」，后续可用更大的真实代码库重扫并回填本表。

