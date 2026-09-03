---
name: handoff-deep-module-review-skill
description: 将 deep-module-mapper 从独立应用迁移为 Claude Code skill `/deep-module-review` 的执行 handoff。
---

# Handoff：实现 `/deep-module-review` skill 迁移

## 身份信息

- **任务**：把 `deep-module-mapper` 从独立 Web 应用降级为 Claude Code skill `/deep-module-review`。
- **项目路径**：`C:/Users/liyongquan/agent panel/deep-module-mapper/`
- **分支**：从 `master` 切出 `feature/deep-module-review-skill`
- **数据时点**：2026-09-02
- ** handing-off from**：规划/评审会话
- **执行状态**：尚未开始实现，设计文档与决策已就绪

## 必读文档（按顺序读）

1. `C:/Users/liyongquan/.claude/plans/cuddly-brewing-storm-设计文档.md` —— 可审计设计文档（实现基线）
2. `C:/Users/liyongquan/.claude/plans/cuddly-brewing-storm-设计文档-评审意见书.md` —— 评审意见书（含阻塞项与通过条件）
3. `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md` —— D1–D7 用户决策落档

## 当前仓库状态

- **master HEAD**：`7352105 docs(wayfinder): close #21 — module cycle/orphan detection done, map archived`
- **工作区**：已清理 frontend 未提交改动；剩余 untracked：`.claude/`、`.dagr/`、`wayfinder/统筹.md`（按协议本地保留）
- **GitHub issue #1**：OPEN（项目地图，迁移后需同步更新）

## 已确认决策（不要改）

| 决策 | 定案 |
|---|---|
| D1 项目形态 | 改为 Claude Code skill |
| D2 skill 名称 | `/deep-module-review` |
| D3 输出形式 | HTML Artifact（架构图 + AI 结论） |
| D4 重组画布 | 删除，只保留 AI 结论与静态图 |
| D5 AI 主动结论 | 是，Artifact 顶部先给结论 |
| D6 AI 评审模型 | 删除 aggregate CLI，由 Claude 直接评审 |
| D7 外部依赖节点 | v1 不在图中显示，仅在 metrics 表汇总 |
| 附带决策 | 3 个 frontend 未提交改动已丢弃 |

## 执行步骤

### Step 0：准备工作区

```bash
cd "C:/Users/liyongquan/agent panel/deep-module-mapper"
git checkout master
git pull origin master
git tag archive/app-before-skill-migration master
git push origin archive/app-before-skill-migration
git checkout -b feature/deep-module-review-skill
```

### Step 1：增强 parser（`exclude_dirs`）

- `parser/_scanner.py`：给 `scan_codebase(root_path, exclude_dirs=None)` 加参数，透传给 `_discover_files`。
- `parser/_external.py`：让 `_discover_files` 使用 `EXCLUDED_DIRS | set(exclude_dirs or [])`；默认 `EXCLUDED_DIRS` 增加 `.dagr/`。
- 跑测试：`python -m pytest parser/tests -q` → 39 passed。

### Step 2：创建 skill 骨架

创建目录结构：

```
.claude/skills/deep-module-review/
├── SKILL.md
├── scripts/
│   ├── analyze.py
│   ├── metrics.py
│   ├── digest.py
│   ├── diagram.py
│   └── template.html
└── tests/
    └── test_skill.py
```

### Step 3：实现 skill 脚本

**`metrics.py`**：
- 复用 `frontend/src/lib/depthScore.ts` 阈值：DEEP≥50，MODERATE≥15，公式 `maxLine / portCount`。
- 复用 `frontend/src/lib/aggregateEdges.ts` 的 `(source, target)` 分组逻辑。
- 复用 `frontend/src/lib/recompose/detect.ts` 的 Tarjan SCC 与孤儿三分类。
- 输出 `metrics.json`。

**`digest.py`**：
- 迁移/适配 `backend/backend/aggregate/digest.py`，保留四级截断阶梯与预算逻辑。
- 移除 Pydantic 依赖、移除 frontend manifest 默认输出路径。
- 输出 `digest.json`。

**`diagram.py`**：
- grid 布局生成 inline SVG。
- 节点按深度着色：deep=green，moderate=amber，shallow=red。
- 箭头表示聚合后的模块间依赖。
- v1 不画外部依赖节点。
- 输出 `diagram.svg`。

**`analyze.py`**：
- 从脚本位置解析 repo root，加入 `sys.path`，`from parser._scanner import scan_codebase`。
- 运行 cwd：仓库根目录。
- 调用 `parser.scan_codebase(repo, exclude_dirs={".git", ".claude", ".dagr", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"})`。
- 调用 metrics / digest / diagram。
- 写入 `.claude/skills/deep-module-review/.last-review/`：`graph.json`、`metrics.json`、`digest.json`、`diagram.svg`。
- 打印结果路径 JSON。

**`template.html`**：
- 自包含 HTML，内联 CSS（light/dark 适配）。
- 占位符：`{{REPO}}`、`{{TIMESTAMP}}`、`{{SUMMARY_METRICS}}`、`{{DIAGRAM_SVG}}`、`{{AI_CONCLUSIONS}}`。

**`SKILL.md`**：
- YAML front matter：`name: deep-module-review`。
- Body 协议：触发词 `/deep-module-review [path]`，默认 cwd，运行 analyze.py，读 metrics/digest，用 Claude 输出结论，填充 template.html 生成 Artifact。

### Step 4：删除旧应用

```bash
rm -rf frontend/
rm -rf backend/
```

- 更新 `.gitignore`：忽略 `.claude/skills/deep-module-review/.last-review/`。
- 重写 `README.md`。

### Step 5：更新 wayfinder 文档

- 复制 `C:/Users/liyongquan/.claude/plans/cuddly-brewing-storm-设计文档.md` → `wayfinder/design-doc-deep-module-review-skill.md`。
- `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md` 已存在。
- 创建/更新 `wayfinder/handoff-deep-module-review-skill.md`（本文档）。
- 更新 `wayfinder/map.md`：
  - Destination 改为 "Claude Code skill `/deep-module-review`"
  - 标记旧 frontend/backend/recompose/AI-aggregation ticket 被迁移取代
  - Open frontier 加入 skill 实现与验证

### Step 6：测试

1. Parser 回归：
   ```bash
   python -m pytest parser/tests -q
   ```
   预期：39 passed。

2. Skill 单元测试：
   ```bash
   python -m pytest .claude/skills/deep-module-review/tests -q
   ```
   覆盖：深度评分边界、边聚合、循环检测、孤儿三分类、SVG 节点数。

3. 端到端：
   ```bash
   python .claude/skills/deep-module-review/scripts/analyze.py \
     "C:/Users/liyongquan/agent panel/deep-module-mapper/parser/tests/fixtures/sample_pkg"
   ```
   验证 `.last-review/` 下 4 个文件生成。

4. 人工：在 Claude Code 中调用 `/deep-module-review`，确认 Artifact 渲染。

### Step 7：提交并推送

建议分多次提交：

```bash
git add parser/
git commit -m "feat(parser): add exclude_dirs parameter, include .dagr in defaults"

git add .claude/skills/deep-module-review/
git commit -m "feat(skill): add /deep-module-review skill with analyze, metrics, digest, diagram"

git rm -rf frontend/ backend/
git commit -m "chore: remove frontend and backend applications"

git add README.md .gitignore wayfinder/
git commit -m "docs: update README, map, and wayfinder docs for skill migration"

git push origin feature/deep-module-review-skill
```

**不要合并到 master**，等用户批准后再开 PR/合并。

## 验收标准

- [ ] `frontend/` 和 `backend/` 已删除。
- [ ] `python -m parser ./some-project` 仍能正常工作。
- [ ] `python -m pytest parser/tests -q` 39 passed。
- [ ] skill 单元测试全部通过。
- [ ] `python .claude/skills/deep-module-review/scripts/analyze.py <repo>` 生成 4 个输出文件。
- [ ] 在 Claude Code 中调用 `/deep-module-review` 输出包含 SVG 图和中文结论的 Artifact。
- [ ] 项目根目录仅剩 `parser/`、skill 目录、wayfinder 文档、README、.gitignore。
- [ ] 分支 `feature/deep-module-review-skill` 已推送到 origin。

## 红线

- 只做本次迁移范围内的事，不扩展功能。
- 不替用户合并到 master。
- 不修改或删除 `parser/`（除 `exclude_dirs` 增强外）。
- 保留 untracked 的 `.claude/`、`.dagr/`、`wayfinder/统筹.md`，不要误提交。
- 遇到未在设计文档中明确的决策，停下来问用户，不要猜。

## 报告模板

完成后向用户汇报：

```
迁移实现完成。
- 分支：feature/deep-module-review-skill
- 提交：<SHA 列表>
- 测试：parser <结果> / skill <结果> / e2e <结果>
- 遗留问题：<如有>
- 下一步：开 PR #N 并合并到 master
```
