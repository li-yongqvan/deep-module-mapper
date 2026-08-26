# #7 Build frontend real-view with React Flow — 评审意见书

> **评审对象**：《#7 Build frontend real-view with React Flow — 设计文档（供评审）》（`wayfinder/design-doc-issue-7-frontend-real-view.md`，2026-08-26）
> **评审方式**：独立复核 —— 以当前工作树 `deep-module-mapper-frontend-real-view` @ `640dec3` 为真值源，实测后端启动命令、Vite 脚手架输出、后端 API 行为、GitHub issue #7。
> **评审结论**：**有条件通过**

---

## 一、总体结论

设计方向与 issue #7 / handoff / 后端契约一致，范围收敛清晰（不做自定义画布、不做 AI、不改后端 API），决策记录格式规范，真值核对总体扎实。

但有两类问题必须在实现前钉死：

1. **两个阻塞项**（F1/F2）：文档里两条可直接执行的命令/声明与实测不符——后端启动命令从仓库根目录跑不起来；D5 声称的 "Vite 6 + React 18" 与 `npm create vite@latest` 实际输出不一致。逐字执行的 agent 会在这里翻车。
2. **若干执行前修补项**（F3–F7）：多为脚手架冗余、UI 边界、README 提醒，成本低但需明确。

总体评价：骨架可执行，事实基础可信；修掉阻塞项后即可作为实现基线。

---

## 二、事实与证据复核

复核范围：文档 §2 全部真值表、§3 决策依据、§5 命令与文件引用、§8 验证步骤。

### 2.1 核实为真

| 计划主张 | 复核结果 |
|---|---|
| `frontend/` 不存在 | ✅ `ls frontend` → `No such file or directory` |
| 当前分支 `feat/frontend-real-view`、工作区仅设计文档未跟踪 | ✅ `git branch --show-current` + `git status --short` 核实 |
| 后端路由 / 状态码 / 返回体与 §2.2 一致 | ✅ 实测 `POST /api/scan` 返回 `202 {jobId}`；`GET /api/scan/{id}/status` 返回 `done`；`GET /api/scan/{id}/graph` 返回 Graph JSON |
| `JobStatus` 枚举 `pending/running/done/error` | ✅ `backend/backend/store.py:12` |
| `Job` 字段 | ✅ `backend/backend/store.py:15-23` |
| Graph JSON 顶层 keys 为 `modules/ports/edges/externalModules/diagnostics` | ✅ 实测 `set(graph.keys())` 命中；`parser/schema.json:8` 一致 |
| CORS 默认 `["*"]` | ✅ `backend/backend/app.py:33` |
| Node.js v24.11.1 / npm 11.6.2 / pnpm 11.8.0 | ✅ 实测 |
| GitHub issue #7 open、阻塞 #5 closed、验收标准与文档一致 | ✅ MCP 读取核实 |
| `@xyflow/react` peerDependencies 支持 React ≥17 | ✅ `npm view @xyflow/react peerDependencies` 核实，React 19 可用 |
| 原型色板 CSS 变量与 §2.6 一致 | ✅ `wayfinder/prototype-ui.html:8-19` |

### 2.2 不实 / 冲突

| 计划主张 | 复核结果 |
|---|---|
| §2.5/§8.3 后端启动命令 `python -m uvicorn backend.app:app --reload --port 8123`「从仓库根目录执行」 | ❌ **实测失败**。仓库根目录下该命令报 `Could not import module "backend.app"`。正确命令应为 `python -m uvicorn backend.backend.app:app --reload --port 8123`，或进入 `backend/` 目录再执行原文命令。 |
| D5「**Vite 6 + React 18 + TypeScript**」 | ❌ **与实测冲突**。`npm create vite@latest frontend -- --template react-ts` 当前输出 Vite `^8.2.2`、React `^19.2.8`、React-DOM `^19.2.8`。 |
| §2.4「`ports`：扁平数组，每项在 `$defs.port` 基础上加 `moduleId`」 | ⚠️ **表述不精确**。该描述仅对**顶层** `ports` 数组成立；`modules[].ports` 中的端口项是 `$defs.port` 本身，**不含 `moduleId`**。实现若误从 `module.ports` 期待 `moduleId` 会出错。 |

### 2.3 不可复核

| 项 | 说明 |
|---|---|
| D1–D4「用户确认（2026-08-26）」 | 仓库 `wayfinder/grilling-decisions/` 下**无 issue-7 决策归档文件**（仅有 issue-3 / issue-5）。后续 agent/评审方无法独立核验该「用户确认」是否发生及具体内容。 |
| 未来 npm 包版本 | 当前实测只能代表 2026-08-26 的 registry 状态；若实现延迟，版本可能再次变化。 |

---

## 三、逐条评审

| 决策/选择 | 结论 | 评审意见 |
|---|---|---|
| D1 前端 dev server 端口 5175 | **认可** | 避开 5173/5176，与记忆一致。 |
| D2 naive 深模块评分公式 | **认可（附条件）** | 公式简单、handoff 允许 naive。阈值 50/15 需**在代码注释中标注「暂定」**，并在 README 说明这是第一近似。 |
| D3 简单网格布局 | **认可** | 与 handoff「simple grid」一致，降低依赖。 |
| D4 CSS Modules + CSS 变量 | **认可** | 与原型色板一致，零运行时开销。 |
| D5 Vite 6 + React 18 | **否决** | 与 `npm create vite@latest` 实际输出冲突。见 F2。必须改为「使用 create-vite 最新模板输出」或显式锁定版本。 |
| D6 useState/useCallback | **认可** | 本票状态规模小，合理。 |
| D7 Vitest + RTL + jsdom + MSW | **认可（附条件）** | 技术选型正确。**条件**：`vitest.config.ts` 必须显式设 `environment: 'jsdom'`，并在 MSW 测试中正确重置/清理。 |
| D8 npm | **认可** | 避免额外包管理器配置。 |
| D9 后端 CORS 维持默认 `["*"]` | **认可（附条件）** | dev 下可用。**条件**：README 中需加警告「生产环境请收紧 `BACKEND_CORS_ORIGINS`」。 |
| §6.1 模块左右各一个 Handle | **认可** | 对 handoff 字面语义的合理简化，实现简单、可测试。但必须在实现代码/PR 描述中显式说明「本票使用模块级把手，非端口级把手」。 |
| §6.2 `max(ports.line)` 代理实现厚度 | **认可** | naive 代理可接受，需在 `depthScore.ts` 注释中写明假设与局限。 |
| §6.3 轮询而非 WebSocket | **认可** | 后端无 WebSocket 支持，handoff 锁定 polling。 |

---

## 四、开放点裁决

### Q1 端口把手语义 —— **接受模块级简化**

认可每个模块左右各一个 Handle 的定案。要求：在 `ModuleNode.tsx` 注释或 PR 描述中明确写出「本票不按每个 public port 渲染 Handle；React Flow 中以模块级 source/target 表达依赖」。若未来 issue 需要端口级连线，再细化。

### Q2 代码行数代理合理性 —— **可接受，附说明义务**

`max(ports.line)` 作为 naive 代理足够。要求：在 `depthScore.ts` 顶部注释写明「实现厚度用最大 port 行号近似；端口分散在文件尾部但实现很薄的场景会误判」。

### Q3 评分阈值 —— **可接受，必须标注暂定**

50/15 作为暂定阈值可用。要求：阈值常量命名如 `DEPTH_THRESHOLD_DEEP`、`DEPTH_THRESHOLD_MODERATE`，并加 `// Naive thresholds; refine in follow-up issue` 注释。

### Q4 布局算法 —— **先网格，后续优化**

认可简单网格。要求：`layout.ts` 暴露列数/间距常量，便于后续替换为 dagre 时不重构调用方。

### Q5 CORS `["*"]` —— **接受，必须 README 警告**

当前 dev 可用。要求：`frontend/README.md` 中明确提醒「后端 CORS 默认 `["*"]`，仅供本地开发；生产环境请设置 `BACKEND_CORS_ORIGINS`」。

### Q6 `frontend/.gitignore` 冲突 —— **无冲突**

实测 Vite 生成的 `.gitignore`（`node_modules`、`dist`、编辑器文件等）与根目录 `.gitignore`（Python 相关）无重复或矛盾。无需修改。

### Q7 MSW + `import.meta.env` —— **可行，附配置条件**

Vitest 默认支持 `import.meta.env`。要求：`vitest.config.ts` 必须显式声明 `environment: 'jsdom'`，并在 MSW 测试的 `afterEach` 中调用 `server.resetHandlers()`，避免测试间污染。

---

## 五、新发现问题

| # | 级别 | 问题 | 要求 |
|---|---|---|---|
| F1 | **阻塞** | 后端启动命令在仓库根目录**无法执行**。文档 §2.5/§8.3 与 `backend/README.md:23` 均写 `python -m uvicorn backend.app:app --reload --port 8123`，但从仓库根目录实测报错 `Could not import module "backend.app"`。 | 设计文档 §2.5 与 §8.3 必须改为**可实际运行的命令**：`python -m uvicorn backend.backend.app:app --reload --port 8123`（从仓库根目录）；或在 `backend/` 目录下执行原文命令。由于红线要求不编辑 `backend/` 文件，设计文档必须自己给出正确命令，并注释说明 README 命令的 cwd 前提。 |
| F2 | **阻塞** | D5 声称「Vite 6 + React 18」，但 `npm create vite@latest` 当前安装的是 Vite 8 + React 19。逐字执行的 agent 将得到一个与决策记录不符的依赖矩阵。 | 二选一：① 更新 D5 为「使用 create-vite 最新模板（当前输出 Vite 8 + React 19）」；② 显式锁定版本，如 `npm create vite@6.0.0 frontend -- --template react-ts` 并手动降级 React 到 18。无论哪种，必须让命令与决策声明一致。 |
| F3 | 重要 | §5.2 步骤 3 安装 `@types/node`，但 Vite `react-ts` 模板已内置 `@types/node`。重复安装无害但冗余。 | 从安装列表中移除 `@types/node`，或保留但说明「模板已含，可省略」。 |
| F4 | 重要 | §5.2 步骤 4「配置 `vite.config.ts` 暴露 `VITE_BACKEND_URL`」具有误导性。Vite 自动暴露所有以 `VITE_` 开头的环境变量，无需额外配置；默认值已经在 `client.ts` 通过 `??` 兜底。 | 删除该步骤，或改写为「确认 `VITE_BACKEND_URL` 通过 `import.meta.env` 读取，无需额外 Vite 配置」。 |
| F5 | 重要 | 未处理**空 Graph** 边界：若扫描结果 `modules` 为空数组，React Flow 将收到空 nodes/edges。需保证 UI 不崩溃，并显示「未解析到模块」提示。 | 在 `App.tsx` 或 `graphToFlow.ts` 中对 `modules.length === 0` 增加显式分支。 |
| F6 | 重要 | §5.7 `Inspector` 位置描述为「右侧/底部」，属于 agent 必须自己发明的决策。 | 明确选择一种布局（推荐右侧固定宽度面板），并在组件/文档中写明。 |
| F7 | 建议 | D1–D4 的用户确认未归档到 `wayfinder/grilling-decisions/`。 | 实现会话后补充 `wayfinder/grilling-decisions/issue-7-frontend-decisions.md`，使后续 agent 可独立复核。 |
| F8 | 建议 | 手动验证步骤 §8.3 使用 master 工作树路径 `C:\Users\liyongquan\agent panel\deep-module-mapper\parser\tests\fixtures\sample_pkg`，但实现应在当前 worktree 验证。 | 改为当前 worktree 的相对路径，如 `parser/tests/fixtures/sample_pkg` 或 `backend/tests/fixtures/mini_pkg`，避免跨 worktree 依赖。 |

---

## 六、通过条件清单（执行前勾选）

- [ ] **F1**：设计文档 §2.5/§8.3 给出从仓库根目录可实际运行的后端启动命令，并说明 README 命令的 cwd 前提。
- [ ] **F2**：D5 与 `npm create vite@...` 命令一致（更新决策为最新模板，或显式锁定 Vite 6 + React 18）。
- [ ] **D2 附带**：评分阈值代码注释标注「暂定」。
- [ ] **D9/Q5 附带**：`frontend/README.md` 加入 CORS 收紧提醒。
- [ ] **Q7 附带**：`vitest.config.ts` 设 `environment: 'jsdom'`，MSW 测试加 `resetHandlers()`。
- [ ] **F5**：空 Graph 边界处理。
- [ ] **F6**：`Inspector` 布局明确为右侧或底部。
- [ ] **F8**：手动验证路径改为当前 worktree 内路径。
- [ ] **§6.1 附带**：代码/PR 说明模块级把手偏离 handoff 字面语义。
- [ ] **§6.2 附带**：`depthScore.ts` 注释写明 `max(line)` 代理假设与局限。

---

## 七、执行检查表（对抗协议 Pass 1/2 产出）

| # | 类别 | 可执行陈述 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | 命令 | `ls -la frontend` → 目录不存在 | ✅ 实测通过 | 工作树根目录 |
| 2 | 命令 | `git branch --show-current` → `feat/frontend-real-view` | ✅ 实测通过 | |
| 3 | 命令 | `git status --short` → 仅设计文档未跟踪 | ✅ 实测通过 | |
| 4 | 命令 | `python -m uvicorn backend.app:app --reload --port 8123` 从仓库根目录启动 | ❌ 实测失败 | 报错 `Could not import module "backend.app"` |
| 5 | 命令 | `python -m uvicorn backend.backend.app:app --reload --port 8123` 从仓库根目录启动 | ✅ 实测通过 | 后端可正常服务 |
| 6 | API 行为 | `POST /api/scan` → `202 {jobId}` | ✅ 实测通过 | |
| 7 | API 行为 | `GET /api/scan/{id}/status` → `done`/`error` | ✅ 实测通过 | |
| 8 | API 行为 | `GET /api/scan/{id}/graph` → Graph JSON | ✅ 实测通过 | |
| 9 | 命令 | `npm create vite@latest frontend -- --template react-ts` | ✅ 实测通过 | 生成可运行项目 |
| 10 | 依赖 | Vite 模板输出 React 版本 | ❌ 实测冲突 | 输出 React 19，非 D5 声称的 React 18 |
| 11 | 依赖 | `@xyflow/react` 支持 React ≥17 | ✅ 实测通过 | `npm view` 核实 |
| 12 | 命令 | `node --version` / `npm --version` / `pnpm --version` | ✅ 实测通过 | 与文档一致 |
| 13 | 远端 | GitHub issue #7 状态与验收标准 | ✅ 实测通过 | MCP 读取 |
| 14 | 代码 | `backend/backend/app.py:24-33` CORS 默认 `["*"]` | ✅ 实测通过 | |
| 15 | 代码 | `parser/schema.json:8` 要求顶层 5 keys | ✅ 实测通过 | |
| 16 | 代码 | `backend/backend/store.py:12` JobStatus 枚举 | ✅ 实测通过 | |
| 17 | 代码 | `wayfinder/handoff-build-frontend-real-view.md` 存在且被正确引用 | ✅ 实测通过 | |
| 18 | 代码 | `wayfinder/grilling-decisions/issue-7-*` 归档 | ⚠️ 无法实测 | 文件不存在，无第三方核验通道 |

---

## 八、结语

本设计文档在范围收敛、API 契约遵守、测试策略上整体可靠；最大风险不是架构，而是**文档里可直接执行的句子与真实环境对不上**（后端启动命令、Vite/React 版本）。这两处阻塞项修掉后，即可按 §5 进入实现。建议以 §六 清单作为 PR 自检表，并在实现完成后回填 §10 评审意见采纳记录。

—— 评审方（独立复核：工作树 `deep-module-mapper-frontend-real-view` @ `640dec3`，2026-08-26）
