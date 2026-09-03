---
name: deep-module-review
description: 对任意 Python 代码库做「深模块评审」。当用户完成一个开发阶段想检查模块设计深度、依赖是否简洁，或输入 /deep-module-review [path] 时使用。扫描代码库模块与依赖 → 生成架构图 SVG → 由 Claude 主动给出结构化中文结论（深模块对齐性 / 依赖简洁性 / 模块深度分布 / 关键发现 / 建议），以 HTML Artifact 输出。只读评审，不改动用户代码。
---

# /deep-module-review

对一个 **Python 代码库**做一次只读的「深模块评审」：用本仓库自带的 `parser/`
解析目标代码库的模块（一个 `.py` 文件 = 一个模块）与依赖，算指标、画架构图，
然后 **Claude 先给结论、再分项评审**（D5），最终以 HTML Artifact 呈现。

## 触发与用法

- 触发：用户输入 `/deep-module-review [path]`；`path` 省略时评审当前工作目录。
- 依赖：本 skill 的 `scripts/analyze.py` 依赖同仓库根下的 `parser/` 包
  （skill 与 parser 一起安装/复制），因此运行位置不受限，`analyze.py` 会自行
  向上定位 `parser/`。

## 步骤

### 1. 运行分析脚本

```bash
python .claude/skills/deep-module-review/scripts/analyze.py <repo>
```

- `<repo>` 为待评审的 Python 仓库根目录（默认当前目录）。
- 脚本把 `.claude/`、`.dagr/`、`node_modules/`、`.venv/`、`dist/` 等工具/瞬态
  目录排除在扫描外；只解析 `.py` 文件。
- 输出到 `.claude/skills/deep-module-review/.last-review/`，stdout 打印四个文件
  的路径 JSON：

  | 文件 | 内容 |
  |---|---|
  | `graph.json` | parser 原始扫描图（5 顶层键：modules/ports/edges/externalModules/diagnostics） |
  | `metrics.json` | 评审指标：summary、逐模块深度评分/fanIn/fanOut/外部依赖/诊断、聚合边、环、孤儿 |
  | `digest.json` | 给模型看的轻量摘要（截断阶梯，噪声模块已滤），含 `meta.truncation` |
  | `diagram.svg` | 内联 SVG 架构图（模块按深度着色、箭头=模块间聚合依赖） |

  若脚本报错（如 `<repo>` 不是含 `.py` 的目录、找不到 parser），如实向用户说明，
  不要编造指标。

### 2. 读取两个 JSON

读 `metrics.json` 与 `digest.json`：

- `metrics.json.summary`：总模块数、聚合边数、环/孤儿数、深度分布、第三方依赖数。
- `metrics.json.modules[]`：每个生产模块的 `depthScore`/`ratio`/`ports`/`fanIn`/
  `fanOut`/`externalDeps`/`finding`（`cycle/scc`、`orphan/isolated`、
  `orphan/third-party-only`、或 `null`）。
- `metrics.json.aggregatedEdges[]`：`source → target` 与 `kinds`、`weight`，
  同对多边已聚合。
- `metrics.json.cycles[]` / `orphans{}`：环成员与孤儿清单（含环内证据边）。
- `digest.json.modules[]`：每个模块的 imports + 端口签名（供评审具体接口用）。

> v1 评审范围 = **生产模块**：`tests/`、`fixtures/` 与 `__init__.py` 门面不进
> 统计与图（用户 2026-09-03 定案）。`__init__.py` 重导出的符号会把消费方依赖
> 指回真正的生产者；图里不画外部依赖节点（D7），第三方依赖只出现在模块的
> `externalDeps` 汇总。

### 3. 生成 HTML Artifact（结论在顶部）

读 `scripts/template.html`，用实际内容替换下列占位符，产出单文件 HTML：

| 占位符 | 替换为 |
|---|---|
| `{{REPO}}` | 被评审仓库名 |
| `{{TIMESTAMP}}` | 人类可读的评审时间 |
| `{{AI_CONCLUSIONS}}` | **AI 结论 HTML**（见下），放图之前 |
| `{{SUMMARY_METRICS}}` | 总览 HTML：顶部 4-6 个数字卡（模块数/聚合边/环/孤儿/深度分布），下方若有用例可加一张简表 |
| `{{DIAGRAM_SVG}}` | `diagram.svg` 原文（模板已包横向滚动容器） |

`AI_CONCLUSIONS` 的结构（评审维度，可用 `<h3>`/列表，保持精炼、有观点）：

1. **一句话总评**：用 `<p class="verdict">` 给一个明确的整体判断（深模块健康度
   好/中/差 + 一句理由）。
2. **深模块对齐性**：哪些模块接口小而实现厚（deep/ratio 高）值得肯定；哪些看似
   deep 但实为虚胖（端口都在顶部却被判深——已知偏差，仅在明显时提示）。
3. **依赖简洁性**：聚合边是否稀疏、方向是否清晰；指出环（耦合重灾区）与
   fanIn 过高/过低的极端模块。
4. **模块深度分布**：deep/moderate/shallow 数量；shallow 集中在哪类文件（薄门面、
   入口脚本、还是真问题）。
5. **关键发现**：环、孤立模块、仅连第三方模块，逐条点名 + 建议走向。
6. **建议**：最多 3-5 条、可执行（如拆接口、下沉实现、消除环、合并扇出碎片）。

**评审准则**：说人话、先结论后论据；数字一定来自 `metrics.json`；不确定的地方
直接说“需人工看代码确认”，不要编造文件名或结论。

### 4. 输出 Artifact 并收尾

- 把填好的 HTML 渲染为 Artifact 交给用户（Artifact 顶部即结论，图在下方作为
  辅助——D5）。
- 提醒用户评审是**只读**的：本 skill 不自动改任何代码；如需重构，另开任务。

## 红线

- 只读：绝不修改被评审代码、不写回、不自动重构。
- 不改 parser/ 与本 skill 的脚本逻辑（那是另外的实现任务）。
- 数字与结论必须可溯源到 `metrics.json`/`digest.json`；找不到就明说。
- v1 图不渲染外部依赖节点（D7）；需要外部依赖信息看模块 `externalDeps`。
