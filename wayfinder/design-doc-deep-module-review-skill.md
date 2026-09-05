> 文档用途：交付专业评审 agent 的评审对象。范围 = 背景 / 真值核对 / 决策记录 / 实现方案 / 不变量 / 验证。
> 溯源约定：**事实**标来源（代码 `file:line` / DB 实查输出 / GitHub issue / grilling 用户确认）；**判断性裁决**单独标注【决策】并给出理由与备选，不冒充事实。
> 数据时点：2026-09-02（真值核对执行日）；**v2 增补数据时点：2026-09-04/05**（§11–§18）。
> 评审状态：v1 已评审通过（有条件通过，F1–F8 已解决，见 §10）并已实现（分支 `feature/deep-module-review-skill`）。**v2 设计已评审：有条件通过（2026-09-05，评审意见书 `wayfinder/design-doc-deep-module-review-skill-v2-评审意见书.md`），F1–F8 采纳记录见 §19，通过条件已全部落进设计文本，可进入实现。**

# 迁移 deep-module-mapper 为 Claude Code skill `/deep-module-review` —— 设计文档（供评审）

## §0 项目上下文（给零背景评审 agent）

**这是什么**：`deep-module-mapper` 是一个正在演进的代码库分析工具，目标从“独立 Web 应用”转向“轻量 Claude Code skill”。当前仓库位于 `C:/Users/liyongquan/agent panel/deep-module-mapper/`。

**当前技术栈与目录**：
- `parser/`：纯 Python 3.10+ 标准库 AST 解析器，无运行时第三方依赖（`parser/pyproject.toml:5`）。公共 API 为 `parser.scan_codebase(root_path)`（`parser/_scanner.py:18`），已提供 CLI `python -m parser <repo_path> [--output graph.json]`（`parser/__main__.py`）。
- `backend/`：Starlette + Uvicorn HTTP API（`backend/backend/app.py:1`），暴露 `/api/scan`、`/api/scan/{job_id}/status`、`/api/scan/{job_id}/graph`（`backend/backend/app.py:106-109`）；含内存 job store（`backend/backend/store.py`）和 Pydantic 模型（`backend/backend/models.py`）。另含 `backend/backend/aggregate/`：AI 聚合 CLI，用于把文件聚合成功能原子并输出 manifest。
- `frontend/`：Vite + React 19 + TypeScript + `@xyflow/react` 的 Web 应用，含现实视图、功能视图、重组画布（拖拽/连线）、Inspector、Toolbar 等。`frontend/src/lib/depthScore.ts` 含深度评分启发式阈值；`frontend/src/lib/aggregateEdges.ts` 含边聚合逻辑；`frontend/src/lib/recompose/detect.ts` 含 Tarjan SCC 循环检测与孤儿三分类。

**项目文档约定**：
- `wayfinder/map.md` 为项目状态地图，镜像 GitHub issue #1。
- 设计文档采用 §0–§10 结构；关键决策落档 `wayfinder/grilling-decisions/`。
- 已有 skill 示例：`temporary-coordinator`（`.claude/skills/temporary-coordinator/SKILL.md`）。

**与本票相关的前序工作**：
- issue #21（模块级循环/孤儿检测）刚完成（PR #23，mergeCommit `f491927`，2026-09-02）。
- issue #22（现实视图/功能视图重设计）尚未开始。
- GitHub issue #1 为项目地图，当前 state=OPEN（§2.4）。

## §1 背景与目标

- **需求来源**：用户反思后认为当前项目已偏离初衷（2026-09-02 对话）。原设想是**轻量工具**用于监测开发进度与保证模块设计深度，但项目已膨胀为独立 Web 应用，维护成本高、与开发上下文割裂。
- **目标**：将项目降级/迁移为一个 Claude Code skill `/deep-module-review`。
  - 触发：用户每完成一个开发阶段，在 Claude Code 中输入 `/deep-module-review [path]`。
  - 输出：一个 HTML Artifact，包含可视化架构图与 AI 主动给出的评审结论。
  - 关注点：是否符合深模块思想、依赖是否简洁、模块深度是否足够。

## §2 真值核对（数据来源，全部可复现）

### 2.1 代码真值：parser 现状

**验证命令**（2026-09-02 执行）：

```bash
cd "C:/Users/liyongquan/agent panel/deep-module-mapper"
python -m parser "C:/Users/liyongquan/agent panel/deep-module-mapper/parser/tests/fixtures/sample_pkg" --output sample-graph.json
python -c "import json; g=json.load(open('sample-graph.json')); print('keys:', list(g.keys())); ..."
rm sample-graph.json
```

**关键输出摘录**：

```text
keys: ['modules', 'ports', 'edges', 'externalModules', 'diagnostics']
modules: 4
ports: 17
edges: 15
externalModules: 2
diagnostics: 3
```

→ **事实：`python -m parser` CLI 可用，输出结构含 5 个顶层键**，与 `parser/schema.json` 及既有设计文档一致。

**parser 运行时依赖**（`parser/pyproject.toml:1-8`）：

```toml
[project]
name = "deep-module-mapper-parser"
requires-python = ">=3.10"
```

→ **事实：parser 无第三方运行时依赖**，仅依赖 Python 3.10+ 标准库。

**parser 测试回归**（2026-09-02 执行）：

```bash
python -m pytest parser/tests -q
```

输出：

```text
39 passed in 0.10s
```

→ **事实：parser 现有 39 个测试全部通过。**

### 2.2 代码真值：backend HTTP API 层

**文件存在性**（2026-09-02 执行 `ls -la backend/backend/`）：

```text
app.py        # Starlette ASGI 应用
models.py     # Pydantic 请求/响应模型
scanner.py    # 后台扫描 worker
store.py      # 内存 job store
aggregate/    # AI 聚合 CLI（独立于 HTTP API）
```

`backend/backend/app.py:106-109` 暴露路由：

```python
routes = [
    Route("/api/scan", scan_endpoint, methods=["POST"]),
    Route("/api/scan/{job_id}/status", status_endpoint, methods=["GET"]),
    Route("/api/scan/{job_id}/graph", graph_endpoint, methods=["GET"]),
]
```

→ **事实：backend 存在仅服务于 HTTP 轮询 API 的模块（app.py/models.py/scanner.py/store.py）。**

### 2.3 代码真值：frontend 现状

**文件存在性**（2026-09-02 执行 `ls frontend/src/`）：

```text
api/          # HTTP 客户端与扫描 API 封装
components/   # React 组件（ModuleNode、RecomposeCanvas、Inspector、Toolbar 等）
hooks/        # useScanJob
lib/          # 图转换、布局、评分、重组逻辑
manifest/     # 功能原子 manifest
__tests__/    # 16 个测试文件
```

→ **事实：frontend 是一个完整的 React/Vite 应用。**

**关键可复用逻辑**：

- `frontend/src/lib/depthScore.ts:22-24`：
  ```typescript
  export const DEPTH_THRESHOLD_DEEP = 50;
  export const DEPTH_THRESHOLD_MODERATE = 15;
  ```
  → 事实：深度评分阈值已定义为 DEEP≥50，MODERATE≥15。

- `frontend/src/lib/aggregateEdges.ts:26-56`：
  → 事实：边聚合逻辑按 `(source, target)` 分组，合并 `kinds`，保留原始边证据。

- `frontend/src/lib/recompose/detect.ts`：
  → 事实：含 Tarjan SCC 循环检测与孤儿三分类（isolated / third-party-only）。

### 2.4 工作区状态

**验证命令**（2026-09-02）：

```bash
git status --short
```

**输出摘录**：

```text
 M frontend/src/__tests__/Inspector.test.tsx
 M frontend/src/components/Inspector.tsx
 M frontend/src/lib/recompose/detect.ts
?? .claude/
?? .dagr/
?? "wayfinder/\347\273\237\347\255\271.md"
```

→ **事实：工作区存在 3 个未提交的 frontend 改动和若干 untracked 文件（含 `.claude/`、`.dagr/`、`wayfinder/统筹.md`）。**

### 2.5 GitHub 状态

**验证命令**（2026-09-02）：

```bash
gh issue view 1 --repo li-yongqvan/deep-module-mapper --json number,title,state
```

**输出摘录**：

```json
{"number":1,"state":"OPEN","title":"Deep Module Mapper — Wayfinder Map"}
```

→ **事实：项目地图 issue #1 当前为 OPEN 状态。**

## §3 Grilling 决策记录

| 编号 | 决策问题 | 定案 | 依据 |
|---|---|---|---|
| D1 | 项目形态：保持独立应用还是改成 Claude Code skill？ | **改成 Claude Code skill** | 用户确认（2026-09-02）。用户认为当前应用太重，希望轻量化、嵌入对话流。 |
| D2 | skill 名称 | **`/deep-module-review`** | 用户确认（2026-09-02）。 |
| D3 | 输出形式 | **HTML Artifact**（架构图 + AI 结论） | 用户确认（2026-09-02）。 |
| D4 | 重组画布（拖拽/连线/评审）是否保留？ | **删除**，仅保留 AI 结论与静态图 | 用户确认（2026-09-02）：重组画布是“锦上添花”，主要看 AI 结论。 |
| D5 | AI 是否主动给出结论？ | **是**，Artifact 顶部先呈现 AI 结论，图作为辅助 | 用户确认（2026-09-02）。 |
| D6 | AI 评审是否继续使用 DeepSeek/本地模型聚合 CLI？ | **否**，由生成图的 Claude 自身直接评审 | 用户确认（2026-09-02）：“直接让生成这个图的 AI 来帮助我评分”。本计划据此建议移除 `backend/backend/aggregate/`。 |
| D7 | v1 Artifact 架构图是否显示外部依赖节点？ | **否**，外部依赖仅在 metrics 表中汇总，图中只画模块间依赖 | 用户确认（2026-09-02），见 `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md` D7。 |

## §4 范围收敛与明确不做

| 项 | 决策 | 依据 |
|---|---|---|
| 保留 `parser/` Python 包 | 保留 | §2.1：已是独立 CLI，输出完整，测试通过。 |
| 保留 `parser/tests/` | 保留 | 解析器回归测试。 |
| 删除 `frontend/` 整个目录 | 删除 | D4：用户不再需要 React 应用与重组画布。 |
| 删除 `backend/backend/app.py`、`models.py`、`scanner.py`、`store.py` | 删除 | §2.2：仅服务于 HTTP API，skill 形态不需要。 |
| 删除 `backend/tests/test_api.py` | 删除 | HTTP API 测试随 API 移除。 |
| 删除 `backend/backend/aggregate/` | 删除 | D6：AI 评审改由 Claude 直接完成。 |
| 迁移 `depthScore.ts`、`aggregateEdges.ts`、`recompose/detect.ts` 算法到 Python | 复用到 skill | 这些逻辑 UI 无关，可在 skill 中复用。 |
| v1 不在图中渲染外部依赖节点 | 不做 | D7：保持 v1 简洁，外部依赖以表格汇总。 |
| 保留历史 Git 记录 | 保留 | 删除 frontend/backend 后仍可通过 Git 历史回查。 |
| 本次迁移不涉及 issue #22（视图重设计） | 不阻塞 | #22 是关于现实/功能视图重设计，skill 形态下这些视图不复存在，#22 将被迁移取代。 |

## §5 实现方案

### 5.1 清理工作区与打 tag

- **丢弃未提交改动**：3 个 frontend 改动（`frontend/src/__tests__/Inspector.test.tsx`、`frontend/src/components/Inspector.tsx`、`frontend/src/lib/recompose/detect.ts`）经用户确认直接丢弃（`git checkout -- ...`），因为 `frontend/` 将在迁移中整体删除。
- **`wayfinder/统筹.md`** 按项目协议保持本地 untracked，不进公共仓库。
- **打 tag**：在删除 frontend/backend 前，给旧应用状态打标签，便于回查：
  ```bash
  git tag archive/app-before-skill-migration master
  git push origin archive/app-before-skill-migration
  ```
- 从干净 master 切出迁移分支：`feature/deep-module-review-skill`（执行期由
  `feature/migrate-to-skill` 改名而来，内容相同）。

### 5.2 增强 parser：支持 `exclude_dirs`

- `parser/_scanner.py:18`：将 `scan_codebase(root_path)` 改为 `scan_codebase(root_path, exclude_dirs=None)`，并透传给 `_discover_files`。
- `parser/_external.py`：让 `_discover_files` 使用 `EXCLUDED_DIRS | set(exclude_dirs or [])`；默认 `EXCLUDED_DIRS` 增加 `.dagr/`（当前工作区已出现该 untracked 目录）。
- 保持向后兼容，现有 `parser/tests/` 继续通过（§2.1 已验证 39 passed）。
- **依据**：skill 需要排除 `.claude/`、`.dagr/`、`node_modules/`、`__pycache__` 等目录，避免自引用噪音。

### 5.3 创建 skill 目录与脚本

创建 `.claude/skills/deep-module-review/`：

```
.claude/skills/deep-module-review/
├── SKILL.md
├── scripts/
│   ├── analyze.py        # 主入口
│   ├── metrics.py        # 深度评分、边聚合、循环/孤儿
│   ├── digest.py         # 给 AI 的轻量摘要
│   ├── diagram.py        # inline SVG 架构图
│   └── template.html     # Artifact HTML 模板
└── tests/
    └── test_skill.py
```

**`metrics.py`**：
- 复用 `depthScore.ts` 阈值：DEEP≥50，MODERATE≥15，公式 `maxLine / portCount`。
- 复用 `aggregateEdges.ts` 的 `(source, target)` 分组逻辑。
- 复用 `recompose/detect.ts` 的 Tarjan SCC 与孤儿三分类。
- 输出每个模块的端口数、fanIn、fanOut、外部依赖数、深度评分、循环/孤儿标记。
- 输出 `metrics.json`。

**`digest.py`**：
- **迁移/适配 `backend/backend/aggregate/digest.py`**，而非从零重写。该文件已实现成熟的四级截断阶梯（no-docstrings / no-params / bare-ports / dropped-ports）和预算控制（`TOTAL_DIGEST_CHARS = 12000`、`API_TOTAL_DIGEST_CHARS = 40000`）。
- 适配点：
  - 移除对 Pydantic 的依赖（skill 保持零第三方依赖）。
  - 移除对 `frontend/src/manifest/feature-atoms.json` 的默认输出路径依赖。
  - 调整默认预算为 ~40K 字符。
  - 保留 `is_noise_module` 过滤逻辑。
- 输出 `digest.json`。

**`diagram.py`**：
- 使用 grid 布局生成 inline SVG。
- 节点按深度评分着色：深绿（deep）、琥珀（moderate）、红（shallow）。
- 箭头表示聚合后的模块间依赖。
- v1 不画外部依赖节点（D7）。
- 输出 `diagram.svg`。

**`analyze.py`**：
- **定位 repo root**：从脚本所在路径向上解析到 deep-module-mapper 仓库根目录（即 `parser/` 所在目录），将其加入 `sys.path`，然后 `from parser._scanner import scan_codebase`。
- **运行 cwd 要求**：从 deep-module-mapper 仓库根目录运行：
  ```bash
  python .claude/skills/deep-module-review/scripts/analyze.py <repo>
  ```
- 调用 `parser.scan_codebase(repo, exclude_dirs={".git", ".claude", ".dagr", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"})`。
- 调用 metrics / digest / diagram。
- 写入 `.claude/skills/deep-module-review/.last-review/`：
  - `graph.json`
  - `metrics.json`
  - `digest.json`
  - `diagram.svg`
- 打印结果路径 JSON。

**`SKILL.md`**：
- YAML front matter：`name: deep-module-review`，description 说明用途。
- Body 协议：
  1. 触发词 `/deep-module-review [path]`，默认当前工作目录。
  2. 执行 `python .claude/skills/deep-module-review/scripts/analyze.py <repo>`。
  3. 读取 `metrics.json` 与 `digest.json`。
  4. 使用系统提示词让 Claude 先给结论，再分项评审：深模块对齐性、依赖简洁性、模块深度分布、关键发现、建议。
  5. 填充 `template.html`，用 Artifact 输出。

**`template.html`**：
- 自包含 HTML，内联 CSS（light/dark 适配）。
- 占位符：`{{REPO}}`、`{{TIMESTAMP}}`、`{{SUMMARY_METRICS}}`、`{{DIAGRAM_SVG}}`、`{{AI_CONCLUSIONS}}`。

### 5.4 删除旧应用

- 删除 `frontend/` 整个目录。
- 删除 `backend/` 整个目录。
- 迁移 `backend/backend/aggregate/digest.py` 到 skill 时，同步迁移/改写 `backend/tests/test_aggregate_*.py` 中有价值的 digest 测试到 `.claude/skills/deep-module-review/tests/`。
- 更新 `.gitignore`：忽略 `.claude/skills/deep-module-review/.last-review/`。
- 重写根目录 `README.md`，说明 `/deep-module-review` 用法。

### 5.5 更新 wayfinder 文档

- `wayfinder/design-doc-deep-module-review-skill.md`：本文档。
- `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md`：落档 D1–D7。
- `wayfinder/handoff-deep-module-review-skill.md`：给执行 agent 的 handoff。
- `wayfinder/map.md`：
  - Destination 从“本地 Web 应用”改为“Claude Code skill `/deep-module-review`”。
  - 标记旧 frontend/backend/recompose/AI-aggregation 相关 ticket 被迁移取代。
  - Open frontier 加入 skill 实现与验证。

## §6 关键设计裁决（【决策】，含理由与备选）

### 6.1 删除 `backend/backend/aggregate/`，改由 Claude 直接评审

- **问题**：是否保留 DeepSeek/本地模型聚合 CLI？
- **定案【决策】**：删除 `backend/backend/aggregate/`，评审由 Claude 直接完成。
- **理由**：用户明确“直接让生成这个图的 AI 来帮助我评分”（D6）。保留聚合 CLI 会引入额外依赖、API 密钥、模型选择复杂度，与“轻量化”目标冲突。
- **备选（不选）**：保留 aggregate CLI 作为可选路径。不选原因：增加配置与维护负担，且用户已确认不需要。

### 6.2 v1 Artifact 不在图中渲染外部依赖节点

- **问题**：外部依赖（第三方库）是否需要在架构图中显示？
- **定案【决策】**：v1 不在图中画外部依赖节点，只在 metrics 表中汇总外部依赖数量。
- **理由**：用户核心关注是模块间关系与模块深度。外部依赖节点过多会 clutter 图表，分散注意力。v1 先最小可用，后续可迭代加入。
- **备选（不选）**：在图中用灰色虚线节点显示外部依赖。不选原因：v1 追求极简，且用户未明确要求保留该可视化。

### 6.3 删除整个 `frontend/` 和 `backend/`，而非保留为可选

- **问题**：旧应用代码是删除还是保留为“可选模式”？
- **定案【决策】**：直接删除。
- **理由**：保留可选模式会留下死代码、双套构建系统、双套测试，违背“轻量化”。Git 历史保留，可随时回查。
- **备选（不选）**：保留在 `legacy/` 目录。不选原因：增加维护与认知负担，且 Git 历史已足够回溯。

## §7 边界与不变量清单

| # | 不变量 | 防护层 | 依据 |
|---|---|---|---|
| 1 | `parser.scan_codebase` 保持向后兼容 | 默认 `exclude_dirs=None`，不传入时行为不变 | §5.2 |
| 2 | skill 不扫描 `.claude/`、`.dagr/`、`node_modules/` 等目录 | `analyze.py` 调用 parser 时传入 `exclude_dirs`；parser 默认 `EXCLUDED_DIRS` 也增加 `.dagr/` | D1、§5.2、§5.3 |
| 3 | 删除 frontend/backend 后 `parser/` 仍可独立运行 | 删除范围不包含 `parser/`，且 parser 测试回归 | §4、§2.1 |
| 4 | 深度评分阈值与既有设计一致 | Python 代码复用 DEEP=50、MODERATE=15 | `depthScore.ts:22-24`、§5.3 |
| 5 | 循环/孤儿检测算法与 #21 一致 | Python 代码复用 Tarjan SCC 与三分类 | `recompose/detect.ts`、§5.3 |
| 6 | 删除操作可回滚 | 迁移前打 tag；Git 历史保留 | §5.1、§6.3 |
| 7 | v1 不自动修改用户代码 | skill 只输出评审结论与图，不做自动重构 | D5 |

## §8 测试与验证计划

### 8.1 parser 回归

```bash
python -m pytest parser/tests -q
```

预期：39 passed（§2.1 已验证）。

### 8.2 skill 单元测试

```bash
python -m pytest .claude/skills/deep-module-review/tests -q
```

覆盖：
- 深度评分边界（0 端口 → shallow；ratio≥50 → deep；15–49 → moderate）。
- 边聚合正确性（同 `(source, target)` 合并 kinds）。
- 循环检测（2 节点环被检出）。
- 孤儿三分类（isolated、third-party-only、normal）。
- SVG 输出包含预期节点数。

### 8.3 端到端测试

```bash
python .claude/skills/deep-module-review/scripts/analyze.py \
  "C:/Users/liyongquan/agent panel/deep-module-mapper/parser/tests/fixtures/sample_pkg"
```

验证：
- `.last-review/graph.json` 存在。
- `.last-review/metrics.json` 含各模块深度评分。
- `.last-review/digest.json` 非空。
- `.last-review/diagram.svg` 为有效 SVG。

### 8.4 人工验证

在 Claude Code 中调用 `/deep-module-review`，确认：
- Artifact 正常渲染。
- 顶部显示 AI 结论。
- 架构图可见，节点按深度着色。

## §9 待评审焦点（Q1–Q2）

> 这些是作者认为最需要评审方盯住的点。

- **Q1**：深度评分阈值 50/15 是否继续沿用？skill 形态下是否应调整或允许用户配置？
  - 当前定案：v1 沿用 50/15（§5.3）。
  - 原因：保持与既有设计一致，避免在转型同时引入评分语义变化。
- **Q2**：迁移 `backend/backend/aggregate/digest.py` 时，是否应同步迁移其测试？
  - 当前定案：是（§5.4）。

## §10 评审意见采纳记录

| 评审项 | 结论 | 采纳落地 |
|---|---|---|
| **F1** 工作区 3 个未提交 frontend 改动未裁决 | 阻塞，属实 | 用户确认直接丢弃；已执行 `git checkout --` 清理工作区（§5.1）。 |
| **F2** D1–D6 用户决策未落档 | 阻塞，属实 | 已创建 `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md`（§5.5）。 |
| **F3** D7 需用户书面确认 | 重要，属实 | 用户确认 v1 不显示外部依赖节点；D7 已落档（§3、§5.5）。 |
| **F4** “迁移前打 tag”无具体命令 | 重要，属实 | §5.1 增补具体 tag 名与命令：`git tag archive/app-before-skill-migration master` 并 push。 |
| **F5** 建议复用 `aggregate/digest.py` 而非重写 | 重要，属实 | §5.3 明确 `digest.py` 迁移/适配 `backend/backend/aggregate/digest.py` 的四级截断阶梯与预算逻辑。 |
| **F6** `analyze.py` sys.path 与 cwd 不明确 | 重要，属实 | §5.3 明确 analyze.py 从脚本路径解析 repo root 加入 `sys.path`，运行 cwd 为仓库根目录。 |
| **F7** `.dagr/` 未加入 `exclude_dirs` | 重要，属实 | §5.2 在 parser 默认 `EXCLUDED_DIRS` 与 skill `exclude_dirs` 中均增加 `.dagr/`。 |
| **F8** 建议迁移 digest 相关测试 | 建议，采纳 | §5.4 明确同步迁移/改写 `backend/tests/test_aggregate_*.py` 中有价值的 digest 测试到 skill tests。 |

**推翻项**：无。

---

# v2 设计（2026-09-05 定稿）：Archify 模块地图 + 模块内下钻

## §11 v2 方向演变（时间线，全部有据）

v1 迁移在本分支实现完毕后，用户试用原型的反馈推动了三轮收敛：

| 日期 | 事件 | 依据 |
|---|---|---|
| 2026-09-03 | v1 基线确认迭代（`feature/deep-module-review-skill` 分支）；17 项 v2 grilling 完成（进度/Delta/理想偏离/增长曲线等监测维度） | grilling 会话 |
| 2026-09-03 | 健康面板原型（7 区块数据面板）被用户否决：**"我不需要这么多数据和趋势。我其实希望它能够产出的就是类似 archify 的图表"** → 数据面板/趋势/指标卡全线废弃，16 项 grilling 中的监测维度随之搁置 | 用户原话 |
| 2026-09-04 | Archify 渲染链路打通：v1 真实扫描数据 → architecture IR → archify deliver，showcase 档 9/9 检查通过，用户认可生产模块图视觉 | 原型 `dmm.html` |
| 2026-09-04 | 用户提出下钻需求："点开模块之后，面板应该再增添一个内部功能的循环路线，让我看一下这个模块所宣称的效果是如何实现的" | 用户原话 |
| 2026-09-04 | 下钻原型完成（可点击单文件页），id 映射 bug 修复后用户验收：**"对，就是这个效果"** | 原型 `prototype.html`，用户原话（2026-09-05） |

## §12 v2 产品定义

**产出 = 单文件 HTML「模块地图」**（`.last-review/map.html`），自上而下：

1. **主图**：Archify architecture 图（showcase 档），节点 = v1 同口径的生产模块（`metrics.py::is_production_module`），卡片带深度副标签与 `浅`/`扇出偏高` tag，外层 region 边界 = 包。
2. **下钻面板 ×N**：点主图模块卡片，页面内滑出该模块面板（同页切换，非跳转）：
   - **一句话效果承诺**（这个模块宣称干什么）；
   - **内部 workflow 泳道图**（Archify workflow 图）：节点 = 模块内真实函数，边 = 真实调用，泳道 = AI 给函数分的业务阶段；
   - **AI 解读**：效果如何实现（三两句）+ 循环回路位置说明；函数级环不存在时如实说明循环发生在文件级迭代（原型先例）。

**交付方式**【决策 V2-D11，评审 F7 采纳】：`map.html` 是**浏览器文件**，不是 Claude.ai Artifact——写入 `.last-review/map.html` 后提示用户浏览器打开。理由：Artifact 通道在本环境不可用（无 claude.ai 登录，v1 评审时已实测），且多面板单文件体积（本仓库 7 面板已 ~290KB）不适合塞进 Artifact。规模策略：单文件目标 ≤ 10MB；超出时只对 deep/moderate 模块生成下钻面板，shallow 模块降为纯文字行——该阈值策略记 TODO，实现时按实测调。

**AI 结论在 v2 的位置**【决策 V2-D1】：从 v1 的"Artifact 顶部主结论"降级——总评缩为主图下方一段简短文字，逐模块观点移入下钻面板的解读区。理由：用户明确只要"类似 archify 的图表"，其余信息按需下钻。

**决策记录**（完整版见 `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md` v2 节）：

| 决策 | 内容 |
|---|---|
| V2-D1 | 产出形态 = Archify 式架构图；数据面板/趋势废弃 |
| V2-D2 | v1 已实现分支作为迭代基线 |
| V2-D3 | 下钻内容 = 真实调用图为底 + AI 分组/阶段命名标注 |
| V2-D4 | 内部图版式 = Archify workflow 泳道图 |
| V2-D5 | 交互 = 单文件 HTML 同页内嵌面板（点卡片展开/切换） |
| V2-D6 | 捕获粒度 = 函数级（类方法暂不拆） |
| V2-D7 | 面板内容 = 承诺 + 泳道图 + AI 解读 + 循环说明 |
| V2-D8 | 2026-09-05 原型验收通过，冻结形态进入实现 |

## §13 v2 真值核对（2026-09-04/05，全部可复现）

### 13.1 parser 现状（扩展的必要性）

- `graph.json` 全部 80 条边中 `call` 类 40 条**全部跨模块**，模块内调用 0 条（实查 `.last-review/graph.json`）。
- `_edges.py:79` 已遍历 `FunctionDef`，但 `resolve_reference` 只对"解析到其他模块"的引用产生边；本地名命中 `module_defs`/`locals_` 时直接跳过（`_edges.py:307-308`）→ 模块内调用信息在现有管线中**主动丢弃**，必须新增采集。

### 13.2 Archify 现状（依赖与约束）

- 事实：Archify 装于 `~/.claude/skills/archify`（本机），组件 schema 无 click/link 字段，交付 HTML 为静态页（渲染器无事件监听；节点组自带 `data-node-id`/`role="button"`/`tabindex`）→ "点开"交互由 skill 自建 wrapper 实现。
- 交付命令：`node bin/archify.mjs deliver architecture|workflow <ir.json> <out.html> --quality standard|showcase --json`；workflow 的 `schema_version` 枚举为 [1, 2]，原型 IR 用 2。
- 约束（原型实测）：节点 id 禁前导下划线（`^[a-zA-Z][a-zA-Z0-9_-]*$`）、workflow `col ≤ 5`、同泳道同列节点禁重叠（<8px 间距即报错）、中文字符串经 GBK 控制台需 `subprocess(encoding="utf-8", errors="replace")`。

### 13.3 原型验证记录（`%TEMP%\dmm_v2_demo\`）

| 产物 | 结果 |
|---|---|
| `extract_intra.py` → `intra.json` | 7 模块 42 函数的真实函数级调用图提取成功（AST 原型） |
| 7 张 workflow 图（standard 档） | 全部 deliver 成功，9/9 检查通过 |
| 主图（architecture，showcase 档） | 手工布局十余次均卡几何交叉 → `hillclimb.py` 爬山搜索出**零诊断布局**，9/9 通过 |
| `prototype.html`（271KB 单文件） | 主图 + 7 面板，点击交互验收通过 |

### 13.4 原型教训（进实现要求）

1. **只抓 `Call` 会漏回调引用**：`_schema.py:108` 的 `sorted(key=_edge_sort_key)` 中 `_edge_sort_key` 是传参引用不是调用 → parser 扩展须同时抓"命中本模块 def 的实参 Name 引用"（原型图上该边为手工补注）。
2. **SVG 内嵌多图须去重内部 id**，但去重正则不能误伤 `data-node-id=` 尾部（原型 bug：`id="([^"]+)"` 把 `data-node-id="main"` 改写成 `"arch-main"`，面板映射失配、点击静默失效；已修为 `(?<=\s)id="..."`）。
3. **本仓库函数级调用图无环**（7 模块全 DAG）→ "循环路线"的诚实呈现 = 泳道分段表达迭代阶段 + 解读文字说明循环发生在文件级迭代；真实环出现时才高亮。

## §14 parser 扩展设计（v2 唯一的 parser 改动）

**目标输出**：每个模块一份模块内调用图，随 scan 结果一并产出：

```
intra: { <module_id>: { funcs: [{name, line}], calls: [{from, to, line}] } }
```

- **节点**：模块级 `def`/`async def`（公有+私有）各一节点；**类 = 单节点**（类名），方法不展开（V2-D6）；类方法体内对本模块函数的调用记为类节点的出边。
- **边**：① 函数体内对同模块其他函数/类的调用；② 模块顶层语句中的调用；③ **回调引用**——函数名以 Name 形式出现在实参位置（如 `sorted(key=f)`）且命中本模块 def（教训 §13.4-1）。
- **输出位置**【决策 V2-D9】：`scan_codebase` 返回 dict 增加**第 6 个顶层键 `intra`**，`parser/schema.json` 同步更新。理由：一次扫描一处产出，skill 侧直接消费；备选（独立 `intra.json` 文件）被否，因会打破"graph.json = 完整扫描结果"的既有心智。既有 5 键的**内容与顺序不变**（扩展实现为纯附加 pass，不动 `resolve_reference` 既有行为）。
- **契约同步清单**【评审 F1 采纳，实现时逐项执行】：
  1. `parser/tests/test_scan_codebase.py:22` 的精确 5 键断言**必须同步修改**——改为"既有 5 键内容逐项不变 + `intra` 键存在且形状正确"；这是评审发现的实锤矛盾点，不改则新增键与测试回归二选一。
  2. `parser/schema.json`：`properties` 增加 `intra`；`intra` **加入 `required`**（本 schema 描述本 parser 的输出，扩展后扫描必产 `intra`）；顶层 `additionalProperties: false` 保持。
  3. `README.md:31` 与 skill `SKILL.md` 中"5 个顶层键"的书面表述同步改为 6 键。
  4. 新增 **golden 单测**：扩展前后对同一 fixture 的 5 键输出逐字节一致（把"内容不变"从主张变成可验证断言）。
- **同名遮蔽消歧**【评审 F2 采纳】——宁缺勿幻，幻边会以"真实调用"误导评审：
  - 边①③（直接调用与回调引用）：该 Name 在引用点作用域内**未被绑定**才入边——至少排除"在宿主函数内被赋值或作参数名"的同名命中（沿用 `collect_local_names` 的名字并集，按宿主函数过滤）。
  - **属性调用不入边**：`obj.method()` 中 attr 恰好命中本模块 def 名的情况（如模块有 `def write_text` 则 `out.write_text(...)`）不采信，不画。
  - 内置名、导入名优先级高于本模块 def 同名命中（import 绑定遮蔽模块级定义）。
- **归属规则**【评审 F6 采纳】：嵌套 def **并入宿主节点**（不独立成节点，其体内调用记宿主出边）；lambda 体内调用归属宿主；条件分支内的 def 按 `ast.walk` 照常收录；模块级同名重定义（罕见）取首个定义并在 `diagnostics` 记一条，不静默。边②（模块顶层语句调用）**必须入图**——原型曾把顶层整体丢弃（`del funcs["<顶层>"]`），实现不得照抄。
- **数据形状**：`intra` = `{ <module_id>: {"funcs": [{"name","line"}], "calls": [{"from","to","line"}]} }`（扁平数组，非原型的嵌套 dict）——单测按此形状写。
- **排除口径**：`intra` 覆盖所有被扫描文件（含 tests/），与 modules 同口径——裁剪是 metrics 层（skill）的职责，parser 不裁（延续现有分层）。
- **性能**：每模块函数 O(几十)、边 O(几百)，`ast.walk` 线性扫描，无递归深度风险。

## §15 渲染管线设计（skill 侧改动）

```
analyze.py（不变）
  → metrics.py（不变，仍产 metrics.json / digest.json）
  → 新 to_archify.py：graph.json + metrics.json → 主图 architecture IR（确定性生成）
  → archify deliver ×(1 主图 + N 内部图)（外部进程调用，见依赖策略）
  → 新 assemble.py：摘各 deliver HTML 的 <svg> 与 <style>（内部 id 加前缀去重，§13.4-2），
      注入下钻面板 DOM 与点击 JS → .last-review/map.html
```

- **泳道/承诺/解读的来源**：AI（Claude）在运行时读 digest.json + 各模块源码后产出每模块的 workflow IR 片段（lanes/nodes/sublabel/承诺/解读），写入 `.last-review/panels/`，由 assemble.py 组装。SKILL.md 增补该步骤的产出规范。
- **Archify 依赖策略**【决策 V2-D10，评审 F5 补全契约】：探测顺序 = 环境变量 `ARCHIFY_DIR` → `~/.claude/skills/archify` → **且 `node --version` 可用**（三者任一缺失即降级；目录在而 node 缺失不许走"探测成功→子进程失败"的未定义路径）。降级产物 = **v1 四件套原样**（graph/metrics/digest.json + `diagram.svg` 填 `template.html`），无下钻面板，输出与提示中**明示**"未启用 Archify 模式"。降级不是错误路径，不抛异常、退出码为 0。
- **模块 id → archify 节点 id 映射**【评审 F3 采纳】：模块 id 形如 `parser/_edges.py`，不满足 archify id pattern（禁 `/` `.` 与前导 `_`）。映射规则：路径确定性拼接——目录段与文件名去扩展名后以 `__` 连接、每段 `_` 前缀剥除（`parser/_edges.py` → `parser__edges`）；**生成后必须查重断言，碰撞即报错**（不静默——`parser/_edges.py` 与假想 `parser/edges.py` 同映射为 `parser__edges` 属于真碰撞，报错优于面板错联）；模块完整原始 id 存入节点 sublabel 或随附映射表，保证面板可溯源。
- **质量档位与布局**【评审 F4 落 Q5 裁决】：主图 showcase，验证失败退 standard。布局 = to_archify.py 内置确定性布局优先；兜底搜索**固定随机种子**，几何交叉校验在**进程内自实现**（判据：archify 重叠最小间距 8px），兜底搜索阶段不再逐候选 spawn node 子进程，仅对最终布局跑一次 archify validate 确认。**布局结果缓存进 `.last-review/layout.json`**：存在且模块集合未变则直接复用——同仓库两次运行图样一致，前后可对比。内部图泳道/列由 AI 标注时给定（列 ≤5、同泳道不同列）。
- **样式合并兜底**【评审 F8 采纳】：assemble.py 合并各 deliver 的 `<style>` 块时先做一致性检查——当前实测各块字节级一致、无 `#元素id` 选择器，可安全去重；**不一致时改为全部顺序拼接**（后写覆盖先写）并在生成文件注释里说明该前提，防 archify 升级分化样式时静默失效。所有 node 子进程调用统一走带 `encoding="utf-8", errors="replace"` 的包装器（§13.2 GBK 教训，单测固化）。
- **红线不变**：全程只读被评审代码；archify 输出与中间 IR 均落 `.last-review/`，不污染用户仓库其他位置。

## §16 不变量（v2 增量后仍全部成立）

1. 只读评审，不改动被扫描代码。
2. `scan_codebase` 既有 5 键**内容不变**（扩展为纯附加 pass）；新增第 6 键 `intra` 按 §14 契约同步清单落地（test_scan_codebase 键断言更新 + schema.json `intra` 入 required + golden 单测验证 5 键逐字节一致）。
3. parser 零第三方运行时依赖不变（archify 是可选外部增强，进程调用，非 import 依赖）。
4. 既有 parser 测试断言不回归——唯 `test_scan_codebase.py:22` 的键断言按 §14 契约同步更新（评审 F1 实锤：精确 5 键断言与新增键互斥，必须改）；测试总数随新增单测增长。
5. 指标口径不变：生产模块范围、深度阈值 50/15、环/孤儿语义均沿用 v1。

## §17 验证计划

1. **parser 扩展单测**（放 `parser/tests/`，沿用现有 pytest 风格）：函数级提取、类=单节点、回调引用成边、顶层调用入图、跨模块不误收、`intra` 键形状与 schema 一致、**golden 测试（扩展前后 5 键输出逐字节一致）**、**shadowing 场景**（局部变量/参数与模块函数同名不成幻边、属性调用不入边、import 绑定遮蔽）、归属规则（嵌套 def 并宿主 / lambda / 条件 def / 同名重定义记诊断）。
2. **to_archify/assemble 单测**（skill 侧）：id 映射 sanitize、**id 碰撞检测断言**、col 钳制、面板 id 与 `data-node-id` 映射一致（防 §13.4-2 复发）、**样式块不一致时改拼接**、**subprocess 包装器编码参数**（防 GBK 回归）。
3. **端到端**：对本仓库跑 `/deep-module-review` → `map.html` 在浏览器打开 → 点开 7 个面板逐一核对函数/边数与 `intra` 数据一致。
4. **降级 e2e ×2**【评审 F5 采纳】：模拟 `ARCHIFY_DIR` 指向空目录、模拟 `~/.claude/skills/archify` 不存在——两条路径都应产出 v1 四件套 + 明示降级，退出码 0；另测 node 运行时缺失（PATH 无 node）同走降级。

## §18 开放点裁决（评审后 Q3–Q5 全部关闭）

- **Q3 archify 缺失降级**：**裁决 = 可接受，但降级契约写死**（评审方意见采纳）——产物清单、明示机制、node 运行时探测见 §15 V2-D10 补全；降级 e2e 见 §17.4。
- **Q4 `intra` 第 6 键消费方**：**裁决 = 同仓库内全部可同步改**——消费方清单经评审补全为 analyze.py / metrics.py / digest.py / `test_scan_codebase.py:22` / `parser/schema.json` / `README.md:31` / `SKILL.md`，逐项列入 §14 契约同步清单。
- **Q5 布局确定性**：**裁决 = 兜底搜索固定 seed + 布局缓存 `.last-review/layout.json` + 进程内几何校验**（见 §15）；"确定性生成"措辞已修正为"确定性布局优先、固定种子搜索兜底、结果缓存"。

## §19 v2 评审意见采纳记录（2026-09-05）

评审对象：本文档 §11–§18 @ `ddb4562`；评审方：独立评审 agent（全新上下文，实测复核）。
评审结论：**有条件通过**（意见书：`wayfinder/design-doc-deep-module-review-skill-v2-评审意见书.md`）。

| 评审项 | 结论 | 采纳落地 |
|---|---|---|
| **F1** V2-D9 兼容面不全：test:22 精确 5 键断言必炸；schema.json `additionalProperties:false` 与 `required` 去留未定；README/SKILL.md"5 键"表述；无 golden 兜底 | 重要，属实 | §14 增"契约同步清单"四项（test 断言改法 / schema `intra` 入 required / README+SKILL.md 表述 / golden 单测）；§16.2/16.4 措辞修正；§17.1 增 golden 项。 |
| **F2** 回调/属性捕获无同名遮蔽消歧，幻边误导评审；无 shadowing 测试 | 重要，属实 | §14 增"同名遮蔽消歧"：作用域未绑定才入边、属性调用不入边（宁缺勿幻）、import 绑定遮蔽模块 def；§17.1 增 shadowing 场景。 |
| **F3** 模块 id → archify id 映射未设计，sanitize 可碰撞致面板错联 | 重要，属实 | §15 增映射规则：确定性路径拼接（`parser/_edges.py`→`parser__edges`）+ 生成后查重断言（碰撞报错不静默）+ 原始 id 随图溯源；§17.2 增碰撞测试。 |
| **F4** "确定性生成"与随机重启爬山矛盾；逐候选 spawn node 不可扩展；两次运行图样不稳 | 重要，属实 | Q5 落裁决（§15/§18）：固定 seed、进程内几何校验（8px 判据）、仅最终布局跑一次 validate、布局缓存 `layout.json`；措辞修正。 |
| **F5** 降级路径零测试、产物形态未写明、探测不查 node 运行时 | 重要，属实 | §15 V2-D10 补全：探测加 `node --version`；降级产物 = v1 四件套 + 明示，退出码 0；§17.4 增降级 e2e ×3（空 ARCHIFY_DIR / 无 archify 目录 / 无 node）。 |
| **F6** 归属规则缺口（嵌套 def/lambda/条件 def/重名）；原型丢弃顶层调用、照抄漏边②；数据形状未定 | 建议，采纳 | §14 增"归属规则"表（嵌套并宿主 / lambda 归宿主 / 条件 def 收录 / 重名取首个并记诊断；顶层调用必须入图、明示不得照抄原型）；数据形状定为扁平数组。 |
| **F7** map.html 实为浏览器文件非 Artifact，转变未明说；单文件体积无上限策略 | 建议，采纳 | §12 增交付方式裁决（V2-D11：写文件+提示浏览器打开，不进 Artifact）+ 规模策略（≤10MB，超出只给 deep/moderate 出面板，阈值记 TODO）。 |
| **F8** 样式合并无"不一致"兜底；GBK subprocess 处理未固化 | 建议，采纳 | §15 增：样式块不一致时改全部拼接并注明前提；subprocess 统一 utf-8 包装器；§17.2 两项单测固化。 |
| 2.2-冲突① test:22 与不变量互斥（=F1 实锤） | 属实 | 并入 F1 落地。 |
| 2.2-冲突② "16 项 grilling"实为 17 项 | 属实 | §11 与 decisions 文件计数均改 17。 |
| 2.2-冲突③ "逐字节兼容"措辞过强 | 属实 | §16.2 改"内容不变 + golden 单测验证逐字节"。 |
| 2.3 不可复核（用户原话、试错次数、dmm.html 时点） | 采信落档 | decisions 文件为准；"十余次"改表述以产物为准；dmm.html 时点不改。 |

**推翻项**：无。五项重要发现全部在设计文本内修复，未推翻任何已验收的形态决策（V2-D1~D8）。

**实现顺序约束**（评审结语采纳）：golden 测试与契约同步先行，parser 扩展（§14）最后动——它是唯一影响既有契约的改动。
