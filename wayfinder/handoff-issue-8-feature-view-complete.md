---
name: handoff-issue-8-feature-view-complete
wayfinder: handoff
ticket: "#8"
status: complete
---

# Handoff: Issue #8 — Feature view（功能原子聚合 + 中文描述）完成

**Ticket**: https://github.com/li-yongqvan/deep-module-mapper/issues/8  
**PR**: https://github.com/li-yongqvan/deep-module-mapper/pull/12（OPEN，`MERGEABLE`，待评审 + 合并授权）  
**Branch/worktree**: `worktree-issue-8-feature-view` @ commit `2ef7427`（16 文件 +4506/−72）  
**执行 Agent 边界**: 仅实现 + 测试 + PR + 本交接；未合并 PR、未关 issue、未动 map。

## 一句话总结

功能视图落地：扫描 deep-module-mapper 自生图从 **29 个文件节点 / 116 条边** 降到 **3 个中文节点 / 2 条边**（扫描并解析代码库 / 扫描 API 服务 / 第三方依赖），默认视图 + 顶部「功能/现实」切换，噪音隐藏，原子可下钻成员文件。

## 评审链（可审计底稿）

1. **计划** → `design-doc-for-review` 升格 → **可审计设计文档**：`C:\Users\liyongquan\.claude\plans\iterative-munching-whale-设计文档.md`（§10 已回填采纳记录 10.1–10.5）
2. **合并审计报告**（对抗评审 × 独立审计）：`C:\Users\liyongquan\.claude\plans\iterative-munching-whale-设计文档-合并审计报告.md` —— **有条件通过**（0 阻塞 / W1–W3 + I1–I5 必改 / C1–C7 建议），§六 通过条件清单**已全部落实**
3. **决策落档**（审计 I5，入库）：`wayfinder/grilling-decisions/issue-8-feature-view-decisions.md`（D1/D2 用户确认 2026-08-27 + D3–D8）

## What shipped

- **manifest（分组唯一事实源）**：`frontend/src/manifest/feature-atoms.json` + `featureAtoms.ts`。curated 版覆盖 parser/（8）+ backend/（4）= 12 生产文件，2 个原子：`scan-and-parse` 扫描并解析代码库 / `scan-api` 扫描 API 服务。格式干净，AI 聚合（#11）可 drop-in。
- **聚合 transform**：`lib/graphToFeatureFlow.ts`——文件→原子映射、噪音（tests/fixtures/`__init__.py`）默认隐藏、原子间依赖聚合（同原子内部边丢弃）、第三方折叠为单节点「第三方依赖」、原子级深度分 `depthScore(端口并集)`。
- **双视图装配**：`App.tsx`——功能视图为**默认**，顶部「功能视图/现实视图」切换（用户确认 D1）；零原子时提示「该代码库暂无功能清单」+ `unassignedCount`，可切现实视图；切换即复位 Inspector selection。
- **下钻**：`Inspector.tsx` 增 atom 分支——中文名 / 一句话描述 / 深度分 / 成员文件 + 各文件端口签名；外部节点展示具体库名（`externalNames`）。
- **共享边聚合**：`lib/aggregateEdges.ts` 从 `graphToFlow` 提取（行为逐字节一致，19 项既有测试守护，D8 回退预案）；`LabeledEdge` 支持功能视图简化中文 label「依赖」（`displayLabel`，`data.rawEdges` 全保留）。
- **布局**：`layout.ts` 增 `ATOM_NODE_WIDTH`(220) + `gridPositions` 宽度参数（同源常量 C6）。
- **文档**：`frontend/README.md` 增功能视图章节（manifest 编辑方法、扫描根前置、深度分说明）。

## Verification

```bash
cd frontend
npm install       # C7：worktree 无 node_modules
npm test          # 32 passed（既有 19 + 新增 13）
npx tsc --noEmit  # 0 errors
npm run build     # ✓
npm run lint      # exit 0（仅 #7 既有警告）
```

**端到端**（真实后端 uvicorn:8124 + Playwright，扫描 deep-module-mapper 根目录）：
- 功能视图：**2 原子 + 1「第三方依赖」= 3 节点、2 条边**（`atom:scan-api→atom:scan-and-parse`、`atom:scan-api→ext:third-party`），中文名/描述正确
- 点击「扫描 API 服务」→ 右侧面板下钻显示 `backend/backend/app.py` 等成员文件 + 端口 ✓
- 切现实视图 → 29 文件级模块节点 ✓
- 扫 manifest 未覆盖库（`parser/tests/fixtures/sample_pkg`）→ 显示「该代码库暂无功能清单」，不崩 ✓
- 截图（环境无法预览图片，DOM 断言全过）：`C:\Users\liyongquan\AppData\Local\Temp\claude\feature-view.png` / `feature-view-drilldown.png`

## Decisions locked（详见 grilling-decisions 文件）

| 决策 | 定案 |
|---|---|
| D1 视图共存 | 功能视图默认 + 顶部切换（用户确认 2026-08-27） |
| D2 第三方依赖 | 聚合为单个灰色节点 + `externalNames` 下钻（用户确认 2026-08-27） |
| D3 manifest 位置/格式 | `frontend/src/manifest/feature-atoms.json`（JSON） |
| D4 聚合位置 | 前端 sibling transform（不改 backend） |
| D5 下钻 UX | 点击原子 → Inspector 展示成员文件 |
| D6 `parser/__init__.py` 入原子 | 纳入 scan-and-parse（公共门面，保跨原子边） |
| D7 原子级评分 | `depthScore(端口并集)` |
| D8 边聚合复用 | 提取 `aggregateEdges`，失败回退 |

## 偏差 / 修复声明（已在 PR #12 正文声明）

1. **D6 豁免**：`parser/__init__.py` 纳入原子，与 handoff Step 1 Done-when 字面冲突；依据 issue #8 验收豁免条款执行（审计 Q2 认可为承重决策——`backend/backend/scanner.py → parser/__init__.py` 是唯一跨原子边）。
2. **ExternalNode 补 Handle（修复 #7 既有缺陷）**：实测 `ExternalNode` 无 Handle 导致 React Flow **error #008，指向外部模块的边从未真正渲染**（现实视图同样受影响，旧 E2E「无控制台错误」结论不准确）。补一对左右 Handle 后功能视图「第三方依赖」边 + 现实视图外部边均正常渲染。功能视图依赖此修复，若统筹方认为需单独复审可提。
3. **功能视图边 label 简化为「依赖」**：kinds 术语对非开发者无意义；`data.rawEdges` 全保留供点边下钻。
4. **两原子深度分均 shallow**（ratio 10.8/10.5）：naive 启发式对小型库的真实结果，README 已声明，阈值校准留后续。

## Code-review 结论（2026-08-27，两轴评审 PR #12）

**结论：无阻塞，可合并。评审发现的可修项已在本 PR 随 code-review 修复提交落地（Standards smell 4 项 + Spec 标准 8 部分缺口），详见「Code-review 修复落地」；无新增待决策项。**

### Standards（对照 #7 设计文档约定 + smell baseline）

- **硬偏离（已声明，保持）**：`ExternalNode` 补 Handle——违反 #7 设计文档 D11 / 不变量 #10「无 Handle」，是修复 React Flow **error #008**（外部边此前两视图均静默丢弃）的刻意改动；**现实视图行为变更**（外部边现在可渲染），需统筹方知情接受。
- **判断项**：新代码用 inline styles（延续既有偏离，非新增）。
- **smell（已修复）**：
  1. `handleStyle` 三文件重复 → **抽共享 `components/PortHandle.tsx`**（落实 #7 §5.6 规划的 PortHandle）；
  2. `ModuleNode` 硬编码 160 → **改用 `layout.NODE_WIDTH`**；
  3. `'依赖'` 双通道 → **去掉 `formatLabel` 回调，只留 `data.displayLabel`**；`edge.label` 保留合并 kinds 供 Inspector 下钻；
  4. App 原子点击重滤 → **改用 `data.files.includes`**（去掉 `atomForFile` 绕路）。
- **D12 保留确认**：`aggregateEdges.ts` 提取逐字节一致（分组键 / id / label / `data:{kinds,rawEdges}` / markerEnd 相同），35/35 测试佐证。

### Spec（issue #8 九条验收）

- **9/9 通过**（标准 8 补齐后）：新增 `Inspector.test.tsx` 渲染测试覆盖原子下钻（成员文件 + 端口）、第三方下钻、边下钻。
- **标准 6 caveat（保持，非 bug）**：原子评分 = 成员端口并集（之和），未真正兑现「fewer ports」语义——spec 措辞含糊，记为已知局限。
- 范围外行为均判定「有记录扩展」（非违规）：第三方节点（D2，用户确认）、默认功能视图+切换（D1，用户确认）、ExternalNode 补 Handle（合理 bug 修复）、边 label「依赖」（C1，在 spec 内）。

### Code-review 修复落地

- 抽共享 `PortHandle`（ModuleNode/ExternalNode/FeatureAtomNode 统一）
- `ModuleNode` 用 `NODE_WIDTH`（常量同源 C6 补全）
- `aggregateEdges` 移除 `formatLabel` 选项（`'依赖'` 单通道经 `displayLabel`）
- App 原子点击用 `data.files` 而非 `atomForFile` 重滤
- 新增 `Inspector.test.tsx`（3 项：原子/第三方/边下钻渲染）
- 验证：35/35 测试、tsc 0、build ✓、lint 0（仅 #7 既有警告）；E2E 冒烟 3 节点 / 2 边 / 边 label「依赖」✓

## Known risks / limits

1. **curated manifest 与扫描根耦合**：manifest 路径相对仓库根，**从仓库根扫描才命中**；扫子目录得空功能视图（有提示 + 可切现实视图）。README 已注明。
2. **manifest 漂移防护**：`featureAtoms.test.ts` 对 self-scan fixture 快照断言（C2）——平行分支新增生产文件若忘更新 manifest，刷新 fixture 即测试失败。
3. **噪音全隐藏**：文件不在任何原子即默认不显示；下钻/现实视图是找回入口。
4. **fixture 快照**：`frontend/src/__tests__/fixtures/deep-module-mapper.graph.json`（85KB）是 2026-08-27 自扫快照，仓库结构变动后需刷新。
5. **深度分阈值 naive**：沿用 #7 的 50/15，原子级同样暂定（`depthScore.ts` 已注明）。

## 待统筹方决策（执行分支不代办）

- **PR #12 评审 + 合并授权**——合并、关 issue #8、更新 `wayfinder/map.md` 均为统筹方职责，我未执行。
- **ExternalNode Handle 修复的复审取舍**（见上「偏差/修复声明 2」）——是否随本 PR 一并接受。
- **评审发现项修复策略（已解决）**：code-review 可修项已在本 PR 修复提交落地（PortHandle 抽取、NODE_WIDTH 统一、`'依赖'` 单通道、Inspector 下钻渲染测试），无需统筹方再定夺修复策略；Spec 标准 8 已由 8/9 → 9/9。
- 验收标准 9 条：**9/9 通过**（标准 8 下钻渲染测试已补，见 Code-review 结论）。

## Completion criterion

本交接在统筹方确认：① PR #12 评审通过并授权合并；② 合并后关闭 issue #8 并更新地图后，视为完成。
