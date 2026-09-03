> **评审对象**：《迁移 deep-module-mapper 为 Claude Code skill `/deep-module-review` —— 设计文档（供评审）》
> **评审方式**：以本地仓库 `C:/Users/liyongquan/agent panel/deep-module-mapper/` @ `7352105`（master HEAD）为真值源，逐项实测与 grep 复核。
> **评审结论**：**有条件通过**

---

## 一、总体结论

设计方向与用户反思高度一致：从独立 Web 应用降级为轻量 Claude Code skill，保留 `parser/` 作为唯一扫描器，删除 frontend/backend，由 Claude 直接输出 Artifact 评审结论。文档事实基础扎实，parser CLI、输出结构、文件存在性、工作区状态、GitHub issue 状态均经实测或 grep 复核。

但有三类问题必须在动手前解决：
1. **执行入口不干净**：当前工作区有 3 个未提交的 frontend 改动，不处理直接切分支会污染迁移分支或丢失改动。
2. **两处设计裁决尚未获得用户书面确认**：v1 不在图中显示外部依赖节点（D7）、是否复用 `backend/backend/aggregate/digest.py` 的截断阶梯而非重写。
3. **删除 frontend/backend 的不可逆操作缺少明确的回滚锚点**：文档说“迁移前打 tag”，但未指定 tag 名与打 tag 命令。

总体评价：骨架可靠、证据链完整，修复阻塞项后可作为执行基线。

---

## 二、事实与证据复核

### 2.1 核实为真

| 计划主张 | 复核结果 |
|---|---|
| `python -m parser <repo> --output graph.json` 可用 | ✅ 实测通过。exit code 0，输出 `sample-graph.json`，含 5 个顶层键。 |
| parser 输出结构为 `{modules, ports, edges, externalModules, diagnostics}` | ✅ 实测通过。输出 `keys: ['modules', 'ports', 'edges', 'externalModules', 'diagnostics']`。 |
| parser 无第三方运行时依赖，仅 Python 3.10+ | ✅ `parser/pyproject.toml:5` 仅声明 `requires-python = ">=3.10"`，无 dependencies。 |
| parser 测试 39 passed | ✅ 实测通过：`python -m pytest parser/tests -q` → `39 passed in 0.10s`。 |
| backend 存在 HTTP-only 模块 `app.py/models.py/scanner.py/store.py` | ✅ `ls backend/backend/` 命中四文件；`app.py:106-109` 暴露 `/api/scan`、`/api/scan/{job_id}/status`、`/api/scan/{job_id}/graph`。 |
| frontend 是完整 React/Vite 应用 | ✅ `ls frontend/src/` 含 `api/`、`components/`、`hooks/`、`lib/`、`manifest/`、`__tests__/`。 |
| `depthScore.ts` 阈值 DEEP=50、MODERATE=15 | ✅ `frontend/src/lib/depthScore.ts:22-24` 逐字命中。 |
| `aggregateEdges.ts` 被多处复用 | ✅ grep 命中 `graphToFlow.ts:14`、`graphToFeatureFlow.ts:15`、`recompose/edges.ts:13` 及自身测试。 |
| `detect.ts` 被 RecomposeCanvas/Inspector/Toolbar 复用 | ✅ grep 命中 `RecomposeCanvas.tsx:46`、`Inspector.tsx:15`、`Toolbar.tsx:8` 及测试。 |
| 工作区存在 3 个 frontend 未提交改动 | ✅ `git status --short` 命中 `M frontend/src/__tests__/Inspector.test.tsx`、`M frontend/src/components/Inspector.tsx`、`M frontend/src/lib/recompose/detect.ts`。 |
| GitHub issue #1 状态为 OPEN | ✅ `gh issue view 1 ... --json state` 返回 `"state":"OPEN"`。 |
| `parser/_external.py` 的 `EXCLUDED_DIRS` 不含 `.claude/` | ✅ `parser/_external.py:15-17` 仅含 `.git/__pycache__/.venv/venv/node_modules/dist/build`，确实无 `.claude/`。 |
| `backend/backend/aggregate/digest.py` 存在成熟的截断阶梯 | ✅ `digest.py:8-13` 声明四级截断（no-docstrings / no-params / bare-ports / dropped-ports），预算 12000/40000 字符。 |

### 2.2 不实 / 冲突

无。

### 2.3 不可复核

| 项 | 说明 |
|---|---|
| 用户口头确认 D1–D6 | 确认发生在本会话对话中，已记录于 §3；但尚未落档到 `wayfinder/grilling-decisions/`。这是执行前必须补的落档动作，见 F2。 |
| #21 的 3 个未提交 frontend 改动的意图 | 无法从代码本身判断是收尾调整还是临时调试，需要用户拍板，见 F1。 |

---

## 三、逐条评审

| 决策/选择 | 结论 | 评审意见 |
|---|---|---|
| D1 改为 Claude Code skill | **认可** | 与用户反思一致，方向正确。 |
| D2 skill 名称 `/deep-module-review` | **认可** | 用户已确认。 |
| D3 输出 HTML Artifact | **认可** | 用户已确认，且与 skill 形态匹配。 |
| D4 删除重组画布 | **认可** | 用户明确“锦上添花”，删除合理。 |
| D5 AI 主动给结论 | **认可** | 用户已确认。 |
| D6 删除 AI aggregation CLI，改由 Claude 直接评审 | **认可** | 用户“直接让生成这个图的 AI 来评分”已确认方向。 |
| D7 v1 不在图中画外部依赖节点 | **认可（附条件）** | 方向合理，但**须用户书面确认**。若用户认为外部依赖是“依赖简洁性”评审的关键输入，则应改为显示。见 F3。 |
| 删除整个 `frontend/` 和 `backend/` | **认可（附条件）** | 方向正确，但**须先打 tag 再删除**（F4）。 |
| 给 `parser.scan_codebase` 增加 `exclude_dirs` | **认可** | 必要改动，且保持向后兼容。 |
| 迁移 `depthScore.ts`/`aggregateEdges.ts`/`detect.ts` 算法到 Python | **认可（附条件）** | 逻辑 UI 无关，可复用。但 `aggregateEdges.ts` 的 FlowEdge 类型依赖需剥离；`detect.ts` 的 `THIRD_PARTY_NODE_ID` 常量需重新定义。 |
| 重写 `digest.py` | **建议复用而非重写** | `backend/backend/aggregate/digest.py` 已有成熟的截断阶梯和预算控制，直接迁移到 skill 比重写更可靠。见 F5。 |

---

## 四、开放点裁决

### O1 如何处理工作区 3 个未提交 frontend 改动 —— **裁决：执行前必须用户拍板**

当前改动涉及 `Inspector.test.tsx`、`Inspector.tsx`、`recompose/detect.ts`。由于 `frontend/` 整个目录将被删除，这些改动若直接丢弃会丢失；若提交到 master，则 master 会多一次 frontend 提交后立即被删除，历史略显奇怪但可接受。

**裁决**：
- 若改动是 #21 后的有价值收尾修复 → 先单独提交到 master（commit message 明确 #21 收尾），再打迁移 tag，再删除 frontend。
- 若改动是临时调试 → 丢弃（`git checkout --` 或 `git restore`）。
- **必须用户书面确认**，不能由执行 agent 擅自决定。

### O2 是否复用 `backend/backend/aggregate/digest.py` —— **裁决：复用截断阶梯，不要从零重写**

该文件已经实现了四级截断、预算控制、噪声模块过滤、imports 去重。skill 的 `digest.py` 应直接迁移/适配此文件，而不是重写一套。

**条件**：
1. 移除对 Pydantic 的依赖（如果 skill 要保持零第三方依赖）。
2. 调整默认预算为 ~40K 字符（与计划一致）。
3. 移除对 `frontend/src/manifest/feature-atoms.json` 的默认输出路径依赖。

### O3 v1 是否显示外部依赖节点 —— **裁决：v1 不显示，但须用户确认**

保持 v1 简洁合理。但这是一个 UX 决策，影响“依赖简洁性”评审的可视化表达。建议：
- 在 metrics 表中明确列出外部依赖数量最多的模块。
- 若用户后续要求，可在 v2 加入外部依赖节点。

---

## 五、新发现问题

| # | 级别 | 问题 | 要求 |
|---|---|---|---|
| F1 | **阻塞** | 工作区 3 个未提交 frontend 改动未裁决。若直接切分支执行迁移，要么污染迁移分支，要么丢失改动。 | 用户在执行前明确拍板：提交 or 丢弃。 |
| F2 | **阻塞** | D1–D6 虽已记录为“用户确认（2026-09-02）”，但尚未落档到 `wayfinder/grilling-decisions/`。后续会话/其他 agent 无法复核。 | 实现前创建 `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md`，附决策原文（问题+选项+定案+弃选理由）。 |
| F3 | **重要** | D7（v1 不画外部依赖节点）是计划建议，不是用户明确确认。 | 执行前用 AskUserQuestion 确认，或把该决策写进 grilling-decisions 并由用户批准。 |
| F4 | **重要** | “迁移前打 tag”没有具体 tag 名和命令。 | 文档明确：执行第 0 步时运行 `git tag archive/app-before-skill-migration master`（或用户指定名称）。 |
| F5 | **重要** | 计划建议重写 `digest.py`，但 `backend/backend/aggregate/digest.py` 已有成熟实现。 | 改为迁移/适配现有 digest.py，保留截断阶梯和预算逻辑。 |
| F6 | **重要** | `analyze.py` 通过 `sys.path` 动态加载 `parser`，但未说明如何解决包内绝对导入（`from . import _diagnostics`）。 | 文档须明确：从 repo root 运行 `python .claude/skills/deep-module-review/scripts/analyze.py <repo>`，脚本把 repo root 加入 `sys.path` 并 import `parser.scan_codebase`。 |
| F7 | **建议** | `.dagr/` 目录出现在 untracked 文件中（`git status`），但未在 `exclude_dirs` 中排除。 | 把 `.dagr/` 加入 skill 的 `exclude_dirs`，并考虑是否加入 `parser/_external.py` 的默认 `EXCLUDED_DIRS`。 |
| F8 | **建议** | 删除 `backend/` 后，`backend/tests/test_aggregate_*.py` 也会被删除，其中可能包含对 digest 逻辑的有价值测试。 | 迁移 digest 到 skill 时，同时迁移/改写相关测试到 `.claude/skills/deep-module-review/tests/`。 |

---

## 六、通过条件清单（执行前勾选）

- [ ] **F1**：用户裁决 3 个未提交 frontend 改动（提交或丢弃）。
- [ ] **F2**：创建 `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md`，D1–D7 落档。
- [ ] **F3**：用户书面确认 D7（v1 不在图中显示外部依赖节点）。
- [ ] **F4**：执行迁移前打 tag，文档明确 tag 名与命令。
- [ ] **F5**：`digest.py` 改为迁移/适配 `backend/backend/aggregate/digest.py`，不从零重写。
- [ ] **F6**：文档明确 `analyze.py` 的 `sys.path` 加载方式与运行 cwd。
- [ ] **F7**：`.dagr/` 加入 skill 的 `exclude_dirs`。
- [ ] **F8**（建议）：迁移 digest 相关测试到 skill tests。
- [ ] 实现完成后：parser 测试 39 passed、skill 单元测试通过、e2e 生成 4 个输出文件、人工调用 `/deep-module-review` 输出 Artifact。

---

## 七、结语

本设计文档证据链完整，方向正确，核心决策均有用户确认支撑。阻塞项集中在“执行入口干净度”（F1）和“决策落档/用户书面确认”（F2/F3），修复成本低但不可跳过。建议满足 §六 清单后，以本文档作为执行基线。

—— 评审方（独立复核：本地仓库 @ 7352105，2026-09-02）

---

## 附录：执行检查表（对抗协议 Pass 1/2 产出）

| 类别 | 检查项 | 状态 | 备注 |
|---|---|---|---|
| 命令 | `python -m parser ... --output sample-graph.json` | ✅ 实测通过 | exit 0，输出 5 顶层键 |
| 命令 | `python -m pytest parser/tests -q` | ✅ 实测通过 | 39 passed |
| 文件 | `backend/backend/app.py/models.py/scanner.py/store.py` 存在 | ✅ 实测通过 | `ls` 命中 |
| 文件 | `frontend/src/lib/depthScore.ts` 存在 | ✅ 实测通过 | `ls` 命中 |
| 文件 | `backend/backend/aggregate/digest.py` 存在 | ✅ 实测通过 | `ls` 命中 |
| grep | `depthScore` 调用方 | ✅ 实测通过 | 4 组件 + 3 lib + 测试 |
| grep | `aggregateEdges` 调用方 | ✅ 实测通过 | graphToFlow / graphToFeatureFlow / recompose/edges + 测试 |
| grep | `detectModuleFindings` 调用方 | ✅ 实测通过 | RecomposeCanvas / Inspector / Toolbar + 测试 |
| GitHub | issue #1 state=OPEN | ✅ 实测通过 | `gh issue view 1` |
| git | 工作区未提交改动 | ✅ 实测通过 | 3 个 frontend 文件 |
| 代码 | `EXCLUDED_DIRS` 不含 `.claude/` | ✅ 实测通过 | `parser/_external.py:15-17` |
| 数据流 | parser output → metrics/digest/diagram → Artifact | ⚠️ 消费端未实测 | Claude 为最终消费者，需在实现后人工验证 |
| 复用 | digest.py 截断逻辑 | ⚠️ 未实测 | 计划建议重写，评审建议复用现有 `aggregate/digest.py` |
