---
name: deep-module-review
description: 对任意 Python 代码库做「深模块评审」。当用户完成一个开发阶段想检查模块设计深度、依赖是否简洁，或输入 /deep-module-review [path] 时使用。扫描代码库模块与依赖 → 生成 Archify 模块地图（可下钻：点模块卡片看内部函数泳道图 + AI 解读）→ Claude 主动给出结构化中文结论。产出单文件 HTML（.last-review/map.html，浏览器打开）；Archify 不可用时降级 v1 SVG Artifact。只读评审，不改动用户代码。
---

# /deep-module-review

对一个 **Python 代码库**做一次只读的「深模块评审」：用本仓库自带的 `parser/`
解析目标代码库的模块（一个 `.py` 文件 = 一个模块）与依赖，算指标，然后

- **v2（默认）**：生成 **Archify 模块地图**（`map.html`）——主图为生产模块架构图，
  点任意模块卡片，页面内下钻展开该模块的「内部函数路线」：一句话效果承诺 +
  workflow 泳道图（节点=真实函数，边=真实调用，泳道=AI 业务阶段）+ AI 解读。
- **降级**：本机没有 Archify / node 时，退回 v1 产出（SVG 架构图 + HTML Artifact）。

## 触发与用法

- 触发：用户输入 `/deep-module-review [path]`；`path` 省略时评审当前工作目录。
- 依赖：`scripts/analyze.py` 依赖同仓库根下的 `parser/` 包（会自行向上定位）；
  v2 渲染额外依赖 [Archify](file://~/.claude/skills/archify) + node（自动探测，
  见第 1 步的 `archify` 字段）。

## 步骤

### 1. 运行分析脚本

```bash
python .claude/skills/deep-module-review/scripts/analyze.py <repo>
```

- `<repo>` 为待评审的 Python 仓库根目录（默认当前目录）。
- `.claude/`、`.dagr/`、`node_modules/`、`.venv/` 等工具/瞬态目录已被排除；
  只解析 `.py` 文件。
- 输出到 `.claude/skills/deep-module-review/.last-review/`，stdout 打印 JSON：
  `archify` 探测结果 + 四个文件路径。

  | 文件 | 内容 |
  |---|---|
  | `graph.json` | parser 原始扫描图（6 顶层键：modules / ports / edges / externalModules / diagnostics / **intra**） |
  | `metrics.json` | 评审指标：summary、逐模块深度评分/fanIn/fanOut/外部依赖/诊断、聚合边、环、孤儿 |
  | `digest.json` | 给模型看的轻量摘要（截断阶梯，噪声模块已滤），含 `meta.truncation` |
  | `diagram.svg` | v1 内联 SVG 架构图（降级时用；v2 也会生成但仅作兜底） |

  `intra` 键（v2 新增）= 每个模块的函数级调用图：
  `{funcs: [{name, line}], calls: [{from, to, line}]}`。类 = 单节点（方法不展开）；
  顶层调用的宿主是伪节点 `<module>`；`sorted(key=f)` 这类回调引用也有边；
  同名遮蔽（局部变量/参数/导入/内置名盖住模块函数）不会产生幻边。

- 若脚本报错（如 `<repo>` 不是含 `.py` 的目录、找不到 parser），如实向用户说明，
  不要编造指标。

### 2A. Archify 可用 → v2 模块地图（默认路径）

stdout JSON 里 `"archify": {"available": true}` 时走本路径。

**② 生成主图 IR：**

```bash
python .claude/skills/deep-module-review/scripts/to_archify.py
```

产出 `architecture.json`（主图 IR，showcase 校验通过或已退 standard）、
`idmap.json`（模块 id → 节点 id 映射，如 `parser/_edges.py` → `parser__edges`）、
`layout.json`（布局缓存，模块集合未变时复用，两次运行图样一致）。

**③ 写下钻面板标注**（这一步是 AI 的工作，不是脚本）：

先读材料：`metrics.json`（哪些模块 deep/shallow/有环）、`digest.json`（接口签名）、
`graph.json` 的 `intra`（每个生产模块的真实函数与调用）、以及**每个生产模块的源码**
（理解每个函数干什么，才能分组、写承诺）。

然后为**每个生产模块**写一份标注文件到
`.claude/skills/deep-module-review/.last-review/panels/<节点id>.json`
（`<节点id>` 用 `idmap.json` 里的值，必须逐模块齐全）：

```jsonc
{
  "module_id": "parser/_edges.py",          // 原始模块 id
  "title": "边提取",                         // 卡片短标题（中文，几个字）
  "promise": "把 AST 里的 import 和符号引用解析成模块依赖边。",  // 一句话效果承诺
  "interp": "AI 解读 HTML（2-3 句）：效果如何实现 + 循环回路位置。可用 <code>/<strong>。",
  "lanes": [{"id": "p1", "label": "Pass1 · 收集"}],   // 业务阶段泳道，id 要匹配 ^[a-zA-Z][\w-]*$
  "nodes": {                                 // 该模块 intra 的每个函数都必须在这里
    "collect_imports": ["p1", 0, "import 语句 → RawImport"],  // [泳道id, 列0-5, 副标签(可省)]
    "resolve_reference": ["p2", 3, "引用解析主逻辑"]
  },
  "extra_edges": []                          // 可选：[{"from","to","label"}] 补标注，已存在的边只加标签
}
```

硬约束（脚本会断言，违反会报错让你改）：
- `nodes` 必须覆盖该模块 `intra.funcs` 的**每一个**函数（含 `<module>`，若有），
  不能有 intra 里不存在的名字；
- 列号 0-5（超出会被钳到 5），同一泳道内列号不得重复；
- 函数名的**原始写法**放 `nodes` 的 key（带下划线前缀没关系，脚本会转换节点 id）；
- `interp` 里诚实说明循环：函数级有环就指出回路位置；无环（本仓库即如此）就
  说明「循环发生在文件级迭代」，泳道分段即迭代阶段——不要硬造环。

另可选写一份总评 `panels/_summary.json`：`{"summary_html": "<p>…2-3 句总评…</p>"}`
（会显示在主图下方；逐模块观点放各面板的 interp，不要堆在这里）。

**④ 组装：**

```bash
python .claude/skills/deep-module-review/scripts/assemble.py
```

校验每份标注 → 逐模块跑 archify 渲染 → 合成单文件 `.last-review/map.html`。
任一标注违反约束会报错指出文件与原因，修好后重跑即可。

**⑤ 交付：** 提示用户**用浏览器打开** `map.html`（点主图模块卡片下钻）。
在对话里给一段简短总评（深模块健康度 + 1-2 个最值得注意的发现，数字来自
`metrics.json`）。注意：`map.html` 是浏览器文件，不是 Artifact——不要塞进
Artifact 通道（V2-D11）。提醒用户评审是**只读**的。

### 2B. Archify 不可用 → v1 降级路径

stdout JSON 里 `"archify": {"available": false}` 时（缺目录或缺 node）：

1. **向用户明示**「未启用 Archify 模式（原因：…），本次为 v1 降级产出」——
   这是协议要求，不是可选项。
2. 按 v1 流程产出：读 `metrics.json` 与 `digest.json`，读 `scripts/template.html`，
   替换占位符 `{{REPO}}`（仓库名）、`{{TIMESTAMP}}`（评审时间）、
   `{{SUMMARY_METRICS}}`（总览数字卡）、`{{DIAGRAM_SVG}}`（diagram.svg 原文）、
   `{{AI_CONCLUSIONS}}`（结论 HTML，放图之前），渲染为 Artifact。
3. `AI_CONCLUSIONS` 结构：一句话总评（`<p class="verdict">`）→ 深模块对齐性 →
   依赖简洁性 → 模块深度分布 → 关键发现（环/孤儿逐条点名）→ 建议（≤5 条可执行）。

### 评审准则（两个路径通用）

- 说人话、先结论后论据；数字一定来自 `metrics.json`/`digest.json`；
  不确定的地方直接说「需人工看代码确认」，不要编造文件名或结论。
- 评审范围 = **生产模块**：`tests/`、`fixtures/` 与 `__init__.py` 门面不进统计与图；
  图里不画外部依赖节点（D7），第三方依赖看模块 `externalDeps`。

## 红线

- 只读：绝不修改被评审代码、不写回、不自动重构。
- 一切产物只落 `.claude/skills/deep-module-review/.last-review/`。
- 不改 parser/ 与本 skill 的脚本逻辑（那是另外的实现任务）。
- 数字与结论必须可溯源到 `metrics.json`/`digest.json`/`graph.json`；找不到就明说。
- 面板泳道/解读必须以 `intra` 真实调用为底，不得虚构函数或调用边。
